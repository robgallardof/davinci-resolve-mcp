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
    assert [f["shot"] for f in result["flagged"]] == [3]  # the subject ends up off-screen in shot 3
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
