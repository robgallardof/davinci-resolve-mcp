"""Where is the action, moment by moment? Motion energy and its centroid on a small proxy.

What an editor's eye follows (the squirrel jumping, the hand reaching for the broom): pixels that change
between frames. Each window reports how much moved and where, so zooms can focus on it. No Resolve.
"""

from __future__ import annotations

from dataclasses import dataclass

PROXY_W = 90  # proxy width; height follows the source aspect


@dataclass(frozen=True)
class ActionSample:
    time_s: float        # window start, source seconds
    energy: float        # mean absolute frame difference (0-255 scale)
    x: float             # centroid of the strongest change, 0..1 from the left
    y: float             # 0..1 from the top
    spread: float        # how scattered the change is (0 = one spot, ~0.5 = whole frame / camera move)
    box: tuple[float, float, float, float] = (0.5, 0.5, 0.5, 0.5)  # robust extent of the change (5-95%)


def samples(path: str, window_s: float = 0.25) -> tuple[list[ActionSample], float, float]:
    """(samples, duration_s, aspect w/h). Camera moves show up as high energy with a large spread."""
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError("Video could not be opened.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width, height = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 16, cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 9
    proxy_h = max(16, round(PROXY_W * height / width))
    per_window = max(1, round(window_s * fps))
    ys, xs = np.mgrid[0:proxy_h, 0:PROXY_W]
    out: list[ActionSample] = []
    previous, acc, count, index = None, None, 0, 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            grey = cv2.GaussianBlur(cv2.cvtColor(cv2.resize(frame, (PROXY_W, proxy_h)), cv2.COLOR_BGR2GRAY), (3, 3), 0)
            grey = grey.astype(np.float32)
            if previous is not None:
                diff = np.abs(grey - previous)
                acc = diff if acc is None else acc + diff
                count += 1
            previous = grey
            index += 1
            if index % per_window == 0 and acc is not None:
                out.append(_summarise((index - per_window) / fps, acc / max(count, 1), xs, ys))
                acc, count = None, 0
    finally:
        cap.release()
    if acc is not None and count:
        out.append(_summarise((index - count) / fps, acc / count, xs, ys))
    return out, index / fps, width / height


def _summarise(time_s, diff, xs, ys):
    import numpy as np
    energy = float(diff.mean())
    threshold = float(np.percentile(diff, 90))
    mask = diff >= max(threshold, 4.0)
    if not mask.any():
        return ActionSample(round(time_s, 3), round(energy, 3), 0.5, 0.5, 0.0)
    w, h = diff.shape[1] - 1, diff.shape[0] - 1
    box = (round(float(np.percentile(xs[mask], 5)) / w, 3), round(float(np.percentile(ys[mask], 5)) / h, 3),
           round(float(np.percentile(xs[mask], 95)) / w, 3), round(float(np.percentile(ys[mask], 95)) / h, 3))
    weights = diff[mask]
    cx = float((xs[mask] * weights).sum() / weights.sum()) / (diff.shape[1] - 1)
    cy = float((ys[mask] * weights).sum() / weights.sum()) / (diff.shape[0] - 1)
    spread = float(np.sqrt(((xs[mask] / (diff.shape[1] - 1) - cx) ** 2 + (ys[mask] / (diff.shape[0] - 1) - cy) ** 2).mean()))
    return ActionSample(round(time_s, 3), round(energy, 3), round(cx, 3), round(cy, 3), round(spread, 3), box)
