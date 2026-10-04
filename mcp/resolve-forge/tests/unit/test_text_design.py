"""Timing, accessibility and pixel guarantees of the designed caption pipeline."""

from pathlib import Path

import pytest

from resolve_forge.domain.formats import safe_for
from resolve_forge.domain.text_design import (ANIMATIONS, DESIGNS, accent_rgba, cues, motion_state,
                                             provided_words, resolve_animation, resolve_style, srt)
from resolve_forge.domain.transcript import Word
from resolve_forge.graphics import cards
from resolve_forge.graphics.sequences import write_frames
from resolve_forge.graphics.text_animation import animate
from resolve_forge.services.overlay_service import _letters
from resolve_forge.services import text_preview_service


def test_auto_art_direction_and_reduced_motion():
    assert resolve_style("auto", 1080, 1920) == "creator"
    assert resolve_style("auto", 1920, 1080) == "studio"
    assert resolve_animation("auto", "creator") == "pop"
    assert resolve_animation("auto", "outline") == "none"
    assert resolve_animation("lift", "creator", True) == "none"
    with pytest.raises(ValueError):
        accent_rgba("lime", "creator")


def test_cues_preserve_speech_and_leave_long_pauses_empty():
    words = [Word("Hola", 0.1, 0.25), Word("México!", 0.3, 0.5), Word("Otra", 4, 4.3), Word("idea.", 4.4, 4.9)]
    result = cues(words, 3, end_s=5)
    assert " ".join(c.text for c in result) == " ".join(w.text for w in words)
    assert result[0].active_at(0.2) == 0
    assert result[0].active_at(0.28) is None
    assert result[0].active_at(0.4) == 1
    assert result[0].end < result[1].start
    assert result[-1].end <= 5
    assert all(a.end <= b.start for a, b in zip(result, result[1:]))
    assert "00:00:04,000 --> 00:00:04,900" in srt(result)


@pytest.mark.parametrize("words", [[Word("x", float("nan"), 1)], [Word("x", 1, 0)],
                                  [Word("a", 2, 3), Word("b", 1, 2)]])
def test_invalid_word_times_are_rejected(words):
    with pytest.raises(ValueError):
        cues(words, 3)


@pytest.mark.parametrize("value", [0, 9, True, 2.5])
def test_invalid_phrase_lengths_are_rejected(value):
    with pytest.raises(ValueError):
        cues([], value)


def test_manual_transcript_validates_types_and_retains_accents():
    assert provided_words([dict(text=" café ", start=0, end=1)])[0].text == "café"
    for row in [dict(text="x", start=True, end=1), dict(start=0, end=1), dict(text="", start=0, end=1)]:
        with pytest.raises(ValueError):
            provided_words([row])


@pytest.mark.parametrize("animation", ANIMATIONS)
@pytest.mark.parametrize("style", DESIGNS)
def test_animated_text_remains_inside_safe_zone_and_holds_legibly(style, animation):
    size = (540, 960)
    safe = safe_for(*size)
    base = cards.render("Tu próxima idea", *size, style=style, position="bottom", safe=safe,
                        active_word=1, emphasis_words=["idea"], max_lines=2)
    rect = safe.rect(*size)
    for frame in (0, 1, 3, 8, 29):
        image = animate(base, animation, frame, 30, 30, safe)
        x0, y0, x1, y1 = image.getchannel("A").getbbox()
        assert rect["x"] <= x0 < x1 <= rect["x"] + rect["width"]
        assert rect["y"] <= y0 < y1 <= rect["y"] + rect["height"]
        assert image.getchannel("A").getextrema()[1] >= 120
    assert animate(base, animation, 29, 30, 30, safe).tobytes() == base.tobytes()
    assert motion_state(animation, 29, 30, 30) == (1, 1, 0)


def test_highlight_changes_pixels_without_moving_other_words():
    from PIL import ImageChops
    size = (1080, 1920)
    a = cards.render("Ideas que importan", *size, style="creator", active_word=0)
    b = cards.render("Ideas que importan", *size, style="creator", active_word=1)
    assert ImageChops.difference(a, b).getbbox() is not None
    # The final word is identical on both frames: no karaoke-induced line reflow.
    bbox = a.getchannel("A").getbbox()
    right = (round(bbox[0] + (bbox[2] - bbox[0]) * 0.75), bbox[1], bbox[2], bbox[3])
    assert a.crop(right).tobytes() == b.crop(right).tobytes()


def test_sequence_reuses_states_and_does_not_overwrite(tmp_path):
    from PIL import Image
    path = tmp_path / "caption"
    rendered = []

    def render(state):
        rendered.append(state)
        return Image.new("RGBA", (16, 16), (255, state * 100, 0, 255))

    write_frames(path, 30, lambda i: int(i >= 10), render)
    files = sorted(path.glob("*.png"))
    assert len(files) == 30 and rendered == [0, 1]
    assert files[0].read_bytes() == files[9].read_bytes()
    assert files[0].read_bytes() != files[10].read_bytes()
    with pytest.raises(FileExistsError):
        write_frames(path, 2, lambda i: 0, render)
    assert len({_letters(i) for i in range(3000)}) == 3000


def test_preview_produces_real_animated_artifacts_without_resolve(tmp_path, monkeypatch):
    from PIL import Image
    monkeypatch.setattr(text_preview_service, "DEFAULT_OUTPUT", tmp_path)
    result = text_preview_service.preview("Tu próxima idea", width=540, height=960)
    assert result["style"] == "creator" and result["animation"] == "pop"
    for key in ("poster", "animated_preview", "contact_sheet"):
        assert Path(result[key]).is_file()
    with Image.open(result["animated_preview"]) as image:
        assert image.is_animated and image.n_frames > 3


def test_words_share_one_baseline_regardless_of_ascenders():
    """'cara' (no ascenders) must sit on the same baseline as 'La' and 'de', not float to the line top."""
    pytest.importorskip("PIL")
    import numpy as np
    from resolve_forge.graphics import cards
    image = np.asarray(cards.render("La cara de", 1080, 1920, style="creator", position="middle").getchannel("A"))
    columns = np.where(image.max(axis=0) > 128)[0]
    gaps = np.where(np.diff(columns) > 12)[0]  # split the ink into the three words
    words = np.split(columns, gaps + 1)
    assert len(words) == 3
    bottoms = [np.where(image[:, w[0]:w[-1] + 1].max(axis=1) > 128)[0].max() for w in words]
    assert max(bottoms) - min(bottoms) <= 3, bottoms


def test_karaoke_tracks_word_duration_and_stops_during_silence():
    cue = cues([Word("Muy", 0, 1), Word("bien", 1.5, 2)], 3)[0]
    assert cue.progress_at(0.25) == 0.25
    assert cue.progress_at(1.25) is None
    assert cue.active_at(1.75) == 1 and cue.progress_at(1.75) == 0.5
    assert resolve_animation("karaoke", "creator", True) == "none"
    assert motion_state("karaoke", 0, 60, 30) == (1, 1, 0)


def test_karaoke_changes_only_word_underline_without_reflow():
    import numpy as np
    first = cards.render("Ideas que importan", 1080, 1920, style="creator", active_word=0, active_progress=0.1)
    last = cards.render("Ideas que importan", 1080, 1920, style="creator", active_word=0, active_progress=0.9)
    difference = np.any(np.asarray(first) != np.asarray(last), axis=2)
    rows, columns = np.where(difference)
    assert len(rows) > 0
    assert rows.max() - rows.min() < 10  # only the thin underline moves
    assert columns.max() < first.getchannel("A").getbbox()[0] + 220
    assert first.getchannel("A").getbbox() == last.getchannel("A").getbbox()
