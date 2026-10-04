"""Audio-reactive graphics with bounded, smooth motion and a coherent typography palette."""

from __future__ import annotations

import math

from ..domain.formats import safe_for
from .cards import render


def background(width, height, title, artist, accent):
    import numpy as np
    from PIL import Image, ImageDraw

    x, y = np.meshgrid(np.linspace(0, 1, width), np.linspace(0, 1, height))
    glow = np.exp(-((x - .35) ** 2 + (y - .38) ** 2) / .12)
    pixels = np.stack([15 + glow * 20, 18 + glow * 16, 28 + glow * 30], axis=2).astype("uint8")
    image = Image.fromarray(pixels).convert("RGBA")
    draw = ImageDraw.Draw(image)
    safe = safe_for(width, height)
    rect = safe.rect(width, height)
    draw.line((rect["x"], rect["y"], rect["x"] + rect["width"] * .14, rect["y"]), fill=accent, width=max(2, width // 180))
    if title:
        image.alpha_composite(render(title, width, height, style="creator", position="top", safe=safe,
                                     max_lines=2, emphasis_words=[title], accent="#%02X%02X%02X" % accent[:3]))
    if artist:
        image.alpha_composite(render(artist, width, height, style="studio", position="bottom", safe=safe, max_lines=2))
    return image


def frame(base, bands, energy, theme, accent):
    from PIL import ImageDraw

    image = base.copy()
    draw = ImageDraw.Draw(image)
    width, height = image.size
    rect = safe_for(width, height).rect(width, height)
    center = (rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] * .5)
    maximum = min(rect["height"] * .19, rect["width"] * .25)
    if theme == "spectrum":
        pitch = rect["width"] * .84 / len(bands)
        left = center[0] - pitch * len(bands) / 2
        for index, level in enumerate(bands):
            amplitude = maximum * (.03 + .97 * float(level))
            x = left + index * pitch
            draw.rounded_rectangle((x, center[1] - amplitude, x + pitch * .60, center[1] + amplitude),
                                   radius=max(1, pitch * .3), fill=accent)
        draw.line((left, center[1], left + pitch * len(bands), center[1]), fill=(*accent[:3], 150), width=1)
    else:
        radius = min(rect["width"], rect["height"]) * (.19 + .035 * energy)
        for index in range(3):
            r = radius + index * min(width, height) * .026
            color = tuple(round(value * (1 - index * .16)) for value in accent[:3]) + (255,)
            draw.ellipse((center[0] - r, center[1] - r, center[0] + r, center[1] + r),
                         outline=color, width=max(1, round(width * .003)))
        for index, level in enumerate(bands):
            angle = index / len(bands) * 2 * math.pi
            start = radius + min(width, height) * .07
            end = start + float(level) * min(width, height) * .035
            draw.line((center[0] + math.cos(angle) * start, center[1] + math.sin(angle) * start,
                       center[0] + math.cos(angle) * end, center[1] + math.sin(angle) * end), fill=accent,
                      width=max(1, round(width * .003)))
    return image.convert("RGB")
