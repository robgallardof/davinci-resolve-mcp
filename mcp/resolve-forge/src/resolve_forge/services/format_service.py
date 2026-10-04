"""Use case: make a platform version (9:16, 4:5, 16:9...) of the current timeline.

Never edits the source timeline: it duplicates it, resizes the copy and
re-frames every clip around its subject so nothing important is cropped.
"""

from __future__ import annotations

from ..domain import formats
from ..domain.framing import frame_subject
from ..gateway import Session, call
from .. import errors as E
from .context import ForgeError, current, source_size
from .subject import Anchor, resolve_anchor


def make_version(session: Session, format_key: str, *, subject: Anchor = "face",
                 center_bias: float = 1.0, name: str | None = None, smart_reframe: bool = False) -> dict:
    ctx = current(session)
    fmt = formats.get(format_key)
    name = name or f"{ctx.timeline.GetName()} [{fmt.key}]"
    copy = ctx.timeline.DuplicateTimeline(name)
    if copy is None:
        raise ForgeError(f"DuplicateTimeline failed: a timeline named '{name}' probably exists.",
                         code=E.TIMELINE_EXISTS, hint="Pass a different `name`.")
    ctx.project.SetCurrentTimeline(copy)  # DuplicateTimeline already moves 'current'; make it explicit

    settings = {"useCustomSettings": "1", "timelineResolutionWidth": str(fmt.width),
                "timelineResolutionHeight": str(fmt.height)}
    for key, value in settings.items():
        copy.SetSetting(key, value)
    got = (int(copy.GetSetting("timelineResolutionWidth")), int(copy.GetSetting("timelineResolutionHeight")))
    if got != (fmt.width, fmt.height):
        raise ForgeError(f"Resolve kept the timeline at {got[0]}x{got[1]}.", code=E.RESOLVE_REFUSED,
                         hint="Set the resolution manually in Timeline Settings.")

    dst = (fmt.width, fmt.height)
    framed = []
    for track in range(1, int(copy.GetTrackCount("video")) + 1):
        for item in copy.GetItemListInTrack("video", track) or []:
            if call(item, "GetMediaPoolItem") is None:
                continue  # titles, generators, adjustment clips keep their own sizing
            if smart_reframe and call(item, "SmartReframe", default=False):
                framed.append({"track": track, "name": item.GetName(), "method": "smart_reframe"})
                continue
            point, how = resolve_anchor(subject, item)
            sizing = frame_subject(source_size(item, dst), dst, point, center_bias=center_bias)
            for prop, value in sizing.as_props().items():
                item.SetProperty(prop, value)
            framed.append({"track": track, "name": item.GetName(), "method": how,
                           "subject": point, **{k: round(v, 3) for k, v in sizing.as_props().items()}})
    return {"timeline": name, "format": fmt.as_dict(), "clips": framed,
            "next": "apply_motion on this timeline, then check text against safe_rect_px"}
