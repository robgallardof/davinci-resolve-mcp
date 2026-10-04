"""The integrated `resolve-forge` server, launched exactly as config/mcp.servers.json says.

Handshake runs always (requires generated config); the read-only calls
are `live` (need Resolve open, Free via bridge or Studio direct).
"""

import asyncio
import json
import os
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[4]
CONFIG = ROOT / ".mcp.json"


def _spec():
    if not CONFIG.exists():
        pytest.skip("run `python scripts/sync.py` first")
    spec = json.loads(CONFIG.read_text(encoding="utf-8"))["mcpServers"]["resolve-forge"]

    return spec


async def _run(calls):
    spec = _spec()
    params = StdioServerParameters(command=spec["command"], args=spec["args"], env={**os.environ, **spec["env"]})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), 120)
            tools = {t.name for t in (await session.list_tools()).tools}
            out = {}
            for name, args in calls:
                res = await session.call_tool(name, args)
                out[name] = res.content[0].text
            return tools, out


def test_integrated_handshake():
    tools, _ = asyncio.run(_run([]))
    assert {"forge_status", "project_workflow", "timeline_versions", "list_media", "render_for"} <= tools


@pytest.mark.live
def test_integrated_reads_live_resolve():
    from resolve_forge.gateway import ResolveUnavailable, Session
    try:
        Session().resolve()
    except ResolveUnavailable as exc:
        pytest.skip(str(exc))
    _, out = asyncio.run(_run([("forge_status", {}), ("project_workflow", {"action": "inspect"}), ("audit_timeline", {})]))
    assert json.loads(out["forge_status"])["ok"]
    assert json.loads(out["project_workflow"])["project"]
    assert json.loads(out["audit_timeline"])["ok"]
