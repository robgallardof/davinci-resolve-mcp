"""The upstream `davinci-resolve` server, launched exactly as config/mcp.servers.json says.

Handshake runs always (skipped if vendor/ is not installed); the read-only calls
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
    spec = json.loads(CONFIG.read_text(encoding="utf-8"))["mcpServers"]["davinci-resolve"]
    if not Path(spec["command"]).exists():
        pytest.skip("upstream not installed (scripts/bootstrap.ps1)")
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


def test_upstream_handshake():
    tools, _ = asyncio.run(_run([]))
    assert {"resolve_control", "project_manager", "timeline", "media_pool", "render"} <= tools


@pytest.mark.live
def test_upstream_reads_live_resolve():
    from resolve_forge.gateway import ResolveUnavailable, Session
    try:
        Session().resolve()
    except ResolveUnavailable as exc:
        pytest.skip(str(exc))
    _, out = asyncio.run(_run([("resolve_control", {"action": "get_version"}),
                               ("project_manager", {"action": "get_current"})]))
    assert "version_string" in out["resolve_control"]
    assert '"name"' in out["project_manager"]
