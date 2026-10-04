import pytest

from resolve_forge.domain import look, text_placement


def stats(**over):
    base = dict(luma=0.5, p2=0.04, p98=0.9, saturation=0.3, r=0.5, g=0.5, b=0.5)
    return [{**base, **over}] * 3


def test_good_footage_needs_no_grade():
    assert look.assess(stats()) == {"issues": [], "cdl": None,
                                    "summary": {"luma": 0.5, "p2": 0.04, "p98": 0.9, "saturation": 0.3, "r": 0.5, "g": 0.5, "b": 0.5}}
    assert look.assess([])["cdl"] is None


@pytest.mark.parametrize("over,word,check", [
    (dict(luma=0.25, p98=0.6), "underexposed", lambda c: c["slope"][0] > 1.2),
    (dict(luma=0.7, p98=0.995), "bright", lambda c: c["slope"][0] < 1),
    (dict(p2=0.3, p98=0.7), "flat", lambda c: c["offset"][0] < 0),
    (dict(saturation=0.1), "dull", lambda c: c["saturation"] > 1),
    (dict(r=0.6, g=0.5, b=0.42), "cast", lambda c: c["offset"][0] < 0 < c["offset"][2]),
])
def test_problems_get_a_gentle_correction(over, word, check):
    result = look.assess(stats(**over))
    assert any(word in issue for issue in result["issues"]) and check(result["cdl"])
    assert 0.8 <= result["cdl"]["slope"][0] <= 1.4 and all(abs(o) <= 0.1 for o in result["cdl"]["offset"])


def test_text_moves_away_from_faces_and_reports_conflicts():
    boxes = {"top": (0.2, 0.15, 0.8, 0.22), "bottom": (0.2, 0.7, 0.8, 0.77), "middle": (0.2, 0.45, 0.8, 0.52)}
    face_top = [(0.4, 0.12, 0.6, 0.3)]
    assert text_placement.choose(boxes, face_top, "top") == ("bottom", ["top text covers a face/subject"])
    assert text_placement.choose(boxes, [], "top") == ("top", [])
    position, conflicts = text_placement.choose(boxes, [(0, 0, 1, 1)], "top")
    assert position == "top" and "no position is free" in conflicts[-1]
