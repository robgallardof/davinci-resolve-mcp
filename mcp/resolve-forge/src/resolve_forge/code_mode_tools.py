"""Thin MCP surface of Code Mode."""

from __future__ import annotations

import os

from mcp.server.fastmcp import Context
from mcp.types import ClientCapabilities, ElicitationCapability, ToolAnnotations
from pydantic import BaseModel

from .errors import ForgeError, payload
from .gateway import ResolveUnavailable

EXECUTE_DOC = """Run a JavaScript async function body that composes Resolve operations, in a sandbox with no files,
network, environment or processes. Globals: `resolve.<tool>(args)` (find tools with search; failures throw
CapabilityError with .code/.hint), `run.mode` ('plan' | 'apply'), `run.check(label, passed, details)`,
`timecode.{rate,secondsToFrame,frameToSeconds,frameToTimecode}`, `console.log`. `return` a JSON value.

Read and analysis calls run at once. State-changing calls need dry_run:false in their arguments (or have no dry_run);
in stage 'plan' they return a preview and are stored, nothing changes, and status is needs_approval with a plan_id.
approve_execution runs the same script again, allowing exactly those calls in that order. render_for needs a passing
preflight_render of the same format first. In 'apply', read the result back and report it with run.check; status is
success, partial, blocked, failed, unverified, contradictory, cancelled or timeout. Runs are not atomic.
Prefer a direct tool for one simple call."""


class _Confirm(BaseModel):
    approve: bool = False


def _supports_elicitation(ctx: Context) -> bool:
    try:
        return ctx.session.check_client_capability(ClientCapabilities(elicitation=ElicitationCapability()))
    except (AttributeError, ValueError):
        return False


def register(mcp, service, env: dict | None = None) -> None:
    env = os.environ if env is None else env
    approval = env.get("RESOLVE_FORGE_CODE_MODE_APPROVAL", "client")
    if approval not in {"client", "elicitation"}:  # a typo must not silently pick the weaker control
        raise ValueError(f"RESOLVE_FORGE_CODE_MODE_APPROVAL must be client or elicitation, got {approval!r}")
    require_prompt = approval == "elicitation"

    async def guarded(action):
        try:
            return await action()
        except (ForgeError, ResolveUnavailable, KeyError, ValueError, OSError) as exc:
            return payload(exc)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
    async def search(query: str = "", category: str | None = None, risk: str | None = None,
                     names: list[str] | None = None, limit: int = 8) -> dict:
        """Find Resolve operations for execute: name, category, risk, previewable, summary and compact params.

        No arguments: categories. names=[...]: full description and input schema of those tools.
        Risks read/analysis/artifact run at once; file_write/project_write/render need approval; system is unavailable.
        """
        return await guarded(lambda: service.search(query, category, risk, names, limit))

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False,
                                          openWorldHint=False), description=EXECUTE_DOC)
    async def execute(code: str) -> dict:
        return await guarded(lambda: service.execute(code))

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False,
                                          openWorldHint=False))
    async def approve_execution(plan_id: str, ctx: Context) -> dict:
        """Apply a plan from execute: the same script, allowing only its listed operations, in order.

        Show the plan to the user first. Refused if the project or timeline changed since. One shot. Not atomic.
        """
        async def action() -> dict:
            summary = service.describe_plan(plan_id)
            if _supports_elicitation(ctx):
                answer = await ctx.elicit(f"Apply these edits in Resolve?\n{summary}", _Confirm)
                if answer.action != "accept" or not answer.data.approve:
                    service.discard(plan_id)
                    return {"ok": False, "status": "blocked", "code": "APPROVAL_DECLINED",
                            "error": "The user did not approve this plan; it was discarded."}
                return await service.approve(plan_id, "client prompt")
            if require_prompt:  # never fall back to a weaker control the user ruled out
                return {"ok": False, "status": "blocked", "code": "APPROVAL_UNAVAILABLE",
                        "error": "This client cannot prompt the user, and RESOLVE_FORGE_CODE_MODE_APPROVAL=elicitation.",
                        "hint": "Use a client with MCP elicitation, or unset that variable to rely on the client's tool permissions."}
            return await service.approve(plan_id, "tool call")
        return await guarded(action)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False))
    async def cancel_execution() -> dict:
        """Stop the active Code Mode run. Steps already applied stay applied."""
        return {"ok": True, **service.cancel()}
