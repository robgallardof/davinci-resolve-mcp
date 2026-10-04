"""Find a media-pool clip by name or file path (importing the file when it is not in the pool)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from .. import errors as E
from ..gateway import call
from .context import ForgeError


def _walk(folder: Any) -> Iterator[Any]:
    yield from (folder.GetClipList() or [])
    for sub in call(folder, "GetSubFolderList", default=[]) or []:
        yield from _walk(sub)


def find_or_import(pool: Any, source: str) -> Any:
    target = Path(source)
    for clip in _walk(pool.GetRootFolder()):
        if clip.GetName() == source or clip.GetName() == target.name:
            return clip
        path = call(clip, "GetClipProperty", "File Path", default="")
        if path and Path(path) == target:
            return clip
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
