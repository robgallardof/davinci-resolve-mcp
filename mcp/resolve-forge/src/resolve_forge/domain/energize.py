"""Pure 'entertainment pacing': turn story ranges into short shots that keep the screen changing.

Every shot is short (default 1.2-2.8 s), gets its own framing and is anchored on the detected action:
  wide   - establishes the space (start of a scene, camera moves)
  medium - x1.25 on the action
  close  - x1.5 on concentrated action (one subject)
  crash  - fast punch to x1.45 at an action peak (the jump, the grab)
Framings never repeat back to back. Long stretches with nothing moving can be trimmed.
The zoom pivot is chosen so the subject is pulled toward the centre without ever revealing frame edges.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median

ZOOM = {"wide": 1.0, "medium": 1.25, "close": 1.5, "crash": 1.45}


@dataclass(frozen=True)
class Sample:
    time_s: float
    energy: float
    x: float
    y: float
    spread: float


def focus_pivot(subject: float, zoom: float, target: float = 0.5) -> float:
    """Pivot p in [0,1] that moves `subject` toward `target` under `zoom`; any p in [0,1] keeps the frame covered."""
    if zoom <= 1.0001:
        return 0.5
    return min(1.0, max(0.0, (zoom * subject - target) / (zoom - 1)))


def dead_ranges(samples: list[Sample], *, energy_below: float = 0.2, minimum_s: float = 2.0) -> list[tuple[float, float]]:
    """Stretches where almost nothing moves (empty room, subject frozen) for at least minimum_s."""
    if not samples:
        return []
    end_of_source = samples[-1].time_s + _step(samples)
    out, start = [], None
    for sample in [*samples, Sample(end_of_source, math.inf, .5, .5, 0)]:
        if sample.energy < energy_below and start is None:
            start = sample.time_s
        elif sample.energy >= energy_below and start is not None:
            if sample.time_s - start >= minimum_s:
                out.append((round(start, 3), round(sample.time_s, 3)))
            start = None
    return out


def _step(samples):
    return samples[1].time_s - samples[0].time_s if len(samples) > 1 else 0.25


def _subtract(ranges, holes, minimum):
    result = []
    for a, b in ranges:
        pieces = [(a, b)]
        for h0, h1 in holes:
            nxt = []
            for p0, p1 in pieces:
                if h1 <= p0 or h0 >= p1:
                    nxt.append((p0, p1))
                    continue
                if h0 - p0 >= minimum:
                    nxt.append((p0, h0))
                if p1 - h1 >= minimum:
                    nxt.append((h1, p1))
            pieces = nxt
        result += pieces
    return result


def _in(samples, a, b):
    return [s for s in samples if a <= s.time_s < b]


def _split(a, b, samples, min_shot, max_shot):
    """Even pieces no longer than max_shot; each inner cut nudged (±0.4 s) onto an action peak (cut on action)."""
    count = max(1, math.ceil((b - a) / max_shot))
    if (b - a) / count < min_shot and count > 1:
        count -= 1
    cuts = [a + (b - a) * i / count for i in range(1, count)]
    nudged = []
    for cut in cuts:
        near = [s for s in samples if abs(s.time_s - cut) <= 0.4]
        best = max(near, key=lambda s: s.energy).time_s if near else cut
        low = (nudged[-1] if nudged else a) + min_shot
        nudged.append(min(max(best, low), b - min_shot) if b - low >= min_shot else cut)
    bounds = [a, *nudged, b]
    if any(y - x > max_shot + 1e-6 for x, y in zip(bounds, bounds[1:])):
        bounds = [a, *cuts, b]  # a nudge broke the length limit: fall back to even cuts
    return [(round(x, 3), round(y, 3)) for x, y in zip(bounds, bounds[1:]) if y - x > 0.05]


def plan(samples: list[Sample], ranges: list[list[float]] | None = None, *, faces: list[tuple] | None = None,
         min_shot_s: float = 1.2,
         max_shot_s: float = 2.8, trim_dead: bool = True, max_zoom: float = 1.6,
         focus_target: tuple[float, float] = (0.5, 0.45)) -> dict:
    if not samples:
        raise ValueError("No motion samples: the source has no decodable video")
    if not 0.5 <= min_shot_s < max_shot_s <= 10:
        raise ValueError("Use 0.5 <= min_shot_s < max_shot_s <= 10 seconds")
    if not 1.0 <= max_zoom <= 2.5:
        raise ValueError("max_zoom must be between 1.0 and 2.5")
    duration = samples[-1].time_s + _step(samples)
    story = [(float(a), float(b)) for a, b in (ranges or [[0.0, duration]])]
    for a, b in story:
        if not (math.isfinite(a) and math.isfinite(b)) or a < 0 or b <= a or b > duration + 0.5:
            raise ValueError("ranges must be [start_s, end_s] inside the source")
    removed = dead_ranges(samples) if trim_dead else []
    kept = _subtract(story, removed, min_shot_s) if removed else story
    typical = median(s.energy for s in samples) or 0.01
    shots, previous = [], None
    for range_index, (a, b) in enumerate(kept):
        for shot_index, (s0, s1) in enumerate(_split(a, b, _in(samples, a, b), min_shot_s, max_shot_s)):
            window = _in(samples, s0, s1) or [min(samples, key=lambda s: abs(s.time_s - s0))]
            focused = [s for s in window if s.spread < 0.3 and s.energy > 0] or window
            weight = sum(s.energy for s in focused) or 1.0
            sx = sum(s.x * s.energy for s in focused) / weight if weight else 0.5
            sy = sum(s.y * s.energy for s in focused) / weight if weight else 0.5
            peak = max(window, key=lambda s: s.energy)
            camera_move = median(s.spread for s in window) > 0.3 and median(s.energy for s in window) > 2 * typical
            concentrated = median(s.spread for s in focused) < 0.18
            seen = [(fx, fy) for ft, fx, fy in faces or [] if s0 <= ft < s1]
            calm = median(s.energy for s in window) < 1.5 * typical
            if camera_move:
                framing, why = "wide", "camera moves: keep it wide"
            elif seen and calm and len(seen) >= max(1, round((s1 - s0) / 1.0)):
                framing, why = "close", "reaction: face in a calm moment"
                sx, sy = float(median(f[0] for f in seen)), float(median(f[1] for f in seen))
            elif shot_index == 0 and range_index == 0:
                framing, why = "wide", "opening: establish the space"
            elif peak.energy >= 3 * typical and peak.spread < 0.3 and previous != "crash":
                framing, why = "crash", f"action peak at {peak.time_s:.2f}s"
            elif shot_index == 0:
                framing, why = "wide", "new scene: establish"
            else:
                framing = "close" if concentrated else "medium"
                why = "single subject in motion" if concentrated else "action area"
            if framing == previous:  # never the same framing twice in a row
                framing = {"wide": "medium", "medium": "close" if concentrated else "wide",
                           "close": "medium", "crash": "medium"}[framing]
                why += "; alternated"
            zoom = min(ZOOM[framing], max_zoom)
            pivot = [round(focus_pivot(sx, zoom, focus_target[0]), 3), round(focus_pivot(sy, zoom, focus_target[1]), 3)]
            shots.append({"start_s": s0, "end_s": s1, "framing": framing, "zoom": round(zoom, 3),
                          "subject": [round(sx, 3), round(sy, 3)], "anchor": pivot,
                          "hit_s": round(peak.time_s, 3) if framing == "crash" else None, "why": why})
            previous = framing
    total = sum(s["end_s"] - s["start_s"] for s in shots)
    return {"shots": shots, "duration_s": round(total, 3), "removed_dead_s": [list(r) for r in removed],
            "average_shot_s": round(total / len(shots), 2) if shots else 0,
            "framings": {name: sum(1 for s in shots if s["framing"] == name) for name in ZOOM},
            "time_basis": "source seconds"}
