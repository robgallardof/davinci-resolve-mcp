"""Use case: look at the edit before (and after) rendering — framing, text over faces, picture quality.

review_shots renders what each planned shot will SHOW (its real crop) with faces, subject and text boxes drawn,
flags every problem and writes one contact sheet the agent must look at. review_video does the same for a
rendered file: frames over time, black or frozen stretches and picture quality. Nothing touches Resolve.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from ..domain import formats, framing_review, look, text_placement
from ..errors import ForgeError
from .analysis_service import source_path
from .render_service import DEFAULT_OUTPUT

THUMB_W = 216


def _cv():
    try:
        import cv2
        import numpy as np
        return cv2, np
    except ImportError as exc:
        raise ForgeError("Review needs OpenCV.", code="MISSING_DEPENDENCY", hint="uv sync --extra vision") from exc


def frame_stats(frame) -> dict:
    cv2, np = _cv()
    small = cv2.resize(frame, (160, int(160 * frame.shape[0] / frame.shape[1])))
    rgb = small[:, :, ::-1].astype(np.float32) / 255
    luma = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    mid = (luma > 0.2) & (luma < 0.8)
    pick = rgb[mid] if mid.any() else rgb.reshape(-1, 3)
    return {"luma": float(np.median(luma)), "p2": float(np.percentile(luma, 2)), "p98": float(np.percentile(luma, 98)),
            "saturation": float(hsv[..., 1].mean() / 255), "r": float(pick[:, 0].mean()),
            "g": float(pick[:, 1].mean()), "b": float(pick[:, 2].mean())}


def _faces(frame):
    from ..analysis import faces
    if not faces.available():
        return []
    cv2, _ = _cv()
    h, w = frame.shape[:2]
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    found = cascade.detectMultiScale(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(int(h * .06), int(h * .06)))
    return [(x / w, y / h, (x + fw) / w, (y + fh) / h) for x, y, fw, fh in found if (y + fh / 2) / h <= 0.75]


def _to_screen(box, zoom, pivot):
    (x0, y0), (x1, y1) = framing_review.on_screen(box[:2], zoom, pivot), framing_review.on_screen(box[2:], zoom, pivot)
    return (x0, y0, x1, y1)


def _text_boxes(text, width, height, fmt):
    """Normalized rectangle the text occupies at each position, from the real renderer."""
    from ..graphics import cards
    boxes = {}
    for position in text_placement.POSITIONS:
        bbox = cards.render(text, width, height, style="creator", position=position, safe=fmt.safe).getchannel("A").getbbox()
        if bbox:
            boxes[position] = (bbox[0] / width, bbox[1] / height, bbox[2] / width, bbox[3] / height)
    return boxes


def _sheet(tiles, columns=6):
    cv2, np = _cv()
    while len(tiles) % columns:
        tiles.append(np.zeros_like(tiles[0]))
    return np.vstack([np.hstack(tiles[i:i + columns]) for i in range(0, len(tiles), columns)])


def review_shots(session, source, shots, format="tiktok", texts=None) -> dict:
    cv2, np = _cv()
    fmt = formats.get(format)
    path = source_path(session, source)
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError("Video could not be opened.")
    thumb_h = round(THUMB_W * fmt.height / fmt.width)
    texts = texts or []
    boxes = {t["text"]: _text_boxes(t["text"], fmt.width, fmt.height, fmt) for t in texts}
    tiles, report, stats, at = [], [], [], 0.0
    windows = []  # (timeline start, end, avoid boxes on screen)
    try:
        for index, shot in enumerate(shots, 1):
            length = float(shot["end_s"]) - float(shot["start_s"])
            moment = float(shot.get("hit_s") or 0) + 0.25 if shot.get("hit_s") else float(shot["start_s"]) + length / 2
            cap.set(cv2.CAP_PROP_POS_MSEC, moment * 1000)
            ok, frame = cap.read()
            if not ok:
                report.append({"shot": index, "issues": ["frame unreadable"]})
                at += length
                continue
            stats.append(frame_stats(frame))
            zoom, pivot = float(shot["zoom"]), tuple(shot["anchor"])
            h, w = frame.shape[:2]
            x0, y0, x1, y1 = framing_review.visible(zoom, pivot)
            crop = frame[int(y0 * h):max(int(y0 * h) + 2, int(y1 * h)), int(x0 * w):max(int(x0 * w) + 2, int(x1 * w))]
            tile = cv2.resize(crop, (THUMB_W, thumb_h), interpolation=cv2.INTER_AREA)
            face_boxes = [_to_screen(b, zoom, pivot) for b in _faces(frame)]
            subject = framing_review.on_screen(tuple(shot["subject"]), zoom, pivot)
            avoid = [*face_boxes, (subject[0] - .08, subject[1] - .06, subject[0] + .08, subject[1] + .06)]
            windows.append((at, at + length, avoid))
            problems = framing_review.issues(shot, [], [])
            for fx0, fy0, fx1, fy1 in face_boxes:
                cv2.rectangle(tile, (int(fx0 * THUMB_W), int(fy0 * thumb_h)), (int(fx1 * THUMB_W), int(fy1 * thumb_h)), (255, 200, 0), 2)
            cv2.circle(tile, (int(subject[0] * THUMB_W), int(subject[1] * thumb_h)), 6, (0, 255, 255), 2)
            for t in texts:
                if t["start_s"] < at + length and at < t["start_s"] + t["duration_s"]:
                    box = boxes[t["text"]].get(t.get("position", "top"))
                    if box:
                        bad = any(text_placement.overlaps(box, a) for a in face_boxes)
                        cv2.rectangle(tile, (int(box[0] * THUMB_W), int(box[1] * thumb_h)), (int(box[2] * THUMB_W), int(box[3] * thumb_h)),
                                      (0, 0, 255) if bad else (255, 255, 255), 2)
                        if bad:
                            problems.append(f"text '{t['text'][:18]}' covers a face")
            color = (0, 0, 255) if problems else (0, 200, 0)
            cv2.rectangle(tile, (0, 0), (THUMB_W - 1, thumb_h - 1), color, 4)
            cv2.putText(tile, f"{index} {at:.1f}s {shot['framing']} x{zoom:.2f}", (6, 20), cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 255, 255), 1)
            tiles.append(tile)
            report.append({"shot": index, "timeline_s": round(at, 2), "framing": shot["framing"], "issues": problems})
            at += length
    finally:
        cap.release()
    placements = []
    for t in texts:
        avoid = [box for start, end, boxes_on in windows if start < t["start_s"] + t["duration_s"] and t["start_s"] < end
                 for box in boxes_on]
        position, conflicts = text_placement.choose(boxes[t["text"]], avoid, t.get("position", "top"))
        placements.append({"text": t["text"], "start_s": t["start_s"], "position": position, "conflicts": conflicts})
    out = DEFAULT_OUTPUT / "reviews" / secrets.token_hex(4)
    out.mkdir(parents=True, exist_ok=True)
    sheet = out / "shots.jpg"
    cv2.imwrite(str(sheet), _sheet(tiles))
    flagged = [r for r in report if r["issues"]]
    return {"sheet": str(sheet), "shots": len(shots), "flagged": flagged, "text_positions": placements,
            "look": look.assess(stats),
            "legend": "green = ok, red = problem; cyan circle = subject, yellow = faces, white/red = text box",
            "next": "LOOK at the sheet. Fix flagged shots (hints/framing), use text_positions, apply look.cdl with "
                    "grade_clips if it improves the frames, then build; after render run review_video."}


def review_video(session, path, every_s=1.5) -> dict:
    cv2, np = _cv()
    file = Path(path).expanduser()
    if not file.is_file():
        raise ValueError("Rendered file not found.")
    cap = cv2.VideoCapture(str(file))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frames / fps
    thumb_h = round(THUMB_W * height / max(width, 1))
    tiles, stats, black, frozen, previous, still_since = [], [], [], [], None, None
    try:
        t = 0.0
        while t < duration:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if not ok:
                break
            s = frame_stats(frame)
            stats.append(s)
            if s["p98"] < 0.06:
                black.append(round(t, 2))
            grey = cv2.cvtColor(cv2.resize(frame, (64, 112)), cv2.COLOR_BGR2GRAY).astype(np.int16)
            if previous is not None and np.abs(grey - previous).mean() < 0.4:
                still_since = still_since if still_since is not None else t - every_s
            else:
                if still_since is not None and t - still_since >= 3 * every_s:
                    frozen.append([round(still_since, 2), round(t, 2)])
                still_since = None
            previous = grey
            tile = cv2.resize(frame, (THUMB_W, thumb_h), interpolation=cv2.INTER_AREA)
            cv2.putText(tile, f"{t:.1f}s", (6, 20), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 255, 255), 1)
            tiles.append(tile)
            t += every_s
    finally:
        cap.release()
    if not tiles:
        raise ValueError("No decodable frames in the rendered file.")
    out = DEFAULT_OUTPUT / "reviews" / secrets.token_hex(4)
    out.mkdir(parents=True, exist_ok=True)
    sheet = out / "render.jpg"
    cv2.imwrite(str(sheet), _sheet(tiles, columns=8))
    issues = ([f"black frames at {black[:6]}"] if black else []) + ([f"frozen picture {frozen[:4]}"] if frozen else [])
    return {"sheet": str(sheet), "duration_s": round(duration, 2), "resolution": f"{width}x{height}", "fps": round(fps, 3),
            "issues": issues, "look": look.assess(stats),
            "next": "LOOK at the sheet: framing, text over faces, colour. Fix and re-render before delivering."}
