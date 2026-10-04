"""Validated CDL/LUT grading on timeline copies and gallery still workflows."""
from pathlib import Path

from .context import current, video_items
from .native import accepted, fork, invoke, number, selected


def grade(session, slope=None, offset=None, power=None, saturation=1.0, lut_path=None, node=1,
          track=1, indices=None, copy_name=None, dry_run=True):
    if type(node) is not int or node < 1:
        raise ValueError("Color nodes use 1-based indices.")
    def triple(values, default, label, low=None):
        values = default if values is None else values
        if len(values) != 3:
            raise ValueError(f"{label} needs exactly three channels.")
        return [number(value, label, low) for value in values]
    cdl = {"NodeIndex": str(node), "Slope": " ".join(map(str, triple(slope, [1, 1, 1], "slope", 0))),
           "Offset": " ".join(map(str, triple(offset, [0, 0, 0], "offset"))),
           "Power": " ".join(map(str, triple(power, [1, 1, 1], "power", .000001))),
           "Saturation": str(number(saturation, "saturation", 0))}
    lut = None
    if lut_path:
        lut = Path(lut_path).expanduser().resolve()
        if not lut.is_file() or lut.suffix.lower() not in {".cube", ".3dl"}:
            raise ValueError("LUT must be an existing .cube or .3dl file.")
    ctx, items = selected(session, track, indices)
    if dry_run:
        return {"clips": [item.GetName() for item in items], "cdl": cdl, "lut": str(lut) if lut else None, "applied": False}
    target = fork(session, "grade", copy_name)
    for item in video_items(target.context, track, indices):
        if lut:
            accepted(item, "SetLUT", node, str(lut))
        if not lut or any(value is not None for value in (slope, offset, power)) or saturation != 1:
            accepted(item, "SetCDL", cdl)
    return {"source": target.source, "timeline": target.target, "clips": len(items), "applied": True,
            "verification": "native_acceptance; inspect grade visually before delivery"}


def inspect(session, track=1, index=1):
    ctx, items = selected(session, track, [index])
    graph = invoke(items[0], "GetNodeGraph")
    return {"clip": items[0].GetName(), "nodes": [{"index": node, "label": invoke(graph, "GetNodeLabel", node),
            "lut": invoke(graph, "GetLUT", node)} for node in range(1, int(invoke(graph, "GetNumNodes")) + 1)]}


def gallery(session, action="list", label=None, output_dir=None):
    ctx = current(session)
    gallery = invoke(ctx.project, "GetGallery")
    if action == "list":
        return {"albums": [{"name": invoke(gallery, "GetAlbumName", album), "stills": len(invoke(album, "GetStills") or [])}
                            for album in invoke(gallery, "GetGalleryStillAlbums") or []]}
    if action == "capture":
        still = accepted(ctx.timeline, "GrabStill")
        album = invoke(gallery, "GetCurrentStillAlbum")
        if label is not None:
            accepted(album, "SetLabel", still, label)
        return {"captured": True, "label": label}
    if action == "export":
        directory = Path(output_dir or Path.home() / "Movies/resolve-forge/stills").expanduser().resolve()
        if directory.exists():
            raise ValueError("Use a new still-export directory to prevent overwrites.")
        directory.mkdir(parents=True)
        album = invoke(gallery, "GetCurrentStillAlbum")
        stills = invoke(album, "GetStills") or []
        if not stills:
            raise ValueError("Current gallery album contains no stills.")
        accepted(album, "ExportStills", stills, str(directory), "forge", "png")
        return {"directory": str(directory), "files": [str(path) for path in directory.iterdir()]}
    raise ValueError("Gallery action must be list, capture or export.")
