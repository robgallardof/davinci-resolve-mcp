"""Own tool contracts across native and JSON bridge fakes; copies must preserve the source."""
import pytest


def test_clip_edit_dry_run_and_copy_isolation(forge):
    source = forge.project.current
    before = [dict(item.props) for item in source.tracks[0]]
    preview = forge("edit_clips", properties={"ZoomX": 1.3}, indices=[2])
    assert preview["ok"] and not preview["applied"] and forge.project.current is source
    result = forge("edit_clips", properties={"ZoomX": 1.3}, indices=[2], dry_run=False, copy_name="Own edit")
    assert result["ok"], result
    assert forge.project.current is not source
    assert forge.items()[1].props["ZoomX"] == 1.3
    assert [item.props for item in source.tracks[0]] == before


@pytest.mark.parametrize("properties", [{"ZoomX": float("inf")}, {"Opacity": 200}, {"Execute": 1}, {"ZoomX": -2}])
def test_invalid_edits_do_not_create_versions(forge, properties):
    count = len(forge.project.timelines)
    result = forge("edit_clips", properties=properties, dry_run=False)
    assert result["code"] == "INVALID_ARGUMENT"
    assert len(forge.project.timelines) == count


def test_markers_use_relative_frames_and_protect_original(forge):
    source = forge.project.current
    result = forge("timeline_markers", entries=[{"seconds": 2, "name": "Hook"}], dry_run=False)
    assert result["ok"], result
    assert source.markers == {}
    assert 60 in forge.project.current.markers  # 2 s * 30 fps, independent of start timecode
    assert forge("timeline_markers", entries=[{"seconds": 2}], dry_run=False)["code"] == "INVALID_ARGUMENT"


def test_track_readback_and_version_name_collision(forge):
    result = forge("configure_track", track_name="Dialogue", locked=True, dry_run=False, copy_name="Tracks")
    assert result["ok"], result
    assert forge.project.current.GetTrackName("video", 1) == "Dialogue"
    assert forge("timeline_versions", action="duplicate", timeline_name="Tracks")["code"] == "TIMELINE_EXISTS"


def test_refused_write_is_not_success(forge):
    from unittest.mock import patch
    from fakes import TimelineItem
    with patch.object(TimelineItem, "SetProperty", return_value=False):
        result = forge("edit_clips", properties={"ZoomX": 1.2}, dry_run=False)
    assert not result["ok"] and result["code"] == "RESOLVE_REFUSED"


def test_media_import_is_idempotent_and_restores_current_bin(forge, tmp_path):
    source = tmp_path / "recording.mov"
    source.write_bytes(b"sample")
    pool = forge.project.pool
    previous = pool.GetCurrentFolder()
    result = forge("ingest_media", paths=[str(source), str(source)], dry_run=False)
    assert result["ok"] and len(result["imported"]) == 1
    assert pool.GetCurrentFolder() is previous
    repeat = forge("ingest_media", paths=[str(source)], dry_run=False)
    assert repeat["ok"] and repeat["already_present"] == 1
    read = forge("media_metadata", source=str(source), values={"Comments": "Interview"}, dry_run=False)
    assert read["ok"], read


def test_audit_and_capabilities_are_read_only(forge):
    source = forge.project.current
    audit = forge("audit_timeline")
    assert audit["ok"] and audit["clips"]["video"] == 3
    capability = forge("list_capabilities")
    assert capability["ok"]
    assert capability["capabilities"]["native_motion_keyframes"]["supported"] == forge.resolve.keyframes
    assert forge.project.current is source


def test_unsupported_native_ai_refuses_before_copy(forge):
    count = len(forge.project.timelines)
    result = forge("native_ai", action="subtitles", dry_run=False)
    assert result["code"] == "BACKEND_UNSUPPORTED" and len(forge.project.timelines) == count


def test_project_save_and_inspect(forge):
    assert forge("project_workflow", action="save")["saved"]
    assert forge("project_workflow", action="inspect")["timelines"][0]["name"] == "Master"


def test_fusion_graph_writes_inputs_after_unlock_and_preserves_source(forge):
    source = forge.project.current
    result = forge("apply_fusion_graph", nodes=[{"id": "zoom", "type": "Transform", "inputs": {"Size": 1.2}}],
                   edges=[["MediaIn1", "zoom", "Input"], ["zoom", "MediaOut1", "Input"]], dry_run=False)
    assert result["ok"], result
    comp = forge.items()[0].comps[0]
    assert comp.tools["Forge_zoom"].static["Size"] == 1.2
    assert not comp.locked and comp.writes_under_lock == 0
    assert source.tracks[0][0].comps == []


def test_same_named_sources_are_never_guessed(forge):
    from fakes import MediaPoolItem
    first = MediaPoolItem("same.mov", path="C:/camera-a/same.mov")
    second = MediaPoolItem("same.mov", path="C:/camera-b/same.mov")
    forge.project.pool.root.clips.extend([first, second])
    result = forge("media_metadata", source="same.mov")
    assert result["code"] == "AMBIGUOUS_SOURCE"


def test_original_motion_tool_creates_a_working_copy_and_reuses_it(forge):
    source = forge.project.current
    result = forge("apply_motion", style="warm_push", anchor="center")
    assert result["ok"], result
    working = forge.project.current
    assert working is not source
    assert source.tracks[0][0].props["ZoomX"] == 1
    assert source.tracks[0][0].keys == {} and source.tracks[0][0].comps == []
    assert forge("apply_motion", style="warm_pull", anchor="center")["ok"]
    assert forge.project.current is working


@pytest.mark.parametrize("retains_value", [True, False])
def test_void_fusion_setters_require_matching_readback(forge, retains_value):
    from unittest.mock import patch
    from fakes import FusionTool
    original = FusionTool.SetInput
    def setter(tool, key, value):
        if retains_value:
            original(tool, key, value)
        return None
    with patch.object(FusionTool, "SetInput", setter):
        result = forge("apply_fusion_graph", nodes=[{"id": "readback", "type": "Transform", "inputs": {"Size": 1.2}}],
                       edges=[["MediaIn1", "readback", "Input"], ["readback", "MediaOut1", "Input"]], dry_run=False)
    assert result["ok"] == retains_value
    if not retains_value:
        assert result["code"] == "READBACK_FAILED"


def test_media_organisation_is_idempotent(forge, tmp_path):
    source = tmp_path / "take.mov"
    source.write_bytes(b"sample")
    assert forge("ingest_media", paths=[str(source)], dry_run=False)["ok"]
    assert forge("organise_media", dry_run=False)["moves"] == 1
    repeated = forge("organise_media", dry_run=False)
    assert repeated["ok"] and repeated["moves"] == 0
