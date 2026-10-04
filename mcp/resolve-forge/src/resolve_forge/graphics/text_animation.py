"""Animation of already-typeset RGBA text. Layout stays fixed across spoken words."""

from __future__ import annotations

from ..domain.formats import SafeZone
from ..domain.text_design import motion_state


def animate(image, animation: str, frame: int, frames: int, fps: float, safe: SafeZone):
    from PIL import Image

    opacity, scale, offset = motion_state(animation, frame, frames, fps)
    if (opacity, scale, offset) == (1.0, 1.0, 0.0):
        return image
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return image
    x0, y0, x1, y1 = bbox
    tile = image.crop(bbox)
    if scale != 1:
        tile = tile.resize((max(1, round(tile.width * scale)), max(1, round(tile.height * scale))), Image.Resampling.LANCZOS)
    if opacity != 1:
        tile.putalpha(tile.getchannel("A").point(lambda value: round(value * opacity)))
    bounds = safe.rect(*image.size)
    x = round((x0 + x1 - tile.width) / 2)
    y = round((y0 + y1 - tile.height) / 2 + offset * min(image.size))
    x = max(bounds["x"], min(x, bounds["x"] + bounds["width"] - tile.width))
    y = max(bounds["y"], min(y, bounds["y"] + bounds["height"] - tile.height))
    out = Image.new("RGBA", image.size)
    out.alpha_composite(tile, (x, y))
    return out
