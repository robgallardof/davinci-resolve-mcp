import pytest

from resolve_forge.analysis.highlights import motion_per_second, rank
from resolve_forge.domain import formats
from resolve_forge.graphics import cards


def _bbox(img):
    return img.getchannel("A").getbbox()


@pytest.mark.parametrize("style", list(cards.STYLES))
@pytest.mark.parametrize("position", cards.POSITIONS)
def test_card_stays_inside_the_safe_zone(style, position):
    w, h = 1080, 1920
    safe = formats.safe_for(w, h)
    img = cards.render("POV: intento limpiar mi cuarto 🧹", w, h, style=style, position=position, safe=safe)
    assert img.size == (w, h) and img.mode == "RGBA"
    x0, y0, x1, y1 = _bbox(img)
    r = safe.rect(w, h)
    assert x0 >= r["x"] - 2 and x1 <= r["x"] + r["width"] + 2
    assert y0 >= r["y"] - 2 and y1 <= r["y"] + r["height"] + 2


def test_card_positions_are_ordered():
    tops = [_bbox(cards.render("texto", 1920, 1080, position=p))[1] for p in cards.POSITIONS]
    assert tops[0] < tops[1] < tops[2]


def test_long_text_wraps_and_short_text_does_not():
    short = _bbox(cards.render("hola", 1080, 1920))
    long = _bbox(cards.render("una frase bastante larga que no entra en una sola línea del vertical", 1080, 1920))
    assert (long[3] - long[1]) > 1.8 * (short[3] - short[1])


def test_unknown_style_or_position():
    with pytest.raises(ValueError):
        cards.render("x", 100, 100, style="neon")
    with pytest.raises(ValueError):
        cards.render("x", 100, 100, position="left")


def test_safe_for_uses_the_strictest_platform():
    z = formats.safe_for(1080, 1920)
    assert z.bottom == max(f.safe.bottom for f in formats.FORMATS.values() if (f.width, f.height) == (1080, 1920))
    assert formats.safe_for(1920, 1080).bottom == pytest.approx(0.10)


def test_rank_finds_the_spikes_without_overlap():
    motion = [1.0] * 40
    for s in (8, 9, 10, 30, 31):
        motion[s] = 12.0
    audio = [-60.0] * 40
    audio[30] = audio[31] = -20.0
    windows = rank(motion, audio, window_s=3, top=2)
    assert [round(w.start) for w in windows] in ([8, 29], [8, 30], [7, 30], [8, 31])
    assert windows[0].end <= windows[1].start


def test_rank_without_audio():
    assert rank([0, 0, 9, 9, 0, 0], None, window_s=2, top=1)[0].start == 2.0


def test_motion_per_second_on_a_real_file(tmp_path):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    path = tmp_path / "clip.mp4"
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 64))
    for i in range(40):  # still for 2 s, then a moving square for 2 s
        frame = np.zeros((64, 64, 3), np.uint8)
        x = 5 if i < 20 else 5 + (i - 20) * 2
        frame[20:40, x:x + 15] = 255
        out.write(frame)
    out.release()
    per_s, fps = motion_per_second(str(path))
    assert fps == pytest.approx(10) and len(per_s) == 4
    assert per_s[3] > per_s[0] + 1


def test_face_anchor_degrades_gracefully_without_the_haar_detector(monkeypatch):
    """OpenCV 5 has no CascadeClassifier: locating a face returns None (default anchor), never crashes."""
    import types
    import sys
    from resolve_forge.analysis import faces
    monkeypatch.setitem(sys.modules, "cv2", types.SimpleNamespace(VideoCapture=lambda *_: None))
    assert faces.available() is False
    assert faces.locate("any.mp4") is None
