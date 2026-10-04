"""Turn an anchor request ("face", "center", [x, y]) into a point for one clip."""

from __future__ import annotations

from typing import Any

from ..analysis import faces
from ..gateway import call
from .context import ForgeError, source_path

Anchor = str | list[float] | tuple[float, float]


def resolve_anchor(anchor: Anchor, item: Any) -> tuple[tuple[float, float], str]:
    """Returns (point, how) — `how` explains where the point came from."""
    if isinstance(anchor, (list, tuple)):
        if len(anchor) != 2 or not all(0 <= float(v) <= 1 for v in anchor):
            raise ForgeError("anchor point must be [x, y] with values in 0..1 (top-left origin)")
        return (float(anchor[0]), float(anchor[1])), "given"
    if anchor == "center":
        return (0.5, 0.5), "center"
    if anchor in ("talking_head", "default"):
        return faces.TALKING_HEAD_DEFAULT, "talking_head default"
    if anchor == "face":
        path = source_path(item)
        if path and faces.available():
            track = faces.locate(path, int(call(item, "GetSourceStartFrame", default=0) or 0),
                                 call(item, "GetSourceEndFrame"))
            if track:
                return track.center, f"face ({track.hits}/{track.samples} samples)"
        why = "opencv not installed" if not faces.available() else "no face found"
        return faces.TALKING_HEAD_DEFAULT, f"talking_head default ({why})"
    raise ForgeError("anchor must be 'face', 'center', 'talking_head' or [x, y]")
