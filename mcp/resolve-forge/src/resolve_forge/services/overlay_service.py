"""Use case: put text on screen (titles or burned-in captions) with frame-exact timing, on Free too.

Why PNG sequences: Resolve's API cannot trim a title or a still (stills always last the default
5 s and ignore endFrame). A card written as an N-frame image sequence imports as ONE clip of
exactly N frames with alpha. Frames are hard links to a single PNG, so a long caption track
costs almost no disk.
"""

from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

from .. import errors as E
from ..domain import formats
from ..domain.transcript import Span
from ..gateway import Session, call
from .context import Context, ForgeError, current
from .render_service import DEFAULT_OUTPUT

OVERLAY_ROOT = DEFAULT_OUTPUT / "overlays"  # under ~/Movies: readable by the Free bridge
POOL_FOLDER = "forge-overlays"


def _letters(n: int) -> str:
    """0 -> 'aa', 1 -> 'ab' ... Folder names must not end in digits or Resolve merges sequences."""
    a, b = divmod(n, 26)
    return "abcdefghijklmnopqrstuvwxyz"[a % 26] + "abcdefghijklmnopqrstuvwxyz"[b]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z]+", "", text.lower())[:12] or "tl"


def write_sequence(image, folder: Path, frames: int) -> Path:
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    first = folder / f"{folder.name}_0000.png"
    image.save(first)
    for n in range(1, max(2, frames)):  # >= 2 frames, or Resolve imports a 5 s still
        dst = folder / f"{folder.name}_{n:04d}.png"
        try:
            os.link(first, dst)
        except OSError:
            shutil.copyfile(first, dst)
    return folder


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


def place_cards(session: Session, cards: list[Span], *, style: str = "box", position: str = "top",
                track: int | None = None, label: str = "text") -> dict:
    from ..graphics import cards as gfx  # Pillow only when needed

    if not cards:
        return {"placed": 0, "track": None}
    ctx = current(session)
    width, height = ctx.width, ctx.height
    safe = formats.safe_for(width, height)
    run = OVERLAY_ROOT / f"{_slug(ctx.timeline.GetName())}_{label}_{int(time.time())}"
    pool = ctx.media_pool
    previous = call(pool, "GetCurrentFolder", default=None)
    folder = _pool_folder(pool)
    call(pool, "SetCurrentFolder", folder)
    try:
        clips = []
        for i, card in enumerate(cards):
            # frame math on absolute positions: back-to-back cards never overlap by a rounding frame
            frames = max(2, ctx.seconds_to_frame(card.end) - ctx.seconds_to_frame(card.start))
            image = gfx.render(card.text, width, height, style=style, position=position, safe=safe)
            seq = write_sequence(image, run / f"{label}{_letters(i)}", frames)
            imported = pool.ImportMedia([str(seq)]) or []
            if len(imported) != 1:
                raise ForgeError(f"Resolve imported {len(imported)} clips for card {i + 1}.", code=E.RESOLVE_REFUSED,
                                 hint="On Free the bridge only reads inside your user profile.")
            clips.append((imported[0], card))
    finally:
        if previous is not None:
            call(pool, "SetCurrentFolder", previous)
    index = _target_track(ctx, track)
    infos = [{"mediaPoolItem": clip, "startFrame": 0, "endFrame": int(clip.GetClipProperty("Frames")),
              "recordFrame": ctx.seconds_to_frame(card.start), "trackIndex": index, "mediaType": 1}
             for clip, card in clips]
    placed = pool.AppendToTimeline(infos) or []
    return {"placed": len(placed), "requested": len(cards), "track": index, "style": style,
            "position": position, "files": str(run), "safe_zone": safe.rect(width, height)}
