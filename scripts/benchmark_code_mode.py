"""Compare Code Mode with the direct tools on the same five workflows, against the same fake Resolve.

    cd mcp/resolve-forge
    uv run --no-sync --with tiktoken --with psutil python ../../scripts/benchmark_code_mode.py

Writes docs/code-mode-benchmarks.md. No model is involved: each route is a fixed script of the requests a competent
agent would send, replayed through the real tools and a real sandbox. So tokens, calls and round trips are exact for
those scripts, while an agent's mistakes and retries are not measured.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
FORGE = ROOT / "mcp" / "resolve-forge"
sys.path[:0] = [str(FORGE / "src"), str(FORGE / "tests")]

from mcp.server.fastmcp import FastMCP  # noqa: E402

from fakes import BridgeLike, FakeTransport, demo_resolve  # noqa: E402
from resolve_forge import code_mode_tools, server, tools  # noqa: E402
from resolve_forge.gateway import Session  # noqa: E402
from resolve_forge.services import code_mode_sandbox, code_mode_service  # noqa: E402

CLIPS = 40
RUNS = 5


def token_counter() -> tuple[Callable[[str], int], str]:
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return (lambda text: len(encoding.encode(text, disallowed_special=()))), "tiktoken cl100k_base"
    except Exception:  # no package, or its encoding could not be downloaded
        return (lambda text: max(1, len(text) // 4)), "characters / 4"


count_tokens, TOKENIZER = token_counter()


def tokens(value) -> int:
    return count_tokens(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str))


class World:
    """A fresh fake Resolve (Free edition through the bridge shape) with both routes wired to the same tools."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.resolve = demo_resolve(studio=False, keyframes=True, clips=CLIPS)
        media = folder / "source.mp4"
        media.write_bytes(b"x")
        for item in self.resolve.project.current.tracks[0]:
            item.GetMediaPoolItem().path = str(media)
        self.session = Session([FakeTransport("bridge", BridgeLike(self.resolve))])
        self.mcp = FastMCP("bench")
        tools.register(self.mcp, self.session)
        self.service = code_mode_service.CodeModeService(self.mcp, self.session, tools.run_in_resolve_thread,
                                                         trace_path=folder / "traces.jsonl")
        code_mode_tools.register(self.mcp, self.service, {})
        self.files = [folder / f"take{index}.{suffix}" for index, suffix in enumerate(["mov", "mp4", "wav"] * 4)]
        for path in self.files:
            path.write_bytes(b"x")

    async def call(self, tool: str, args: dict) -> dict:
        result = await self.mcp.call_tool(tool, args)
        content = result[0] if isinstance(result, tuple) else result
        return json.loads(content[0].text)


@dataclass
class Measure:
    tool_calls: int = 0
    round_trips: int = 0
    traffic_tokens: int = 0     # requests the model wrote plus replies it read
    cumulative_input: int = 0   # what is re-sent each turn with no prompt cache: listing + everything so far
    errors: int = 0
    seconds: list[float] = field(default_factory=list)
    correct: bool = False


async def play(world: World, turns: list[list[tuple[str, dict | Callable]]], listing_tokens: int) -> Measure:
    """Each inner list is one model turn: its calls can go out together. An argument may depend on earlier replies."""
    measure, replies = Measure(), {}
    context = listing_tokens
    for turn in turns:
        measure.round_trips += 1
        measure.cumulative_input += context
        for tool, args in turn:
            args = args(replies) if callable(args) else args
            reply = await world.call(tool, args)
            replies[tool] = reply
            traffic = tokens({"tool": tool, "arguments": args}) + tokens(reply)
            measure.tool_calls += 1
            measure.traffic_tokens += traffic
            context += traffic
            if reply.get("ok") is False:
                measure.errors += 1
    measure.cumulative_input += context  # the final turn, where the model reads everything and answers
    measure.round_trips += 1
    return measure


def approve(replies: dict) -> dict:
    return {"plan_id": replies["execute"]["plan"]["plan_id"]}


@dataclass
class Workflow:
    name: str
    direct: Callable[[World], list]
    code: Callable[[World], list]
    correct: Callable[[World], bool]
    setup: Callable[[World], list] = lambda world: []


def timelines(world: World) -> set[str]:
    return {timeline.GetName() for timeline in world.resolve.project.timelines}


def untouched_source(world: World) -> bool:
    source = next(timeline for timeline in world.resolve.project.timelines if timeline.GetName() == "Master")
    return all(item.props.get("ZoomX") in (None, 1, 1.0) for item in source.tracks[0])


READ_ONE = Workflow(
    "1. Simple read (project status)",
    lambda w: [[("forge_status", {})]],
    lambda w: [[("execute", {"code": "return await resolve.forge_status();"})]],
    lambda w: True)

INSPECT = """const status = await resolve.forge_status();
const audit = await resolve.audit_timeline();
const clips = (await resolve.list_clips({track: 1})).clips;
const longest = clips.reduce((a, b) => b.duration > a.duration ? b : a);
return {timeline: status.timeline, fps: status.fps, clips: clips.length,
        total: clips.reduce((sum, clip) => sum + clip.duration, 0), longest: longest.name,
        problems: audit.issues.filter(i => i.severity !== 'info').length, gaps: audit.issues.filter(i => i.code === 'GAP').length};"""

INSPECTION = Workflow(
    f"2. Timeline inspection ({CLIPS} clips)",
    lambda w: [[("forge_status", {}), ("audit_timeline", {}), ("list_clips", {"track": 1})]],
    lambda w: [[("search", {"query": "timeline clips audit"})], [("execute", {"code": INSPECT})]],
    lambda w: True)

ORGANISE = """const before = await resolve.list_media();
const moved = await resolve.organise_media({by: 'extension', dry_run: false});
if (run.mode === 'apply') {
    const after = JSON.stringify(await resolve.list_media());
    run.check('every take still listed', ['take0.mov', 'take1.mp4', 'take2.wav'].every(n => after.includes(n)));
}
return {moves: moved.moves ?? null};"""

MEDIA = Workflow(
    "3. Multi-step media organisation",
    lambda w: [[("list_media", {}), ("organise_media", {"by": "extension"})],
               [("organise_media", {"by": "extension", "dry_run": False})], [("list_media", {})]],
    lambda w: [[("search", {"query": "media bins organise"})], [("execute", {"code": ORGANISE})],
               [("approve_execution", approve)]],
    lambda w: all(path.exists() for path in w.files),
    setup=lambda w: [("ingest_media", {"paths": [str(path) for path in w.files], "dry_run": False})])

MARKERS = [{"seconds": 2 * index + 1, "name": f"beat {index}"} for index in range(6)]
EDIT = f"""const clips = (await resolve.list_clips({{track: 1}})).clips;
const chosen = clips.filter(c => c.duration >= 300).slice(0, 10).map(c => c.index);
await resolve.edit_clips({{properties: {{ZoomX: 1.2, ZoomY: 1.2}}, indices: chosen, copy_name: 'Cut A', dry_run: false}});
await resolve.timeline_markers({{entries: {json.dumps(MARKERS)}, dry_run: false}});
await resolve.configure_track({{kind: 'video', index: 1, track_name: 'Main', dry_run: false}});
if (run.mode === 'apply') {{
    const after = (await resolve.list_clips({{track: 1}})).clips;
    run.check('zoom on the chosen clips', chosen.every(i => Number(after[i - 1].zoom) === 1.2));
    run.check('markers present', (await resolve.timeline_markers({{}})).markers.length === {len(MARKERS)});
}}
return {{chosen: chosen.length}};"""
CHOSEN = list(range(1, 11))

EDITING = Workflow(
    "4. Approval-controlled edit (3 edits with previews, verified)",
    lambda w: [[("list_clips", {"track": 1})],
               [("edit_clips", {"properties": {"ZoomX": 1.2, "ZoomY": 1.2}, "indices": CHOSEN}),
                ("timeline_markers", {"entries": MARKERS}),
                ("configure_track", {"kind": "video", "index": 1, "track_name": "Main"})],
               [("edit_clips", {"properties": {"ZoomX": 1.2, "ZoomY": 1.2}, "indices": CHOSEN, "copy_name": "Cut A", "dry_run": False})],
               [("timeline_markers", {"entries": MARKERS, "dry_run": False})],
               [("configure_track", {"kind": "video", "index": 1, "track_name": "Main", "dry_run": False})],
               [("list_clips", {"track": 1}), ("timeline_markers", {})]],
    lambda w: [[("search", {"names": ["edit_clips", "timeline_markers", "configure_track"]})],
               [("execute", {"code": EDIT})], [("approve_execution", approve)]],
    lambda w: untouched_source(w) and "Cut A" in {name.split(" [")[0] for name in timelines(w)}
    and len(w.resolve.project.current.GetMarkers()) == len(MARKERS))

RENDER = """const check = await resolve.preflight_render({format: 'youtube_1080'});
if (!check.technical_passed) return {problems: check.issues};
const spec = (await resolve.list_formats({orientation: 'horizontal'})).formats.youtube_1080;
const job = await resolve.render_for({format: 'youtube_1080', target_dir: TARGET, name: 'bench', start: false});
if (run.mode === 'apply') run.check('job queued', Boolean((await resolve.render_status({job_id: job.job_id})).job_id));
return {codec: spec.codec, size: [spec.width, spec.height], job: job.job_id ?? null};"""

DELIVERY = Workflow(
    "5. Render configuration and verification",
    lambda w: [[("list_formats", {"orientation": "horizontal"}), ("preflight_render", {"format": "youtube_1080"})],
               [("render_for", {"format": "youtube_1080", "target_dir": str(w.folder / "out"), "name": "bench", "start": False})],
               [("render_status", lambda r: {"job_id": r["render_for"]["job_id"]})]],
    lambda w: [[("search", {"query": "render preflight status format"})],
               [("execute", {"code": RENDER.replace("TARGET", json.dumps(str(w.folder / "out")))})],
               [("approve_execution", approve)]],
    lambda w: True)

WORKFLOWS = [READ_ONE, INSPECTION, MEDIA, EDITING, DELIVERY]


async def fixed_cost(mcp: FastMCP, instructions: str) -> int:
    listing = [tool.model_dump(mode="json", exclude_none=True) for tool in await mcp.list_tools()]
    return tokens(listing) + tokens(instructions)


def listing_cost() -> int:
    world_folder = Path(tempfile.mkdtemp())
    try:
        return asyncio.run(fixed_cost(World(world_folder).mcp, server.INSTRUCTIONS))
    finally:
        shutil.rmtree(world_folder, ignore_errors=True)


def run_route(workflow: Workflow, route: str, listing: int) -> Measure:
    best = None
    for _ in range(RUNS):
        folder = Path(tempfile.mkdtemp())
        try:
            world = World(folder)
            turns = workflow.direct(world) if route == "direct" else workflow.code(world)

            async def scenario():
                for tool, args in workflow.setup(world):
                    await world.call(tool, args)
                started = time.perf_counter()
                result = await play(world, turns, listing)
                return result, time.perf_counter() - started
            measure, seconds = asyncio.run(scenario())
            measure.correct = measure.errors == 0 and workflow.correct(world)
            if best is None:
                best = measure
            best.seconds.append(seconds)
            best.correct = best.correct and measure.correct
        finally:
            shutil.rmtree(folder, ignore_errors=True)
    return best


def sandbox_costs() -> dict:
    """Startup, peak memory and CPU of the sandbox process itself, running a script that composes real calls."""
    import psutil

    async def once() -> tuple[float, float, float]:
        sandbox = code_mode_sandbox.Sandbox(code_mode_sandbox.Limits())
        started = time.perf_counter()
        await sandbox.start("return 1", "plan", [])
        await sandbox.receive()
        elapsed = (time.perf_counter() - started) * 1000
        process = psutil.Process(sandbox._process.pid) if sandbox._process.returncode is None else None
        memory, cpu = 0.0, 0.0
        if process:
            try:
                memory = process.memory_info().rss / 1048576
                cpu = sum(process.cpu_times()[:2]) * 1000
            except psutil.Error:
                pass
        await sandbox.close()
        return elapsed, memory, cpu

    async def busy() -> tuple[float, float]:
        sandbox = code_mode_sandbox.Sandbox(code_mode_sandbox.Limits())
        code = "const rows = []; for (let i = 0; i < 200000; i++) rows.push({i, name: 'clip' + i}); " \
               "await new Promise(r => setTimeout(r, 300)); return rows.filter(r => r.i % 2).length;"
        await sandbox.start(code, "plan", [])
        process, peak, cpu = psutil.Process(sandbox._process.pid), 0.0, 0.0
        reader = asyncio.ensure_future(sandbox.receive())
        while not reader.done():
            try:
                peak = max(peak, process.memory_info().rss / 1048576)
                cpu = sum(process.cpu_times()[:2]) * 1000
            except psutil.Error:
                break
            await asyncio.sleep(0.01)
        await reader
        await sandbox.close()
        return peak, cpu

    samples = [asyncio.run(once()) for _ in range(12)]
    peak, cpu = asyncio.run(busy())
    return {"startup_ms": statistics.median(s[0] for s in samples), "idle_rss_mb": statistics.median(s[1] for s in samples),
            "idle_cpu_ms": statistics.median(s[2] for s in samples), "busy_peak_rss_mb": peak, "busy_cpu_ms": cpu}


def startup_cost() -> dict:
    """Time to import and build the server in a fresh interpreter, and its resident memory afterwards."""
    probe = ("import time; t = time.perf_counter(); from resolve_forge import server; mcp = server.build(); "
             "e = (time.perf_counter() - t) * 1000; import psutil; "
             "print(e, psutil.Process().memory_info().rss / 1048576)")
    rows = []
    for _ in range(7):
        done = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
        if done.returncode:
            raise RuntimeError(done.stderr)
        rows.append([float(value) for value in done.stdout.split()])
    return {"build_ms": statistics.median(r[0] for r in rows), "rss_mb": statistics.median(r[1] for r in rows)}


def render(results: list[dict], listing: int, sandbox: dict, startup: dict) -> str:
    lines = ["# Code Mode benchmarks", "",
             "Generated by `scripts/benchmark_code_mode.py`; do not edit by hand. Reproduce:", "",
             "```", "cd mcp/resolve-forge", "uv run --no-sync --with tiktoken --with psutil python ../../scripts/benchmark_code_mode.py", "```", "",
             f"Machine: {platform.system()} {platform.release()}, Python {platform.python_version()}, "
             f"Deno {subprocess.run([code_mode_sandbox.find_deno(), '--version'], capture_output=True, text=True).stdout.split()[1]}. "
             f"Tokens: {TOKENIZER} (an approximation of any model's own count). Timeline: {CLIPS} clips on a fake Resolve. "
             f"Times are the median of {RUNS} runs.", "",
             "## How to read this", "",
             "- **Route A, direct tools.** It plays the role of the \"compound tools\" baseline: these are already intent-level tools.",
             "- **Route B, granular 1:1 API tools: not measured, because this project has none.** It deliberately never had them.",
             "- **Route C, Code Mode**, including the `search` calls an agent needs to discover what it wants to call.",
             "- These are replayed request scripts, not a model. Exact for the scripts; they say nothing about how often an agent writes a wrong script, retries, or skips the preview.",
             "- **Fake Resolve.** Times show overhead on top of instant calls. Real Resolve calls take longer, and they take the same on both routes.",
             "- Direct-route turns batch independent calls, the best case for it. Clients that defer tool schemas (for example Claude Code's tool search) pay less than the listing below.",
             "- `Input (uncached)` adds up what each turn re-sends without a prompt cache. Both routes carry the same listing, so more round trips multiply it. Prompt caching shrinks that on both.", "",
             "## What every conversation pays before the first call", "",
             "| Tools listed | Tool list + instructions (tokens) |", "|---:|---:|",
             f"| 69 | {listing:,} |", "",
             "## Workflows", "",
             "| Workflow | Route | Tool calls | Round trips | Traffic (tokens) | Input, uncached (tokens) | Overhead (ms) | Errors | Correct |",
             "|---|---|---:|---:|---:|---:|---:|---:|:---:|"]
    for row in results:
        for label, key in (("A direct", "direct"), ("C Code Mode", "code")):
            m = row[key]
            lines.append(f"| {row['name']} | {label} | {m.tool_calls} | {m.round_trips} | {m.traffic_tokens:,} | {m.cumulative_input:,} | "
                         f"{statistics.median(m.seconds) * 1000:.0f} | {m.errors} | {'yes' if m.correct else 'NO'} |")
    lines += ["", "## Difference between the routes", "",
              "| Workflow | Traffic A | Traffic C | C vs A | Round trips A | Round trips C |", "|---|---:|---:|---:|---:|---:|"]
    for row in results:
        a, c = row["direct"], row["code"]
        lines.append(f"| {row['name']} | {a.traffic_tokens:,} | {c.traffic_tokens:,} | {(c.traffic_tokens - a.traffic_tokens) / a.traffic_tokens:+.0%} | {a.round_trips} | {c.round_trips} |")
    lines += ["", "## Runtime cost", "",
              "| Measure | Value |", "|---|---:|",
              f"| Sandbox startup to first result | {sandbox['startup_ms']:.0f} ms |",
              f"| Sandbox resident memory, trivial script | {sandbox['idle_rss_mb']:.0f} MB |",
              f"| Sandbox peak memory, 200,000 rows filtered | {sandbox['busy_peak_rss_mb']:.0f} MB |",
              f"| Sandbox CPU, trivial script | {sandbox['idle_cpu_ms']:.0f} ms |",
              f"| Sandbox CPU, 200,000 rows filtered | {sandbox['busy_cpu_ms']:.0f} ms |"]
    lines.append(f"| Server import + build | {startup['build_ms']:.0f} ms, {startup['rss_mb']:.0f} MB resident |")
    lines += ["", "The sandbox exists only during a run. The Deno dependency adds its binary to the environment (about 94 MB on Windows).", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "code-mode-benchmarks.md")
    args = parser.parse_args()
    listing = listing_cost()
    results = [{"name": workflow.name, "direct": run_route(workflow, "direct", listing),
                "code": run_route(workflow, "code", listing)} for workflow in WORKFLOWS]
    report = render(results, listing, sandbox_costs(), startup_cost())
    args.output.write_text(report, encoding="utf-8")
    print(report)
    return 0 if all(row[route].correct for row in results for route in ("direct", "code")) else 1


if __name__ == "__main__":
    sys.exit(main())
