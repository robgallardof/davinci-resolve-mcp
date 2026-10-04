"""Every MCP tool end-to-end (tool -> service -> domain -> gateway) on each edition/transport.

Runs against fakes, so it proves the wiring and the Free/Studio branches, not
Resolve's rendering — that is what tests/live is for.
"""

import pytest

from conftest import Forge
from fakes import TIMELINE_START
from resolve_forge.services.appliers import FUSION_TOOL


def test_status_reports_transport_and_capabilities(forge: Forge):
    s = forge("forge_status")
    assert s["ok"] and s["version"].startswith("21") and s["timeline"] == "Master"
    assert s["transport"] in ("bridge", "direct") and s["resolution"] == "1920x1080" and s["fps"] == 30
    assert s["native_keyframes"] is forge.resolve.keyframes
    assert s["edition"] == ("Studio" if forge.resolve.studio else "Free")


def test_list_clips(forge: Forge):
    r = forge("list_clips")
    assert r["ok"] and [c["index"] for c in r["clips"]] == [1, 2] and r["timeline_start"] == TIMELINE_START


def test_catalogues_need_no_resolve():
    f = Forge(False, True, True, reachable=False)
    assert len(f("list_styles")["styles"]) >= 8
    assert {"tiktok", "reels", "shorts", "youtube_1080"} <= set(f("list_formats")["formats"])
    assert f("preview_motion", style="tiktok_punch", seconds=12)["tracks"]["zoom"]


@pytest.mark.parametrize("style", ["tiktok_punch", "tiktok_smooth", "warm_push", "youtube_dynamic",
                                   "emphasis", "handheld", "vlog_mix", "warm_pull"])
def test_apply_motion_every_style(forge: Forge, style):
    r = forge("apply_motion", style=style, anchor="talking_head", hits_s=[3.0])
    assert r["ok"], r
    expected = "keyframes" if forge.resolve.keyframes else "fusion"
    assert [c["backend"] for c in r["clips"]] == [expected, expected]
    for item in forge.items():
        if expected == "keyframes":
            assert item.keys["ZoomX"]
        else:
            assert FUSION_TOOL in item.comps[0].tools


def test_apply_motion_cuts_are_timeline_seconds(forge: Forge):
    r = forge("apply_motion", style="tiktok_punch", cuts_s=[4.0, 13.0], clips=[1, 2], backend="auto")
    assert r["ok"]
    first, second = forge.items()
    if forge.resolve.keyframes:
        assert first.keys["ZoomX"][120] == pytest.approx(1.15)   # 4 s into clip 1
        assert second.keys["ZoomX"][90] == pytest.approx(1.15)   # 13 s = 3 s into clip 2
        assert sorted({round(v, 4) for v in first.keys["ZoomX"].values()}) == [1.0, 1.15]


def test_apply_motion_subset_and_validation(forge: Forge):
    assert forge("apply_motion", style="warm_push", clips=[2])["clips"][0]["index"] == 2
    assert not forge("apply_motion", style="warm_push", clips=[9])["ok"]
    assert "unknown style" in forge("apply_motion", style="spin360")["error"]
    assert not forge("apply_motion", style="warm_push", anchor=[2, 0])["ok"]


def test_fusion_backend_forced_works_everywhere(forge: Forge):
    r = forge("apply_motion", style="warm_push", backend="fusion", anchor=[0.3, 0.3])
    assert r["ok"] and all(c["backend"] == "fusion" for c in r["clips"])


def test_clear_motion(forge: Forge):
    forge("apply_motion", style="vlog_mix")
    forge("apply_motion", style="warm_push", backend="fusion")
    removed = forge("clear_motion")["removed"]
    assert removed["fusion"] == 2
    assert removed["keyframes"] > 0 or not forge.resolve.keyframes
    assert all(not any(i.keys.values()) for i in forge.items())


def test_make_platform_version_vertical(forge: Forge):
    master = forge.project.current
    r = forge("make_platform_version", format="tiktok", subject=[0.7, 0.4])
    assert r["ok"], r
    copy = forge.project.current
    assert copy is not master and copy.name == "Master [tiktok]"
    assert (copy.settings["timelineResolutionWidth"], copy.settings["timelineResolutionHeight"]) == ("1080", "1920")
    assert master.settings["timelineResolutionWidth"] == "1920"           # master untouched
    assert master.tracks[0][0].props["ZoomX"] == 1.0
    clip = copy.tracks[0][0]
    assert clip.props["ZoomX"] == pytest.approx(3.1605, rel=1e-3) and clip.props["Pan"] < 0
    assert copy.tracks[1][0].props["ZoomX"] == 1.0                         # titles keep their sizing
    assert len(r["clips"]) == 2
    status = forge("forge_status")
    assert status["resolution"] == "1080x1920"


def test_make_platform_version_twice_names_clash(forge: Forge):
    assert forge("make_platform_version", format="reels")["ok"]
    forge.project.current = forge.project.timelines[0]
    assert "already exist" in forge("make_platform_version", format="reels")["error"]


def test_smart_reframe_only_on_studio_falls_back_on_free(forge: Forge):
    r = forge("make_platform_version", format="shorts", smart_reframe=True)
    methods = {c["method"] for c in r["clips"]}
    if forge.resolve.studio:
        assert methods == {"smart_reframe"}
    else:
        assert all(m.startswith("talking_head") or m == "face" for m in methods)


def test_render_for_and_status(forge: Forge, tmp_path):
    forge("make_platform_version", format="youtube_4k")
    r = forge("render_for", format="youtube_4k", target_dir=str(tmp_path / "out"))
    assert r["ok"] and r["started"] and (tmp_path / "out").is_dir()
    assert r["codec"] == ("H265" if forge.resolve.studio else "H264")      # Free falls back
    job = forge.project.jobs[r["job_id"]]
    assert job["CustomName"] and job["FormatWidth"] == 3840
    assert forge("render_status", job_id=r["job_id"])["JobStatus"] == "Complete"


def test_render_warns_when_timeline_does_not_match(forge: Forge, tmp_path):
    assert "make_platform_version" in forge("render_for", format="tiktok", target_dir=str(tmp_path))["warning"]


def test_errors_are_actionable_without_resolve():
    f = Forge(False, True, True, reachable=False)
    r = f("forge_status")
    assert not r["ok"] and "resolve_bridge" in r["error"] and "External scripting" in r["error"]


def test_errors_without_project_or_timeline():
    f = Forge(False, True, True)
    f.project.current = None
    assert "No current timeline" in f("list_clips")["error"]
    f.resolve.project = None
    assert "No project" in f("forge_status")["error"]


def test_list_formats_by_orientation(forge: Forge):
    vertical = forge("list_formats", orientation="vertical")["formats"]
    horizontal = forge("list_formats", orientation="horizontal")["formats"]
    assert {"tiktok", "reels", "facebook_reels", "shorts", "stories", "snapchat", "feed_4x5"} == set(vertical)
    assert {"youtube_1080", "youtube_4k", "facebook_1080", "linkedin_1080", "x_1080", "web_1080"} == set(horizontal)
    assert all(f["orientation"] == "vertical" for f in vertical.values())
    assert not forge("list_formats", orientation="diagonal")["ok"]


def test_vertical_master_to_horizontal_version():
    f = Forge(False, True, True, source=(1080, 1920))
    r = f("make_platform_version", format="facebook_1080", subject="center")
    assert r["ok"]
    clip = f.project.current.tracks[0][0]
    assert clip.props["ZoomX"] == pytest.approx((1920 / 1080) / (1080 / 1920), rel=1e-3)
    assert f("forge_status")["resolution"] == "1920x1080"


def test_render_defaults_to_free_safe_folder(forge: Forge, tmp_path, monkeypatch):
    from resolve_forge.services import render_service
    monkeypatch.setattr(render_service, "DEFAULT_OUTPUT", tmp_path / "Movies" / "resolve-forge")
    r = forge("render_for", format="youtube_1080", start=False)
    assert r["ok"] and r["file"].replace("\\", "/").split("/")[-3:-1] == ["Movies", "resolve-forge"]
