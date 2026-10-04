"""The real server process over stdio, exactly as Claude Code / Codex / Cursor launch it."""

import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {"forge_status", "list_clips", "list_styles", "list_formats", "preview_motion", "apply_motion",
                  "clear_motion", "make_platform_version", "locate_subject", "render_for", "render_status",
                  "transcribe_timeline", "add_captions", "add_text_overlay", "find_highlights", "assemble_timeline"}


async def _session_run(calls):
    params = StdioServerParameters(command=sys.executable, args=["-m", "resolve_forge.server"], env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await asyncio.wait_for(session.initialize(), 60)
            tools = {t.name for t in (await session.list_tools()).tools}
            results = {}
            for name, args in calls:
                res = await session.call_tool(name, args)
                results[name] = json.loads(res.content[0].text)
            return init, tools, results


def test_stdio_handshake_tools_and_calls():
    init, tools, results = asyncio.run(_session_run([
        ("list_styles", {}),
        ("preview_motion", {"style": "youtube_dynamic", "seconds": 20}),
        ("forge_status", {}),
    ]))
    assert init.serverInfo.name == "resolve-forge" and "apply_motion" in (init.instructions or "")
    assert EXPECTED_TOOLS <= tools
    assert len(tools) == 56
    assert {"plan_edit", "analyse_music", "assemble_montage", "create_music_visualizer", "find_story_moments", "plan_beat_cuts", "align_text", "place_sound_effects", "add_music_bed", "plan_energized_edit", "energize_timeline", "review_shots", "review_video"} <= tools
    assert {"list_text_styles", "preview_text_style"} <= tools
    assert {"project_workflow", "ingest_media", "timeline_versions", "apply_fusion_graph", "audit_timeline"} <= tools
    assert results["list_styles"]["ok"] and results["preview_motion"]["ok"]
    status = results["forge_status"]
    # Resolve may or may not be open on the machine running the suite; both answers must be well-formed.
    assert status["ok"] or "Cannot reach DaVinci Resolve" in status["error"]
