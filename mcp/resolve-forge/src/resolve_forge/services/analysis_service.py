"""Source analysis and cut plans; analysis never edits the current timeline."""
from pathlib import Path

from ..domain.edit_decisions import keep_ranges, onset_hits, silence_ranges
from ..errors import ForgeError
from .context import current
from .media_lookup import find_existing
from .native import number


def source_path(session, source):
    path = Path(source).expanduser()
    if path.is_file():
        return str(path.resolve())
    ctx = current(session, need_timeline=False)
    clip = find_existing(ctx.media_pool, source)
    path = clip.GetClipProperty("File Path") if clip else ""
    if not path or not Path(path).is_file():
        raise ValueError("Source needs an existing file or one unambiguous media-pool clip.")
    return path



def audio(session, source, threshold_db=-40, minimum_s=.5, padding_s=.15):
    number(threshold_db, "silence threshold", -120, 0)
    number(minimum_s, "minimum silence", .05)
    number(padding_s, "breath padding", 0)
    from ..analysis import media
    if not media.available():
        raise ForgeError("Audio analysis requires the speech extra.", code="MISSING_DEPENDENCY", hint="uv sync --extra speech")
    from ..analysis.audio_events import levels
    values, duration, step = levels(source_path(session, source))
    silences = silence_ranges(values, step, threshold_db, minimum_s)
    return {"source": source, "duration_s": duration, "silences": silences,
            "keep_ranges": keep_ranges(duration, silences, padding_s), "hits_s": onset_hits(values, step),
            "hits_method": "energy_onsets; not tempo or downbeat estimation", "time_basis": "source seconds",
            "next": "assemble_timeline(source, cuts=keep_ranges, name=...) creates a new timeline"}


def scenes(session, source, threshold=.45, minimum_gap_s=.5):
    number(threshold, "scene threshold", .01, 1)
    number(minimum_gap_s, "minimum scene gap", .05)
    try:
        import cv2
    except ImportError:
        raise ForgeError("Scene analysis requires OpenCV.", code="MISSING_DEPENDENCY", hint="uv sync --extra vision")
    cap = cv2.VideoCapture(source_path(session, source))
    if not cap.isOpened():
        raise ValueError("Video could not be opened.")
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        cap.release()
        raise ValueError("Video frame rate is unavailable.")
    previous, frame_index, boundaries = None, 0, [0.0]
    try:
        while True:
            success, image = cap.read()
            if not success:
                break
            hsv = cv2.cvtColor(cv2.resize(image, (160, 90)), cv2.COLOR_BGR2HSV)
            histogram = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
            cv2.normalize(histogram, histogram)
            time_s = frame_index / fps
            if previous is not None and time_s - boundaries[-1] >= minimum_gap_s and cv2.compareHist(previous, histogram, cv2.HISTCMP_BHATTACHARYYA) >= threshold:
                boundaries.append(time_s)
            previous = histogram
            frame_index += 1
    finally:
        cap.release()
    duration = frame_index / fps
    if not frame_index:
        raise ValueError("Source contains no decodable video frames.")
    return {"source": source, "fps": fps, "duration_s": duration, "boundaries_s": boundaries[1:],
            "scenes": [[a, b] for a, b in zip(boundaries, boundaries[1:] + [duration])],
            "time_basis": "source seconds", "method": "HSV histogram distance"}
