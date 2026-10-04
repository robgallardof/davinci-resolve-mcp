import pytest

from resolve_forge.domain.production import plan


def orders(**kwargs):
    return plan("An interview with relevant photos and reactions", "interview", "reels", 20,
                [dict(id="talk", path="talk.mp4", role="dialogue", start_s=3, end_s=23),
                 dict(id="photo", path="memory.jpg", role="context", kind="image")], **kwargs)


def test_multiple_sources_do_not_force_grid_or_treat_photo_as_second_speaker():
    result = orders()
    assert result["composition"]["choice"] == "adaptive"
    assert result["tasks"][0]["inputs"][1]["kind"] == "image"
    assert all(t["mutation_owner"] == "producer coordinator only" for t in result["tasks"])
    positions = {name: index for index, name in enumerate(result["mutation_order"])}
    for task in result["tasks"]:
        assert all(positions[dep] < positions[task["id"]] for dep in task["depends_on"])
    assert result["tasks"][-1]["agent_role"] == "qa-editor"


def test_grid_needs_motive_and_references_remain_observations():
    with pytest.raises(ValueError, match="why simultaneous"):
        orders(composition="grid")
    result = orders(composition="grid", composition_reason="Show the interview alongside contextual photo",
                    references=[dict(path="reference.png", observations="Four differently sourced panels",
                                     adaptation="Use only during the relevant answer")])
    assert result["composition"]["reason"]
    assert "not independent" in result["tasks"][0]["context"]["references"][0]["status"]
    assert "neither spawns" in result["execution_contract"]


@pytest.mark.parametrize("source", [
    dict(id="a", path="a.wav", kind="audio", role="voice", start_s=0, end_s=10),
    dict(id="a", path="a.mp4", role="voice", start_s=float("nan"), end_s=10),
    dict(id="a", path="a.mp4", role="voice", start_s=True, end_s=10),
    dict(id="a", path="a.mp4", role="voice", start_s=10, end_s=3),
])
def test_invalid_sources_do_not_create_executable_work_orders(source):
    with pytest.raises(ValueError):
        plan("A story", "vlog", "reels", 10, [source])
