"""Pure picture-quality assessment and a gentle CDL suggestion (exposure, contrast, saturation, cast).

Inputs are frame statistics in 0..1. The suggestion is conservative on purpose: phone footage should look
clean and natural, not 'graded'. Apply it with grade_clips (on a copy) and check the frames again.
"""

from __future__ import annotations

from statistics import median


def assess(stats: list[dict]) -> dict:
    """stats: [{luma, p2, p98, saturation, r, g, b}] per sampled frame -> {issues, cdl|None, summary}."""
    if not stats:
        return {"issues": [], "cdl": None, "summary": {}}
    m = {key: float(median(s[key] for s in stats)) for key in ("luma", "p2", "p98", "saturation", "r", "g", "b")}
    issues, slope, offset, saturation = [], 1.0, 0.0, 1.0
    if m["luma"] < 0.33 or m["p98"] < 0.72:
        slope = min(1.35, 0.85 / max(m["p98"], 0.3))
        issues.append(f"underexposed (median luma {m['luma']:.2f}, highlights {m['p98']:.2f})")
    elif m["p98"] > 0.985 and m["luma"] > 0.62:
        slope = 0.93
        issues.append(f"bright/clipping (median luma {m['luma']:.2f})")
    if m["p98"] - m["p2"] < 0.6:
        slope *= 1.08
        offset = -0.025
        issues.append(f"flat contrast (range {m['p98'] - m['p2']:.2f})")
    elif m["p2"] > 0.12:
        offset = -min(0.06, m["p2"] - 0.06)
        issues.append(f"lifted blacks ({m['p2']:.2f})")
    if m["saturation"] < 0.16:
        saturation = 1.15
        issues.append(f"dull colour (saturation {m['saturation']:.2f})")
    elif m["saturation"] > 0.62:
        saturation = 0.9
        issues.append(f"oversaturated ({m['saturation']:.2f})")
    grey = (m["r"] + m["g"] + m["b"]) / 3
    cast = [round(grey - m[c], 3) for c in ("r", "g", "b")]
    channel_offsets = [0.0, 0.0, 0.0]
    if max(abs(c) for c in cast) > 0.05:
        channel_offsets = [max(-0.04, min(0.04, c * 0.5)) for c in cast]
        names = {0: "red", 1: "green", 2: "blue"}
        strongest = max(range(3), key=lambda i: abs(cast[i]))
        issues.append(f"colour cast ({'too much' if cast[strongest] < 0 else 'too little'} {names[strongest]})")
    slope = min(1.4, max(0.85, slope))  # stacked fixes stay gentle: natural phone footage, not a 'grade'
    cdl = None
    if issues:
        cdl = {"slope": [round(slope, 3)] * 3,
               "offset": [round(offset + o, 3) for o in channel_offsets],
               "power": [1.0, 1.0, 1.0], "saturation": round(saturation, 3)}
    return {"issues": issues, "cdl": cdl, "summary": {k: round(v, 3) for k, v in m.items()}}
