"""Use case: give clips life — apply a named motion style to timeline items."""

from __future__ import annotations

from ..domain import styles
from ..gateway import Session
from .appliers import APPLIERS, apply_plan
from .context import Context, current, describe, source_size, video_items
from .subject import Anchor, resolve_anchor


def _relative(ctx: Context, seconds: list[float] | None, start: int, duration: int) -> list[int] | None:
    """Timeline seconds -> frames relative to one clip (only those inside it)."""
    if seconds is None:
        return None
    frames = (ctx.seconds_to_frame(s) - start for s in seconds)
    return [f for f in frames if 0 < f < duration]


def animate(session: Session, style: str, *, track: int = 1, clips: list[int] | None = None,
            cuts_s: list[float] | None = None, hits_s: list[float] | None = None,
            intensity: float = 1.0, anchor: Anchor = "face", backend: str = "auto", seed: int = 7) -> dict:
    ctx = current(session)
    dst = (ctx.width, ctx.height)
    results = []
    for n, item in enumerate(video_items(ctx, track, clips)):
        start, duration = int(item.GetStart()), int(item.GetDuration())
        point, how = resolve_anchor(anchor, item)
        plan = styles.build(
            style, duration=duration, fps=ctx.fps, anchor=point, intensity=intensity, seed=seed + n,
            cuts=_relative(ctx, cuts_s, start, duration), hits=_relative(ctx, hits_s, start, duration),
        )
        outcome = apply_plan(item, plan, source_size(item, dst), dst, backend)
        results.append({**describe(item, clips[n] if clips else n + 1), **outcome,
                        "anchor": point, "anchor_source": how, "peak_zoom": round(plan.peak_zoom(), 3),
                        "notes": list(plan.notes)})
    return {"style": style, "timeline": ctx.timeline.GetName(), "clips": results}


def clear(session: Session, *, track: int = 1, clips: list[int] | None = None) -> dict:
    ctx = current(session)
    removed = {name: 0 for name in APPLIERS}
    for item in video_items(ctx, track, clips):
        for name, applier in APPLIERS.items():
            removed[name] += applier.clear(item)
    return {"removed": removed}
