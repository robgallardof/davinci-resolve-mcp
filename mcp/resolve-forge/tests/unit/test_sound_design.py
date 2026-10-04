import pytest

from resolve_forge.domain.sound_design import cues, density_warnings, lanes


def test_cues_need_a_reason_and_are_sorted_with_default_gain():
    out = cues([dict(time_s=3, source="hit.wav", reason="remate confirmado"),
                dict(time_s=1, source="whoosh.wav", reason="cambio de sección", gain_db=-12)])
    assert [c["time_s"] for c in out] == [1, 3] and out[1]["gain_db"] == -8
    for bad in [dict(time_s=1, source="a.wav"), dict(time_s=-1, source="a", reason="x"),
                dict(time_s=1, source="a", reason="x", gain_db=20), dict(time_s=float("nan"), source="a", reason="x")]:
        with pytest.raises(ValueError):
            cues([bad])


def test_density_flags_stacked_and_automatic_effects():
    sparse = cues([dict(time_s=t, source="a", reason="r") for t in (0, 5, 10)])
    assert density_warnings(sparse) == []
    dense = cues([dict(time_s=t, source="a", reason="r") for t in (0, .3, 1, 1.5, 2)])
    warnings = density_warnings(dense)
    assert any("under" in w for w in warnings) and any("automatic" in w for w in warnings)


def test_overlapping_sounds_get_separate_lanes():
    assert lanes([(0, 10), (5, 15), (12, 20), (16, 30)]) == [0, 1, 0, 1]
