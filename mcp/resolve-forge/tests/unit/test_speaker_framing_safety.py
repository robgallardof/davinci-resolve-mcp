import pytest
from resolve_forge.domain import layouts
from resolve_forge.services.speaker_layout_service import _graph


def test_five_people_are_all_visible_in_vertical_split():
    faces = [(i * .18, .2, i * .18 + .1, .4) for i in range(5)]
    plan = layouts.layout_plan(faces, [(0, (0, 1, 2, 3, 4))], 5, 1080, 1920, 16/9)
    assert [p['person'] for p in plan[0]['panels']] == list(range(5))
    rects = layouts.panels(5, 1080, 1920)
    assert sum((x1-x0)*(y1-y0) for x0,y0,x1,y1 in rects) == pytest.approx(1)
    for face, panel in zip(faces, plan[0]['panels']):
        x0,y0,x1,y1 = panel['crop']
        assert x0 <= face[0] and y0 <= face[1] and x1 >= face[2] and y1 >= face[3]


def test_impossible_portrait_crop_preserves_full_face_and_group():
    faces = [(.05, .1, .45, .8), (.55, .1, .95, .8)]
    assert layouts.crop_for(faces[0], 9/16, 16/9) == (0,0,1,1)
    plan = layouts.layout_plan(faces, [], 5, 1080, 1920, 16/9)
    assert plan[0]['panels'][0]['crop'] == (0,0,1,1)
    graph = _graph(plan, 1920, 1080, 1080, 1920, 30)
    assert 'force_original_aspect_ratio=decrease' in graph and 'pad=1080:1920' in graph


def test_brief_listening_pause_holds_speaker_then_switches():
    plan = layouts.segments([(0, (0,)), (2, ()), (2.3, (1,)), (4.3, ())], 6, people=2)
    assert [s['people'] for s in plan] == [[0],[1]]
    assert plan[1]['start_s'] == 2.3


def test_late_first_sample_still_covers_start_of_clip():
    plan = layouts.segments([(2,(1,))], 5, people=2)
    assert plan[0]['start_s'] == 0 and plan[-1]['end_s'] == 5


@pytest.mark.parametrize('samples', [[(1,(0,)),(0,(1,))], [(0,(2,))], [(5,(0,))]])
def test_invalid_speaker_evidence_is_rejected(samples):
    with pytest.raises(ValueError):
        layouts.segments(samples, 5, people=2)


def test_audio_failure_cannot_invent_a_speaker(monkeypatch):
    from resolve_forge.analysis import speakers, audio_events
    def fail(*args, **kwargs):
        raise RuntimeError('missing audio')
    monkeypatch.setattr(audio_events, 'levels', fail)
    assert speakers._voice('missing.mp4', [0, .25], .25) == [False, False]


def test_continuous_dialogue_energy_is_not_rejected_without_silence(monkeypatch):
    from resolve_forge.analysis import speakers, audio_events
    monkeypatch.setattr(audio_events, 'levels', lambda *a, **kw: ([-20] * 8, None, .25))
    assert speakers._voice('dialogue.mp4', [0, .25, .5], .25) == [True] * 3
    monkeypatch.setattr(audio_events, 'levels', lambda *a, **kw: ([-60] * 8, None, .25))
    assert speakers._voice('silence.mp4', [0, .25], .25) == [False] * 2


def test_split_panel_graph_starts_at_origin():
    plan = layouts.layout_plan([(.1,.2,.2,.4),(.7,.2,.8,.4)], [(0,(0,1))], 5, 1080,1920,16/9)
    assert 'layout=0_0|0_960' in _graph(plan,1920,1080,1080,1920,30)
