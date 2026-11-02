"""A fake Resolve behind the real tools, with Code Mode on top and a real Deno sandbox."""

import asyncio
import json

import pytest

from conftest import Forge
from fakes import BridgeLike, FakeTransport, demo_resolve
from resolve_forge import code_mode_tools, tools
from resolve_forge.gateway import Session
from resolve_forge.services import code_mode_service
from resolve_forge.services.code_mode_sandbox import Limits


class CodeForge(Forge):
    def __init__(self, tmp_path, *, limits: Limits | None = None, env: dict | None = None, **options):
        super().__init__(options.pop("studio", False), options.pop("keyframes", True), options.pop("bridge", True), **options)
        self.trace = tmp_path / "traces.jsonl"
        self.service = code_mode_service.CodeModeService(self.mcp, self.session, tools.run_in_resolve_thread,
                                                         limits or Limits(), self.trace)
        tools.set_write_gate(code_mode_service.write_gate)
        code_mode_tools.register(self.mcp, self.service, env or {})

    def run(self, code: str) -> dict:
        return self("execute", code=code)

    def approve(self, reply: dict) -> dict:
        assert reply["status"] == "needs_approval", reply
        return self("approve_execution", plan_id=reply["plan"]["plan_id"])

    def traces(self) -> list[dict]:
        return [json.loads(line) for line in self.trace.read_text(encoding="utf-8").splitlines()]

    def together(self, *calls):
        """Tool calls that overlap, as a client issuing concurrent requests would make them."""
        async def run():
            return await asyncio.gather(*(self.mcp.call_tool(name, args) for name, args in calls))
        return [json.loads((result[0] if isinstance(result, tuple) else result)[0].text) for result in asyncio.run(run())]


@pytest.fixture
def code_forge(tmp_path):
    forge = CodeForge(tmp_path)
    yield forge
    tools.set_write_gate(None)


__all__ = ["BridgeLike", "CodeForge", "FakeTransport", "Session", "code_forge", "demo_resolve"]
