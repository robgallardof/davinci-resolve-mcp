import pytest

from resolve_forge.domain.alignment import align
from resolve_forge.domain.transcript import Word


def heard():
    # Whisper misheard the name and dropped a word.
    return [Word("Hola", 0, .4), Word("soy", .4, .6), Word("Jose", .6, 1.0), Word("y", 1.2, 1.3),
            Word("esto", 1.3, 1.6), Word("es", 1.6, 1.8), Word("forge.", 1.8, 2.3)]


def test_known_text_wins_and_takes_recognised_timing():
    words, coverage = align("Hola, soy José y esto es Forge", heard())
    assert [w.text for w in words] == ["Hola,", "soy", "José", "y", "esto", "es", "Forge"]
    assert (words[2].start, words[2].end) == (.6, 1.0)  # accents/case/punctuation still match
    assert coverage == 1


def test_unmatched_words_are_spread_between_neighbours_without_overlap():
    words, coverage = align("Hola soy Rob Gallardo y esto es Forge", heard())
    rob, gallardo = words[2], words[3]
    assert .6 <= rob.start < gallardo.start < gallardo.end <= 1.2
    assert all(a.end <= b.start for a, b in zip(words, words[1:]))
    assert coverage == pytest.approx(6 / 8, abs=.01)


def test_alignment_requires_text_and_recognition():
    with pytest.raises(ValueError):
        align("   ", heard())
    with pytest.raises(ValueError):
        align("hola", [])
