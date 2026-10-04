"""Pure beat-aligned cut slots for music edits. Phrases, not every beat; faster only where energy is confirmed."""

from __future__ import annotations

import math


def _finite(value, label, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{label} must be >= {minimum}")
    return float(value)


def slots(beats_s: list[float], start_s: float, duration_s: float, *, beats_per_cut: int = 4,
          intense: list[list[float]] | None = None, intense_beats_per_cut: int | None = None,
          min_slot_s: float = .35) -> list[list[float]]:
    """Cut points on the beat grid: [[start, end], ...] in MUSIC seconds, starting at the beat nearest start_s.

    intense: confirmed high-energy ranges (e.g. a drop the agent listened to) where cuts happen every
    intense_beats_per_cut beats (default half of beats_per_cut). Elsewhere the phrase length is kept.
    """
    _finite(start_s, "start_s", 0)
    _finite(duration_s, "duration_s", .1)
    if not isinstance(beats_per_cut, int) or isinstance(beats_per_cut, bool) or not 1 <= beats_per_cut <= 64:
        raise ValueError("beats_per_cut must be an integer from 1 to 64")
    fast = intense_beats_per_cut or max(1, beats_per_cut // 2)
    if not isinstance(fast, int) or not 1 <= fast <= beats_per_cut:
        raise ValueError("intense_beats_per_cut must be an integer from 1 to beats_per_cut")
    grid = sorted(_finite(b, "beat", 0) for b in beats_s)
    if len(grid) < 2:
        raise ValueError("At least two beats are required; analyse_music returned no reliable grid")
    ranges = []
    for pair in intense or []:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("intense ranges are [start_s, end_s] pairs")
        a, b = _finite(pair[0], "intense start", 0), _finite(pair[1], "intense end", 0)
        if b <= a:
            raise ValueError("intense ranges need end > start")
        ranges.append((a, b))
    index = min(range(len(grid)), key=lambda i: abs(grid[i] - start_s))
    end_s = grid[index] + duration_s  # duration counts from the snapped first beat
    result = []
    while index < len(grid) - 1 and grid[index] < end_s - 1e-6:
        here = grid[index]
        step = fast if any(a <= here < b for a, b in ranges) else beats_per_cut
        nxt = min(index + step, len(grid) - 1)
        stop = min(grid[nxt], end_s)
        if stop - here >= min_slot_s:
            result.append([round(here, 3), round(stop, 3)])
        elif result:
            result[-1][1] = round(stop, 3)
        index = nxt
    if not result:
        raise ValueError("The requested range holds no complete cut; extend duration_s or lower beats_per_cut")
    return result


def fill(shots: list[dict], music_slots: list[list[float]]) -> list[dict]:
    """Give each slot the next reviewed shot long enough for it, in order, cycling through the list.

    shots: {source, start_s, end_s} usable source ranges. A reused shot continues from its unused footage
    (back to its in-point once exhausted). Shots are trimmed, never stretched, so the music stays on the grid.
    """
    if not shots or len(shots) > 1000:
        raise ValueError("Provide 1-1000 reviewed shots")
    ranges = []
    for shot in shots:
        if not isinstance(shot, dict) or not {"source", "start_s", "end_s"} <= shot.keys():
            raise ValueError("Each shot must contain source/start_s/end_s")
        start, end = _finite(shot["start_s"], "shot start", 0), _finite(shot["end_s"], "shot end", 0)
        if end <= start:
            raise ValueError("Each shot needs end_s > start_s")
        ranges.append((shot["source"], start, end))
    cursor, used, out = 0, [r[1] for r in ranges], []
    for a, b in music_slots:
        need = b - a
        for attempt in range(len(ranges)):
            index = (cursor + attempt) % len(ranges)
            source, start, end = ranges[index]
            if end - start + 1e-6 < need:
                continue
            if end - used[index] + 1e-6 < need:
                used[index] = start
            out.append(dict(source=source, start_s=round(used[index], 3), end_s=round(used[index] + need, 3), music_s=[a, b]))
            used[index] += need
            cursor = index + 1
            break
        else:
            raise ValueError(f"No shot is long enough for the {need:.2f}s slot at {a:.2f}s; add longer shots or lower beats_per_cut")
    return out
