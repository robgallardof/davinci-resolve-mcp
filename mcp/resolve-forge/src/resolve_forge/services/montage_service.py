"""A fresh multi-source timeline from reviewed cuts; source audio stays opt-in for music montages."""

from __future__ import annotations

from ..domain import formats
from ..errors import ForgeError
from ..gateway import call
from .context import current
from .media_lookup import find_or_import
from .native import accepted, mark_working, number, name as validate_name, setup_new_timeline


def assemble(session, shots, name, format=None, music_source=None, music_start_s=0.0, dry_run=True):
    name = validate_name(name)
    if not shots or len(shots) > 1000:
        raise ValueError("shots needs 1-1000 reviewed {source,start_s,end_s} ranges")
    fmt = formats.get(format) if format else None
    number(music_start_s, "music start", 0)
    decisions = []
    for shot in shots:
        if not isinstance(shot, dict) or not {"source", "start_s", "end_s"} <= shot.keys():
            raise ValueError("Each shot must contain source/start_s/end_s")
        source = validate_name(shot["source"])
        if any(isinstance(shot[key], bool) or not isinstance(shot[key], (int, float)) for key in ("start_s", "end_s")):
            raise ValueError("Shot times must be numeric source seconds")
        start = number(shot.get("start_s"), "shot start", 0)
        end = number(shot.get("end_s"), "shot end", start)
        if end <= start:
            raise ValueError("Each shot needs end_s > start_s")
        decisions.append(dict(source=source, start_s=start, end_s=end))
    if music_source is not None:
        validate_name(music_source)
    if dry_run:
        return {"dry_run": True, "timeline": name, "shots": decisions, "duration_s": sum(s["end_s"] - s["start_s"] for s in decisions),
                "format": fmt.key if fmt else None, "music_source": music_source, "music_start_s": music_start_s,
                "source_audio": "master music on A1; shot audio excluded" if music_source else "source linked audio"}
    ctx = current(session, need_timeline=False)
    for index in range(1, int(ctx.project.GetTimelineCount()) + 1):
        timeline = ctx.project.GetTimelineByIndex(index)
        if timeline and timeline.GetName() == name:
            raise ForgeError(f"Timeline '{name}' already exists", code="TIMELINE_EXISTS")
    sources = {source: find_or_import(ctx.media_pool, source) for source in dict.fromkeys(s["source"] for s in decisions)}
    music = find_or_import(ctx.media_pool, music_source) if music_source else None
    # Resolve source frame rates before timeline creation so a refused range does not leave a new version.
    source_ranges = []
    for shot in decisions:
        clip = sources[shot["source"]]
        fps = float(call(clip, "GetClipProperty", "FPS", default=0) or ctx.fps)
        number(fps, "source frame rate", .001)
        start, end = round(shot["start_s"] * fps), round(shot["end_s"] * fps)
        if end <= start:
            raise ValueError("Shot is shorter than one source frame")
        available = call(clip, "GetClipProperty", "Frames", default=None)
        if available and end > int(available):
            raise ValueError(f"Range exceeds source duration: {shot['source']}")
        source_ranges.append((clip, fps, start, end))
    total = sum((end - start) / fps for _, fps, start, end in source_ranges)
    music_fps = float(call(music, "GetClipProperty", "FPS", default=0) or ctx.fps) if music else 0
    if music:
        number(music_fps, "music frame rate", .001)
        available = call(music, "GetClipProperty", "Frames", default=None)
        if available and round((music_start_s + total) * music_fps) > int(available):
            raise ValueError("Music source is shorter than the montage; shorten the montage or choose another range")
    timeline = accepted(ctx.media_pool, "CreateEmptyTimeline", name)
    accepted(ctx.project, "SetCurrentTimeline", timeline)
    mark_working(session, current(session))
    setup_new_timeline(timeline, fmt, source_ranges[0][1])
    tl_fps = float(timeline.GetSetting("timelineFrameRate") or ctx.fps)
    origin = int(timeline.GetStartFrame())
    record, infos = origin, []
    for clip, fps, start, end in source_ranges:
        info = dict(mediaPoolItem=clip, startFrame=start, endFrame=end, recordFrame=record, trackIndex=1)
        if music:
            info["mediaType"] = 1
        infos.append(info)
        record += round((end - start) * tl_fps / fps)
    placed = ctx.media_pool.AppendToTimeline(infos) or []
    if len(placed) != len(infos):
        raise ForgeError("Resolve partially inserted the montage; inspect its new timeline", code="RESOLVE_REFUSED")
    if music:
        if int(timeline.GetTrackCount("audio")) < 1:
            accepted(timeline, "AddTrack", "audio", "stereo")
        duration = (record - origin) / tl_fps
        result = ctx.media_pool.AppendToTimeline([dict(mediaPoolItem=music, startFrame=round(music_start_s * music_fps),
                                                     endFrame=round((music_start_s + duration) * music_fps),
                                                     recordFrame=origin, trackIndex=1, mediaType=2)])
        if not result:
            raise ForgeError("Resolve refused the master music track; inspect the new timeline", code="RESOLVE_REFUSED")
    return {"dry_run": False, "timeline": name, "shots": len(placed), "duration_s": (record - origin) / tl_fps,
            "music_source": music_source, "music_start_s": music_start_s, "resolution": f"{timeline.GetSetting('timelineResolutionWidth')}x{timeline.GetSetting('timelineResolutionHeight')}"}
