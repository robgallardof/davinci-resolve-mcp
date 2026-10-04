"""Pure speaker layouts for multi-person footage (podcasts, interviews, two people on a couch).

Given who is on screen (a face box per person) and who speaks when, decide per segment:
  single - frame the active speaker
  split  - when 2+ people talk over each other (or the user asks): 2 stacked (vertical) / side by side
           (horizontal); 3 as two on top + one below; 4 as a 2x2 grid
  wide   - nobody identifiable speaks: keep the group shot
and compute each panel's crop in source coordinates so the face sits in the upper third with headroom.
This is a stylistic choice: only use it when the user wants it (or approves the producer's suggestion).
"""

from __future__ import annotations

import math


def panels(count: int, out_w: int, out_h: int) -> list[tuple[float, float, float, float]]:
    """Screen rectangles (x0, y0, x1, y1, normalized) for `count` panels on a frame of out_w x out_h."""
    vertical = out_h > out_w
    if count <= 1:
        return [(0.0, 0.0, 1.0, 1.0)]
    if count == 2:
        return [(0, 0, 1, .5), (0, .5, 1, 1)] if vertical else [(0, 0, .5, 1), (.5, 0, 1, 1)]
    if count == 3:
        return [(0, 0, .5, .5), (.5, 0, 1, .5), (0, .5, 1, 1)] if vertical else [(0, 0, 1 / 3, 1), (1 / 3, 0, 2 / 3, 1), (2 / 3, 0, 1, 1)]
    return [(0, 0, .5, .5), (.5, 0, 1, .5), (0, .5, .5, 1), (.5, .5, 1, 1)]


def crop_for(face: tuple[float, float, float, float], panel_aspect: float, source_aspect: float,
             face_share: float = 0.32) -> tuple[float, float, float, float]:
    """Source crop (normalized) with panel aspect (w/h) where the face fills `face_share` of the height and
    sits in the upper third. Shifted (never shrunk below the face) to stay inside the source."""
    fx0, fy0, fx1, fy1 = face
    face_h = max(fy1 - fy0, 0.02)
    h = min(1.0, face_h / face_share)
    w = h * panel_aspect / source_aspect  # normalized width for the same pixel aspect as the panel
    if w > 1.0:  # source too narrow for this panel: use full width, recompute height
        w, h = 1.0, min(1.0, source_aspect / panel_aspect)
    cx, cy = (fx0 + fx1) / 2, (fy0 + fy1) / 2
    x0 = min(max(cx - w / 2, 0.0), 1.0 - w)
    y0 = min(max(cy - h / 3, 0.0), 1.0 - h)  # eyes ~ upper third
    return (round(x0, 4), round(y0, 4), round(x0 + w, 4), round(y0 + h, 4))


def segments(active: list[tuple[float, tuple[int, ...]]], duration_s: float, *, people: int,
             min_segment_s: float = 1.5, mode: str = "auto") -> list[dict]:
    """active: (time_s, speaking person indices) samples in order. mode: auto | single | split.

    Hysteresis: a layout lasts at least min_segment_s, so quick back-and-forth does not flicker."""
    if mode not in ("auto", "single", "split"):
        raise ValueError("mode must be auto, single or split")
    if people < 1:
        raise ValueError("No people detected to lay out")
    if not active:
        return [{"start_s": 0.0, "end_s": round(duration_s, 3), "layout": "wide", "people": list(range(people))}]

    def decide(speakers):
        if mode == "split" and people > 1:
            return ("split", tuple(range(min(people, 4))))
        if len(speakers) >= 2 and mode == "auto":
            return ("split", tuple(sorted(speakers))[:4])
        if speakers:
            return ("single", (sorted(speakers)[0],))
        return ("wide", tuple(range(people)))

    raw = []
    for index, (time_s, speakers) in enumerate(active):
        end = active[index + 1][0] if index + 1 < len(active) else duration_s
        state = decide(tuple(speakers))
        if raw and raw[-1][2] == state:
            raw[-1][1] = end
        else:
            raw.append([time_s, end, state])
    merged = []
    for start, end, state in raw:  # absorb blips shorter than min_segment_s into the previous layout
        if merged and (end - start < min_segment_s or merged[-1][2] == state):
            merged[-1][1] = end
        else:
            merged.append([start, end, state])
    if len(merged) > 1 and merged[0][1] - merged[0][0] < min_segment_s:
        merged[1][0] = merged[0][0]
        merged.pop(0)
    return [{"start_s": round(a, 3), "end_s": round(b, 3), "layout": s[0], "people": list(s[1])} for a, b, s in merged]


def layout_plan(faces: list[tuple[float, float, float, float]], active: list[tuple[float, tuple[int, ...]]],
                duration_s: float, out_w: int, out_h: int, source_aspect: float, mode: str = "auto",
                min_segment_s: float = 1.5) -> list[dict]:
    """Segments with, for each, the panels: screen rect + source crop of the person shown there."""
    if not faces:
        raise ValueError("No faces: speaker layouts need visible people")
    out = []
    for segment in segments(active, duration_s, people=len(faces), min_segment_s=min_segment_s, mode=mode):
        shown = segment["people"] if segment["layout"] != "wide" else []
        rects = panels(len(shown) if segment["layout"] == "split" else 1, out_w, out_h)
        if segment["layout"] == "wide":
            panel_list = [{"person": None, "screen": rects[0], "crop": _group_crop(faces, out_w / out_h, source_aspect)}]
        else:
            panel_list = []
            for person, rect in zip(shown, rects):
                aspect = ((rect[2] - rect[0]) * out_w) / ((rect[3] - rect[1]) * out_h)
                panel_list.append({"person": person, "screen": rect, "crop": crop_for(faces[person], aspect, source_aspect)})
        out.append({**segment, "panels": panel_list})
    return out


def _group_crop(faces, out_aspect, source_aspect):
    """Crop with the output aspect that contains every face (centred on the group)."""
    x0, x1 = min(f[0] for f in faces), max(f[2] for f in faces)
    y0, y1 = min(f[1] for f in faces), max(f[3] for f in faces)
    w = min(1.0, max(x1 - x0 + 0.2, out_aspect / source_aspect * 0.5))
    h = min(1.0, w * source_aspect / out_aspect)
    if h >= 1.0:
        h, w = 1.0, min(1.0, out_aspect / source_aspect)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    left = min(max(cx - w / 2, 0.0), 1.0 - w)
    top = min(max(cy - h / 3, 0.0), 1.0 - h)
    return (round(left, 4), round(top, 4), round(left + w, 4), round(top + h, 4))


def cluster_people(face_samples: list[tuple[float, float, float, float]], gap: float = 0.12) -> list[tuple[float, float, float, float]]:
    """Group face boxes by horizontal position (people sit apart): median box per person, left to right."""
    if not face_samples:
        return []
    ordered = sorted(face_samples, key=lambda b: (b[0] + b[2]) / 2)
    groups, current = [], [ordered[0]]
    for box in ordered[1:]:
        if (box[0] + box[2]) / 2 - (current[-1][0] + current[-1][2]) / 2 > gap:
            groups.append(current)
            current = [box]
        else:
            current.append(box)
    groups.append(current)
    keep = [g for g in groups if len(g) >= max(2, math.ceil(len(face_samples) * 0.05))] or groups

    def med(values):
        values = sorted(values)
        return values[len(values) // 2]
    return [tuple(round(med([b[i] for b in g]), 4) for i in range(4)) for g in keep]
