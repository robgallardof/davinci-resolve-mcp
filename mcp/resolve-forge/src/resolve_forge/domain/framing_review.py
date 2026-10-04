"""Pure self-review of a framed shot: is the zoom motivated, well placed and sharp enough?

A zoom with pivot p and factor z shows source coordinates [p - p/z, p + (1 - p)/z] on each axis, and puts a
source point s on screen at p + z (s - p). With that, every shot can be checked before anything is built:
the subject must stay on screen and near the centre, the action must not be cropped out, faces must not be
cut, and the zoom must not upscale a small source into mush. Failing shots are downgraded, never forced.
"""

from __future__ import annotations

DOWNGRADE = {"crash": "medium", "close": "medium", "medium": "wide", "wide": "wide"}
SCREEN_SAFE = (0.12, 0.88, 0.12, 0.85)  # x0, x1, y0, y1: where a subject reads (UI and edges excluded)


def visible(zoom: float, pivot: tuple[float, float]) -> tuple[float, float, float, float]:
    """Source rectangle (x0, y0, x1, y1) that remains on screen."""
    px, py = pivot
    return (px - px / zoom, py - py / zoom, px + (1 - px) / zoom, py + (1 - py) / zoom)


def on_screen(point: tuple[float, float], zoom: float, pivot: tuple[float, float]) -> tuple[float, float]:
    return (pivot[0] + zoom * (point[0] - pivot[0]), pivot[1] + zoom * (point[1] - pivot[1]))


def issues(shot: dict, action: list[tuple[float, float, float]], faces: list[tuple[float, float]],
           upscale: float = 1.0, max_upscale: float = 2.6, min_coverage: float = 0.6) -> list[str]:
    """Problems of one framed shot. action: (x, y, energy) samples inside the shot; faces: (x, y)."""
    zoom = float(shot["zoom"])
    found = []
    if zoom <= 1.0001:
        return found
    pivot = tuple(shot["anchor"])
    x0, y0, x1, y1 = visible(zoom, pivot)
    sx, sy = on_screen(tuple(shot["subject"]), zoom, pivot)
    sx0, sx1, sy0, sy1 = SCREEN_SAFE
    if not (sx0 <= sx <= sx1 and sy0 <= sy <= sy1):
        found.append(f"subject ends up at the edge ({sx:.2f}, {sy:.2f})")
    total = sum(e for _, _, e in action)
    if total > 0:
        inside = sum(e for x, y, e in action if x0 <= x <= x1 and y0 <= y <= y1)
        if inside / total < min_coverage:
            found.append(f"crops out the action ({inside / total:.0%} of the movement visible)")
    if any(not (x0 <= fx <= x1 and y0 <= fy <= y1) for fx, fy in faces):
        found.append("cuts a face out of frame")
    if upscale * zoom > max_upscale:
        found.append(f"too soft: source upscaled x{upscale * zoom:.2f}")
    return found


def max_zoom_for(upscale: float, max_upscale: float = 2.6) -> float:
    """Largest zoom that keeps the effective upscale acceptable (never below 1)."""
    return max(1.0, max_upscale / max(upscale, 1e-6))
