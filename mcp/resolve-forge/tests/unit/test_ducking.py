import numpy as np
import pytest

from resolve_forge.domain.ducking import gain_curve, speech_regions
from resolve_forge.domain.transcript import Word


def level(curve, t):
    times, dbs = zip(*curve)
    return float(np.interp(t, times, dbs))


def test_words_merge_into_regions_without_pumping_between_words():
    words = [Word("a", 1, 1.3), Word("b", 1.5, 2), Word("c", 5, 5.5)]
    assert speech_regions(words) == [(1, 2), (5, 5.5)]


def test_curve_ducks_under_speech_rises_between_lines_and_fades_the_bed():
    curve = gain_curve([(2, 4), (10, 12)], 15)
    assert level(curve, 0) == -90 and level(curve, 15) == -90
    assert level(curve, 3) == -20 and level(curve, 11) == -20
    assert level(curve, 7) == -10
    assert all(a[0] <= b[0] for a, b in zip(curve, curve[1:]))


def test_close_lines_stay_ducked_and_speech_at_start_never_peaks():
    curve = gain_curve([(0, 3), (3.5, 6)], 10)
    assert max(level(curve, t) for t in np.arange(0, 6, .05)) <= -20 + 1e-9


def test_levels_are_validated():
    with pytest.raises(ValueError):
        gain_curve([], 10, speech_db=-5, open_db=-10)
    with pytest.raises(ValueError):
        gain_curve([], 0)
