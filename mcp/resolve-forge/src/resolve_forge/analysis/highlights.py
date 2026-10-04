"""Find the moments worth keeping: visual motion + audio activity, scored per second.

What a human editor scrubs for in a long phone clip (the squirrel jumping, the reaction),
turned into ranked, non-overlapping windows ready for assemble_timeline.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class Window:
    start: float
    end: float
    score: float
    motion: float
    audio: float

    def as_dict(self) -> dict:
        return {"start_s": round(self.start, 2), "end_s": round(self.end, 2), "score": round(self.score, 2),
                "motion": round(self.motion, 2), "audio_db": round(self.audio, 1)}


def motion_per_second(path: str) -> tuple[list[float], float]:
    """Mean absolute frame difference per second on a small grey proxy (fast, codec-agnostic)."""
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    diffs, prev = [], None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        grey = cv2.cvtColor(cv2.resize(frame, (96, 160)), cv2.COLOR_BGR2GRAY).astype(np.int16)
        diffs.append(0.0 if prev is None else float(np.abs(grey - prev).mean()))
        prev = grey
    cap.release()
    step = max(1, int(round(fps)))
    return [float(np.mean(diffs[i:i + step])) for i in range(0, len(diffs) - step + 1, step)], fps


def _z(values: list[float]) -> list[float]:
    if len(values) < 2:
        return [0.0] * len(values)
    mu, sd = statistics.fmean(values), statistics.pstdev(values) or 1.0
    return [(v - mu) / sd for v in values]


def rank(motion: list[float], audio_db: list[float] | None, *, window_s: float = 4.0, top: int = 6,
         audio_weight: float = 0.5, min_gap_s: float = 1.0) -> list[Window]:
    """Pure scoring: best non-overlapping windows. `audio_db` may be None (no audio stack)."""
    n = len(motion)
    audio = (audio_db or [])[:n] + [-90.0] * max(0, n - len(audio_db or []))
    zm, za = _z(motion), _z(audio) if audio_db else [0.0] * n
    per_second = [m + audio_weight * a for m, a in zip(zm, za)]
    w = max(1, int(round(window_s)))
    candidates = []
    for s in range(0, max(1, n - w + 1)):
        sl = slice(s, s + w)
        candidates.append((statistics.fmean(per_second[sl]), s))
    picked: list[Window] = []
    for score, s in sorted(candidates, reverse=True):
        if any(s < p.end + min_gap_s and s + w > p.start - min_gap_s for p in picked):
            continue
        picked.append(Window(float(s), float(min(n, s + w)), score,
                             statistics.fmean(motion[s:s + w]), statistics.fmean(audio[s:s + w])))
        if len(picked) == top:
            break
    return sorted(picked, key=lambda p: p.start)
