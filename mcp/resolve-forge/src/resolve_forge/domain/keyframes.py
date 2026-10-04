"""Backend-agnostic keyframe model: a Track is a list of (frame, value, ease)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .easing import Ease, ease


@dataclass(frozen=True)
class Keyframe:
    frame: float  # clip-relative frame (0 = first frame of the timeline item)
    value: float
    ease_out: Ease = Ease.IN_OUT  # curve of the segment that LEAVES this key


@dataclass(frozen=True)
class Track:
    param: str  # "zoom", "angle", "pan", "tilt" — mapped per backend
    keyframes: tuple[Keyframe, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        frames = [k.frame for k in self.keyframes]
        if frames != sorted(frames) or len(set(frames)) != len(frames):
            raise ValueError(f"track {self.param}: keyframes must be strictly increasing")

    def sample(self, frame: float) -> float:
        keys = self.keyframes
        if not keys:
            raise ValueError(f"track {self.param} is empty")
        if frame <= keys[0].frame:
            return keys[0].value
        for a, b in zip(keys, keys[1:]):
            if frame < b.frame:
                t = (frame - a.frame) / (b.frame - a.frame)
                return a.value + (b.value - a.value) * ease(t, a.ease_out)
        return keys[-1].value

    def bake(self, step: int = 1) -> list[tuple[float, float]]:
        """Per-frame samples — the universal fallback for backends without easing."""
        if not self.keyframes:
            return []
        start, end = int(self.keyframes[0].frame), int(self.keyframes[-1].frame)
        frames = list(range(start, end + 1, max(1, step)))
        if frames[-1] != end:
            frames.append(end)
        return [(f, self.sample(f)) for f in frames]

    def dense(self, step: int = 2) -> list[tuple[float, float]]:
        """Every key plus samples inside eased segments.

        For backends that can only set plain values (Fusion over the Free-edition
        bridge): the curve shape lives in the samples, not in handles.
        """
        keys = self.expand_holds().keyframes
        out: list[tuple[float, float]] = []
        for a, b in zip(keys, keys[1:]):
            out.append((a.frame, a.value))
            if a.ease_out not in (Ease.LINEAR, Ease.HOLD):
                f = a.frame + step
                while f < b.frame:
                    out.append((f, self.sample(f)))
                    f += step
        if keys:
            out.append((keys[-1].frame, keys[-1].value))
        return out

    def expand_holds(self) -> "Track":
        """Rewrite HOLD segments as two keys one frame apart (for backends without steps)."""
        out: list[Keyframe] = []
        for a, b in zip(self.keyframes, self.keyframes[1:] + (None,)):
            if a.ease_out is Ease.HOLD and b is not None:
                out.append(Keyframe(a.frame, a.value, Ease.LINEAR))
                if b.frame - 1 > a.frame:
                    out.append(Keyframe(b.frame - 1, a.value, Ease.LINEAR))
            else:
                out.append(a)
        return Track(self.param, tuple(out))

