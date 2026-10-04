import pytest

from resolve_forge.domain.energize import Sample, ZOOM, dead_ranges, focus_pivot, plan


def scene(seconds=20, step=0.25, quiet=(), peaks=(), at=(0.8, 0.7), spread=0.1, camera=()):
    out = []
    for i in range(int(seconds / step)):
        t = i * step
        energy = 0.05 if any(a <= t < b for a, b in quiet) else 1.0
        if any(abs(t - p) < 0.13 for p in peaks):
            energy = 6.0
        moving = any(a <= t < b for a, b in camera)
        out.append(Sample(round(t, 3), 4.0 if moving else energy, *at, 0.45 if moving else spread))
    return out


def test_pivot_pulls_the_subject_to_the_centre_and_never_reveals_edges():
    z = 1.5
    for subject in (0.0, 0.1, 0.5, 0.8, 1.0):
        p = focus_pivot(subject, z)
        assert 0 <= p <= 1
        on_screen = p + z * (subject - p)
        assert abs(on_screen - 0.5) <= abs(subject - 0.5) + 1e-9  # closer to (or as close to) the centre
    assert focus_pivot(0.7, 1.0) == 0.5


def test_dead_time_is_found_and_trimmed_from_the_story():
    samples = scene(20, quiet=[(8, 12)])
    assert dead_ranges(samples) == [(8.0, 12.0)]
    result = plan(samples)
    assert result["removed_dead_s"] == [[8.0, 12.0]]
    assert all(not (8 < s["start_s"] < 12) for s in result["shots"])
    assert result["duration_s"] == pytest.approx(16, abs=0.01)


def test_shots_are_short_and_framings_never_repeat_back_to_back():
    result = plan(scene(30), max_shot_s=2.8, min_shot_s=1.2)
    shots = result["shots"]
    assert all(1.2 - 1e-6 <= s["end_s"] - s["start_s"] <= 2.8 + 1e-6 for s in shots)
    assert all(a["framing"] != b["framing"] for a, b in zip(shots, shots[1:]))
    assert shots[0]["framing"] == "wide"
    assert all(a["end_s"] == b["start_s"] for a, b in zip(shots, shots[1:]))  # no gaps inside a range


def test_action_peaks_get_crash_zooms_aimed_at_the_action():
    result = plan(scene(12, peaks=[5.0]))
    crash = [s for s in result["shots"] if s["framing"] == "crash"]
    assert crash and crash[0]["start_s"] <= 5.0 < crash[0]["end_s"] and crash[0]["hit_s"] == pytest.approx(5.0)
    assert crash[0]["zoom"] == ZOOM["crash"] and crash[0]["subject"] == [0.8, 0.7]
    assert crash[0]["anchor"][0] > 0.8  # pivot beyond the subject pulls it toward the centre


def test_camera_moves_stay_wide_and_calm_faces_become_reaction_closeups():
    result = plan(scene(12, camera=[(3, 6)]), ranges=[[0, 12]])
    moving = [s for s in result["shots"] if 3 <= (s["start_s"] + s["end_s"]) / 2 < 6]
    assert moving and all(s["framing"] in ("wide", "medium") for s in moving)
    calm = [Sample(t / 4, 0.3, 0.5, 0.8, 0.1) for t in range(48)]
    faces = [(t / 2, 0.6, 0.4) for t in range(24)]
    reaction = plan(calm, faces=faces, trim_dead=False)["shots"]
    assert any(s["framing"] == "close" and s["subject"] == [0.6, 0.4] and "reaction" in s["why"] for s in reaction)


def test_zoom_cap_and_validation():
    capped = plan(scene(12, peaks=[5.0]), max_zoom=1.2)
    assert max(s["zoom"] for s in capped["shots"]) <= 1.2
    for kwargs in (dict(min_shot_s=3, max_shot_s=2), dict(max_zoom=3), dict(ranges=[[5, 2]])):
        with pytest.raises(ValueError):
            plan(scene(10), **kwargs)
    with pytest.raises(ValueError):
        plan([])


def test_crash_zoom_and_focus_hold_styles():
    from resolve_forge.domain import styles
    crash = styles.build("crash_zoom", duration=60, fps=30, hits=[20], intensity=1.0)
    zoom = crash.track("zoom")
    assert zoom.keyframes[0].value == 1.0 and crash.peak_zoom() == pytest.approx(1.45 * 1.03, rel=1e-3)
    assert [k.frame for k in zoom.keyframes][:3] == [0, 20, 25]  # holds, then punches in 5 frames at the hit
    hold = styles.build("focus_hold", duration=60, fps=30, intensity=2.0)
    assert hold.track("zoom").keyframes[0].value == pytest.approx(1.5)


def test_editor_hints_aim_at_the_real_subject_and_force_framings():
    """The detector follows the biggest motion (the person); a hint after watching aims at the pet instead."""
    samples = scene(12, at=(0.2, 0.4))  # person moving on the left
    hinted = plan(samples, hints=[{"start_s": 0, "end_s": 6, "focus": [0.8, 0.72]},
                                  {"start_s": 6, "end_s": 12, "framing": "wide"}])
    first = [s for s in hinted["shots"] if s["end_s"] <= 6.2]
    assert first and all(s["subject"] == [0.8, 0.72] and s["framing"] != "wide" for s in first)
    assert all(s["framing"] == "wide" for s in hinted["shots"] if s["start_s"] >= 6)
    for bad in ({"start_s": 3, "end_s": 1}, {"start_s": 0, "end_s": 1, "focus": [2, 0]},
                {"start_s": 0, "end_s": 1, "framing": "dolly"}):
        with pytest.raises(ValueError):
            plan(samples, hints=[bad])


def test_self_review_downgrades_bad_zooms_and_respects_source_sharpness():
    from resolve_forge.domain import framing_review as review
    # visible rect / on-screen maths
    assert review.visible(2.0, (0.5, 0.5)) == (0.25, 0.25, 0.75, 0.75)
    assert review.on_screen((0.75, 0.5), 2.0, (0.5, 0.5)) == (1.0, 0.5)
    shot = {"zoom": 1.5, "anchor": [0.0, 0.0], "subject": [0.9, 0.9]}
    assert any("edge" in i for i in review.issues(shot, [], []))
    assert any("crops out" in i for i in review.issues({"zoom": 1.5, "anchor": [0.5, 0.5], "subject": [0.5, 0.5]},
                                                        [(0.02, 0.02, 5.0)], []))
    assert any("face" in i for i in review.issues({"zoom": 1.5, "anchor": [1, 1], "subject": [0.8, 0.8]}, [], [(0.1, 0.1)]))
    assert any("soft" in i for i in review.issues({"zoom": 1.5, "anchor": [0.5, 0.5], "subject": [0.5, 0.5]}, [], [], upscale=1.875))
    # a 576 px phone clip on a 1080 timeline: the planner never zooms beyond what stays sharp
    sharp = plan(scene(20, peaks=[5.0, 12.0]), upscale=1.875)
    assert all(s["zoom"] * 1.875 <= 2.6 + 1e-6 for s in sharp["shots"])
    assert sharp["self_review"]["max_zoom_used"] == pytest.approx(2.6 / 1.875, abs=1e-3)
    # action split across both corners: a close-up on one corner would hide the rest -> downgraded
    split = [Sample(t / 4, 1.0, 0.05 if t % 2 else 0.95, 0.5, 0.1) for t in range(80)]
    for s in plan(split, trim_dead=False)["shots"]:
        assert s["framing"] in ("wide", "medium") or not s.get("self_review")
