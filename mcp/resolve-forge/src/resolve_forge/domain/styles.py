"""Named motion styles — the editorial vocabulary agents use ("tiktok_punch", "warm_push"...).

Each style is a small function (duration, fps, cuts, hits) -> MotionPlan. New
styles are added by registering a function; nothing else changes (open/closed).
"""

from __future__ import annotations

from typing import Callable

from .easing import Ease
from .keyframes import Keyframe, Track
from .motion import (
    Anchor, CENTER, MotionPlan, emphasis_pulses, handheld, min_zoom_for_rotation,
    multiply, punch_cuts, rhythm_cuts, slow_push,
)

StyleFn = Callable[..., MotionPlan]
STYLES: dict[str, tuple[StyleFn, str]] = {}


def style(name: str, summary: str):
    def register(fn: StyleFn) -> StyleFn:
        STYLES[name] = (fn, summary)
        return fn
    return register


def build(name: str, *, duration: int, fps: float, cuts: list[int] | None = None,
          hits: list[int] | None = None, anchor: Anchor = CENTER, intensity: float = 1.0,
          seed: int = 7) -> MotionPlan:
    if name not in STYLES:
        raise KeyError(f"unknown style '{name}'. Available: {', '.join(sorted(STYLES))}")
    fn, _ = STYLES[name]
    plan = fn(duration=duration, fps=fps, cuts=cuts, hits=hits or [], k=max(0.1, intensity), seed=seed)
    return MotionPlan(plan.tracks, anchor, name, plan.notes)


def _scale(base: float, k: float) -> float:
    """Scale how far a zoom level departs from 1.0 by intensity k."""
    return 1.0 + (base - 1.0) * k


@style("warm_push", "Slow continuous push-in 1.00→1.08 with ease in/out. Calm, cinematic; horizontal & long-form.")
def _warm_push(*, duration, fps, cuts, hits, k, seed):
    return MotionPlan((slow_push(duration, 1.0, _scale(1.08, k)),))


@style("warm_pull", "Slow pull-out 1.08→1.00. Use for endings, reveals, reflective beats.")
def _warm_pull(*, duration, fps, cuts, hits, k, seed):
    return MotionPlan((slow_push(duration, _scale(1.08, k), 1.0),))


@style("tiktok_punch", "Hard jump-zooms alternating 1.00/1.15 every ~2.5–3.5 s (or at given cuts). High retention vertical.")
def _tiktok_punch(*, duration, fps, cuts, hits, k, seed):
    cuts = cuts if cuts is not None else rhythm_cuts(duration, fps, (2.5, 3.5), seed=seed)
    return MotionPlan((punch_cuts(duration, cuts, (1.0, _scale(1.15, k))),))


@style("tiktok_smooth", "Like tiktok_punch but each zoom eases in over 6 frames — energetic without feeling cut.")
def _tiktok_smooth(*, duration, fps, cuts, hits, k, seed):
    cuts = cuts if cuts is not None else rhythm_cuts(duration, fps, (2.5, 4.0), seed=seed)
    return MotionPlan((punch_cuts(duration, cuts, (1.0, _scale(1.12, k)), ramp=6),))


@style("youtube_dynamic", "Subtle push 1.00→1.05 under the whole clip + punch to ×1.10 at cuts every ~6–9 s. Horizontal talking head.")
def _youtube_dynamic(*, duration, fps, cuts, hits, k, seed):
    cuts = cuts if cuts is not None else rhythm_cuts(duration, fps, (6.0, 9.0), seed=seed)
    zoom = multiply("zoom", [
        slow_push(duration, 1.0, _scale(1.05, k)),
        punch_cuts(duration, cuts, (1.0, _scale(1.10, k))),
    ], duration)
    return MotionPlan((zoom,))


@style("emphasis", "Quick bump to ×1.06 on each hit frame (key words), relaxing back. Pass hits from the transcript.")
def _emphasis(*, duration, fps, cuts, hits, k, seed):
    targets = hits or cuts or rhythm_cuts(duration, fps, (3.0, 5.0), seed=seed)
    return MotionPlan((emphasis_pulses(duration, targets, _scale(1.06, k)),))


@style("handheld", "Organic ±0.4° rotation wobble with a 1.04 safety zoom. Makes static tripod shots feel alive.")
def _handheld(*, duration, fps, cuts, hits, k, seed):
    angle = 0.4 * k
    safety = min_zoom_for_rotation(1920, 1080, angle) + 0.01
    zoom = Track("zoom", (Keyframe(0, safety, Ease.LINEAR), Keyframe(max(1, duration - 1), safety)))
    return MotionPlan((zoom, handheld(duration, fps, angle, seed=seed)),
                      notes=(f"safety zoom ×{safety:.3f} hides rotated corners",))


@style("vlog_mix", "warm_push + hard punches at cuts + handheld wobble. The 'everything' vertical vlog look.")
def _vlog_mix(*, duration, fps, cuts, hits, k, seed):
    cuts = cuts if cuts is not None else rhythm_cuts(duration, fps, (2.5, 4.0), seed=seed)
    safety = min_zoom_for_rotation(1080, 1920, 0.3 * k) + 0.01
    zoom = multiply("zoom", [
        slow_push(duration, safety, safety * _scale(1.05, k)),
        punch_cuts(duration, cuts, (1.0, _scale(1.12, k))),
    ], duration)
    return MotionPlan((zoom, handheld(duration, fps, 0.3 * k, seed=seed)))


def catalogue() -> dict[str, str]:
    return {name: summary for name, (_, summary) in sorted(STYLES.items())}
