"""Media ingest, metadata and bin organisation. No deletion or hidden relinking."""
from pathlib import Path

from .context import current
from .media_lookup import walk_media, find_existing
from .native import accepted, invoke, name


def folders(folder, prefix=""):
    path = f"{prefix}/{folder.GetName()}".strip("/")
    yield folder, path
    for child in folder.GetSubFolderList() or []:
        yield from folders(child, path)


def catalogue(session):
    ctx = current(session, need_timeline=False)
    return {"bins": [{"path": path, "clips": [{"name": clip.GetName(), "properties": invoke(clip, "GetClipProperty"),
                     "metadata": invoke(clip, "GetMetadata") if callable(getattr(clip, "GetMetadata", None)) else {}}
                    for clip in folder.GetClipList() or []]} for folder, path in folders(ctx.media_pool.GetRootFolder())]}


def bin_folder(pool, bin_name):
    root = pool.GetRootFolder()
    matching = [folder for folder in root.GetSubFolderList() or [] if folder.GetName() == bin_name]
    return matching[0] if matching else accepted(pool, "AddSubFolder", root, name(bin_name))


def ingest(session, paths, bin_name="Imported", dry_run=True):
    if not paths:
        raise ValueError("At least one media path is required.")
    resolved = list(dict.fromkeys(str(Path(path).expanduser().resolve()) for path in paths))
    if any(not Path(path).is_file() for path in resolved):
        raise ValueError("Every media path must be an existing file.")
    ctx = current(session, need_timeline=False)
    known = {str(Path(clip.GetClipProperty("File Path")).resolve()) for clip in walk_media(ctx.media_pool.GetRootFolder())
             if clip.GetClipProperty("File Path")}
    pending = [path for path in resolved if path not in known]
    if dry_run or not pending:
        return {"import": pending, "already_present": len(resolved) - len(pending), "applied": False}
    pool, previous = ctx.media_pool, ctx.media_pool.GetCurrentFolder()
    try:
        accepted(pool, "SetCurrentFolder", bin_folder(pool, bin_name))
        imported = accepted(pool, "ImportMedia", pending)
        imported_paths = {str(Path(clip.GetClipProperty("File Path")).resolve()) for clip in imported}
        missing = sorted(set(pending) - imported_paths)
        return {"imported": [{"name": clip.GetName(), "path": clip.GetClipProperty("File Path")} for clip in imported],
                "unresolved": missing, "complete": not missing, "applied": True}
    finally:
        accepted(pool, "SetCurrentFolder", previous)


def organise(session, by="extension", dry_run=True):
    if by not in {"extension", "directory"}:
        raise ValueError("Organise by extension or directory.")
    ctx = current(session, need_timeline=False)
    grouped, pending = {}, {}
    root = ctx.media_pool.GetRootFolder()
    for folder, location in folders(root):
        for clip in folder.GetClipList() or []:
            path = Path(clip.GetClipProperty("File Path") or "")
            group = (path.suffix.lstrip(".").upper() if by == "extension" else path.parent.name) or "Other"
            grouped.setdefault(group, []).append(clip)
            if location != f"{root.GetName()}/{group}":
                pending.setdefault(group, []).append(clip)
    if not dry_run:
        for group, clips in pending.items():
            accepted(ctx.media_pool, "MoveClips", clips, bin_folder(ctx.media_pool, group))
    return {"groups": {group: [clip.GetName() for clip in clips] for group, clips in grouped.items()},
            "moves": sum(map(len, pending.values())), "applied": not dry_run}


def metadata(session, source, values=None, dry_run=True):
    if values and any(not isinstance(key, str) or not isinstance(value, str) for key, value in values.items()):
        raise ValueError("Metadata keys and values must be strings.")
    ctx = current(session, need_timeline=False)
    # Metadata lookup never imports a file just to answer a read.
    clip = find_existing(ctx.media_pool, source)
    if clip is None:
        raise ValueError("Specify one existing media name or absolute path.")
    before = invoke(clip, "GetMetadata") or {}
    if values and not dry_run:
        accepted(clip, "SetMetadata", values)
        after = invoke(clip, "GetMetadata") or {}
        from .native import verify
        for key, value in values.items():
            verify(value, after.get(key), key)
    return {"source": source, "before": before, "requested": values or {}, "applied": bool(values) and not dry_run}
