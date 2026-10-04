"""Use case: rank the best moments of a source clip before cutting."""

from __future__ import annotations

from pathlib import Path

from .. import errors as E
from ..analysis import highlights, media
from ..gateway import Session
from .context import ForgeError, current
from .media_lookup import file_path, find_or_import


def find(session: Session, source: str, *, top: int = 6, window_s: float = 4.0) -> dict:
    try:
        import cv2  # noqa: F401
    except ImportError as exc:
        raise ForgeError("Highlight detection needs opencv.", code=E.MISSING_DEPENDENCY,
                         hint="cd mcp/resolve-forge && uv sync --extra vision") from exc
    # A file on disk is analysed without Resolve, like analyse_audio/analyse_music; pool names need Resolve.
    if Path(source).expanduser().is_file():
        path = str(Path(source).expanduser().resolve())
    else:
        ctx = current(session, need_timeline=False)
        path = file_path(find_or_import(ctx.media_pool, source))
    motion, _fps = highlights.motion_per_second(path)
    audio = media.loudness_per_second(media.load_audio(path)) if media.available() else None
    windows = highlights.rank(motion, audio, window_s=window_s, top=top)
    return {"source": path, "duration_s": len(motion), "audio_used": audio is not None,
            "highlights": [w.as_dict() for w in windows],
            "next": "assemble_timeline(source, cuts=[[start_s, end_s], ...]) with the windows you keep"}
