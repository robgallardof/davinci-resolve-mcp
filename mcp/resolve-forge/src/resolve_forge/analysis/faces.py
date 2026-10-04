"""Where is the speaker? Optional face detection used to anchor zooms and reframes.

Reads the source media file directly (never touches the project). Needs the
optional `vision` extra (opencv-python-headless); without it callers get None
and fall back to a talking-head default.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

TALKING_HEAD_DEFAULT = (0.5, 0.38)  # eyes sit around the upper third in most framings


@dataclass(frozen=True)
class FaceTrack:
    center: tuple[float, float]  # normalized, top-left origin (median of samples)
    size: float  # median face height / frame height
    samples: int
    hits: int


def available() -> bool:
    """OpenCV with the Haar face detector (OpenCV 5 removed CascadeClassifier from the main module)."""
    try:
        import cv2
    except ImportError:
        return False
    return hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data")


def locate(path: str, start_frame: int = 0, end_frame: int | None = None, samples: int = 12) -> FaceTrack | None:
    """Median face position over `samples` frames in [start_frame, end_frame)."""
    if not available():
        return None
    import cv2
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        end = min(end_frame or total, total)
        span = max(1, end - start_frame)
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        xs, ys, sizes, hits = [], [], [], 0
        for i in range(samples):
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame + int(span * (i + 0.5) / samples))
            ok, frame = cap.read()
            if not ok:
                continue
            h, w = frame.shape[:2]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(int(h * 0.06), int(h * 0.06)))
            if len(faces) == 0:
                continue
            x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])  # the biggest face is the speaker
            xs.append((x + fw / 2) / w)
            ys.append((y + fh / 2) / h)
            sizes.append(fh / h)
            hits += 1
        if not hits:
            return None
        return FaceTrack((statistics.median(xs), statistics.median(ys)), statistics.median(sizes), samples, hits)
    finally:
        cap.release()


def points(path: str, step_s: float = 0.5) -> list[tuple[float, float, float]]:
    """(time_s, x, y) of the biggest face every step_s seconds; empty when OpenCV lacks the detector."""
    if not available():
        return []
    import cv2
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return []
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        out, frame_index, step = [], 0, max(1, round(step_s * fps))
        while frame_index < total:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok:
                break
            h, w = frame.shape[:2]
            scale = 480 / max(h, w)
            small = cv2.resize(frame, (round(w * scale), round(h * scale))) if scale < 1 else frame
            sh, sw = small.shape[:2]
            found = cascade.detectMultiScale(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 1.1, 5,
                                             minSize=(int(sh * 0.06), int(sh * 0.06)))
            if len(found):
                x, y, fw, fh = max(found, key=lambda f: f[2] * f[3])
                fx, fy = float((x + fw / 2) / sw), float((y + fh / 2) / sh)
                if fy <= 0.75:  # Haar false positives cluster on floor/furniture texture at the bottom
                    out.append((round(frame_index / fps, 3), round(fx, 3), round(fy, 3)))
            frame_index += step
        return out
    finally:
        cap.release()
