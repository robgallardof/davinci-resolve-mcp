"""Self-review before and after rendering, on real (synthetic) video files."""
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")


def clip(path, seconds=6, fps=15, black_from=None, frozen=None):
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (180, 320))
    for i in range(seconds * fps):
        t = i / fps
        frame = np.full((320, 180, 3), 120, np.uint8)
        if not (frozen and frozen[0] <= t < frozen[1]):
            cv2.circle(frame, (40 + (i * 7) % 100, 240), 14, (240, 240, 240), -1)
        if black_from is not None and t >= black_from:
            frame[:] = 0
        out.write(frame)
    out.release()


def test_review_shots_draws_the_real_crops_and_places_text(forge, tmp_path):
    path = tmp_path / "src.mp4"
    clip(path)
    shots = [{"start_s": 0, "end_s": 2, "framing": "wide", "zoom": 1.0, "anchor": [.5, .5], "subject": [.5, .6]},
             {"start_s": 2, "end_s": 4, "framing": "medium", "zoom": 1.25, "anchor": [.5, 1.0], "subject": [.5, .75]},
             {"start_s": 4, "end_s": 6, "framing": "close", "zoom": 1.5, "anchor": [0, 0], "subject": [.95, .95]}]
    texts = [{"text": "Hola", "start_s": 0.5, "duration_s": 1, "position": "bottom"}]
    result = forge("review_shots", source=str(path), shots=shots, format="tiktok", texts=texts)
    assert result["ok"], result
    assert Path(result["sheet"]).is_file() and result["shots"] == 3
    assert [f["shot"] for f in result["flagged"]] == [2, 3]  # small source is too soft when punched in; shot 3 also misses subject
    assert result["text_positions"][0]["position"] in ("top", "middle")  # bottom would cover the subject
    assert "issues" in result["look"]


def test_review_video_finds_black_and_frozen_stretches(forge, tmp_path):
    path = tmp_path / "render.mp4"
    clip(path, seconds=10, black_from=8.5, frozen=(2, 6))
    result = forge("review_video", path=str(path), every_s=0.5)
    assert result["ok"], result
    assert Path(result["sheet"]).is_file() and result["resolution"] == "180x320"
    assert any("black" in i for i in result["issues"]) and any("frozen" in i for i in result["issues"])
    assert forge("review_video", path=str(tmp_path / "missing.mp4"))["code"] == "INVALID_ARGUMENT"


def test_review_video_reports_freeze_through_last_frame_and_rejects_bad_sampling(forge, tmp_path):
    path = tmp_path / "frozen.mp4"
    clip(path, seconds=6, frozen=(0, 6))
    result = forge("review_video", path=str(path), every_s=.5)
    assert any("frozen" in i for i in result["issues"])
    for step in (0, -1, float("nan"), float("inf")):
        assert forge("review_video", path=str(path), every_s=step)["code"] == "INVALID_ARGUMENT"


def test_review_shots_flags_partial_face_crop_even_when_subject_is_centered(forge, tmp_path, monkeypatch):
    from resolve_forge.services import review_service
    path = tmp_path / "face.mp4"
    clip(path)
    monkeypatch.setattr(review_service, "_faces", lambda frame: [(.02, .2, .4, .5)])
    shot = dict(start_s=0, end_s=2, framing="close", zoom=1.5, anchor=[.5, .5], subject=[.5, .4])
    result = forge("review_shots", source=str(path), shots=[shot])
    assert "cuts a face out of frame" in result["flagged"][0]["issues"]


def test_review_shots_samples_face_entering_near_end_with_time_evidence(forge, tmp_path, monkeypatch):
    from resolve_forge.services import review_service
    path = tmp_path / "late-face.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 15, (320, 180))
    for i in range(30):
        writer.write(np.full((180, 320, 3), 200 if i >= 25 else 120, np.uint8))
    writer.release()
    monkeypatch.setattr(review_service, "_faces", lambda frame: [(.8, .2, .95, .5)] if frame.mean() > 150 else [])
    shot = dict(start_s=0, end_s=2, framing="wide", zoom=1, anchor=[.5,.5], subject=[.5,.5])
    result = forge("review_shots", source=str(path), shots=[shot])
    assert result["ok"], result
    assert len(result["flagged"]) == 1
    samples = result["flagged"][0]["samples"]
    assert samples[0]["issues"] == samples[1]["issues"] == []
    assert "cuts a face out of frame" in samples[2]["issues"]
    assert samples[2]["source_s"] == pytest.approx(1.933, abs=.001)


def test_review_shots_checks_effective_source_upscale_but_warns_at_base(forge, tmp_path, monkeypatch):
    from resolve_forge.services import review_service
    path = tmp_path / "small.mp4"
    clip(path)
    monkeypatch.setattr(review_service, "_faces", lambda frame: [])
    shot = dict(start_s=0, end_s=2, framing="close", zoom=1.5, anchor=[.5,.5], subject=[.5,.5])
    result = forge("review_shots", source=str(path), shots=[shot])
    assert any("too soft" in issue and "9.00" in issue for issue in result["flagged"][0]["issues"])
    shot.update(framing="wide", zoom=1)
    result = forge("review_shots", source=str(path), shots=[shot])
    assert result["flagged"] == [] and result["warnings"]


def test_review_shots_rejects_empty_and_all_unreadable_frames(forge, tmp_path):
    path = tmp_path / "src.mp4"
    clip(path)
    empty = forge("review_shots", source=str(path), shots=[])
    assert empty["code"] == "INVALID_ARGUMENT" and "at least one" in empty["error"]
    shot = dict(start_s=10, end_s=12, framing="wide", zoom=1, anchor=[.5,.5], subject=[.5,.5])
    unreadable = forge("review_shots", source=str(path), shots=[shot])
    assert unreadable["code"] == "MEDIA_NOT_FOUND" and "decoded" in unreadable["error"]


def test_review_video_checks_short_black_tail_between_interval_samples(forge, tmp_path):
    path = tmp_path / "black-tail.mp4"
    clip(path, seconds=6, black_from=5.8)
    result = forge("review_video", path=str(path), every_s=1.5)
    assert result["ok"], result
    assert any("black" in issue for issue in result["issues"])
    assert result["sampled_frames"] == result["decoded_frames"] == 5


def test_review_video_does_not_certify_partially_decodable_file(forge, tmp_path, monkeypatch):
    from resolve_forge.services import review_service
    path = tmp_path / "bad-sample.mp4"
    clip(path)
    original_capture = cv2.VideoCapture

    class FailedSample:
        def __init__(self, file):
            self.capture = original_capture(file)
            self.msec = 0

        def get(self, prop): return self.capture.get(prop)
        def set(self, prop, value):
            self.msec = value
            return self.capture.set(prop, value)
        def read(self):
            return (False, None) if self.msec == 1500 else self.capture.read()
        def release(self): self.capture.release()

    monkeypatch.setattr(review_service.cv2 if hasattr(review_service, "cv2") else cv2,
                        "VideoCapture", FailedSample)
    result = forge("review_video", path=str(path), every_s=1.5)
    assert result["ok"], result
    assert result["unreadable_samples_s"] == [1.5]
    assert result["decoded_frames"] == result["sampled_frames"] - 1
    assert any("unreadable" in issue for issue in result["issues"])
