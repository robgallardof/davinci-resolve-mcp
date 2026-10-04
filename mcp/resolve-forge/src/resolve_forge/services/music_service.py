"""Music evidence and a finished visualizer asset; analysis mono, delivered soundtrack original stereo."""

from __future__ import annotations

import secrets
import subprocess

from ..domain.text_design import accent_rgba
from ..errors import ForgeError
from .analysis_service import source_path
from .native import number
from .render_service import DEFAULT_OUTPUT


def _dependencies():
    from ..analysis import media
    if not media.available():
        raise ForgeError("Music analysis/rendering requires audio decoding", code="MISSING_DEPENDENCY", hint="uv sync --extra speech")


def analyse(session, source):
    _dependencies()
    from ..analysis.music import analyse as analyse_file
    return {"source": source, **analyse_file(source_path(session, source))}


def visualizer(session, source, title="", artist="", theme="spectrum", width=1080, height=1920,
               fps=30, start_s=0.0, duration_s=15.0, accent="#B8A4FF"):
    if theme not in ("spectrum", "pulse"):
        raise ValueError("theme must be spectrum or pulse")
    if width % 2 or height % 2 or not 320 <= width <= 3840 or not 320 <= height <= 3840:
        raise ValueError("Dimensions must be even numbers from 320 to 3840")
    if len(title) > 80 or len(artist) > 80:
        raise ValueError("Title and artist may each have at most 80 characters")
    number(fps, "visualizer fps", 12, 60)
    number(start_s, "music start", 0)
    number(duration_s, "visualizer duration", .1, 120)
    if fps != int(fps):
        raise ValueError("Visualizer fps must be an integer")
    color = accent_rgba(accent, "studio")
    _dependencies()
    import av
    import imageio_ffmpeg
    import numpy as np
    from ..analysis.media import load_audio
    from ..graphics import music_visuals

    path = source_path(session, source)
    samples = load_audio(path)
    if start_s + duration_s > len(samples) / 16000 + 1 / fps:
        raise ValueError("Music range exceeds the decoded source duration")
    count = max(1, round(duration_s * fps))
    duration_s = count / fps
    if start_s + duration_s > len(samples) / 16000:
        raise ValueError("Frame-rounded music range exceeds the source; shorten duration by one frame")
    base = music_visuals.background(width, height, title, artist, color)
    output = DEFAULT_OUTPUT / "music-visuals" / secrets.token_hex(6)
    output.mkdir(parents=True, exist_ok=False)
    silent = output / "visual.mp4"
    movie = output / "music-video.mp4"
    frequency = np.fft.rfftfreq(2048, 1 / 16000)
    edges = np.geomspace(45, 7500, 49)
    masks = [(frequency >= a) & (frequency < b) for a, b in zip(edges, edges[1:])]
    bands, envelope = np.zeros(48), 0.0
    reference = max(float(np.quantile(np.abs(samples), .95)), 1e-5)
    container = av.open(str(silent), "w")
    try:
        stream = container.add_stream("libx264", rate=int(fps))
        stream.width, stream.height, stream.pix_fmt = width, height, "yuv420p"
        stream.options = {"crf": "18", "preset": "fast"}
        for index in range(count):
            offset = round((start_s + index / fps) * 16000)
            block = samples[max(0, offset - 1024):offset + 1024]
            block = np.pad(block, (0, max(0, 2048 - len(block))))[:2048]
            spectrum = np.abs(np.fft.rfft(block * np.hanning(2048)))
            power = np.array([float(np.sqrt(np.mean(spectrum[mask] ** 2))) if mask.any() else 0 for mask in masks])
            target = np.clip(np.log1p(power / reference) / 5, 0, 1)
            bands += (target - bands) * np.where(target > bands, .35, .12)
            loud = min(1.0, float(np.sqrt(np.mean(block ** 2))) / reference)
            envelope += (loud - envelope) * (.25 if loud > envelope else .1)
            image = music_visuals.frame(base, bands, envelope, theme, color)
            if index == count // 2:
                image.save(output / "poster.jpg", quality=95)
            frame = av.VideoFrame.from_ndarray(np.asarray(image), format="rgb24")
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    finally:
        container.close()
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-nostdin", "-n", "-i", str(silent),
               "-ss", str(start_s), "-i", path, "-map", "0:v:0", "-map", "1:a:0", "-t", str(duration_s),
               "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", str(movie)]
    try:
        result = subprocess.run(command, capture_output=True, timeout=300, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired as exc:
        raise ForgeError("Soundtrack mux exceeded its time limit", code="AUDIO_PROCESSING_TIMEOUT") from exc
    if result.returncode:
        raise ForgeError("Soundtrack mux failed: " + result.stderr.decode(errors="replace")[-500:], code="AUDIO_PROCESSING_FAILED")
    with av.open(str(movie)) as probe:
        audio = probe.streams.audio[0]
        video = probe.streams.video[0]
        actual = float(probe.duration / av.time_base)
        if (video.width, video.height) != (width, height) or abs(actual - duration_s) > .15:
            raise ForgeError("Generated music video failed duration/resolution checks", code="READBACK_FAILED")
        channels = len(audio.layout.channels)
    return {"video_file": str(movie), "poster": str(output / "poster.jpg"), "resolution": f"{width}x{height}",
            "fps": fps, "duration_s": duration_s, "source_start_s": start_s, "audio_channels": channels,
            "theme": theme, "mix": "Original source audio stream, not the mono analysis waveform. No loudness normalization applied.",
            "next": "Import with ingest_media or assemble_timeline(source=video_file, cuts=[[0,duration_s]], name=...). Add provided lyrics only if requested."}


def beat_cuts(session, music_source, shots, duration_s, music_start_s=0.0, beats_per_cut=4,
              intense=None, intense_beats_per_cut=None, beats_s=None):
    """Montage shots cut on the music's beat grid; beats_s skips analysis when the agent already confirmed a grid."""
    from ..domain import beat_cuts as plan
    analysis = None
    if beats_s is None:
        analysis = analyse(session, music_source)
        if not analysis["beats_s"]:
            raise ForgeError("No reliable beat grid in this music", code="INVALID_ARGUMENT",
                             hint="Pass beats_s from a grid you confirmed by listening, or cut on phrases manually")
        beats_s = analysis["beats_s"]
    slots = plan.slots(beats_s, music_start_s, duration_s, beats_per_cut=beats_per_cut,
                       intense=intense, intense_beats_per_cut=intense_beats_per_cut)
    montage = plan.fill(shots, slots)
    out = {"music_source": music_source, "music_start_s": slots[0][0], "duration_s": round(slots[-1][1] - slots[0][0], 3),
           "cuts": len(montage), "shots": montage, "time_basis": "shots in SOURCE seconds; music_s in MUSIC seconds",
           "next": "assemble_montage(shots=shots, music_source=music_source, music_start_s=music_start_s, dry_run=False)",
           "review": "Cuts follow the estimated grid. Listen to the result: move cuts to real phrase changes and "
                     "check half/double-time before rendering. Frame rounding can shift a cut by up to one frame."}
    if analysis:
        out.update(tempo_bpm=analysis["tempo_bpm"], confidence=analysis["confidence"],
                   section_candidates=analysis["section_candidates"])
        if analysis["confidence"] < .4:
            out["warning"] = "Low beat-grid confidence; confirm the tempo by ear or pass beats_s explicitly."
    return out
