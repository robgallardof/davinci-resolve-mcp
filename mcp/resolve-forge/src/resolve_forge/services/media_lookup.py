"""Find a media-pool clip by name or file path (importing the file when it is not in the pool)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from .. import errors as E
from ..gateway import call
from .context import ForgeError


def walk_media(folder: Any) -> Iterator[Any]:
    yield from (folder.GetClipList() or [])
    for sub in call(folder, "GetSubFolderList", default=[]) or []:
        yield from walk_media(sub)


def find_existing(pool: Any, source: str) -> Any | None:
    """Exact path for path inputs, exact name otherwise; ambiguity is never guessed."""
    target = Path(source).expanduser()
    explicit_path = target.is_absolute() or "/" in source or "\\" in source
    candidates = []
    for clip in walk_media(pool.GetRootFolder()):
        path = call(clip, "GetClipProperty", "File Path", default="")
        matches = bool(path) and Path(path).resolve() == target.resolve() if explicit_path else clip.GetName() == source
        if matches:
            candidates.append(clip)
    if len(candidates) > 1:
        raise ForgeError(f"Media source '{source}' is ambiguous.", code="AMBIGUOUS_SOURCE",
                         hint="Use a unique absolute source path.")
    return candidates[0] if candidates else None


def find_or_import(pool: Any, source: str) -> Any:
    target = Path(source)
    existing = find_existing(pool, source)
    if existing is not None:
        return existing
    if target.is_file():
        imported = pool.ImportMedia([str(target)]) or []
        if imported:
            return imported[0]
        raise ForgeError(f"Resolve refused to import {target}.", code=E.RESOLVE_REFUSED,
                         hint="On Free the bridge only reads media inside your user profile.")
    raise ForgeError(f"No media-pool clip or file called '{source}'.", code=E.MEDIA_NOT_FOUND,
                     hint="Pass the clip's name as shown in the Media Pool, or an absolute file path.")


def file_path(clip: Any) -> str:
    path = call(clip, "GetClipProperty", "File Path", default="")
    if not path:
        raise ForgeError(f"'{clip.GetName()}' has no file on disk (generator/compound?).", code=E.MEDIA_NOT_FOUND)
    return path
