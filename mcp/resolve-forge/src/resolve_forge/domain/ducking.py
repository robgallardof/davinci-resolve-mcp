"""Pure music-bed ducking: speech regions -> a piecewise-linear gain curve in dB. No audio here."""

from __future__ import annotations

import math

from .transcript import Word


def speech_regions(words: list[Word], merge_gap_s: float = .8) -> list[tuple[float, float]]:
    """Merge word spans separated by less than merge_gap_s: music should not pump between words."""
    regions: list[list[float]] = []
    for word in sorted(words, key=lambda w: w.start):
        if regions and word.start - regions[-1][1] < merge_gap_s:
            regions[-1][1] = max(regions[-1][1], word.end)
        else:
            regions.append([word.start, word.end])
    return [(a, b) for a, b in regions]


def gain_curve(regions: list[tuple[float, float]], duration_s: float, *, speech_db: float = -20.0, open_db: float = -10.0,
               attack_s: float = .25, release_s: float = .6, fade_in_s: float = .5, fade_out_s: float = 1.5) -> list[tuple[float, float]]:
    """[(time_s, gain_db)] breakpoints: down to speech_db before each region, back to open_db after it,
    plus a fade-in/out of the whole bed. Linear interpolation between points is the intended use."""
    for value, label in ((duration_s, "duration"), (attack_s, "attack"), (release_s, "release")):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{label} must be positive")
    if not (-60 <= speech_db <= 0 and -60 <= open_db <= 0) or speech_db > open_db:
        raise ValueError("Levels must be -60..0 dB with speech_db <= open_db")
    silent = -90.0
    merged: list[list[float]] = []
    for start, end in sorted(regions):
        start, end = max(0.0, start), min(duration_s, end)
        if end <= start:
            continue
        if merged and start - attack_s <= merged[-1][1] + release_s:  # ramps would collide: stay ducked
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    fade_in = min(fade_in_s, duration_s / 2)
    speech_first = bool(merged) and merged[0][0] - attack_s <= fade_in
    points = [(0.0, silent), (fade_in, speech_db if speech_first else open_db)]
    for index, (start, end) in enumerate(merged):
        if not (index == 0 and speech_first):
            points += [(start - attack_s, open_db), (start, speech_db)]
        points += [(max(fade_in, end), speech_db), (min(duration_s, max(fade_in, end) + release_s), open_db)]
    tail = max(points[-1][0], duration_s - fade_out_s)
    points += [(tail, points[-1][1]), (duration_s, silent)]
    clean: list[tuple[float, float]] = []
    for time_s, db in points:  # monotonic times; a repeated time is a step to the later value
        time_s = max(time_s, clean[-1][0]) if clean else time_s
        clean.append((round(time_s, 4), db))
    return clean
