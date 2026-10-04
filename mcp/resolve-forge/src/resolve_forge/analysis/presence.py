"""Who is on screen and are they engaging? People (HOG) and faces (frontal + both profiles) over time.

A person detected without any face is someone seen from behind: on social video that reads as dead time
unless something else (the pet, an object) is happening. No Resolve; reads the file directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Presence:
    time_s: float
    faces: tuple[tuple[float, float], ...] = field(default_factory=tuple)                   # face centres, 0..1
    people: tuple[tuple[float, float, float, float], ...] = field(default_factory=tuple)    # x0, y0, x1, y1, 0..1


def available() -> bool:
    try:
        import cv2
    except ImportError:
        return False
    return all(hasattr(cv2, name) for name in ("CascadeClassifier", "HOGDescriptor", "data"))


def scan(path: str, step_s: float = 0.5) -> list[Presence]:
    if not available():
        return []
    import cv2
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return []
    front = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    profile = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    out = []
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        step = max(1, round(step_s * fps))
        for index in range(0, total, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = cap.read()
            if not ok:
                break
            h, w = frame.shape[:2]
            scale = 480 / max(h, w)
            face_img = cv2.resize(frame, (round(w * scale), round(h * scale)))
            gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
            fh, fw = gray.shape
            size = (int(fh * 0.05), int(fh * 0.05))
            found = [(x + bw / 2, y + bh / 2) for x, y, bw, bh in front.detectMultiScale(gray, 1.1, 4, minSize=size)]
            found += [(x + bw / 2, y + bh / 2) for x, y, bw, bh in profile.detectMultiScale(gray, 1.1, 4, minSize=size)]
            found += [(fw - (x + bw / 2), y + bh / 2) for x, y, bw, bh in profile.detectMultiScale(cv2.flip(gray, 1), 1.1, 4, minSize=size)]
            faces = tuple((round(float(x / fw), 3), round(float(y / fh), 3)) for x, y in found if y / fh <= 0.75)
            body_scale = 512 / max(h, w)
            body = cv2.resize(frame, (round(w * body_scale), round(h * body_scale)))
            bh_, bw_ = body.shape[:2]
            rects, weights = hog.detectMultiScale(body, winStride=(8, 8), padding=(8, 8), scale=1.05)
            people = tuple((round(float(x / bw_), 3), round(float(y / bh_), 3), round(float((x + rw) / bw_), 3), round(float((y + rh) / bh_), 3))
                           for (x, y, rw, rh), weight in zip(rects, list(weights.ravel()) if len(weights) else [])
                           if float(weight) > 0.5)
            out.append(Presence(round(index / fps, 3), faces, people))
    finally:
        cap.release()
    return out
