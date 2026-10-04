"""Read-only project audits and observed capabilities, without version guesses."""
from pathlib import Path

from .context import current

CAPABILITIES = {
    "project_backup": ("manager", "ExportProject"), "native_subtitles": ("timeline", "CreateSubtitlesFromAudio"),
    "gallery_stills": ("timeline", "GrabStill"), "native_scene_cuts": ("clip", "DetectSceneCuts"),
    "native_motion_keyframes": ("clip", "AddKeyframe"), "smart_reframe": ("clip", "SmartReframe"),
    "cdl_grade": ("clip", "SetCDL"), "lut_grade": ("clip", "SetLUT"), "fusion": ("clip", "AddFusionComp"),
    "audio_sync": ("pool", "AutoSyncAudio"), "metadata": ("media", "SetMetadata")}


def capabilities(session):
    ctx = current(session, need_timeline=False)
    items = ctx.timeline.GetItemListInTrack("video", 1) or [] if ctx.timeline else []
    clip = next((item for item in items if item.GetMediaPoolItem() is not None), None)
    targets = {"manager": ctx.resolve.GetProjectManager(), "timeline": ctx.timeline, "clip": clip,
               "pool": ctx.media_pool, "media": clip.GetMediaPoolItem() if clip else None}
    return {"version": ctx.resolve.GetVersionString(), "transport": session.transport_name,
            "capabilities": {key: {"supported": callable(getattr(targets[scope], method, None)), "method": method,
                                   "meaning": "observed method availability; operation may still be edition-gated"}
                             for key, (scope, method) in CAPABILITIES.items()}}


def audit(session):
    ctx = current(session)
    issues, counts = [], {}
    for kind in ("video", "audio"):
        counts[kind] = 0
        for track in range(1, int(ctx.timeline.GetTrackCount(kind)) + 1):
            items = sorted(ctx.timeline.GetItemListInTrack(kind, track) or [], key=lambda item: item.GetStart())
            previous_end = None
            for index, item in enumerate(items, 1):
                counts[kind] += 1
                location = {"kind": kind, "track": track, "index": index, "name": item.GetName()}
                start, duration = int(item.GetStart()), int(item.GetDuration())
                if duration <= 0:
                    issues.append({**location, "severity": "error", "code": "EMPTY_CLIP"})
                if previous_end is not None and start != previous_end:
                    issues.append({**location, "severity": "info", "code": "GAP" if start > previous_end else "OVERLAP",
                                   "frames": abs(start - previous_end)})
                previous_end = max(previous_end or start, start + duration)
                media = item.GetMediaPoolItem()
                path = media.GetClipProperty("File Path") if media else None
                if path and not Path(path).exists():
                    issues.append({**location, "severity": "warning", "code": "SOURCE_UNAVAILABLE", "path": path})
    return {"timeline": ctx.timeline.GetName(), "fps": ctx.fps, "resolution": [ctx.width, ctx.height],
            "clips": counts, "issues": issues, "passed": not any(issue["severity"] == "error" for issue in issues),
            "scope": "structure and local source visibility; does not certify final rendered picture/audio"}
