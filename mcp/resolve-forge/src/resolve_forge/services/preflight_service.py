"""Read-only technical checks before render. Never certify unobserved pixels or sound."""
from math import isfinite
from pathlib import Path

from ..domain import formats
from ..domain.preflight import uncovered
from ..gateway import call
from .context import current


def inspect(session, format_key: str | None = None) -> dict:
    ctx = current(session)
    timeline = ctx.timeline
    start = int(timeline.GetStartFrame())
    # Resolve's GetEndFrame is exclusive, as used by timeline assembly/render ranges.
    end = int(timeline.GetEndFrame())
    issues, coverage, counts = [], {"video": [], "audio": []}, {"video": 0, "audio": 0}
    if end <= start:
        issues.append({"severity": "error", "code": "EMPTY_TIMELINE"})
    for kind in coverage:
        for track in range(1, int(timeline.GetTrackCount(kind)) + 1):
            enabled = call(timeline, "GetIsTrackEnabled", kind, track, default=None)
            if enabled is False:
                continue
            if enabled is None:
                issues.append({"severity": "warning", "code": "TRACK_STATE_UNKNOWN", "kind": kind, "track": track})
            for index, item in enumerate(timeline.GetItemListInTrack(kind, track) or [], 1):
                if call(item, "GetClipEnabled", default=None) is False:
                    continue
                location = {"kind": kind, "track": track, "index": index, "name": item.GetName()}
                counts[kind] += 1
                left, duration = int(item.GetStart()), int(item.GetDuration())
                if duration <= 0:
                    issues.append({**location, "severity": "error", "code": "EMPTY_CLIP"})
                else:
                    coverage[kind].append((left, left + duration))
                media = item.GetMediaPoolItem()
                path = media.GetClipProperty("File Path") if media else None
                if path and "%" not in str(path) and not Path(path).exists():
                    issues.append({**location, "severity": "error", "code": "SOURCE_UNAVAILABLE", "path": path})
                if kind == "video":
                    for key in ("ZoomX", "ZoomY", "Pan", "Tilt"):
                        value = call(item, "GetProperty", key, default=None)
                        if value is None:
                            issues.append({**location, "severity": "warning", "code": "TRANSFORM_UNREADABLE", "property": key})
                            continue
                        try:
                            number = float(value)
                        except (ValueError, TypeError):
                            number = float("nan")
                        if not isfinite(number) or (key.startswith("Zoom") and number <= 0):
                            issues.append({**location, "severity": "error", "code": "INVALID_TRANSFORM", "property": key, "value": str(value)})
                        elif key.startswith("Zoom") and number > 1.5:
                            issues.append({**location, "severity": "warning", "code": "REVIEW_HIGH_ZOOM", "property": key, "value": number})
    video_gaps = uncovered(coverage["video"], start, end)
    audio_gaps = uncovered(coverage["audio"], start, end)
    for gap in video_gaps:
        issues.append({**gap, "severity": "error", "code": "VIDEO_COVERAGE_GAP"})
    for gap in audio_gaps:
        issues.append({**gap, "severity": "warning", "code": "AUDIO_COVERAGE_GAP", "meaning": "No enabled timeline audio clip; deliberate silence may be valid."})
    expected = formats.get(format_key) if format_key else None
    if expected and (ctx.width, ctx.height) != (expected.width, expected.height):
        issues.append({"severity": "error", "code": "FORMAT_RESOLUTION_MISMATCH", "expected": [expected.width, expected.height], "actual": [ctx.width, ctx.height]})
    if expected and expected.max_seconds and (end - start) / ctx.fps > expected.max_seconds:
        issues.append({"severity": "error", "code": "FORMAT_DURATION_EXCEEDED", "limit_s": expected.max_seconds})
    return {"timeline": timeline.GetName(), "resolution": [ctx.width, ctx.height], "fps": ctx.fps,
            "duration_s": max(0, end - start) / ctx.fps, "clips": counts, "issues": issues,
            "technical_passed": not any(i["severity"] == "error" for i in issues),
            "visual_review_required": True,
            "unverified": ["animated zoom paths and subject framing", "text/face collisions", "actual black/frozen frames", "audio loudness, clipping and intelligibility", "color and LUT appearance"],
            "next_steps": ["Inspect review_shots contact sheet before rendering", "Listen to the edited timeline", "Run review_video on the rendered file"],
            "scope": "Timeline properties and enabled-track coverage only. Missing files can be cached by Resolve; relink or verify playback. Generators/Fusion may produce sound or picture not inferable from clip coverage."}
