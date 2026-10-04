"""Timeline versions, tracks, markers, clip settings and interchange."""
from pathlib import Path

from .context import current, video_items
from .native import accepted, fork, invoke, name, number, selected, timelines, verify

CLIP_PROPERTIES = {"ZoomX", "ZoomY", "Pan", "Tilt", "RotationAngle", "Opacity", "Pitch", "Yaw",
                   "AnchorPointX", "AnchorPointY", "CropLeft", "CropRight", "CropTop", "CropBottom"}
MARKER_COLORS = {"Blue", "Cyan", "Green", "Yellow", "Red", "Pink", "Purple", "Fuchsia", "Rose", "Lavender", "Sky", "Mint", "Lemon", "Sand", "Cocoa", "Cream"}


def versions(session, action="list", timeline_name=None):
    ctx = current(session, need_timeline=False)
    if action == "list":
        return {"timelines": [{"index": index, "name": timeline.GetName(), "current": timeline.GetName() == (ctx.timeline.GetName() if ctx.timeline else None)}
                              for index, timeline in enumerate(timelines(ctx.project), 1)]}
    if action == "create":
        accepted(ctx.media_pool, "CreateEmptyTimeline", name(timeline_name))
        return {"timeline": timeline_name}
    if action == "select":
        matches = [timeline for timeline in timelines(ctx.project) if timeline.GetName() == name(timeline_name)]
        if len(matches) != 1:
            raise ValueError("Timeline name must identify exactly one timeline.")
        accepted(ctx.project, "SetCurrentTimeline", matches[0])
        return {"timeline": matches[0].GetName()}
    if action == "duplicate":
        target = fork(session, "version", timeline_name)
        return {"source": target.source, "timeline": target.target}
    raise ValueError("Timeline action must be list, create, select or duplicate.")


def clips(session, properties=None, track=1, indices=None, enabled=None, color=None, copy_name=None, dry_run=True):
    properties = properties or {}
    if not properties and enabled is None and color is None:
        raise ValueError("Specify clip properties, enabled state or color.")
    if set(properties) - CLIP_PROPERTIES:
        raise ValueError(f"Unsupported clip properties: {sorted(set(properties) - CLIP_PROPERTIES)}")
    values = {key: number(value, key, 0 if key.startswith("Zoom") or key == "Opacity" else None,
                          100 if key == "Opacity" else None) for key, value in properties.items()}
    if color is not None and color not in MARKER_COLORS:
        raise ValueError("Unsupported clip color.")
    ctx, items = selected(session, track, indices)
    rows = [{"name": item.GetName(), "before": {key: invoke(item, "GetProperty", key) for key in values}} for item in items]
    if dry_run:
        return {"clips": rows, "properties": values, "applied": False}
    target = fork(session, "clips", copy_name)
    for item in video_items(target.context, track, indices):
        for key, value in values.items():
            accepted(item, "SetProperty", key, value)
            verify(value, invoke(item, "GetProperty", key), key)
        if enabled is not None:
            accepted(item, "SetClipEnabled", enabled)
            verify(enabled, invoke(item, "GetClipEnabled"), "enabled")
        if color is not None:
            accepted(item, "SetClipColor", color)
            verify(color, invoke(item, "GetClipColor"), "color")
    return {"source": target.source, "timeline": target.target, "clips": rows, "applied": True}


def markers(session, entries=None, copy_name=None, dry_run=True):
    ctx = current(session)
    existing = invoke(ctx.timeline, "GetMarkers") or {}
    if entries is None:
        return {"markers": [{"frame": int(float(frame)), "seconds": float(frame) / ctx.fps, **value} for frame, value in existing.items()]}
    length = int(invoke(ctx.timeline, "GetEndFrame")) - ctx.start_frame
    prepared, frames = [], set()
    for entry in entries:
        frame = int(round(number(entry["seconds"], "marker time", 0) * ctx.fps))
        duration = max(1, int(round(number(entry.get("duration_s", 0), "duration", 0) * ctx.fps)))
        color = entry.get("color", "Blue")
        if frame + duration > length or frame in frames or color not in MARKER_COLORS:
            raise ValueError("Markers must fit the timeline, use distinct frames and valid colors.")
        if any(int(float(key)) == frame for key in existing):
            raise ValueError("A marker already occupies the requested frame; it will not be overwritten.")
        frames.add(frame)
        prepared.append({"frame": frame, "duration": duration, "color": color, "name": name(entry.get("name", "Forge")), "note": str(entry.get("note", ""))})
    if dry_run:
        return {"markers": prepared, "applied": False}
    target = fork(session, "markers", copy_name)
    for entry in prepared:
        accepted(target.context.timeline, "AddMarker", entry["frame"], entry["color"], entry["name"], entry["note"], entry["duration"], "resolve-forge")
    after = invoke(target.context.timeline, "GetMarkers") or {}
    if not frames <= {int(float(key)) for key in after}:
        raise ValueError("Resolve did not retain all markers.")
    return {"source": target.source, "timeline": target.target, "markers": prepared, "applied": True}


def track(session, kind="video", index=1, track_name=None, enabled=None, locked=None, add=False, copy_name=None, dry_run=True):
    if kind not in {"video", "audio", "subtitle"} or type(index) is not int or index < 1:
        raise ValueError("Specify a valid track kind and a 1-based index.")
    ctx = current(session)
    count = int(invoke(ctx.timeline, "GetTrackCount", kind))
    if not add and index > count:
        raise ValueError("Track index is out of range.")
    if track_name is not None:
        name(track_name)
    plan = {"kind": kind, "index": count + 1 if add else index, "name": track_name, "enabled": enabled, "locked": locked, "add": add}
    if dry_run:
        return {"track": plan, "applied": False}
    target = fork(session, "tracks", copy_name)
    tl, index = target.context.timeline, plan["index"]
    if add:
        accepted(tl, "AddTrack", kind)
        verify(count + 1, invoke(tl, "GetTrackCount", kind), "track count")
    for value, setter, getter in ((track_name, "SetTrackName", "GetTrackName"), (enabled, "SetTrackEnable", "GetIsTrackEnabled"), (locked, "SetTrackLock", "GetIsTrackLocked")):
        if value is not None:
            accepted(tl, setter, kind, index, value)
            verify(value, invoke(tl, getter, kind, index), getter)
    return {"source": target.source, "timeline": target.target, "track": plan, "applied": True}


def export(session, output_path, format_name="otio"):
    constants = {"otio": "EXPORT_OTIO", "fcpxml": "EXPORT_FCPXML_1_10", "aaf": "EXPORT_AAF", "edl": "EXPORT_EDL", "drt": "EXPORT_DRT"}
    if format_name not in constants:
        raise ValueError("Supported interchange: otio, fcpxml, aaf, edl, drt.")
    ctx = current(session)
    output = Path(output_path).expanduser().resolve()
    if output.exists() or output.suffix.lower() != "." + format_name:
        raise ValueError("Use a new output path with the matching format extension.")
    constant = getattr(ctx.resolve, constants[format_name], None)
    if constant is None:
        from ..errors import ForgeError
        raise ForgeError("This Resolve version lacks the requested export format.", code="BACKEND_UNSUPPORTED")
    output.parent.mkdir(parents=True, exist_ok=True)
    accepted(ctx.resolve.GetProjectManager(), "SaveProject")
    accepted(ctx.timeline, "Export", str(output), constant)
    if not output.is_file() or output.stat().st_size == 0:
        raise ValueError("The exported file is absent or empty.")
    return {"file": str(output), "bytes": output.stat().st_size}
