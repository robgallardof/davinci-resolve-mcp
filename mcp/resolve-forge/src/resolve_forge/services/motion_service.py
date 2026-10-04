"""Use case: give clips life — apply a named motion style to timeline items."""

from __future__ import annotations

from ..domain import styles
from ..domain.keyframes import Keyframe, Track
from ..domain.motion import MotionPlan
from ..gateway import Session
from .appliers import APPLIERS, Unsupported, apply_plan
from ..errors import BACKEND_UNSUPPORTED, ForgeError
from .context import Context, current, describe, source_size, video_items
from .subject import Anchor, resolve_anchor
from .native import working_copy


def _relative(ctx: Context, seconds: list[float] | None, start: int, duration: int) -> list[int] | None:
    """Timeline seconds -> frames relative to one clip (only those inside it)."""
    if seconds is None:
        return None
    frames = (ctx.seconds_to_frame(s) - start for s in seconds)
    return [f for f in frames if 0 < f < duration]


def animate(session: Session, style: str, *, track: int = 1, clips: list[int] | None = None,
            cuts_s: list[float] | None = None, hits_s: list[float] | None = None,
            intensity: float = 1.0, anchor: Anchor = "face", backend: str = "auto", seed: int = 7,
            zoom_limit: float | None = None) -> dict:
    ctx = current(session)
    dst = (ctx.width, ctx.height)
    plans = []
    for n, item in enumerate(video_items(ctx, track, clips)):
        start, duration = int(item.GetStart()), int(item.GetDuration())
        point, how = resolve_anchor(anchor, item)
        plan = styles.build(
            style, duration=duration, fps=ctx.fps, anchor=point, intensity=intensity, seed=seed + n,
            cuts=_relative(ctx, cuts_s, start, duration), hits=_relative(ctx, hits_s, start, duration),
        )
        if zoom_limit is not None:
            plan = MotionPlan(tuple(Track(t.param, tuple(Keyframe(k.frame, min(k.value, zoom_limit), k.ease_out)
                                                        for k in t.keyframes)) if t.param == "zoom" else t
                                    for t in plan.tracks), plan.anchor, plan.label, plan.notes)
        plans.append((plan, point, how))
    if backend != "auto" and backend not in APPLIERS:
        raise ValueError("Unknown motion backend.")
    ctx = working_copy(session, "motion")
    results = []
    for n, (item, (plan, point, how)) in enumerate(zip(video_items(ctx, track, clips), plans)):
        outcome = apply_plan(item, plan, source_size(item, dst), dst, backend)
        results.append({**describe(item, clips[n] if clips else n + 1), **outcome,
                        "anchor": point, "anchor_source": how, "peak_zoom": round(plan.peak_zoom(), 3),
                        "notes": list(plan.notes)})
    return {"style": style, "timeline": ctx.timeline.GetName(), "clips": results}


def clear(session: Session, *, track: int = 1, clips: list[int] | None = None) -> dict:
    ctx = current(session)
    video_items(ctx, track, clips)  # validate selection before creating a version
    ctx = working_copy(session, "motion")
    removed = {name: 0 for name in APPLIERS}
    for item in video_items(ctx, track, clips):
        for name, applier in APPLIERS.items():
            try:
                removed[name] += applier.clear(item)
            except Unsupported as exc:
                raise ForgeError(str(exc), code=BACKEND_UNSUPPORTED,
                                 hint="Preserve existing Fusion effects. Inspect the graph and remove only ForgeMotion manually on a copy; do not delete or rebuild the composition.") from exc
    return {"removed": removed}
