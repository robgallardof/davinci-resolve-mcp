"""Use case: motivated sound effects on new audio tracks of a working copy. Gain is baked into a new WAV."""

from __future__ import annotations

import secrets
from pathlib import Path

from ..domain.sound_design import cues as validate_cues, density_warnings, lanes
from ..errors import ForgeError
from .analysis_service import source_path
from .audio_service import ffmpeg_executable, run
from .media_lookup import find_or_import
from .native import accepted, working_copy
from .render_service import DEFAULT_OUTPUT


def _with_gain(source_file: str, gain_db: float, folder: Path) -> str:
    """A new 48 kHz WAV with the gain applied; 0 dB uses the original file untouched."""
    if gain_db == 0:
        return source_file
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / f"{Path(source_file).stem}_{gain_db:+.1f}dB.wav"
    if not output.exists():
        run([ffmpeg_executable(), "-hide_banner", "-nostdin", "-n", "-i", source_file, "-vn",
             "-af", f"volume={gain_db}dB,alimiter=limit=0.95", "-ar", "48000", "-c:a", "pcm_s24le", str(output)])
        if not output.is_file() or output.stat().st_size < 44:
            raise ForgeError("The gain-adjusted effect was not written.", code="AUDIO_PROCESSING_FAILED")
    return str(output)


def place(session, raw_cues, gain_db=-8.0, dry_run=True):
    timed = validate_cues(raw_cues, gain_db)
    warnings = density_warnings(timed)
    if dry_run:
        return {"dry_run": True, "cues": timed, "warnings": warnings,
                "next": "Review each reason against the picture, then call again with dry_run=false"}
    folder = DEFAULT_OUTPUT / "sfx" / secrets.token_hex(4)
    files = {}
    for cue in timed:  # resolve and render every effect before touching the timeline
        key = (cue["source"], cue["gain_db"])
        if key not in files:
            files[key] = _with_gain(source_path(session, cue["source"]), cue["gain_db"], folder)
    ctx = working_copy(session, "sfx")
    pool = ctx.media_pool
    clips, intervals = [], []
    for cue in timed:
        clip = find_or_import(pool, files[(cue["source"], cue["gain_db"])])
        frames = int(float(clip.GetClipProperty("Frames") or 0))
        if frames < 1:
            raise ForgeError(f"Resolve reports no duration for {cue['source']}.", code="RESOLVE_REFUSED")
        start = ctx.seconds_to_frame(cue["time_s"])
        clips.append((clip, frames, start))
        intervals.append((start, start + frames))
    lane_of = lanes(intervals)
    base = int(ctx.timeline.GetTrackCount("audio"))
    for _ in range(max(lane_of) + 1):
        accepted(ctx.timeline, "AddTrack", "audio", "stereo")
    infos = [dict(mediaPoolItem=clip, startFrame=0, endFrame=frames, recordFrame=start,
                  trackIndex=base + lane + 1, mediaType=2)
             for (clip, frames, start), lane in zip(clips, lane_of)]
    placed = pool.AppendToTimeline(infos) or []
    if len(placed) != len(infos):
        raise ForgeError(f"Resolve placed {len(placed)} of {len(infos)} effects.", code="RESOLVE_REFUSED",
                         hint="Inspect the working timeline; a partial insertion may exist.")
    return {"dry_run": False, "placed": len(placed), "tracks": [base + lane + 1 for lane in sorted(set(lane_of))],
            "timeline": ctx.timeline.GetName(), "cues": timed, "warnings": warnings, "files": str(folder),
            "review": "Listen in context: effects should sit under the voice (check the mix and loudness before render_for)."}
