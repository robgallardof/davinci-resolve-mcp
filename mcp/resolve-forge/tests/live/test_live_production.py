"""Live: music montage cut on the beat, and a known script aligned to real speech.

    uv run pytest -m live -v

In a throwaway 30 fps project: a 120 BPM click track and two synthetic shots -> plan_beat_cuts ->
assemble_montage(music on A1) and checks, on the real timeline, that every cut lands on its beat within
one frame and that the music is one continuous clip as long as the picture. Then align_text times the
TTS script with real Whisper. The project and media are preserved for inspection.
"""

from __future__ import annotations

import asyncio
import json
import time
import wave
from pathlib import Path

import pytest

from mcp.server.fastmcp import FastMCP
from resolve_forge import tools
from resolve_forge.analysis import transcribe
from resolve_forge.gateway import ResolveUnavailable, Session

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")
pytest.importorskip("av")
pytestmark = pytest.mark.live
FPS = 30


class Live:
    def __init__(self, session: Session):
        self.session = session
        self.mcp = FastMCP("live-production")
        tools.register(self.mcp, session)

    def __call__(self, tool: str, **args) -> dict:
        result = asyncio.run(self.mcp.call_tool(tool, args))
        content = result[0] if isinstance(result, tuple) else result
        data = json.loads(content[0].text)
        assert data["ok"], f"{tool} failed: {data}"
        return data


def _shot(path: Path, color: tuple[int, int, int], seconds: int = 6) -> None:
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (1280, 720))
    frame = np.full((720, 1280, 3), color, np.uint8)
    for _ in range(FPS * seconds):
        out.write(frame)
    out.release()


def _click_track(path: Path, bpm: int = 120, seconds: int = 16, rate: int = 48000) -> None:
    samples = np.zeros(rate * seconds, np.float32)
    click = np.random.default_rng(3).normal(size=4800) * np.exp(-np.arange(4800) / 540) * .4
    for at in np.arange(0, seconds - .2, 60 / bpm):
        index = round(at * rate)
        samples[index:index + len(click)] += click
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())


@pytest.fixture(scope="module")
def live():
    session = Session()
    try:
        resolve = session.resolve()
    except ResolveUnavailable as exc:
        pytest.skip(str(exc))
    pm = resolve.GetProjectManager()
    previous = pm.GetCurrentProject()
    previous_name = previous.GetName() if previous else None
    pm.SaveProject()
    name = f"forge_production_{int(time.time())}"
    work = Path.home() / "Movies" / "forge-live" / name
    work.mkdir(parents=True, exist_ok=True)
    project = pm.CreateProject(name)
    assert project
    try:
        project.SetSetting("timelineFrameRate", str(FPS))
        _shot(work / "wide.mp4", (40, 90, 160))
        _shot(work / "close.mp4", (160, 90, 40))
        _click_track(work / "song.wav")
        resolve.OpenPage("edit")
        yield Live(session), work, project
    finally:
        saved = pm.SaveProject()
        pm.CloseProject(pm.GetCurrentProject())
        if previous_name:
            pm.LoadProject(previous_name)
        assert saved, "Could not preserve the production test project"
        # Preserve generated project/media for inspection; no deletion without a user request.


def test_beat_montage_cuts_land_on_the_grid_with_continuous_music(live):
    forge, work, project = live
    shots = [dict(source=str(work / f), start_s=0, end_s=6) for f in ("wide.mp4", "close.mp4")]
    plan = forge("plan_beat_cuts", music_source=str(work / "song.wav"), shots=shots, duration_s=8, beats_per_cut=4)
    assert plan["tempo_bpm"] == pytest.approx(120, rel=.05)
    forge("assemble_montage", shots=[{k: s[k] for k in ("source", "start_s", "end_s")} for s in plan["shots"]],
          name="Beat montage", music_source=str(work / "song.wav"), music_start_s=plan["music_start_s"], dry_run=False)
    clips = forge("list_clips")
    origin = clips["timeline_start"]
    assert len(clips["clips"]) == plan["cuts"]
    for clip, shot in zip(clips["clips"], plan["shots"]):
        expected = round((shot["music_s"][0] - plan["music_start_s"]) * FPS)
        assert abs((clip["start"] - origin) - expected) <= 1, (clip, shot)
    timeline = project.GetCurrentTimeline()
    music = timeline.GetItemListInTrack("audio", 1)
    picture = sum(c["duration"] for c in clips["clips"])
    assert len(music) == 1 and abs(music[0].GetDuration() - picture) <= 1


def test_align_text_times_the_known_script_with_real_speech(live, tmp_path):
    if not transcribe.available():
        pytest.skip("speech extra not installed (uv sync --extra speech)")
    import subprocess
    import sys
    if sys.platform != "win32":
        pytest.skip("TTS sample uses Windows System.Speech")
    forge, work, _ = live
    script = "Hello everyone. Today I am editing a music video with Forge."
    voice = work / "script.wav"
    command = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
               f"$s.SetOutputToWaveFile('{voice}'); $s.Speak('{script}'); $s.Dispose()")
    subprocess.run(["powershell", "-NoProfile", "-Command", command], check=True, capture_output=True, timeout=60)
    result = forge("align_text", source=str(voice), text=script, language="en")
    assert [w["text"] for w in result["words"]] == script.split()
    assert result["coverage"] >= .7
    assert all(a["end"] <= b["start"] + 1e-6 for a, b in zip(result["words"], result["words"][1:]))
    processed = forge("enhance_audio", source=str(voice), preset="dialogue",
                      output_path=str(work / "enhanced_script.wav"), dry_run=False)
    assert processed["applied"] and Path(processed["file"]).is_file()
    assert processed["peak_target_met"]


def test_music_bed_and_sound_effects_land_on_new_audio_tracks(live):
    forge, work, project = live
    forge("assemble_montage", shots=[dict(source=str(work / "wide.mp4"), start_s=0, end_s=6)],
          name="Audio production", music_source=str(work / "song.wav"), dry_run=False)
    timeline = project.GetCurrentTimeline()
    before = int(timeline.GetTrackCount("audio"))
    picture_before = [(c.GetStart(), c.GetDuration()) for c in timeline.GetItemListInTrack("video", 1)]
    words = [{"text": "uno", "start": 1.0, "end": 1.6}, {"text": "dos.", "start": 1.7, "end": 2.4}]
    bed = forge("add_music_bed", music_source=str(work / "song.wav"), words=words, dry_run=False)
    _click_track(work / "effect.wav", seconds=1)
    sfx = forge("place_sound_effects", cues=[dict(time_s=2.0, source=str(work / "effect.wav"), reason="live check")],
                dry_run=False)
    current = project.GetCurrentTimeline()
    assert [(c.GetStart(), c.GetDuration()) for c in current.GetItemListInTrack("video", 1)] == picture_before
    assert int(current.GetTrackCount("audio")) >= before + 2
    assert len(current.GetItemListInTrack("audio", bed["track"])) == 1
    assert len(current.GetItemListInTrack("audio", sfx["tracks"][0])) == 1
