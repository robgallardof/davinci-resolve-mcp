import pytest
from resolve_forge.domain.edit_decisions import keep_ranges, onset_hits, silence_ranges
from resolve_forge.domain.fusion_graph import validate


def test_silence_merges_and_keeps_breath_margins():
    silence = silence_ranges([-10, -50, -50, -50, -10, -50], .1, minimum_s=.2)
    assert len(silence) == 1 and silence[0] == pytest.approx([.1, .4])
    assert keep_ranges(1, silence, .05) == [[0, .15000000000000002], [.35000000000000003, 1]]


def test_overlapping_removals_are_unified_and_bounded():
    assert keep_ranges(10, [[-2, 3], [2, 5], [8, 20]], 0) == [[5, 8]]
    assert keep_ranges(10, [], 0) == [[0, 10]]
    assert keep_ranges(10, [[0, 10]], 0) == []


def test_onsets_respect_minimum_gap():
    assert onset_hits([-50, -10, -50, -10, -50, -10], .1, .3) == [.1, .5]


def test_graph_rejects_cycles_and_duplicate_input_connections():
    nodes = [{"id": "a", "type": "Transform"}, {"id": "b", "type": "Blur"}]
    with pytest.raises(ValueError, match="cycles"):
        validate(nodes, [["a", "b", "Input"], ["b", "a", "Input"]])
    with pytest.raises(ValueError, match="exactly one"):
        validate(nodes, [["a", "MediaOut1", "Input"], ["b", "MediaOut1", "Input"]])
    with pytest.raises(ValueError, match="palette"):
        validate([{"id": "loader", "type": "Loader"}], [])


def test_graph_accepts_a_connected_effect_chain():
    nodes = [{"id": "scale", "type": "Transform", "inputs": {"Size": 1.2}}]
    edges = [["MediaIn1", "scale", "Input"], ["scale", "MediaOut1", "Input"]]
    assert validate(nodes, edges) == (nodes, edges)
