import pytest

from resolve_forge.domain import beat_cuts, editorial
from resolve_forge.domain.story_moments import KIND_BY_SIGNAL, candidates
from resolve_forge.domain.transcript import Word


def joke():
    # setup ... 1.2 s comic pause ... short punchline, then 1 s of laughter (no words).
    return [Word("So", 0, .3), Word("my", .3, .5), Word("dog", .5, .9), Word("learned", .9, 1.3), Word("taxes.", 1.3, 1.8),
            Word("He", 3.0, 3.2), Word("owes", 3.2, 3.6), Word("me.", 3.6, 4.0),
            Word("Questions?", 6.0, 6.6)]


def envelope(step=.05, seconds=7):
    levels = [-80.0] * int(seconds / step)
    for word in joke():
        for i in range(int(word.start / step), int(word.end / step)):
            levels[i] = -20.0
    for i in range(int(4.1 / step), int(5.1 / step)):  # laughter after the punchline
        levels[i] = -22.0
    return levels


def test_comedy_candidates_find_pause_punchline_and_reaction_with_evidence():
    moments = candidates(joke(), envelope(), .05, "comedy")
    by_kind = {m["kind"]: m for m in moments}
    assert by_kind["punchline"]["time_s"] == 3.0 and "pause" in by_kind["punchline"]["evidence"]
    assert 4.0 <= by_kind["reaction"]["time_s"] <= 4.2 and by_kind["reaction"]["text"] == "He owes me."
    assert by_kind["setup"]["text"] == "Questions?"
    assert moments == sorted(moments, key=lambda m: m["time_s"])
    assert all(0 <= m["score"] <= 1 for m in moments)


def test_candidate_kinds_are_valid_story_beats_for_plan_edit():
    for content_type, kinds in KIND_BY_SIGNAL.items():
        assert set(kinds.values()) <= set(editorial.RECIPES[content_type]["moments"])
    with pytest.raises(ValueError, match="analyse_music"):
        candidates(joke(), [], .05, "music")


def test_candidates_without_audio_still_use_transcript_timing():
    moments = candidates(joke(), [], .05, "interview")
    assert {m["signal"] for m in moments} == {"pause_line", "question"}


def test_beat_slots_follow_phrases_and_speed_up_only_in_confirmed_ranges():
    beats = [round(i * .5, 3) for i in range(40)]  # 120 BPM
    calm = beat_cuts.slots(beats, 0, 8)
    assert calm == [[0, 2], [2, 4], [4, 6], [6, 8]]
    mixed = beat_cuts.slots(beats, .1, 8, intense=[[4, 8]])
    assert mixed == [[0, 2], [2, 4], [4, 5], [5, 6], [6, 7], [7, 8]]
    for a, b in zip(mixed, mixed[1:]):
        assert a[1] == b[0]  # contiguous: the music never jumps


def test_beat_slot_validation():
    with pytest.raises(ValueError):
        beat_cuts.slots([1.0], 0, 4)
    with pytest.raises(ValueError):
        beat_cuts.slots([0, .5, 1], 0, 4, beats_per_cut=0)
    with pytest.raises(ValueError):
        beat_cuts.slots([0, .5, 1], 0, 4, intense=[[2, 1]])


def test_fill_trims_cycles_and_continues_unused_footage_without_stretching():
    slots = [[0, 2], [2, 4], [4, 5], [5, 6]]
    shots = [dict(source="a", start_s=10, end_s=13.5), dict(source="b", start_s=0, end_s=1.5)]
    out = beat_cuts.fill(shots, slots)
    assert [(s["source"], s["start_s"], s["end_s"]) for s in out] == [
        ("a", 10, 12), ("a", 10, 12), ("b", 0, 1), ("a", 12, 13)]
    with pytest.raises(ValueError, match="long enough"):
        beat_cuts.fill([dict(source="b", start_s=0, end_s=1)], [[0, 2]])
