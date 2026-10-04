"""Entertainment pacing through the MCP surface: detection on a real (synthetic) video, then a built timeline."""
import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")


def corner_action(path, seconds=12, fps=15, size=(180, 320)):
    """Static wall; a square jumps around the lower-right corner, still for 4 s in the middle (dead time)."""
    w, h = size
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    rng = np.random.default_rng(1)
    for i in range(seconds * fps):
        frame = np.full((h, w, 3), 90, np.uint8)
        t = i / fps
        if not 4 <= t < 8:
            x, y = int(w * 0.75 + rng.integers(-12, 12)), int(h * 0.75 + rng.integers(-12, 12))
        else:
            x, y = int(w * 0.75), int(h * 0.75)
        cv2.rectangle(frame, (x - 12, y - 12), (x + 12, y + 12), (240, 240, 240), -1)
        out.write(frame)
    out.release()


def test_plan_finds_the_action_and_trims_the_still_part(forge, tmp_path):
    path = tmp_path / "pet.mp4"
    corner_action(path)
    plan = forge("plan_energized_edit", source=str(path), use_faces=False)
    assert plan["ok"], plan
    assert plan["removed_dead_s"] and 3.5 <= plan["removed_dead_s"][0][0] <= 4.5
    assert all(not (4.6 < s["start_s"] < 7.4) for s in plan["shots"])
    zoomed = [s for s in plan["shots"] if s["framing"] != "wide"]
    assert zoomed and all(s["subject"][0] > 0.6 and s["subject"][1] > 0.6 for s in zoomed)  # found the corner
    assert all(a["framing"] != b["framing"] for a, b in zip(plan["shots"], plan["shots"][1:]))


def test_energize_builds_one_clip_per_shot_with_its_own_framing(forge, tmp_path):
    path = tmp_path / "pet.mp4"
    corner_action(path)
    master = forge.project.current
    preview = forge("energize_timeline", source=str(path), name="Energized", format="tiktok")
    assert preview["ok"] and preview["dry_run"] and forge.project.current is master
    result = forge("energize_timeline", source=str(path), name="Energized", format="tiktok",
                   shots=preview["shots"], dry_run=False)
    assert result["ok"], result
    clips = forge.project.current.tracks[0]
    assert len(clips) == result["shots"] == len(preview["shots"])
    assert result["resolution"] == "1080x1920"
    framings = [s["framing"] for s in preview["shots"]]
    animated = [bool(c.comps) or bool(c.keys) for c in clips]
    assert all(animated[i] for i, f in enumerate(framings) if f != "wide") and master.tracks[0][0].comps == []
    bad = dict(preview["shots"][0], anchor=[2, 0])
    assert forge("energize_timeline", source=str(path), name="Bad", shots=[bad], dry_run=False)["code"] == "INVALID_ARGUMENT"
