"""Pure rules for motivated sound effects: every cue needs a reason, density is reviewed, overlaps get lanes."""

from __future__ import annotations

import math


def cues(raw: list[dict], default_gain_db: float = -8.0) -> list[dict]:
    """Validated cues {time_s, source, reason, gain_db}, sorted by time (timeline seconds)."""
    if not isinstance(raw, list) or not 1 <= len(raw) <= 200:
        raise ValueError("cues needs 1-200 {time_s, source, reason} entries")
    out = []
    for cue in raw:
        if not isinstance(cue, dict):
            raise ValueError("Each cue must be an object")
        time_s, source, reason = cue.get("time_s"), cue.get("source"), cue.get("reason")
        gain = cue.get("gain_db", default_gain_db)
        if isinstance(time_s, bool) or not isinstance(time_s, (int, float)) or not math.isfinite(time_s) or time_s < 0:
            raise ValueError("cue time_s must be a finite, non-negative timeline second")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("cue source must name a sound file or media-pool clip")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Every sound effect needs an editorial reason (what on screen motivates it)")
        if isinstance(gain, bool) or not isinstance(gain, (int, float)) or not -40 <= gain <= 6:
            raise ValueError("gain_db must be between -40 and +6")
        out.append(dict(time_s=float(time_s), source=source.strip(), reason=reason.strip(), gain_db=float(gain)))
    return sorted(out, key=lambda c: c["time_s"])


def density_warnings(timed: list[dict], minimum_gap_s: float = .5, per_second: float = .5) -> list[str]:
    """Flags SFX that stack up: two within minimum_gap_s, or more than one every 1/per_second seconds."""
    warnings = []
    for a, b in zip(timed, timed[1:]):
        if b["time_s"] - a["time_s"] < minimum_gap_s:
            warnings.append(f"SFX at {a['time_s']:.2f}s and {b['time_s']:.2f}s are under {minimum_gap_s}s apart")
    if len(timed) >= 4:
        span = timed[-1]["time_s"] - timed[0]["time_s"]
        if span > 0 and len(timed) / span > per_second:
            warnings.append(f"{len(timed)} SFX in {span:.1f}s: more than one every {1 / per_second:.0f}s feels automatic")
    return warnings


def lanes(intervals: list[tuple[float, float]]) -> list[int]:
    """Greedy lane (0-based) per [start, end) so overlapping sounds never overwrite each other."""
    ends: list[float] = []
    out = []
    for start, end in intervals:
        for lane, busy_until in enumerate(ends):
            if busy_until <= start:
                ends[lane] = end
                out.append(lane)
                break
        else:
            ends.append(end)
            out.append(len(ends) - 1)
    return out
