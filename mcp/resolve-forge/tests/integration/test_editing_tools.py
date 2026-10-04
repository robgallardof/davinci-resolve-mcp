"""The editing tools learned from the reference MCPs, end-to-end on every edition/transport."""

import asyncio
import json

import pytest

from fakes import TIMELINE_START
from resolve_forge.analysis import transcribe
from resolve_forge.domain.transcript import Word
from resolve_forge.services import overlay_service, transcript_service


class FakeTranscriber:
    name = "fake@cpu"

    def __init__(self, words):
        self.words, self.calls = words, 0

    def transcribe(self, path, language=None):
        self.calls += 1
        return self.words, "es"


SPEECH = [Word(t, s, s + 0.3) for t, s in [
    ("Hola", 0.2), ("a", 0.6), ("todos.", 0.9),      # clip 1 source 0-10 s
    ("Hoy", 12.0), ("tengo", 12.4), ("3", 12.8), ("ardillas!", 13.2),   # used by clip 2 (source 12-22)
]]


@pytest.fixture
def speech(monkeypatch, tmp_path):
    fake = FakeTranscriber(SPEECH)
    monkeypatch.setattr(transcript_service, "_DEFAULT", fake)
    monkeypatch.setattr(transcribe, "available", lambda: True)
    monkeypatch.setattr(overlay_service, "OVERLAY_ROOT", tmp_path / "overlays")
    return fake


@pytest.fixture
def talking(forge, tmp_path):
    """Both demo clips come from the same file; clip 2 starts 12 s into the source."""
    src = tmp_path / "take.mp4"
    src.write_bytes(b"x")
    for item in forge.items():
        item.mpi.path = str(src)
    forge.items()[1].left = 12 * 30
    return forge


def test_transcribe_maps_every_clip_to_timeline_seconds(talking, speech):
    r = talking("transcribe_timeline", include_words=True)
    assert r["ok"], r
    by_text = {w["text"]: w["start"] for w in r["words"]}
    assert by_text["Hola"] == pytest.approx(0.2)          # clip 1 at 0 s, source 0
    assert by_text["Hoy"] == pytest.approx(10.0)          # clip 2 at 10 s, source 12 -> 10
    assert [s["text"] for s in r["sentences"]] == ["Hola a todos.", "Hoy tengo 3 ardillas!"]
    assert r["cuts_s"] == [10.0] and 10.8 in r["hits_s"]
    assert speech.calls == 2  # one per clip; the WhisperTranscriber caches per file on top of this


def test_transcribe_requires_the_speech_extra(talking, monkeypatch):
    monkeypatch.setattr(transcribe, "available", lambda: False)
    r = talking("transcribe_timeline")
    assert r["code"] == "MISSING_DEPENDENCY" and "speech" in r["hint"]


def test_add_captions_places_exact_non_overlapping_cards(talking, speech):
    r = talking("add_captions", max_words=3)
    assert r["ok"], r
    track = talking.project.current.tracks[r["track"] - 1]
    assert r["track"] == 3 and len(track) == r["placed"] == r["requested"]
    starts = [i.start - TIMELINE_START for i in track]
    assert starts[0] == round(0.2 * 30)
    for a, b in zip(track, track[1:]):
        assert a.start + a.duration <= b.start
    assert all(i.mpi.frames >= 2 for i in track)  # sequences, never 5 s stills


def test_add_captions_without_speech(talking, speech):
    speech.words = []
    r = talking("add_captions")
    assert r["ok"] and r["placed"] == 0 and "add_text_overlay" in r["note"]


def test_add_text_overlay_is_frame_exact_and_safe(forge, speech):
    r = forge("add_text_overlay", text="POV: intento limpiar 🧹", start_s=4.5, duration_s=4.0, style="box")
    assert r["ok"], r
    item = forge.project.current.tracks[r["track"] - 1][0]
    assert item.start - TIMELINE_START == 135 and item.duration == 120
    assert r["safe_zone"]["y"] > 0
    pool_folders = [f.GetName() for f in forge.project.pool.root.subfolders]
    assert pool_folders == ["forge-overlays"]  # media pool stays tidy
    assert not forge("add_text_overlay", text="x", start_s=0, duration_s=0)["ok"]
    assert forge("add_text_overlay", text="x", start_s=0, duration_s=1, style="neon")["code"] == "INVALID_ARGUMENT"


def test_two_overlays_go_to_separate_tracks(forge, speech):
    a = forge("add_text_overlay", text="uno", start_s=0, duration_s=2)
    b = forge("add_text_overlay", text="dos", start_s=1, duration_s=2)
    assert a["track"] != b["track"]


def test_assemble_timeline_from_a_cut_list(forge, tmp_path):
    src = tmp_path / "vlog.mp4"
    src.write_bytes(b"x")
    r = forge("assemble_timeline", source=str(src), cuts=[[3, 7.5], [29.5, 34]], name="Cut", format="reels")
    assert r["ok"], r
    tl = forge.project.current
    assert tl.name == "Cut" and r["resolution"] == "1080x1920" and r["duration_s"] == pytest.approx(9.0)
    clips = tl.tracks[0]
    assert [(c.left, c.start - TIMELINE_START, c.duration) for c in clips] == [(90, 0, 135), (885, 135, 135)]
    again = forge("assemble_timeline", source="vlog.mp4", cuts=[[0, 1]], name="Cut")
    assert again["code"] == "TIMELINE_EXISTS"
    assert len([c for c in forge.project.pool.root.clips if c.GetName() == "vlog.mp4"]) == 1  # found, not re-imported


def test_assemble_timeline_validation(forge):
    assert forge("assemble_timeline", source="x", cuts=[[5, 2]], name="Bad")["code"] == "INVALID_ARGUMENT"
    assert forge("assemble_timeline", source="nope.mp4", cuts=[[0, 1]], name="Bad")["code"] == "MEDIA_NOT_FOUND"


def test_find_highlights_on_a_real_video(forge, tmp_path):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    path = tmp_path / "pet.mp4"
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 64))
    for i in range(100):  # action only between 6 s and 8 s
        frame = np.zeros((64, 64, 3), np.uint8)
        x = 10 + ((i * 7) % 40 if 60 <= i < 80 else 0)
        frame[20:40, x:x + 12] = 255
        out.write(frame)
    out.release()
    r = forge("find_highlights", source=str(path), top=1, window_s=2)
    assert r["ok"], r
    best = r["highlights"][0]
    assert 5 <= best["start_s"] <= 7 and best["end_s"] - best["start_s"] == 2


def test_resources_read_state_and_errors(forge):
    async def read(uri):
        contents = await forge.mcp.read_resource(uri)
        return json.loads(list(contents)[0].content)

    status = asyncio.run(read("resolve://status"))
    assert status["timeline"] == "Master" and status["resolution"] == "1920x1080"
    tl = asyncio.run(read("resolve://timeline"))
    assert set(tl["tracks"]) == {"V1", "V2"} and len(tl["tracks"]["V1"]) == 2
    assert "tiktok" in asyncio.run(read("forge://formats"))
    assert "warm_push" in asyncio.run(read("forge://styles"))
    forge.project.current = None
    assert asyncio.run(read("resolve://timeline"))["code"] == "NO_TIMELINE"
