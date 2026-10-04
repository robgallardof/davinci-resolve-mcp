"""Live: the editing tools on a real Resolve (Free or Studio) with real speech.

    uv run pytest -m live -v

Generates a 6 s talking clip (Windows TTS voice muxed with PyAV), then in a throwaway
project: find_highlights -> assemble_timeline(reels) -> transcribe_timeline (real Whisper)
-> add_captions + add_text_overlay -> render, and checks the PIXELS of the render: the caption
band is lit while someone talks and the title band during the overlay. Cleans everything up.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
import wave
from pathlib import Path

import pytest

from mcp.server.fastmcp import FastMCP
from resolve_forge import tools
from resolve_forge.analysis import transcribe
from resolve_forge.domain import formats
from resolve_forge.gateway import ResolveUnavailable, Session

av = pytest.importorskip("av")
np = pytest.importorskip("numpy")
cv2 = pytest.importorskip("cv2")
pytestmark = pytest.mark.live

SENTENCE = "Hello everyone. Today I am cleaning my room with my squirrel. This is amazing!"


def _tts(path: Path) -> None:
    if sys.platform != "win32":
        pytest.skip("TTS sample uses Windows System.Speech")
    script = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              f"$s.SetOutputToWaveFile('{path}'); $s.Speak('{SENTENCE}'); $s.Dispose()")
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True, capture_output=True, timeout=60)


def _talking_clip(path: Path, wav_path: Path, seconds: float = 7.0) -> None:
    with wave.open(str(wav_path)) as w:
        rate, pcm = w.getframerate(), np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    out = av.open(str(path), "w")
    v = out.add_stream("mpeg4", rate=30)
    v.width, v.height, v.pix_fmt, v.bit_rate = 640, 360, "yuv420p", 2_000_000
    a = out.add_stream("aac", rate=rate)
    a.layout = "mono"
    img = np.full((360, 640, 3), 70, np.uint8)
    cv2.circle(img, (320, 140), 70, (200, 180, 160), -1)
    for _ in range(int(seconds * 30)):
        for pkt in v.encode(av.VideoFrame.from_ndarray(img, format="rgb24")):
            out.mux(pkt)
    pcm = np.concatenate([pcm, np.zeros(max(0, int(seconds * rate) - len(pcm)), np.int16)])[: int(seconds * rate)]
    for i in range(0, len(pcm), 1024):
        frame = av.AudioFrame.from_ndarray(pcm[i:i + 1024].reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate = rate
        for pkt in a.encode(frame):
            out.mux(pkt)
    for stream in (v, a):
        for pkt in stream.encode(None):
            out.mux(pkt)
    out.close()


class Live:
    def __init__(self, session: Session):
        self.mcp = FastMCP("live-edit")
        tools.register(self.mcp, session)

    def __call__(self, tool: str, **args) -> dict:
        result = asyncio.run(self.mcp.call_tool(tool, args))
        content = result[0] if isinstance(result, tuple) else result
        data = json.loads(content[0].text)
        assert data["ok"], f"{tool} failed: {data}"
        return data

    def render(self, fmt: str, folder: Path, name: str) -> Path:
        job = self("render_for", format=fmt, target_dir=str(folder), name=name)
        deadline = time.time() + 300
        while time.time() < deadline:
            st = self("render_status", job_id=job["job_id"])
            if str(st.get("JobStatus")).lower() in ("complete", "failed", "cancelled"):
                assert str(st["JobStatus"]).lower() == "complete", st
                return sorted(folder.glob(f"{name}*"))[0]
            time.sleep(1)
        raise TimeoutError(job)


@pytest.fixture(scope="module")
def live():
    if not transcribe.available():
        pytest.skip("speech extra not installed (uv sync --extra speech)")
    session = Session()
    try:
        resolve = session.resolve()
    except ResolveUnavailable as exc:
        pytest.skip(str(exc))
    pm = resolve.GetProjectManager()
    previous = pm.GetCurrentProject()
    previous_name = previous.GetName() if previous else None
    pm.SaveProject()
    name = f"forge_edit_{int(time.time())}"
    work = Path.home() / "Movies" / "forge-live" / name
    work.mkdir(parents=True, exist_ok=True)
    project = pm.CreateProject(name)
    assert project
    try:
        project.SetSetting("timelineFrameRate", "30")
        _tts(work / "voice.wav")
        _talking_clip(work / "talk.mp4", work / "voice.wav")
        resolve.OpenPage("edit")
        yield Live(session), work, name
    finally:
        pm.CloseProject(pm.GetCurrentProject())
        if previous_name:
            pm.LoadProject(previous_name)
        # Preserve generated project/media for inspection; no deletion without a user request.


def test_edit_pipeline_end_to_end(live):
    forge, work, name = live
    src = str(work / "talk.mp4")

    hl = forge("find_highlights", source=src, top=2, window_s=3)
    assert hl["highlights"]

    tl = forge("assemble_timeline", source=src, cuts=[[0, 7]], name="talk", format="reels")
    assert tl["clips"] == 1 and tl["resolution"] == "1080x1920"

    speech = forge("transcribe_timeline", include_words=True)
    text = " ".join(s["text"] for s in speech["sentences"]).lower()
    assert "squirrel" in text and speech["cuts_s"], speech

    caps = forge("add_captions", style="outline", position="bottom", max_words=3)
    assert caps["placed"] == caps["requested"] > 2
    title = forge("add_text_overlay", text="POV: limpiando 🐿️", start_s=0.0, duration_s=2.0, style="box")
    assert title["placed"] == 1

    out = forge.render("reels", work, "edit")
    cap = cv2.VideoCapture(str(out))
    assert (int(cap.get(3)), int(cap.get(4))) == (1080, 1920)
    safe = formats.safe_for(1080, 1920).rect(1080, 1920)

    def band(t: float, top: bool) -> float:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * 30))
        ok, frame = cap.read()
        assert ok
        y0 = safe["y"] if top else safe["y"] + safe["height"] - 300
        region = frame[y0:y0 + 300, safe["x"]:safe["x"] + safe["width"]]
        return float((region.min(axis=2) > 230).mean())  # share of near-white pixels

    first_word = speech["words"][0]
    talking_at = first_word["start"] + 0.1
    assert band(talking_at, top=False) > 0.01, "caption not visible in the render while speaking"
    assert band(1.0, top=True) > 0.05, "title card not visible in the render"
    assert band(6.8, top=True) < 0.01, "title card should be gone after its 2 s"
