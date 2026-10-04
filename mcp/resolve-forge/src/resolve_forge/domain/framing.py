"""Edit-page sizing math (Inspector Zoom / Position X / Position Y).

Conventions (Resolve Inspector):
  * Source clips are first fitted to the timeline ("Scale entire image to fit").
  * ZoomX/ZoomY multiply that fitted size, around the frame center.
  * Pan (Position X) is in timeline pixels, positive moves the image right.
  * Tilt (Position Y) is in timeline pixels, positive moves the image up.
Subject points are normalized source coordinates, top-left origin.
"""

from __future__ import annotations

from dataclasses import dataclass

Point = tuple[float, float]


@dataclass(frozen=True)
class Sizing:
    zoom: float
    pan: float
    tilt: float

    def as_props(self) -> dict[str, float]:
        return {"ZoomX": self.zoom, "ZoomY": self.zoom, "Pan": self.pan, "Tilt": self.tilt}


def fit_scale(src_w: int, src_h: int, dst_w: int, dst_h: int) -> float:
    return min(dst_w / src_w, dst_h / src_h)


def cover_zoom(src_w: int, src_h: int, dst_w: int, dst_h: int) -> float:
    """Inspector zoom that makes a fitted source fill the timeline (no bars)."""
    return max(dst_w / src_w, dst_h / src_h) / fit_scale(src_w, src_h, dst_w, dst_h)


def _clamp(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


def frame_subject(src: tuple[int, int], dst: tuple[int, int], subject: Point,
                  zoom: float | None = None, center_bias: float = 1.0) -> Sizing:
    """Zoom (default: cover) and move the image so `subject` approaches frame center.

    center_bias 1.0 centers the subject fully; 0.0 leaves the composition alone.
    The result is clamped so no black edge ever enters the frame.
    """
    (sw, sh), (dw, dh) = src, dst
    z = zoom if zoom is not None else cover_zoom(sw, sh, dw, dh)
    disp_w, disp_h = sw * fit_scale(sw, sh, dw, dh) * z, sh * fit_scale(sw, sh, dw, dh) * z
    pan = -(subject[0] - 0.5) * disp_w * center_bias
    tilt = (subject[1] - 0.5) * disp_h * center_bias
    return Sizing(z, _clamp(pan, max(0.0, (disp_w - dw) / 2)), _clamp(tilt, max(0.0, (disp_h - dh) / 2)))


def rezoom_keeping(src: tuple[int, int], dst: tuple[int, int], base: Sizing,
                   new_zoom: float, subject: Point) -> Sizing:
    """Change zoom while the subject stays where it is on screen (zoom 'into the face')."""
    (sw, sh), (dw, dh) = src, dst
    f = fit_scale(sw, sh, dw, dh)
    dz = new_zoom - base.zoom
    pan = base.pan - (subject[0] - 0.5) * sw * f * dz
    tilt = base.tilt + (subject[1] - 0.5) * sh * f * dz
    disp_w, disp_h = sw * f * new_zoom, sh * f * new_zoom
    return Sizing(new_zoom, _clamp(pan, max(0.0, (disp_w - dw) / 2)), _clamp(tilt, max(0.0, (disp_h - dh) / 2)))
