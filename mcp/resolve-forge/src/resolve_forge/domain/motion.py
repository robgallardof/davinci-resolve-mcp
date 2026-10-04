"""Motion plans: what a clip should do over time, independent of how Resolve applies it.

A plan is a set of tracks ("zoom" as a multiplier of the clip's current zoom,
"angle" in degrees) plus an anchor: the point of the frame the motion is built
around (usually the speaker's face) in normalized coordinates, top-left origin.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .easing import Ease
from .keyframes import Keyframe, Track

Anchor = tuple[float, float]
CENTER: Anchor = (0.5, 0.5)


@dataclass(frozen=True)
class MotionPlan:
    tracks: tuple[Track, ...]
    anchor: Anchor = CENTER
    label: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)

    def track(self, param: str) -> Track | None:
        return next((t for t in self.tracks if t.param == param), None)

    def peak_zoom(self) -> float:
        zoom = self.track("zoom")
        return max((k.value for k in zoom.keyframes), default=1.0) if zoom else 1.0


# ── cut points ──────────────────────────────────────────────────────────────

def rhythm_cuts(
    duration: int, fps: float, every_s: tuple[float, float] = (2.5, 3.5),
    tail_guard_s: float = 0.8, seed: int = 7,
) -> list[int]:
    """Deterministic, slightly irregular cut points (regular rhythms read as robotic)."""
    lo, hi = sorted(every_s)
    rng = random.Random(seed)
    cuts, t = [], 0.0
    limit = duration - tail_guard_s * fps
    while True:
        t += rng.uniform(lo, hi) * fps
        if t >= limit:
            return cuts
        cuts.append(int(round(t)))


def _clean(cuts: list[int], duration: int, min_gap: int) -> list[int]:
    out: list[int] = []
    for c in sorted(set(int(c) for c in cuts)):
        if min_gap <= c <= duration - min_gap and (not out or c - out[-1] >= min_gap):
            out.append(c)
    return out


# ── builders (one responsibility each) ──────────────────────────────────────

def slow_push(duration: int, start: float = 1.0, end: float = 1.08, ease: Ease = Ease.IN_OUT) -> Track:
    """Continuous, barely noticeable push-in (or pull-out if end < start)."""
    return Track("zoom", (Keyframe(0, start, ease), Keyframe(max(1, duration - 1), end)))


def punch_cuts(
    duration: int, cuts: list[int], levels: tuple[float, ...] = (1.0, 1.15),
    ramp: int = 0, min_gap: int = 12,
) -> Track:
    """Alternate zoom levels at each cut: the classic talking-head 'jump zoom'.

    ramp=0 gives a hard punch on the cut; ramp>0 eases into the new level over
    that many frames (softer, reads as a camera move instead of a cut).
    """
    cuts = _clean(cuts, duration, min_gap)
    keys: list[Keyframe] = []
    level_at = lambda i: levels[i % len(levels)]  # noqa: E731
    step = Ease.HOLD if ramp <= 0 else Ease.OUT
    keys.append(Keyframe(0, level_at(0), Ease.HOLD))
    for i, cut in enumerate(cuts, start=1):
        if ramp > 0:
            keys.append(Keyframe(cut, level_at(i - 1), step))
            keys.append(Keyframe(min(cut + ramp, duration - 1), level_at(i), Ease.HOLD))
        else:
            keys.append(Keyframe(cut, level_at(i), Ease.HOLD))
    last = keys[-1]
    if last.frame < duration - 1:
        keys.append(Keyframe(duration - 1, last.value, Ease.HOLD))
    return Track("zoom", tuple(_dedupe(keys)))


def emphasis_pulses(
    duration: int, hits: list[int], peak: float = 1.06, attack: int = 5, release: int = 20,
) -> Track:
    """Quick push on an emphasized word that relaxes back (a 'bump')."""
    keys = [Keyframe(0, 1.0, Ease.LINEAR)]
    for h in _clean(hits, duration, attack + release):
        keys += [
            Keyframe(max(h - attack, keys[-1].frame + 1), 1.0, Ease.OUT),
            Keyframe(h, peak, Ease.IN_OUT),
            Keyframe(min(h + release, duration - 2), 1.0, Ease.LINEAR),
        ]
    keys.append(Keyframe(duration - 1, 1.0))
    return Track("zoom", tuple(_dedupe(keys)))


def handheld(duration: int, fps: float, amount_deg: float = 0.4, period_s: float = 0.9, seed: int = 3) -> Track:
    """Slow organic rotation wobble — fakes an operator holding the camera."""
    rng = random.Random(seed)
    step = max(2, int(period_s * fps))
    keys = [Keyframe(f, rng.uniform(-amount_deg, amount_deg), Ease.IN_OUT) for f in range(0, duration - 1, step)]
    keys.append(Keyframe(duration - 1, 0.0))
    return Track("angle", tuple(_dedupe(keys)))


def multiply(param: str, tracks: list[Track], duration: int, step: int = 3) -> Track:
    """Compose zoom tracks multiplicatively (push x punches x pulses) by baking."""
    frames = sorted({*range(0, duration, step), duration - 1, *(int(k.frame) for t in tracks for k in t.keyframes)})
    keys = [Keyframe(f, math.prod(t.sample(f) for t in tracks), Ease.LINEAR) for f in frames]
    return Track(param, tuple(_dedupe(keys)))


def min_zoom_for_rotation(width: int, height: int, max_angle_deg: float) -> float:
    """Smallest uniform zoom that keeps a rotated frame free of black corners."""
    a = math.radians(abs(max_angle_deg))
    w, h = width, height
    return max((w * math.cos(a) + h * math.sin(a)) / w, (h * math.cos(a) + w * math.sin(a)) / h)


def _dedupe(keys: list[Keyframe]) -> list[Keyframe]:
    out: list[Keyframe] = []
    for k in sorted(keys, key=lambda k: k.frame):
        if out and k.frame <= out[-1].frame:
            continue
        out.append(k)
    return out
