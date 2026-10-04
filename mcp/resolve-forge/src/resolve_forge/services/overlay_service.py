"""Use case: put text on screen (titles or burned-in captions) with frame-exact timing, on Free too.

Why PNG sequences: Resolve's API cannot trim a title or a still (stills always last the default
5 s and ignore endFrame). A card written as an N-frame image sequence imports as ONE clip of
exactly N frames with alpha. Frames are hard links to a single PNG, so a long caption track
costs almost no disk.
"""

from __future__ import annotations

import re
import secrets
from pathlib import Path

from .. import errors as E
from ..domain import formats
from ..domain.transcript import Span
from ..domain.text_design import DESIGNS, CaptionCue, accent_rgba, resolve_animation, resolve_style
from ..gateway import Session, call
from .context import Context, ForgeError, current
from .render_service import DEFAULT_OUTPUT
from .native import number, working_copy

OVERLAY_ROOT = DEFAULT_OUTPUT / "overlays"  # under ~/Movies: readable by the Free bridge
POOL_FOLDER = "forge-overlays"


def _conform_rate(clip, fps):
    """Image sequences import at the PROJECT rate; a 30 fps timeline in a 24 fps project would stretch
    every card 1.25x and slow its animation. Set the sequence to the timeline rate (readback-checked)."""
    call(clip, "SetClipProperty", "FPS", f"{fps:g}")
    return clip


def _source_frames(clip, frames, fps):
    """Frames of the sequence that fill `frames` timeline frames, if Resolve kept another clip rate."""
    clip_fps = float(call(clip, "GetClipProperty", "FPS", default=0) or fps)
    return max(1, round(frames * clip_fps / fps)) if abs(clip_fps - fps) > 1e-3 else frames


def _letters(n: int) -> str:
    """0 -> 'aa', 1 -> 'ab' ... Folder names must not end in digits or Resolve merges sequences."""
    result = ""
    while True:
        n, digit = divmod(n, 26)
        result = chr(97 + digit) + result
        if n == 0:
            return result.rjust(2, "a") if len(result) == 1 else "a" + result


def _slug(text: str) -> str:
    return re.sub(r"[^a-z]+", "", text.lower())[:12] or "tl"


def write_sequence(image, folder: Path, frames: int) -> Path:
    from ..graphics.sequences import write_frames
    return write_frames(folder, frames, lambda _: None, lambda _: image)


def _target_track(ctx: Context, track: int | None) -> int:
    if track:
        while int(ctx.timeline.GetTrackCount("video")) < track:
            ctx.timeline.AddTrack("video")
        return track
    ctx.timeline.AddTrack("video")  # a fresh top track: never collides with existing clips
    return int(ctx.timeline.GetTrackCount("video"))


def _pool_folder(pool):
    root = pool.GetRootFolder()
    for sub in call(root, "GetSubFolderList", default=[]) or []:
        if sub.GetName() == POOL_FOLDER:
            return sub
    return call(pool, "AddSubFolder", root, POOL_FOLDER, default=None) or root


def place_cards(session: Session, cards: list[Span | CaptionCue], *, style: str = "box", position: str = "top",
                track: int | None = None, label: str = "text", animation: str = "auto",
                accent: str | None = None, emphasis_words: list[str] | None = None,
                reduced_motion: bool = False) -> dict:
    from ..graphics import cards as gfx  # Pillow only when needed
    from ..graphics.sequences import write_frames
    from ..graphics.text_animation import animate

    if not cards:
        return {"placed": 0, "track": None}
    for card in cards:
        number(card.start, "card start", 0)
        number(card.end, "card end", card.start)
        if card.end <= card.start:
            raise ValueError("Cards need a positive duration.")
    ctx = current(session)
    width, height = ctx.width, ctx.height
    style = resolve_style(style, width, height)
    animation = resolve_animation(animation, style, reduced_motion)
    accent_rgba(accent, style)
    safe = formats.safe_for(width, height)
    # Validate every card before importing media or creating tracks.
    for card in cards:
        gfx.render(card.text, width, height, style=style, position=position, safe=safe,
                   accent=accent, emphasis_words=emphasis_words, max_lines=2 if style in DESIGNS else None)
    run = OVERLAY_ROOT / f"{_slug(ctx.timeline.GetName())}_{label}_{secrets.token_hex(6)}"
    pool = ctx.media_pool
    previous = call(pool, "GetCurrentFolder", default=None)
    folder = _pool_folder(pool)
    call(pool, "SetCurrentFolder", folder)
    try:
        clips = []
        for i, card in enumerate(cards):
            # frame math on absolute positions: back-to-back cards never overlap by a rounding frame
            frames = max(1, ctx.seconds_to_frame(card.end) - ctx.seconds_to_frame(card.start))
            highlight = style in DESIGNS and DESIGNS[style].highlight and isinstance(card, CaptionCue)
            ramp = max(1, min(round(ctx.fps * 0.18), frames - 1))

            def state_at(frame):
                # Frame samples are aligned to the rounded recordFrame, not the unrounded word start.
                seconds = (ctx.seconds_to_frame(card.start) - ctx.start_frame + frame) / ctx.fps
                active = card.active_at(seconds) if highlight else None
                return active, min(frame, ramp) if animation != "none" else 0

            base_images = {}

            def render_state(state):
                active, frame = state
                if active not in base_images:
                    base_images[active] = gfx.render(card.text, width, height, style=style, position=position,
                                                    safe=safe, active_word=active, accent=accent,
                                                    emphasis_words=emphasis_words,
                                                    max_lines=2 if style in DESIGNS else None)
                return animate(base_images[active], animation, frame, frames, ctx.fps, safe)

            seq = write_frames(run / f"{label}{_letters(i)}", frames, state_at, render_state)
            imported = pool.ImportMedia([str(seq)]) or []
            if len(imported) != 1:
                raise ForgeError(f"Resolve imported {len(imported)} clips for card {i + 1}.", code=E.RESOLVE_REFUSED,
                                 hint="On Free the bridge only reads inside your user profile.")
            clips.append((_conform_rate(imported[0], ctx.fps), card, frames))
    finally:
        if previous is not None:
            call(pool, "SetCurrentFolder", previous)
    ctx = working_copy(session, "text")
    index = _target_track(ctx, track)
    infos = [{"mediaPoolItem": clip, "startFrame": 0, "endFrame": _source_frames(clip, frames, ctx.fps),
              "recordFrame": ctx.seconds_to_frame(card.start), "trackIndex": index, "mediaType": 1}
             for clip, card, frames in clips]
    placed = pool.AppendToTimeline(infos) or []
    if len(placed) != len(cards):
        raise ForgeError(f"Resolve placed {len(placed)} of {len(cards)} cards.", code=E.RESOLVE_REFUSED,
                         hint="Inspect the working timeline; a partial insertion may exist.")
    return {"placed": len(placed), "requested": len(cards), "track": index, "style": style,
            "animation": animation, "reduced_motion": reduced_motion, "accent": accent or (DESIGNS[style].accent if style in DESIGNS else None),
            "position": position, "files": str(run), "safe_zone": safe.rect(width, height)}
