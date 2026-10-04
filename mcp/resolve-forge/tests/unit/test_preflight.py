from types import SimpleNamespace

from resolve_forge.domain.preflight import uncovered
from resolve_forge.services import preflight_service


def test_coverage_union_includes_head_tail_and_other_tracks():
    assert uncovered([(110, 150), (140, 180), (100, 115)], 100, 200) == [
        {"start_frame": 180, "end_frame": 200, "frames": 20}]
    assert uncovered([(120, 130)], 100, 150) == [
        {"start_frame": 100, "end_frame": 120, "frames": 20},
        {"start_frame": 130, "end_frame": 150, "frames": 20}]


class Clip:
    def __init__(self, start, duration, zoom=1, enabled=True, path=""):
        self.start, self.duration, self.zoom, self.enabled, self.path = start, duration, zoom, enabled, path

    def GetStart(self): return self.start
    def GetDuration(self): return self.duration
    def GetName(self): return "clip"
    def GetClipEnabled(self): return self.enabled
    def GetMediaPoolItem(self): return self
    def GetClipProperty(self, key): return self.path
    def GetProperty(self, key): return self.zoom if key.startswith("Zoom") else 0


class Timeline:
    def __init__(self, video, audio=None, disabled=()):
        self.tracks = {"video": video, "audio": audio or []}
        self.disabled = disabled

    def GetName(self): return "copy"
    def GetStartFrame(self): return 100
    def GetEndFrame(self): return 200
    def GetTrackCount(self, kind): return len(self.tracks[kind])
    def GetItemListInTrack(self, kind, track): return self.tracks[kind][track - 1]
    def GetIsTrackEnabled(self, kind, track): return (kind, track) not in self.disabled


def inspect(monkeypatch, timeline, format_key=None):
    monkeypatch.setattr(preflight_service, "current", lambda _: SimpleNamespace(
        timeline=timeline, width=1920, height=1080, fps=30))
    return preflight_service.inspect(None, format_key)


def test_upper_track_fills_gap_but_disabled_track_does_not(monkeypatch):
    tracks = [[Clip(100, 30), Clip(170, 30)], [Clip(130, 40)]]
    result = inspect(monkeypatch, Timeline(tracks))
    assert result["technical_passed"]
    assert result["visual_review_required"]
    disabled = inspect(monkeypatch, Timeline(tracks, disabled=[("video", 2)]))
    assert not disabled["technical_passed"]
    assert next(i for i in disabled["issues"] if i["code"] == "VIDEO_COVERAGE_GAP")["frames"] == 40


def test_invalid_zoom_offline_media_and_wrong_format_block(monkeypatch, tmp_path):
    result = inspect(monkeypatch, Timeline([[Clip(100, 100, zoom=float("nan"), path=str(tmp_path / "missing.mp4"))]]), "reels")
    codes = {i["code"] for i in result["issues"]}
    assert {"INVALID_TRANSFORM", "SOURCE_UNAVAILABLE", "FORMAT_RESOLUTION_MISMATCH"} <= codes
    assert not result["technical_passed"]


def test_audio_gap_and_high_zoom_require_review_without_false_failure(monkeypatch):
    result = inspect(monkeypatch, Timeline([[Clip(100, 100, zoom=1.8)]], [[Clip(120, 60)]]))
    codes = {i["code"] for i in result["issues"]}
    assert {"AUDIO_COVERAGE_GAP", "REVIEW_HIGH_ZOOM"} <= codes
    assert result["technical_passed"]


def test_disabled_clip_does_not_cover_black(monkeypatch):
    result = inspect(monkeypatch, Timeline([[Clip(100, 100, enabled=False)]]))
    assert not result["technical_passed"]
    assert result["clips"]["video"] == 0
