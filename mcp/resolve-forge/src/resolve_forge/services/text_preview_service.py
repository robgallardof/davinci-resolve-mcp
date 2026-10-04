"""Reviewable text art direction without a Resolve connection or a transcription model."""

from __future__ import annotations

import secrets

from ..domain.formats import safe_for
from ..domain.text_design import DESIGNS, accent_rgba, motion_state, resolve_animation, resolve_style
from ..graphics import cards
from ..graphics.text_animation import animate
from .render_service import DEFAULT_OUTPUT


def preview(text: str, *, style: str = "auto", width: int = 1080, height: int = 1920,
            position: str = "bottom", animation: str = "auto", accent: str | None = None,
            emphasis_words: list[str] | None = None, reduced_motion: bool = False) -> dict:
    from PIL import Image, ImageDraw

    if not 320 <= width <= 3840 or not 320 <= height <= 3840:
        raise ValueError("Preview width and height must be between 320 and 3840")
    if len(text) > 160:
        raise ValueError("Preview text must have at most 160 characters; use a short caption or title")
    style = resolve_style(style, width, height)
    animation = resolve_animation(animation, style, reduced_motion)
    accent_rgba(accent, style)
    safe = safe_for(width, height)
    tokens = text.split()
    highlight = animation == "karaoke" or style in DESIGNS and DESIGNS[style].highlight
    base = cards.render(text, width, height, style=style, position=position, safe=safe,
                        active_word=0 if highlight else None, accent=accent,
                        emphasis_words=emphasis_words, max_lines=2 if style in DESIGNS else None)
    output = DEFAULT_OUTPUT / "text-previews" / secrets.token_hex(6)
    output.mkdir(parents=True, exist_ok=False)
    poster = output / "text.png"
    base.save(poster)
    # Half-resolution animated preview: sample timing is illustrative, not a transcript.
    scale = min(1.0, 540 / width, 960 / height)
    preview_size = (round(width * scale), round(height * scale))
    frames = []
    count, fps = 36, 18
    cache = {}
    for frame in range(count):
        active = min(len(tokens) - 1, frame * len(tokens) // count) if highlight else None
        progress = (frame * len(tokens) % count) / count if animation == "karaoke" else None
        key = active, progress
        if key not in cache:
            cache[key] = cards.render(text, width, height, style=style, position=position, safe=safe,
                                        active_word=active, accent=accent, emphasis_words=emphasis_words,
                                        active_progress=progress,
                                        max_lines=2 if style in DESIGNS else None)
        rgba = animate(cache[key], animation, frame, count, fps, safe)
        rgba = rgba.resize(preview_size, Image.Resampling.LANCZOS)
        background = Image.new("RGB", preview_size, (34, 39, 50))
        background.paste(rgba, mask=rgba.getchannel("A"))
        frames.append(background)
    animated = output / "animation.webp"
    frames[0].save(animated, save_all=True, append_images=frames[1:], duration=round(1000 / fps), loop=0, lossless=True)
    sheet = Image.new("RGB", (preview_size[0] * 3, preview_size[1] + 44), (16, 20, 28))
    draw = ImageDraw.Draw(sheet)
    for index, frame in enumerate((0, count // 2, count - 1)):
        sheet.paste(frames[frame], (index * preview_size[0], 44))
        draw.text((index * preview_size[0] + 16, 14), f"{style} / {frame / fps:.2f}s", fill="white")
    contact = output / "contact-sheet.jpg"
    sheet.save(contact, quality=94)
    return {"style": style, "animation": animation, "resolution": f"{width}x{height}",
            "poster": str(poster), "animated_preview": str(animated), "contact_sheet": str(contact),
            "safe_zone": safe.rect(width, height), "timing": "Illustrative two-second sample; final captions use spoken word timestamps.",
            "motion": motion_state(animation, 0, count, fps), "reduced_motion": reduced_motion}
