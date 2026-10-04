"""Gentle display-referred creative CDL looks, never log/HDR input transforms."""
from math import isfinite

PRESETS = {
    "natural": {"slope": [1.02, 1.02, 1.02], "offset": [-.005] * 3, "power": [1.] * 3, "saturation": 1.03},
    "warm": {"slope": [1.035, 1.01, .99], "offset": [.004, 0., -.004], "power": [1.] * 3, "saturation": 1.04},
    "crisp": {"slope": [1.06] * 3, "offset": [-.02] * 3, "power": [1.02] * 3, "saturation": 1.05},
    "muted": {"slope": [1.] * 3, "offset": [.006] * 3, "power": [1.] * 3, "saturation": .90},
}


def parameters(preset: str, intensity: float = .5) -> dict:
    if preset not in PRESETS:
        raise ValueError(f"Unknown grade preset; choose {', '.join(PRESETS)}.")
    if isinstance(intensity, bool) or not isinstance(intensity, (int, float)) or not isfinite(intensity) or not 0 <= intensity <= 1:
        raise ValueError("intensity must be a finite number in 0..1.")
    look = PRESETS[preset]
    return {key: [round(identity + intensity * (value - identity), 6) for value in look[key]]
            for key, identity in (("slope", 1.), ("offset", 0.), ("power", 1.))} | {
                "saturation": round(1. + intensity * (look["saturation"] - 1.), 6)}
