import pytest

from resolve_forge.domain.grade_presets import PRESETS, parameters
from resolve_forge.services import grade_preset_service


@pytest.mark.parametrize("preset", PRESETS)
def test_strength_zero_is_identity_and_one_is_preset(preset):
    assert parameters(preset, 0) == {"slope": [1.] * 3, "offset": [0.] * 3, "power": [1.] * 3, "saturation": 1.}
    assert parameters(preset, 1) == PRESETS[preset]


@pytest.mark.parametrize("strength", [-.1, 1.1, float("nan"), float("inf"), True, "0.5"])
def test_invalid_strength_rejected(strength):
    with pytest.raises(ValueError):
        parameters("natural", strength)


def test_service_delegates_copy_and_preview_to_existing_grade(monkeypatch):
    calls = []
    monkeypatch.setattr(grade_preset_service.color_service, "grade", lambda session, **kwargs: calls.append(kwargs) or {"applied": False})
    result = grade_preset_service.apply(None, "warm", .25, indices=[2], copy_name="review")
    assert not result["applied"]
    assert calls[0]["dry_run"] is True
    assert calls[0]["copy_name"] == "review"
    assert calls[0]["indices"] == [2]
    assert calls[0]["slope"] == parameters("warm", .25)["slope"]
