"""Project lifecycle, settings, color, gallery, sync, native AI and interchange through the MCP surface."""

from pathlib import Path

import pytest


def test_grade_previews_then_applies_cdl_and_lut_only_to_a_copy(forge, tmp_path):
    lut = tmp_path / "look.cube"
    lut.write_text("LUT_3D_SIZE 2\n" + "0 0 0\n" * 8, encoding="utf-8")
    master = forge.project.current
    preview = forge("grade_clips", slope=[1.1, 1, .9], saturation=1.2, lut_path=str(lut))
    assert preview["ok"] and not preview["applied"] and preview["cdl"]["Slope"] == "1.1 1.0 0.9"
    assert all(not item.cdl for item in master.tracks[0])
    result = forge("grade_clips", slope=[1.1, 1, .9], saturation=1.2, lut_path=str(lut), dry_run=False)
    assert result["ok"] and result["applied"] and result["clips"] == 2
    copy = forge.project.current
    assert copy is not master and all(not item.cdl and not item.luts for item in master.tracks[0])
    assert all(item.cdl[-1]["Saturation"] == "1.2" and item.luts[1] == str(lut.resolve()) for item in copy.tracks[0])
    graph = forge("inspect_grade", index=1)
    assert graph["ok"] and graph["nodes"][0]["lut"] == str(lut.resolve())


@pytest.mark.parametrize("args", [dict(slope=[1, 1]), dict(power=[0, 1, 1]), dict(saturation=-1), dict(node=0),
                                  dict(lut_path="missing.cube"), dict(slope=[float("nan"), 1, 1])])
def test_invalid_grades_are_rejected_without_copies(forge, args):
    count = len(forge.project.timelines)
    assert forge("grade_clips", dry_run=False, **args)["code"] == "INVALID_ARGUMENT"
    assert len(forge.project.timelines) == count


def test_gallery_capture_label_and_export_never_overwrite(forge, tmp_path):
    assert forge("gallery_stills")["albums"] == [{"name": "Stills 1", "stills": 0}]
    assert forge("gallery_stills", action="export", output_dir=str(tmp_path / "empty"))["code"] == "INVALID_ARGUMENT"
    captured = forge("gallery_stills", action="capture", label="look A")
    assert captured["ok"] and forge.project.gallery.album.labels == {1: "look A"}
    exported = forge("gallery_stills", action="export", output_dir=str(tmp_path / "stills"))
    assert exported["ok"] and len(exported["files"]) == 1 and Path(exported["files"][0]).is_file()
    again = forge("gallery_stills", action="export", output_dir=str(tmp_path / "stills"))
    assert again["code"] == "INVALID_ARGUMENT"
    assert forge("gallery_stills", action="delete")["code"] == "INVALID_ARGUMENT"


def test_sync_resolves_each_source_once_and_uses_the_native_constant(forge, tmp_path):
    files = [tmp_path / "cam.mp4", tmp_path / "mic.wav"]
    for f in files:
        f.write_bytes(b"x")
    forge.project.pool.ImportMedia([str(f) for f in files])
    preview = forge("sync_audio", sources=["cam.mp4", str(files[1])])
    assert preview["ok"] and preview["applied"] is False and not hasattr(forge.project.pool, "synced")
    result = forge("sync_audio", sources=["cam.mp4", "mic.wav"], mode="timecode", dry_run=False)
    assert result["ok"] and forge.project.pool.synced == (["cam.mp4", "mic.wav"], {"audioSyncMode": 1})
    assert forge("sync_audio", sources=["cam.mp4", "cam.mp4"])["code"] == "INVALID_ARGUMENT"
    assert forge("sync_audio", sources=["cam.mp4", "ghost.wav"])["code"] == "INVALID_ARGUMENT"
    assert forge("sync_audio", sources=["cam.mp4", "mic.wav"], mode="phase")["code"] == "INVALID_ARGUMENT"


def test_project_create_load_list_and_backup_without_overwrite(forge, tmp_path):
    created = forge("project_workflow", action="create", project_name="Cliente A")
    assert created["ok"] and created["project"] == "Cliente A"
    assert forge("project_workflow", action="create", project_name="Cliente A")["code"] == "RESOLVE_REFUSED"
    assert "Cliente A" in forge("project_workflow", action="list")["projects"]
    assert forge("project_workflow", action="load", project_name="Cliente A")["project"] == "Cliente A"
    backup = tmp_path / "cliente.drp"
    result = forge("project_workflow", action="backup", output_path=str(backup))
    assert result["ok"] and backup.is_file() and result["bytes"] > 0
    assert forge("project_workflow", action="backup", output_path=str(backup))["code"] == "INVALID_ARGUMENT"
    assert forge("project_workflow", action="backup", output_path=str(tmp_path / "x.zip"))["code"] == "INVALID_ARGUMENT"
    assert forge("project_workflow", action="create", project_name="bad\nname")["code"] == "INVALID_ARGUMENT"
    assert forge("project_workflow", action="destroy")["code"] == "INVALID_ARGUMENT"


def test_project_settings_preview_apply_and_refusal(forge):
    preview = forge("configure_project", settings={"timelineFrameRate": 25})
    assert preview["ok"] and preview["before"] == {"timelineFrameRate": "30"} and not preview["applied"]
    assert forge.project.settings["timelineFrameRate"] == "30"
    applied = forge("configure_project", settings={"timelineFrameRate": 25}, dry_run=False)
    assert applied["ok"] and forge.project.settings["timelineFrameRate"] == "25"
    assert forge("configure_project", settings={"readOnlySetting": 1}, dry_run=False)["code"] == "RESOLVE_REFUSED"
    assert forge("configure_project", settings={})["code"] == "INVALID_ARGUMENT"
    assert forge("configure_project", settings={"x": [1]})["code"] == "INVALID_ARGUMENT"


def test_native_ai_runs_on_a_copy_when_the_build_supports_it(forge):
    forge.resolve.native_ai = True
    master = forge.project.current
    preview = forge("native_ai", action="subtitles")
    assert preview["ok"] and preview["targets"] == 1 and not preview["applied"]
    result = forge("native_ai", action="subtitles", dry_run=False)
    assert result["ok"] and result["applied"] and forge.project.current is not master
    assert forge.project.current.__dict__.get("subtitled") and not master.__dict__.get("subtitled")
    assert forge("native_ai", action="dance")["code"] == "INVALID_ARGUMENT"


def test_timeline_versions_create_select_and_duplicate(forge):
    names = [t["name"] for t in forge("timeline_versions")["timelines"]]
    assert names == ["Master"]
    assert forge("timeline_versions", action="create", timeline_name="Corte 2")["ok"]
    assert forge("timeline_versions", action="select", timeline_name="Master")["timeline"] == "Master"
    assert forge("timeline_versions", action="select", timeline_name="Nope")["code"] == "INVALID_ARGUMENT"
    duplicated = forge("timeline_versions", action="duplicate", timeline_name="Master v2")
    assert duplicated["ok"] and duplicated["timeline"] == "Master v2"
    current = [t for t in forge("timeline_versions")["timelines"] if t["current"]]
    assert [t["name"] for t in current] == ["Master v2"]
    assert forge("timeline_versions", action="purge")["code"] == "INVALID_ARGUMENT"


def test_interchange_exports_a_new_file_and_refuses_unknown_or_existing(forge, tmp_path):
    out = tmp_path / "cut.otio"
    result = forge("export_interchange", output_path=str(out))
    assert result["ok"] and out.read_text(encoding="utf-8") == "otio:Master"
    assert forge("export_interchange", output_path=str(out))["code"] == "INVALID_ARGUMENT"
    assert forge("export_interchange", output_path=str(tmp_path / "cut.edl"), format_name="otio")["code"] == "INVALID_ARGUMENT"
    assert forge("export_interchange", output_path=str(tmp_path / "cut.aaf"), format_name="aaf")["code"] == "BACKEND_UNSUPPORTED"
    assert forge("export_interchange", output_path=str(tmp_path / "cut.mov"), format_name="mov")["code"] == "INVALID_ARGUMENT"
