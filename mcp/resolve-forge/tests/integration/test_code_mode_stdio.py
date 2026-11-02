"""Code Mode through the real server process over stdio, as an MCP client launches it. No Resolve: its absence is the test."""

import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def _session(tmp_path, actions):
    env = {**os.environ, "RESOLVE_FORGE_CODE_MODE_TRACE": str(tmp_path / "traces.jsonl")}
    params = StdioServerParameters(command=sys.executable, args=["-m", "resolve_forge.server"], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), 60)
            names = {tool.name for tool in (await session.list_tools()).tools}
            replies = []
            for name, args in actions:
                result = await asyncio.wait_for(session.call_tool(name, args), 60)
                replies.append(json.loads(result.content[0].text))
            return names, replies


def test_code_mode_over_stdio_beside_the_direct_tools(tmp_path):
    names, (found, composed, offline, nothing_active, direct) = asyncio.run(_session(tmp_path, [
        ("search", {"query": "formats"}),
        ("execute", {"code": "const f = await resolve.list_formats({orientation: 'vertical'});"
                             "return Object.keys(f.formats).filter(k => f.formats[k].height === 1920).length;"}),
        ("execute", {"code": "return await resolve.forge_status();"}),
        ("cancel_execution", {}),
        ("list_styles", {}),
    ]))
    assert {"search", "execute", "approve_execution", "cancel_execution", "list_styles", "apply_motion"} <= names and len(names) == 69
    assert found["tools"][0]["name"] == "list_formats"
    assert composed["status"] == "success" and composed["result"] > 3
    assert offline["status"] == "failed" and offline["code"] in {"RESOLVE_UNREACHABLE", "RESOLVE_BUSY"}
    assert nothing_active["cancelling"] is False and direct["ok"]
    assert json.loads((tmp_path / "traces.jsonl").read_text(encoding="utf-8").splitlines()[0])["status"] == "success"
