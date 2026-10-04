"""Use case: background music under a voice, ducked from the transcript and baked into a new stereo WAV."""

from __future__ import annotations

import secrets
import wave

from ..domain.ducking import gain_curve, speech_regions
from ..domain.text_design import provided_words
from ..errors import ForgeError
from ..gateway import call
from . import transcript_service
from .analysis_service import source_path
from .context import current
from .media_lookup import find_or_import
from .native import accepted, number, working_copy
from .render_service import DEFAULT_OUTPUT

RATE = 48000


def _decode_stereo(path: str, start_s: float, duration_s: float):
    import av
    import numpy as np
    chunks = []
    with av.open(path) as container:
        if not container.streams.audio:
            raise ValueError("The music source has no audio stream")
        resampler = av.AudioResampler(format="flt", layout="stereo", rate=RATE)
        for frame in container.decode(audio=0):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1, 2))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1, 2))
    samples = np.concatenate(chunks) if chunks else np.zeros((0, 2), np.float32)
    first, count = round(start_s * RATE), round(duration_s * RATE)
    if first + count > len(samples):
        raise ValueError(f"The music lasts {len(samples) / RATE:.1f}s; it cannot cover {duration_s:.1f}s from "
                         f"{start_s:.1f}s (no looping). Choose a longer track or an earlier start.")
    return samples[first:first + count]


def _write_wav24(path, stereo) -> None:
    import numpy as np
    scaled = (np.clip(stereo, -1, 1) * 8388607).astype("<i4")
    packed = scaled.reshape(-1).view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(3)
        out.setframerate(RATE)
        out.writeframes(packed)


def add(session, music_source, music_start_s=0.0, speech_db=-20.0, open_db=-10.0, words=None, dry_run=True):
    number(music_start_s, "music start", 0)
    ctx = current(session)
    duration = (int(ctx.timeline.GetEndFrame()) - ctx.start_frame) / ctx.fps
    if duration <= 0:
        raise ValueError("The current timeline is empty")
    if words is not None:
        spoken = provided_words(words)
    else:
        transcript_service.require_speech_stack()
        spoken = transcript_service.timeline_words(ctx, transcript_service._DEFAULT).words
    regions = speech_regions(spoken)
    curve = gain_curve(regions, duration, speech_db=speech_db, open_db=open_db)
    summary = {"music_source": music_source, "duration_s": round(duration, 3), "speech_regions": [[round(a, 2), round(b, 2)] for a, b in regions],
               "levels_db": {"under_voice": speech_db, "between_lines": open_db}, "time_basis": "timeline seconds"}
    if dry_run:
        return {"dry_run": True, **summary, "gain_curve": curve}
    import numpy as np
    stereo = _decode_stereo(source_path(session, music_source), music_start_s, duration)
    times, levels = zip(*curve)
    gain = 10 ** (np.interp(np.arange(len(stereo)) / RATE, times, levels) / 20)
    folder = DEFAULT_OUTPUT / "music-bed" / secrets.token_hex(4)
    folder.mkdir(parents=True, exist_ok=False)
    output = folder / "music_bed.wav"
    _write_wav24(output, stereo * gain[:, None].astype(np.float32))
    ctx = working_copy(session, "music")
    clip = find_or_import(ctx.media_pool, str(output))
    fps = float(call(clip, "GetClipProperty", "FPS", default=0) or ctx.fps)
    available = int(float(call(clip, "GetClipProperty", "Frames", default=0) or 0))
    end = round(duration * fps) if not available else min(available, round(duration * fps))
    accepted(ctx.timeline, "AddTrack", "audio", "stereo")
    track = int(ctx.timeline.GetTrackCount("audio"))
    placed = ctx.media_pool.AppendToTimeline([dict(mediaPoolItem=clip, startFrame=0, endFrame=end,
                                                   recordFrame=ctx.start_frame, trackIndex=track, mediaType=2)])
    if not placed:
        raise ForgeError("Resolve refused the music bed; inspect the working timeline.", code="RESOLVE_REFUSED")
    return {"dry_run": False, **summary, "track": track, "timeline": ctx.timeline.GetName(), "file": str(output),
            "review": "Listen to the mix; voice should stay clear. Then normalise/render at the platform loudness."}
