"""Easing curves shared by every motion backend.

One definition of each curve, expressed as a cubic bezier (CSS-style control
points). Backends derive what they need from it: Resolve interpolation names,
Fusion spline handles, or baked per-frame samples.
"""

from __future__ import annotations

from enum import Enum


class Ease(str, Enum):
    LINEAR = "linear"
    IN = "in"
    OUT = "out"
    IN_OUT = "in_out"
    HOLD = "hold"  # jump at the next keyframe (smash cut / punch-in)


# (x1, y1, x2, y2) — the same numbers CSS uses for ease-in / ease-out / ease-in-out.
_BEZIER: dict[Ease, tuple[float, float, float, float]] = {
    Ease.LINEAR: (1 / 3, 1 / 3, 2 / 3, 2 / 3),
    Ease.IN: (0.42, 0.0, 0.98, 1.0),
    Ease.OUT: (0.02, 0.0, 0.58, 1.0),
    Ease.IN_OUT: (0.42, 0.0, 0.58, 1.0),
}

# Interpolation names accepted by TimelineItem.SetKeyframeInterpolation (Resolve 20+).
RESOLVE_INTERPOLATION: dict[Ease, str] = {
    Ease.LINEAR: "Linear",
    Ease.IN: "EaseIn",
    Ease.OUT: "EaseOut",
    Ease.IN_OUT: "EaseInOut",
    Ease.HOLD: "Linear",  # holds are modelled as two keys one frame apart
}


def _cubic(a: float, b: float, t: float) -> float:
    """1-D cubic bezier with endpoints 0 and 1 and control values a, b."""
    u = 1 - t
    return 3 * u * u * t * a + 3 * u * t * t * b + t ** 3


def ease(t: float, kind: Ease) -> float:
    """Progress 0..1 for normalized time t 0..1."""
    t = min(1.0, max(0.0, t))
    if kind is Ease.HOLD:
        return 0.0 if t < 1.0 else 1.0
    if kind is Ease.LINEAR:
        return t
    x1, y1, x2, y2 = _BEZIER[kind]
    # Solve x(s) = t for s by bisection (monotonic in s), then return y(s).
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if _cubic(x1, x2, mid) < t:
            lo = mid
        else:
            hi = mid
    return _cubic(y1, y2, (lo + hi) / 2)
