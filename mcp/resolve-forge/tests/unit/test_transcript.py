import pytest

from resolve_forge.domain.transcript import (Word, caption_chunks, cut_points, emphasis_hits, map_clip,
                                             sentences)


def words(spec):
    """'hola:0-0.4 mundo.:0.5-0.9' -> [Word]"""
    out = []
    for token in spec.split():
        text, times = token.rsplit(":", 1)
        a, b = times.split("-")
        out.append(Word(text, float(a), float(b)))
    return out


def test_map_clip_retimes_only_words_inside_the_used_range():
    src = words("antes:1-1.5 dentro:10.2-10.6 tambien:11-11.4 despues:20-20.5")
    mapped = map_clip(src, src_in=10.0, src_out=12.0, timeline_at=3.0)
    assert [w.text for w in mapped] == ["dentro", "tambien"]
    assert mapped[0].start == pytest.approx(3.2) and mapped[1].end == pytest.approx(4.4)


def test_map_clip_clamps_a_word_cut_by_the_edit():
    mapped = map_clip(words("cortada:9.9-10.3"), 10.0, 12.0, 0.0)
    assert mapped[0].start == pytest.approx(0.0)


def test_sentences_split_on_punctuation_and_pauses():
    spans = sentences(words("Hola:0-0.3 a:0.35-0.4 todos.:0.45-0.8 Hoy:0.9-1.1 limpio:1.15-1.5 "
                            "mi:3.0-3.1 cuarto:3.15-3.5"))
    assert [s.text for s in spans] == ["Hola a todos.", "Hoy limpio", "mi cuarto"]


def test_caption_chunks_respect_word_and_sentence_limits():
    ws = words("uno:0-0.2 dos:0.25-0.4 tres:0.45-0.6 cuatro:0.65-0.8 cinco:0.85-1.0 fin.:1.05-1.3 "
               "otra:1.4-1.6 frase:1.65-1.9")
    chunks = caption_chunks(ws, max_words=4)
    assert [c.text for c in chunks] == ["uno dos tres cuatro", "cinco fin.", "otra frase"]
    for a, b in zip(chunks, chunks[1:]):
        assert a.end <= b.start + 1e-9  # never overlapping
    assert chunks[0].end == pytest.approx(chunks[1].start)  # short gap bridged: no blinking


def test_caption_chunks_keep_a_long_pause_empty():
    chunks = caption_chunks(words("hola:0-0.3 adios:5-5.3"))
    assert chunks[0].end < 1.0 and chunks[1].start == pytest.approx(5.0)


def test_emphasis_hits_prefer_numbers_and_exclamations_and_space_them():
    ws = words("tengo:0-0.2 3:0.3-0.5 ardillas:0.6-1.0 increible!:1.2-1.6 este:4-4.2 resultado.:4.3-4.9")
    assert emphasis_hits(ws) == [0.3, 4.3]  # '!' at 1.2 is < 2 s after the number


def test_cut_points_skip_first_and_too_close():
    spans = sentences(words("a.:0-0.5 b.:1-1.5 c.:4-4.5 d.:5-5.5 e.:9-9.5"))
    assert cut_points(spans) == [1.0, 4.0, 9.0]
