"""Who is speaking, moment by moment? Faces grouped into people + mouth motion while there is voice.

Active-speaker evidence without a neural model: a person speaks when the mouth region of their face moves
clearly more than usual for them *and* the audio has voice at that moment. Good enough to choose framings
for podcasts and interviews; the agent still reviews the result (review_shots / review_video).
"""

from __future__ import annotations

from statistics import median


def scan(path: str, step_s: float = 0.25):
    """(people face boxes, [(time_s, speaking indices)], duration_s, aspect w/h)."""
    import cv2
    import numpy as np

    from ..domain.layouts import cluster_people
    from .presence import available

    if not available():
        raise ValueError("Speaker analysis needs OpenCV with face detection (uv sync --extra vision).")
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError("Video could not be opened.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    width, height = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 16, cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 9
    front = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    profile = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
    step = max(1, round(step_s * fps))
    scale = 480 / max(width, height)
    frames, boxes = [], []
    try:
        for index in range(0, total, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = cap.read()
            ok2, nxt = cap.read()
            if not ok:
                break
            small = cv2.resize(frame, (round(width * scale), round(height * scale)))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            sh, sw = gray.shape
            size = (int(sh * 0.05), int(sh * 0.05))
            found = list(front.detectMultiScale(gray, 1.1, 4, minSize=size)) + list(profile.detectMultiScale(gray, 1.1, 4, minSize=size))
            boxes += [(x / sw, y / sh, (x + w) / sw, (y + h) / sh) for x, y, w, h in found]
            nxt_gray = cv2.cvtColor(cv2.resize(nxt, (sw, sh)), cv2.COLOR_BGR2GRAY) if ok2 else gray
            frames.append((index / fps, gray.astype(np.int16), nxt_gray.astype(np.int16)))
    finally:
        cap.release()
    people = cluster_people([tuple(map(float, b)) for b in boxes])
    if not people:
        return [], [], total / fps, width / height
    mouth = []  # per sample, per person: motion in the lower part of the face
    for time_s, gray, nxt in frames:
        sh, sw = gray.shape
        row = []
        for x0, y0, x1, y1 in people:
            fh = y1 - y0
            a, b = int((y0 + fh * 0.6) * sh), int(min(1.0, y1 + fh * 0.1) * sh)
            c, d = int((x0 + (x1 - x0) * 0.2) * sw), int((x1 - (x1 - x0) * 0.2) * sw)
            region = np.abs(nxt[a:b, c:d] - gray[a:b, c:d])
            row.append(float(region.mean()) if region.size else 0.0)
        mouth.append(row)
    voiced = _voice(path, [t for t, _, _ in frames], step_s)
    baseline = [median(r[i] for r in mouth) or 0.01 for i in range(len(people))]
    active = []
    for (time_s, _, _), row, voice in zip(frames, mouth, voiced):
        ratios = [value / base for value, base in zip(row, baseline)]
        top = max(ratios) if ratios else 0
        speaking = tuple(i for i, r in enumerate(ratios) if voice and r >= 1.4 and r >= 0.7 * top)
        active.append((round(time_s, 3), speaking))
    return people, active, total / fps, width / height


def _voice(path, times, step_s):
    """True where the audio carries voice-level energy (relative to the clip's own loudness)."""
    try:
        from .audio_events import levels
        values, _, step = levels(path, step_s=step_s)
    except Exception:
        return [True] * len(times)
    if not values:
        return [True] * len(times)
    floor = sorted(values)[len(values) // 5]
    out = []
    for t in times:
        i = min(len(values) - 1, int(t / step))
        out.append(values[i] > max(-45.0, floor + 10))
    return out
