"""Read-side helpers: the current project/timeline and the clips an operation targets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..gateway import Session, call


class ForgeError(RuntimeError):
    """A user-facing failure with an actionable message."""


@dataclass
class Context:
    resolve: Any
    project: Any
    timeline: Any
    media_pool: Any
    fps: float
    width: int
    height: int

    @property
    def start_frame(self) -> int:
        return int(self.timeline.GetStartFrame())

    def seconds_to_frame(self, seconds: float) -> int:
        """Timeline seconds (0 = timeline start) to an absolute timeline frame."""
        return self.start_frame + int(round(seconds * self.fps))


def current(session: Session, *, need_timeline: bool = True) -> Context:
    resolve = session.resolve()
    project = resolve.GetProjectManager().GetCurrentProject()
    if project is None:
        raise ForgeError("No project open in Resolve.")
    timeline = project.GetCurrentTimeline()
    if need_timeline and timeline is None:
        raise ForgeError("No current timeline. Open or create one first.")
    src = timeline if timeline is not None else project
    return Context(
        resolve=resolve, project=project, timeline=timeline, media_pool=project.GetMediaPool(),
        fps=float(src.GetSetting("timelineFrameRate") or 30),
        width=int(src.GetSetting("timelineResolutionWidth") or 1920),
        height=int(src.GetSetting("timelineResolutionHeight") or 1080),
    )


def video_items(ctx: Context, track: int = 1, indices: list[int] | None = None) -> list[Any]:
    """Clips on a video track, optionally filtered by 1-based position."""
    items = [i for i in (ctx.timeline.GetItemListInTrack("video", track) or []) if i is not None]
    if not items:
        raise ForgeError(f"Video track {track} has no clips.")
    if not indices:
        return items
    bad = [i for i in indices if not 1 <= i <= len(items)]
    if bad:
        raise ForgeError(f"Clip index out of range {bad}; track {track} has {len(items)} clips.")
    return [items[i - 1] for i in indices]


def source_size(item: Any, fallback: tuple[int, int]) -> tuple[int, int]:
    mpi = call(item, "GetMediaPoolItem")
    res = call(mpi, "GetClipProperty", "Resolution", default="") if mpi else ""
    try:
        w, h = (int(v) for v in str(res).lower().split("x"))
        return w, h
    except ValueError:
        return fallback


def source_path(item: Any) -> str | None:
    mpi = call(item, "GetMediaPoolItem")
    return (call(mpi, "GetClipProperty", "File Path", default=None) or None) if mpi else None


def describe(item: Any, index: int) -> dict:
    return {
        "index": index, "name": item.GetName(), "start": item.GetStart(),
        "duration": item.GetDuration(), "zoom": call(item, "GetProperty", "ZoomX"),
    }
