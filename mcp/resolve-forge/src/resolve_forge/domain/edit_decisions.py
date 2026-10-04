"""Pure temporal decisions for silence cuts and music emphasis; no media I/O."""
import math
from statistics import median


def silence_ranges(levels, step_s, threshold_db=-40, minimum_s=.5):
    if step_s <= 0 or minimum_s <= 0 or not math.isfinite(threshold_db):
        raise ValueError("Invalid silence-analysis parameters.")
    result, start = [], None
    for index, level in enumerate([*levels, float("inf")]):
        if level <= threshold_db and start is None:
            start = index
        if level > threshold_db and start is not None:
            if (index - start) * step_s >= minimum_s:
                result.append([round(start * step_s, 6), round(index * step_s, 6)])
            start = None
    return result


def keep_ranges(duration_s, removed, padding_s=.15):
    if duration_s <= 0 or not math.isfinite(duration_s) or padding_s < 0:
        raise ValueError("Invalid duration or padding.")
    cuts = sorted((max(0, a + padding_s), min(duration_s, b - padding_s)) for a, b in removed if b > a)
    merged = []
    for a, b in cuts:
        if b <= a:
            continue
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    result, cursor = [], 0
    for a, b in merged:
        if a > cursor:
            result.append([cursor, a])
        cursor = b
    if cursor < duration_s:
        result.append([cursor, duration_s])
    return result


def onset_hits(levels, step_s, minimum_gap_s=.2):
    """Energy-onset candidates, explicitly not a music beat/downbeat model."""
    if step_s <= 0 or minimum_gap_s <= 0 or not levels:
        raise ValueError("Invalid onset-analysis parameters.")
    differences = [max(0, levels[index] - levels[index - 1]) for index in range(1, len(levels))]
    threshold = max(3.0, min(12.0, median(differences) * 1.5)) if differences else 3
    hits = []
    for index, difference in enumerate(differences, 1):
        at = index * step_s
        if difference >= threshold and (not hits or at - hits[-1] >= minimum_gap_s):
            hits.append(round(at, 6))
    return hits
