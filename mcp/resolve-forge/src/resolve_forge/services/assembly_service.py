"""Use case: build a timeline from source ranges (a cut list), e.g. picked with find_highlights."""

from __future__ import annotations

from .. import errors as E
from ..domain import formats
from ..gateway import Session, call
from .context import ForgeError, current
from .media_lookup import find_or_import
from .native import mark_working, setup_new_timeline


def assemble(session: Session, source: str, cuts: list[list[float]], *, name: str,
             format: str | None = None) -> dict:
    ctx = current(session, need_timeline=False)
    if not cuts or any(len(c) != 2 or c[1] <= c[0] for c in cuts):
        raise ForgeError("cuts must be [[start_s, end_s], ...] with end > start.", code=E.INVALID_ARGUMENT)
    pool, project = ctx.media_pool, ctx.project
    for i in range(1, int(call(project, "GetTimelineCount", default=0) or 0) + 1):
        tl = project.GetTimelineByIndex(i)
        if tl is not None and tl.GetName() == name:
            raise ForgeError(f"A timeline named '{name}' already exists.", code=E.TIMELINE_EXISTS,
                             hint="Pass a different `name`.")
    clip = find_or_import(pool, source)
    src_fps = float(call(clip, "GetClipProperty", "FPS", default=0) or ctx.fps)
    timeline = pool.CreateEmptyTimeline(name)
    if timeline is None:
        raise ForgeError("CreateEmptyTimeline failed.", code=E.RESOLVE_REFUSED)
    project.SetCurrentTimeline(timeline)
    applied = setup_new_timeline(timeline, formats.get(format) if format else None, src_fps)
    record = int(timeline.GetStartFrame())
    tl_fps = float(timeline.GetSetting("timelineFrameRate") or ctx.fps)
    infos = []
    for a, b in cuts:
        s, e = round(a * src_fps), round(b * src_fps)
        infos.append({"mediaPoolItem": clip, "startFrame": s, "endFrame": e, "recordFrame": record, "trackIndex": 1})
        record += round((e - s) * tl_fps / src_fps)
    placed = pool.AppendToTimeline(infos) or []
    mark_working(session, current(session))
    return {"timeline": name, "clips": len(placed), "requested": len(cuts),
            "duration_s": round((record - int(timeline.GetStartFrame())) / tl_fps, 2),
            "resolution": f"{timeline.GetSetting('timelineResolutionWidth')}x{timeline.GetSetting('timelineResolutionHeight')}",
            "fps": tl_fps, "settings": applied,
            "next": "apply_motion / add_text_overlay / render_for"}
