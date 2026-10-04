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

from . import framing_review

ZOOM = {"wide": 1.0, "medium": 1.25, "close": 1.5, "crash": 1.45}


@dataclass(frozen=True)
class Sample:
    time_s: float
    energy: float
    x: float
    y: float
    spread: float
    box: tuple[float, float, float, float] | None = None  # extent of the moving region, if known


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


def _hints(hints):
    """Editor overrides after watching: {start_s, end_s, focus: [x, y]?, framing: wide|medium|close|crash?}."""
    out = []
    for hint in hints or []:
        if not isinstance(hint, dict) or float(hint.get("end_s", 0)) <= float(hint.get("start_s", 0)):
            raise ValueError("Each hint needs start_s < end_s (source seconds)")
        focus = hint.get("focus")
        if focus is not None and not (isinstance(focus, (list, tuple)) and len(focus) == 2
                                      and all(0 <= float(v) <= 1 for v in focus)):
            raise ValueError("hint focus must be [x, y] in 0..1")
        if hint.get("framing") not in (None, *ZOOM):
            raise ValueError(f"hint framing must be one of {', '.join(ZOOM)}")
        out.append((float(hint["start_s"]), float(hint["end_s"]), focus, hint.get("framing"), bool(hint.get("keep"))))
    return out


def _inside(point, box):
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def _grow(box, margin=0.1):
    w, h = box[2] - box[0], box[3] - box[1]
    return (box[0] - w * margin, box[1] - h * margin, box[2] + w * margin, box[3] + h * margin)


def interest(window, focused, presence, typical, hinted, peak):
    """Why would anyone keep watching this shot? (score, reasons).

    +2 a face is visible, +1 the subject acts away from any person (the pet, an object), +1 action peak,
    +2 editor hint; -2 people are seen only from behind. Body boxes that sit identical in several samples are
    furniture (a cat tree fools the detector) and are ignored.
    """
    score, reasons = 0, []
    faces = sum(1 for _, f, _ in presence if f)

    def static(box, index):
        return any(i != index and any(max(abs(a - b) for a, b in zip(box, other)) < 0.015 for other in boxes)
                   for i, (_, _, boxes) in enumerate(presence))

    bodies = [[_grow(b) for b in boxes if not static(b, i)] for i, (_, _, boxes) in enumerate(presence)]
    # The body detector misses people seen from behind or cut by the frame; a tall moving region is a person.
    movers = [s for s in window if s.box and s.box[3] - s.box[1] >= 0.4 and s.energy >= 0.5 * typical]
    for s in movers:
        near = min(range(len(presence)), key=lambda i: abs(presence[i][0] - s.time_s)) if presence else None
        if near is not None:
            bodies[near] = [*bodies[near], s.box]
    with_body = sum(1 for b in bodies if b)
    if faces:
        score += 2
        reasons.append("face visible")
    concentrated = bool(focused) and median(s.spread for s in focused) < 0.18
    threshold = 0.1 if concentrated else max(0.2, 0.3 * typical)
    for s in focused:
        if s.spread >= 0.3 or s.energy < threshold:
            continue
        near = min(range(len(presence)), key=lambda i: abs(presence[i][0] - s.time_s)) if presence else None
        if near is None or not any(_inside((s.x, s.y), box) for box in bodies[near]):
            score += 1
            reasons.append("subject acting (not the person's body)")
            break
    if peak.energy >= 3 * typical and peak.spread < 0.3:
        score += 1
        reasons.append("action peak")
    if presence and not faces and with_body >= max(1, len(presence) // 2):
        score -= 2
        reasons.append("person seen from behind, no face")
    if hinted:
        score += 2
        reasons.append("editor hint")
    if not reasons:
        reasons.append("no face, no subject action")
    return score, reasons


def plan(samples: list[Sample], ranges: list[list[float]] | None = None, *, faces: list[tuple] | None = None,
         presence: list[tuple] | None = None, drop_dull: bool = True,
         hints: list[dict] | None = None,
         min_shot_s: float = 1.2,
         max_shot_s: float = 2.8, trim_dead: bool = True, max_zoom: float = 1.6,
         focus_target: tuple[float, float] = (0.5, 0.45), upscale: float = 1.0, max_upscale: float = 2.6) -> dict:
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
    overrides = _hints(hints)
    removed = dead_ranges(samples) if trim_dead else []
    kept = _subtract(story, removed, min_shot_s) if removed else story
    typical = median(s.energy for s in samples) or 0.01
    # A small source (WhatsApp 576 px) is already upscaled to the timeline; zoom only as far as it stays sharp.
    max_zoom = min(max_zoom, framing_review.max_zoom_for(upscale, max_upscale))
    if presence is not None and faces is None:
        faces = [(t, fx, fy) for t, found, _ in presence for fx, fy in found]
    shots, previous, corrected, cut = [], None, 0, []
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
            mid_hint = next((h for h in overrides if h[0] <= (s0 + s1) / 2 < h[1]), None)
            if presence is not None:
                here = [p for p in presence if s0 <= p[0] < s1]
                score, reasons = interest(window, focused, here, typical,
                                          bool(mid_hint and (mid_hint[2] is not None or mid_hint[4])), peak)
                protected = bool(mid_hint and (mid_hint[4] or mid_hint[2] is not None))  # keep / editor's focus
                if drop_dull and score <= 0 and not protected:
                    cut.append({"start_s": s0, "end_s": s1, "why": "; ".join(reasons) or "no interaction"})
                    continue
            mean_focus = sum(s.energy for s in focused) / len(focused)
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
            elif mean_focus < 0.5 * typical and not seen:
                framing, why = "wide", "nothing to focus on: no zoom"
            else:
                framing = "close" if concentrated else "medium"
                why = "single subject in motion" if concentrated else "action area"
            mid = (s0 + s1) / 2
            hint = next((h for h in overrides if h[0] <= mid < h[1]), None)
            if hint and hint[2] is not None:  # the editor saw the real subject (the pet, not the person)
                sx, sy = float(hint[2][0]), float(hint[2][1])
                if framing == "wide" and not camera_move:
                    framing = "close"
                why += "; focus from hint"
            if hint and hint[3] is not None:
                framing, why = hint[3], why + f"; {hint[3]} from hint"
            elif framing == previous:  # never the same framing twice in a row
                framing = {"wide": "medium", "medium": "close" if concentrated else "wide",
                           "close": "medium", "crash": "medium"}[framing]
                why += "; alternated"
            if framing == previous and not (hint and hint[3]):
                framing = "medium" if framing != "medium" else "close"
            # What must stay visible depends on what the shot is about: the action, or the face/hinted subject.
            reaction = why.startswith("reaction")
            hinted = bool(hint and hint[2] is not None)
            action = [] if reaction or hinted else [(s.x, s.y, s.energy) for s in focused]
            must_see_faces = [] if hinted else seen
            notes = []
            while True:  # self-review: downgrade any zoom that would mis-frame, crop the action or go soft
                zoom = min(ZOOM[framing], max_zoom)
                if zoom <= 1.0001 and framing != "wide":
                    framing = "wide"
                    continue
                pivot = [round(focus_pivot(sx, zoom, focus_target[0]), 3), round(focus_pivot(sy, zoom, focus_target[1]), 3)]
                shot = {"start_s": s0, "end_s": s1, "framing": framing, "zoom": round(zoom, 3),
                        "subject": [round(sx, 3), round(sy, 3)], "anchor": pivot,
                        "hit_s": round(peak.time_s, 3) if framing == "crash" else None, "why": why}
                problems = framing_review.issues(shot, action, must_see_faces, upscale, max_upscale)
                if not problems or framing == "wide":
                    break
                notes.append(f"{framing}->{framing_review.DOWNGRADE[framing]}: {problems[0]}")
                framing = framing_review.DOWNGRADE[framing]
            if notes:
                corrected += 1
                shot["self_review"] = notes
            shots.append(shot)
            previous = framing
    total = sum(s["end_s"] - s["start_s"] for s in shots)
    return {"shots": shots, "duration_s": round(total, 3), "removed_dead_s": [list(r) for r in removed],
            "average_shot_s": round(total / len(shots), 2) if shots else 0,
            "framings": {name: sum(1 for s in shots if s["framing"] == name) for name in ZOOM},
            "cut_dull": cut,
            "self_review": {"corrected_shots": corrected, "max_zoom_used": round(max_zoom, 3), "upscale": round(upscale, 3)},
            "time_basis": "source seconds"}
