"""Pure text placement: titles and captions must never cover a face or the subject of the shot."""

from __future__ import annotations

POSITIONS = ("top", "bottom", "middle")


def overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float], pad: float = 0.01) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (ax1 + pad < bx0 or bx1 + pad < ax0 or ay1 + pad < by0 or by1 + pad < ay0)


def choose(boxes: dict[str, tuple[float, float, float, float]], avoid: list[tuple[float, float, float, float]],
           preferred: str = "top") -> tuple[str, list[str]]:
    """Pick the first position (preferred first) whose text box avoids every face/subject box on screen.

    boxes: normalized text rectangle per position; avoid: normalized rectangles of faces/subject.
    Returns (position, conflicts of the preferred position)."""
    order = [preferred, *[p for p in POSITIONS if p != preferred]]
    conflicts = [f"{preferred} text covers a face/subject" for box in avoid if overlaps(boxes[preferred], box)][:1]
    for position in order:
        if position in boxes and not any(overlaps(boxes[position], box) for box in avoid):
            return position, conflicts
    return preferred, conflicts + ["no position is free: shorten the text or move it to a calmer shot"]
