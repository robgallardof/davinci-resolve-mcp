"""Live: Code Mode on a real Resolve (Free or Studio), in a throwaway project with synthetic media.

    uv run pytest -m live tests/live/test_live_code_mode.py -v

Needs Resolve open (Free: Workspace > Scripts > resolve_bridge). Connects, discovers operations, inspects a timeline,
plans, applies an approved edit, reads it back and checks the audit trace. Your open project is saved first and reopened
afterwards. The throwaway project stays in the database, like the other live tests: nothing here ever deletes one.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
from pathlib import Path

import imageio_ffmpeg
import pytest
from mcp.server.fastmcp import FastMCP

from resolve_forge import code_mode_tools, tools
from resolve_forge.gateway import ResolveUnavailable, Session
from resolve_forge.services import code_mode_service

pytestmark = pytest.mark.live


class Live:
    def __init__(self, session: Session, trace: Path):
        self.mcp = FastMCP("live-code-mode")
        tools.register(self.mcp, session)
        self.trace = trace
        service = code_mode_service.CodeModeService(self.mcp, session, tools.run_in_resolve_thread, trace_path=trace)
        tools.set_write_gate(code_mode_service.write_gate)
        code_mode_tools.register(self.mcp, service, {})

    def __call__(self, tool: str, **args) -> dict:
        result = asyncio.run(self.mcp.call_tool(tool, args))
        content = result[0] if isinstance(result, tuple) else result
        return json.loads(content[0].text)


def _clip(path: Path, seconds: int = 4) -> None:
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=30:duration={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(path)], check=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=120)


@pytest.fixture(scope="module")
def live():
    session = Session()
    try:
        resolve = session.resolve()
    except ResolveUnavailable as exc:
        pytest.skip(str(exc))
    manager = resolve.GetProjectManager()
    previous = manager.GetCurrentProject()
    previous_name = previous.GetName() if previous else None
    manager.SaveProject()
    name = f"forge_code_mode_{int(time.time())}"
    work = Path.home() / "Movies" / "forge-live" / name
    work.mkdir(parents=True, exist_ok=True)
    assert manager.CreateProject(name), "could not create the throwaway project"
    forge = Live(session, work / "traces.jsonl")
    clip = work / "synthetic.mp4"
    _clip(clip)
    created = forge("assemble_timeline", source=str(clip), cuts=[[0.0, 1.0], [1.0, 2.0], [2.0, 4.0]], name="Code Mode source")
    assert created["ok"], created
    yield forge, clip, name
    tools.set_write_gate(None)
    manager.SaveProject()
    if previous_name:
        manager.LoadProject(previous_name)


def test_end_to_end_plan_approve_verify(live):
    forge, clip, project = live
    assert forge("search", query="markers")["tools"][0]["name"] == "timeline_markers"

    inspected = forge("execute", code="""
        const status = await resolve.forge_status();
        const clips = (await resolve.list_clips({track: 1})).clips;
        const audit = await resolve.audit_timeline();
        return {project: status.project, timeline: status.timeline, fps: status.fps, durations: clips.map(c => c.duration), passed: audit.passed};
    """)
    assert inspected["status"] == "success", inspected
    assert inspected["result"]["project"] == project and inspected["result"]["timeline"] == "Code Mode source"
    durations = inspected["result"]["durations"]
    assert len(durations) == 3 and durations[2] >= durations[0]

    source_before = forge("list_clips", track=1)["clips"]
    script = """
        const marks = [{seconds: 0.5, name: 'first'}, {seconds: 1.5, name: 'second'}];
        await resolve.timeline_markers({entries: marks, copy_name: 'Code Mode copy', dry_run: false});
        if (run.mode === 'apply') {
            const found = (await resolve.timeline_markers({})).markers;
            run.check('both markers read back', found.length === 2, found.map(m => m.frame));
            run.check('frame accurate', found.map(m => m.frame).join() === marks.map(m => timecode.secondsToFrame(m.seconds, FPS)).join());
        }
    """.replace("FPS", str(inspected["result"]["fps"]))
    plan = forge("execute", code=script)
    assert plan["status"] == "needs_approval", plan
    assert plan["plan"]["project"] == project and forge("forge_status")["timeline"] == "Code Mode source"  # nothing changed yet

    done = forge("approve_execution", plan_id=plan["plan"]["plan_id"])
    assert done["status"] == "success", done
    assert all(check["passed"] for check in done["checks"]) and len(done["checks"]) == 2
    assert forge("forge_status")["timeline"] == "Code Mode copy"

    assert forge("timeline_versions", action="select", timeline_name="Code Mode source")["ok"]
    assert forge("list_clips", track=1)["clips"] == source_before  # the source timeline is as it was
    assert forge("timeline_markers")["markers"] == []

    assert forge("approve_execution", plan_id=plan["plan"]["plan_id"])["code"] == "PLAN_NOT_FOUND"
    assert clip.stat().st_size > 0
    trace = [json.loads(line) for line in forge.trace.read_text(encoding="utf-8").splitlines()]
    assert [entry["status"] for entry in trace] == ["success", "needs_approval", "success"]
