import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from fakes import BridgeLike, FakeTransport, demo_resolve  # noqa: E402
from resolve_forge import tools  # noqa: E402
from resolve_forge.gateway import Session  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402

# (id, studio, keyframes, via bridge) — the combinations that behave differently.
EDITIONS = [
    pytest.param((False, True, True), id="free-21-bridge"),
    pytest.param((True, True, False), id="studio-21-direct"),
    pytest.param((True, False, False), id="studio-19-direct-no-keyframes"),
    pytest.param((False, False, True), id="free-19-bridge-no-keyframes"),
]


class Forge:
    """The real tool surface wired to a fake Resolve, called exactly like an MCP client would."""

    def __init__(self, studio: bool, keyframes: bool, bridge: bool, *, reachable: bool = True, **demo):
        self.resolve = demo_resolve(studio=studio, keyframes=keyframes, **demo)
        handle = BridgeLike(self.resolve) if bridge else self.resolve
        transports = [FakeTransport("bridge" if bridge else "direct", handle)] if reachable else []
        self.session = Session(transports)
        self.mcp = FastMCP("test")
        tools.register(self.mcp, self.session)

    def __call__(self, tool: str, **args) -> dict:
        result = asyncio.run(self.mcp.call_tool(tool, args))
        content = result[0] if isinstance(result, tuple) else result
        return json.loads(content[0].text)

    @property
    def project(self):
        return self.resolve.project

    def items(self, track: int = 1):
        return self.project.current.tracks[track - 1]


@pytest.fixture(params=EDITIONS)
def forge(request) -> Forge:
    return Forge(*request.param)
