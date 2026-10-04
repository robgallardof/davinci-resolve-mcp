"""Live end-to-end against a running DaVinci Resolve — Free (bridge) or Studio (direct).

    uv run pytest -m live -v

What it does, in a throwaway project it creates and preserves for inspection:
  1. saves your current project, creates `forge_live_<time>` (30 fps, 1920x1080)
  2. generates two 3 s synthetic clips with opencv, imports them, builds a timeline
  3. apply_motion (auto backend on clip 1, Fusion on clip 2), checks the API state
  4. renders and checks PIXELS: first and last frame of each clip must differ,
     i.e. the animation really reaches the render (not just the Inspector)
  5. make_platform_version("tiktok") + render -> the file is 1080x1920
  6. preserves the scratch project and reopens the one you had
Skipped automatically when Resolve is not reachable.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from mcp.server.fastmcp import FastMCP
from resolve_forge import tools
from resolve_forge.gateway import ResolveUnavailable, Session

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

pytestmark = pytest.mark.live
FPS, W, H, SECONDS = 30, 1920, 1080, 3


def _make_clip(path: Path, hue: int) -> None:
    """A static, detailed frame: any zoom/rotation changes many pixels."""
    img = np.zeros((H, W, 3), np.uint8)
    for y in range(0, H, 60):
        for x in range(0, W, 60):
            if (x // 60 + y // 60) % 2:
                img[y:y + 60, x:x + 60] = (hue, 180, 255 - hue)
    cv2.circle(img, (W // 2, int(H * 0.38)), 160, (240, 240, 240), -1)
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    for _ in range(FPS * SECONDS):
        out.write(img)
    out.release()


class Live:
    def __init__(self, session: Session):
        self.session = session
        self.mcp = FastMCP("live")
        tools.register(self.mcp, session)

    def __call__(self, tool: str, **args) -> dict:
        result = asyncio.run(self.mcp.call_tool(tool, args))
        content = result[0] if isinstance(result, tuple) else result
        data = json.loads(content[0].text)
        assert data["ok"], f"{tool} failed: {data}"
        return data

    def wait_render(self, job_id: str, timeout: float = 300) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self("render_status", job_id=job_id)
            if str(status.get("JobStatus")).lower() in ("complete", "failed", "cancelled"):
                return status
            time.sleep(1)
        raise TimeoutError(f"render {job_id} did not finish in {timeout}s")


@pytest.fixture(scope="module")
def live():
    session = Session()
    try:
        resolve = session.resolve()
    except ResolveUnavailable as exc:
        pytest.skip(str(exc))
    pm = resolve.GetProjectManager()
    previous = pm.GetCurrentProject()
    previous_name = previous.GetName() if previous else None
    pm.SaveProject()
    name = f"forge_live_{int(time.time())}"
    # The Free-edition bridge only reads/writes inside its allowed roots (default output: ~/Movies).
    work = Path.home() / "Movies" / "forge-live" / name
    work.mkdir(parents=True, exist_ok=True)
    project = pm.CreateProject(name)
    assert project, "could not create the scratch project"
    try:
        project.SetSetting("timelineFrameRate", str(FPS))
        project.SetSetting("timelineResolutionWidth", str(W))
        project.SetSetting("timelineResolutionHeight", str(H))
        paths = [work / "take1.mp4", work / "take2.mp4"]
        for i, p in enumerate(paths):
            _make_clip(p, 60 + i * 100)
        pool = project.GetMediaPool()
        clips = pool.ImportMedia([str(p) for p in paths])
        assert clips and len(clips) == 2, "ImportMedia failed"
        assert pool.CreateTimelineFromClips("forge_live", clips), "CreateTimelineFromClips failed"
        resolve.OpenPage("edit")
        yield Live(session), work
    finally:
        pm.CloseProject(pm.GetCurrentProject())
        if previous_name:
            pm.LoadProject(previous_name)
        # Preserve generated project/media for inspection; no deletion without a user request.


def _frames(path: Path, indices: list[int]):
    cap = cv2.VideoCapture(str(path))
    size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    frames = {}
    for i in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        assert ok, f"could not read frame {i} of {path}"
        frames[i] = frame.astype("int16")
    cap.release()
    return size, frames


def _rendered(target: Path, stem: str) -> Path:
    files = sorted(target.glob(f"{stem}*"))
    assert files, f"no rendered file for {stem} in {target}"
    return files[0]


def test_1_status(live):
    forge, _ = live
    status = forge("forge_status")
    assert status["transport"] in ("direct", "bridge") and status["resolution"] == f"{W}x{H}"
    assert len(forge("list_clips")["clips"]) == 2


def test_2_motion_reaches_the_render(live):
    forge, renders = live
    auto = forge("apply_motion", style="warm_push", clips=[1], anchor="center", intensity=1.5)
    fusion = forge("apply_motion", style="warm_push", clips=[2], anchor="center", intensity=1.5, backend="fusion")
    assert fusion["clips"][0]["backend"] == "fusion"
    job = forge("render_for", format="youtube_1080", target_dir=str(renders), name="motion")
    assert str(forge.wait_render(job["job_id"]).get("JobStatus")).lower() == "complete"
    total = FPS * SECONDS
    (w, h), f = _frames(_rendered(renders, "motion"), [1, total - 3, total + 1, 2 * total - 3])
    assert (w, h) == (W, H)
    first_clip = abs(f[1] - f[total - 3]).mean()
    second_clip = abs(f[total + 1] - f[2 * total - 3]).mean()
    backend = auto["clips"][0]["backend"]
    print(f"clip1 backend={backend} diff={first_clip:.2f} | clip2 backend=fusion diff={second_clip:.2f}")
    assert first_clip > 3, f"{backend} motion not visible in render (diff {first_clip:.2f})"
    assert second_clip > 3, f"fusion motion not visible in render (diff {second_clip:.2f})"


def test_3_clear_motion_renders_static_again(live):
    """Negative control: without motion the same frames must match, so the diff in test 2 means something."""
    forge, renders = live
    removed = forge("clear_motion")["removed"]
    assert sum(removed.values()) >= 1
    job = forge("render_for", format="youtube_1080", target_dir=str(renders), name="static")
    assert str(forge.wait_render(job["job_id"]).get("JobStatus")).lower() == "complete"
    total = FPS * SECONDS
    _, f = _frames(_rendered(renders, "static"), [1, total - 3])
    diff = abs(f[1] - f[total - 3]).mean()
    print(f"static diff={diff:.2f}")
    assert diff < 2, f"clip still moves after clear_motion (diff {diff:.2f})"


def test_4_vertical_version_renders_9x16(live):
    forge, renders = live
    version = forge("make_platform_version", format="tiktok", subject="center", name="forge_live [tiktok]")
    assert len(version["clips"]) == 2
    assert forge("forge_status")["resolution"] == "1080x1920"
    forge("apply_motion", style="tiktok_punch", anchor="center")
    job = forge("render_for", format="tiktok", target_dir=str(renders), name="vertical")
    assert str(forge.wait_render(job["job_id"]).get("JobStatus")).lower() == "complete"
    (w, h), _ = _frames(_rendered(renders, "vertical"), [0])
    assert (w, h) == (1080, 1920)


def test_5_owned_markers_preserve_the_source_timeline(live):
    forge, _ = live
    project = forge.session.resolve().GetProjectManager().GetCurrentProject()
    source = project.GetCurrentTimeline()
    before = source.GetMarkers()
    result = forge("timeline_markers", entries=[{"seconds": .5, "name": "Forge QA"}], dry_run=False)
    assert result["timeline"] != result["source"]
    assert source.GetMarkers() == before
    markers = project.GetCurrentTimeline().GetMarkers()
    assert 15 in {int(float(frame)) for frame in markers}


def test_6_owned_grade_and_fusion_graph_reach_native_resolve(live):
    forge, _ = live
    result = forge("grade_clips", slope=[1.02, 1., .98], saturation=.95, indices=[1], dry_run=False)
    assert result["applied"] and result["timeline"] != result["source"]
    graph = forge("apply_fusion_graph", nodes=[{"id": "qa", "type": "Transform", "inputs": {"Size": 1.04}}],
                  edges=[["MediaIn1", "qa", "Input"], ["qa", "MediaOut1", "Input"]], index=1, dry_run=False)
    assert graph["applied"]
    project = forge.session.resolve().GetProjectManager().GetCurrentProject()
    item = project.GetCurrentTimeline().GetItemListInTrack("video", 1)[0]
    node = item.GetFusionCompByIndex(1).FindTool("Forge_qa")
    assert node and node.GetInput("Size") == pytest.approx(1.04)
