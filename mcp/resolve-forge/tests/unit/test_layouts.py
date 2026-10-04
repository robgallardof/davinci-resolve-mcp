import pytest

from resolve_forge.domain import layouts


def test_panels_follow_orientation():
    assert layouts.panels(2, 1080, 1920) == [(0, 0, 1, .5), (0, .5, 1, 1)]   # vertical: stacked
    assert layouts.panels(2, 1920, 1080) == [(0, 0, .5, 1), (.5, 0, 1, 1)]   # horizontal: side by side
    three = layouts.panels(3, 1080, 1920)
    assert three[2] == (0, .5, 1, 1) and three[0][3] == .5                    # two on top, one below
    assert len(layouts.panels(4, 1080, 1920)) == 4


def test_crop_keeps_the_face_in_the_upper_third_with_panel_aspect_and_inside_the_source():
    face = (0.70, 0.30, 0.80, 0.45)
    x0, y0, x1, y1 = layouts.crop_for(face, panel_aspect=1080 / 960, source_aspect=16 / 9)
    assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
    assert ((x1 - x0) * 16) / ((y1 - y0) * 9) == pytest.approx(1080 / 960, rel=0.01)
    assert x0 <= 0.70 and x1 >= 0.80 and y0 <= 0.30 and y1 >= 0.45          # the whole face is inside
    assert (0.375 - y0) / (y1 - y0) < 0.45                                    # face centre in the upper part


def test_segments_follow_the_speaker_split_on_overlap_and_never_flicker():
    active = [(t * 0.5, (0,)) for t in range(8)] + [(4 + t * 0.5, (0, 1)) for t in range(6)] \
        + [(7 + t * 0.5, (1,)) for t in range(6)] + [(10, (0,)), (10.5, (1,))]
    segs = layouts.segments(active, 11.0, people=2)
    assert [s["layout"] for s in segs] == ["single", "split", "single"]
    assert segs[0]["people"] == [0] and segs[1]["people"] == [0, 1] and segs[2]["people"] == [1]
    assert all(s["end_s"] - s["start_s"] >= 1.5 for s in segs)
    assert segs[-1]["end_s"] == 11.0                                          # 0.5 s blips were absorbed
    assert {s["layout"] for s in layouts.segments(active, 11.0, people=2, mode="split")} == {"split"}
    assert layouts.segments([], 5.0, people=2)[0]["layout"] == "wide"
    with pytest.raises(ValueError):
        layouts.segments(active, 11.0, people=2, mode="grid")


def test_people_are_clustered_left_to_right():
    boxes = [(0.1, 0.3, 0.2, 0.45)] * 5 + [(0.7, 0.3, 0.8, 0.45)] * 6 + [(0.12, 0.31, 0.21, 0.46)] * 4
    people = layouts.cluster_people(boxes)
    assert len(people) == 2 and people[0][0] < people[1][0]
