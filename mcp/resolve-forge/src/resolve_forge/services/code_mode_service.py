"""Use case: run agent-written JavaScript against the registered tools, under the same validation as a direct call.

A run has two stages. `plan` executes the script with state-changing calls answered by previews and stored as a plan.
`apply`, after approval, executes the same script again; each state-changing call must match the next stored operation.
Every call goes through FastMCP's own dispatch, so there is no second implementation of any editing operation.
"""

from __future__ import annotations

import asyncio
import contextvars
import hashlib
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .. import errors as E
from ..domain import code_mode as policy
from ..errors import ForgeError
from ..gateway import Session, call
from .code_mode_sandbox import Limits, Sandbox, SandboxError
from .context import current

PLAN_TTL_S = 900
MAX_PLANS = 16
TRACE_BYTES = 5 * 1048576
PREVIEW_CHARS = 1500

_host_dispatch: contextvars.ContextVar[bool] = contextvars.ContextVar("code_mode_host_dispatch", default=False)
_applying = False  # one Resolve per process: while approved edits run, direct writes wait their turn


def write_gate(name: str, kwargs: dict) -> dict | None:
    """Refuse a direct state-changing call while an approved run is between its steps.

    FastMCP passes every parameter, defaults included, so dry_run in kwargs means the tool has one.
    """
    if not _applying or _host_dispatch.get():
        return None
    if policy.decide(name, kwargs, "dry_run" in kwargs).effect != "approve":
        return None
    return {"ok": False, "code": E.RESOLVE_BUSY, "error": "A Code Mode run is applying approved edits to Resolve.",
            "hint": "Retry when execute/approve_execution has returned, or call cancel_execution."}


def fingerprint(session: Session) -> dict:
    """What an approved plan assumed about the world. Never raises: a failure here must not lose a report of edits."""
    try:
        return _read_state(session)
    except Exception:  # a transport can fail in any way; an unreadable Resolve never compares equal to a readable one
        return {"reachable": False}


def _read_state(session: Session) -> dict:
    """Clip names and positions are hashed, so a moved clip counts as a change even with the same clip counts."""
    ctx = current(session, need_timeline=False)
    state = {"reachable": True, "project": ctx.project.GetName(),
             "rendering": bool(call(ctx.project, "IsRenderingInProgress", default=False))}
    timeline = ctx.timeline
    if timeline is None:
        return state
    digest, tracks = hashlib.sha256(), {}
    for kind in ("video", "audio"):
        counts = []
        for index in range(1, int(timeline.GetTrackCount(kind) or 0) + 1):
            items = [item for item in (timeline.GetItemListInTrack(kind, index) or []) if item is not None]
            counts.append(len(items))
            for item in items:
                digest.update(f"{kind}{index}|{item.GetName()}|{item.GetStart()}|{item.GetDuration()}\n".encode())
        tracks[kind] = counts
    return state | {"timeline": timeline.GetName(), "timeline_id": call(timeline, "GetUniqueId"),
                    "start_frame": int(timeline.GetStartFrame()), "end_frame": int(timeline.GetEndFrame()),
                    "tracks": tracks, "digest": digest.hexdigest()[:16]}


def _stale_fields(before: dict, now: dict) -> list[str]:
    return sorted(key for key in set(before) | set(now) if key != "rendering" and before.get(key) != now.get(key))


def _bounded_text(value: Any, limit: int = PREVIEW_CHARS) -> Any:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return value if len(text) <= limit else {"truncated": True, "bytes": len(text), "head": text[:limit]}


@dataclass
class Plan:
    plan_id: str
    code: str
    operations: list[dict]
    state: dict
    created: float


@dataclass
class Run:
    execution_id: str
    stage: str  # plan | apply
    code: str
    plan: Plan | None = None
    approved_by: str | None = None
    calls: list[dict] = field(default_factory=list)
    operations: list[dict] = field(default_factory=list)  # plan: recorded. apply: approved operations in order
    checks: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    preflight_passed: set = field(default_factory=set)
    next_operation: int = 0
    halted: bool = False
    contradicted: bool = False
    result: Any = None
    ended: str = "failed"  # finished | failed | timeout | cancelled
    script_ms: float = 0.0
    state_before: dict = field(default_factory=dict)
    started_at: str = ""
    started: float = 0.0


class CodeModeService:
    def __init__(self, engine: Any, session: Session, resolve_thread: Callable[..., Any],
                 limits: Limits | None = None, trace_path: Path | None = None) -> None:
        self.engine, self.session, self.resolve_thread = engine, session, resolve_thread
        self.limits = limits or Limits.from_env()
        self.trace_path = trace_path or Path(os.environ.get("RESOLVE_FORGE_CODE_MODE_TRACE") or
                                             Path.home() / ".resolve-forge" / "code-mode-traces.jsonl").expanduser()
        self._plans: dict[str, Plan] = {}
        self._tools: dict[str, Any] | None = None
        self._lock = asyncio.Lock()
        self._cancel: asyncio.Event | None = None

    # ---- discovery ---------------------------------------------------------------------------------------------

    async def _catalog(self) -> dict[str, Any]:
        if self._tools is None:  # generated from the registered tools; only the policy table is hand-written
            self._tools = {tool.name: tool for tool in await self.engine.list_tools() if tool.name in policy.CATALOG}
        return self._tools

    async def previewable(self) -> set[str]:
        return {name for name, tool in (await self._catalog()).items() if "dry_run" in tool.inputSchema.get("properties", {})}

    async def search(self, query: str = "", category: str | None = None, risk: str | None = None,
                     names: list[str] | None = None, limit: int = 8) -> dict:
        tools = await self._catalog()
        if names:
            unknown = sorted(set(names) - set(tools))
            return {"tools": [self._entry(tools[name], full=True) for name in names if name in tools],
                    **({"unknown": unknown} if unknown else {})}
        entries = [self._entry(tool) for tool in tools.values()]
        if not query and not category and not risk:
            categories: dict[str, int] = {}
            for entry in entries:
                categories[entry["category"]] = categories.get(entry["category"], 0) + 1
            return {"categories": categories, "risks": list(policy.RISKS), "next": "search(query=...) or search(category=...)"}
        out: dict[str, Any] = {"tools": policy.rank(entries, query, category=category, risk=risk, limit=max(1, min(limit, 30)))}
        if notes := policy.unsupported_notes(query):
            out["unsupported"] = notes
        return out

    @staticmethod
    def _entry(tool: Any, full: bool = False) -> dict:
        category, risk, needs_resolve = policy.CATALOG[tool.name]
        description = (tool.description or "").strip()
        properties = tool.inputSchema.get("properties", {})
        entry = {"name": tool.name, "category": category, "risk": risk, "needs_resolve": needs_resolve,
                 "previewable": "dry_run" in properties, "summary": description.split("\n")[0],
                 "params": policy.compact_params(tool.inputSchema)}
        if full:
            entry |= {"description": description, "input_schema": tool.inputSchema,
                      "connections": ["bridge", "direct"],
                      "edition": "observed at runtime: call list_capabilities; never assumed from the version"}
        return entry

    # ---- execution ---------------------------------------------------------------------------------------------

    async def execute(self, code: str) -> dict:
        if not isinstance(code, str) or not code.strip():
            raise ValueError("code must be a non-empty JavaScript function body.")
        if len(code.encode("utf-8")) > self.limits.code_bytes:
            raise ValueError(f"code exceeds {self.limits.code_bytes} bytes.")
        return await self._guarded(lambda: self._start(Run(secrets.token_hex(6), "plan", code)))

    def describe_plan(self, plan_id: str) -> dict:
        plan = self._live_plan(plan_id)
        return {"plan_id": plan.plan_id, "operations": [{key: op[key] for key in ("tool", "risk", "args")} for op in plan.operations],
                "project": plan.state.get("project"), "timeline": plan.state.get("timeline")}

    async def approve(self, plan_id: str, approved_by: str) -> dict:
        async def begin() -> dict:
            plan = self._live_plan(plan_id)
            del self._plans[plan_id]  # one shot, whatever happens next
            run = Run(secrets.token_hex(6), "apply", plan.code, plan=plan, approved_by=approved_by, operations=plan.operations)
            state = await self.resolve_thread(fingerprint, self.session)
            stale = _stale_fields(plan.state, state)
            if stale:
                raise ForgeError(f"Resolve changed since the plan was made ({', '.join(stale)}).", code="STALE_STATE",
                                 hint="Inspect the current state and call execute again for a new plan.")
            if state.get("rendering"):
                raise ForgeError("A render is in progress.", code=E.RESOLVE_BUSY, hint="Wait for render_status, then plan again.")
            return await self._start(run, state)
        return await self._guarded(begin)

    def discard(self, plan_id: str) -> None:
        self._plans.pop(plan_id, None)

    def cancel(self) -> dict:
        if self._cancel is None:
            return {"cancelling": False, "reason": "No Code Mode run is active."}
        self._cancel.set()
        return {"cancelling": True, "note": "A Resolve call already in progress finishes first; it cannot be interrupted."}

    def _live_plan(self, plan_id: str) -> Plan:
        now = time.monotonic()
        for key in [key for key, plan in self._plans.items() if now - plan.created > PLAN_TTL_S]:
            del self._plans[key]
        plan = self._plans.get(plan_id)
        if plan is None:
            raise ForgeError(f"No pending plan '{plan_id}'.", code="PLAN_NOT_FOUND",
                             hint="Plans are one-shot and expire after 15 minutes; call execute again.")
        return plan

    async def _guarded(self, begin: Callable[[], Any]) -> dict:
        if self._lock.locked():
            return {"ok": False, "code": "CODE_MODE_BUSY", "error": "Another Code Mode run is active.",
                    "hint": "Wait for it, or call cancel_execution."}
        async with self._lock:
            return await begin()

    async def _start(self, run: Run, state: dict | None = None) -> dict:
        global _applying
        run.started, run.started_at = time.monotonic(), _now()
        run.state_before = state if state is not None else await self.resolve_thread(fingerprint, self.session)
        self._cancel = asyncio.Event()
        _applying = run.stage == "apply"
        sandbox = Sandbox(self.limits)
        try:
            await sandbox.start(run.code, run.stage, sorted(await self._catalog()))
            await self._loop(run, sandbox)
        except SandboxError as exc:
            run.errors.append({"code": exc.code, "error": str(exc)})
            run.ended = "failed"
        except ForgeError as exc:
            run.errors.append({"code": exc.code, "error": exc.message, "hint": exc.hint})
            run.ended = "failed"
        except OSError as exc:  # the pipe broke: the sandbox died while the host was replying
            run.errors.append({"code": "SANDBOX_CRASHED", "error": f"Lost the sandbox: {exc}"})
            run.ended = "failed"
        except asyncio.CancelledError:  # the client cancelled the MCP request; awaiting again could be refused
            run.ended = "cancelled"
            self._trace(run, self._report(run, run.state_before))
            raise
        except Exception as exc:  # edits may already be applied, so what happened must still be reported
            run.errors.append({"code": "CODE_MODE_INTERNAL", "error": f"{type(exc).__name__}: {exc}"})
            run.ended = "failed"
        finally:
            _applying = False
            self._cancel = None
            await sandbox.close()
        return self._finish(run, await self._state_after(run))

    async def _state_after(self, run: Run) -> dict:
        return await asyncio.shield(self.resolve_thread(fingerprint, self.session)) if self._applied(run) else run.state_before

    async def _loop(self, run: Run, sandbox: Sandbox) -> None:
        wall_deadline = run.started + self.limits.wall_ms / 1000
        cancelled = asyncio.ensure_future(self._cancel.wait())
        budget = self.limits.timeout_ms / 1000
        try:
            while True:
                started = time.monotonic()
                remaining = min(budget - run.script_ms / 1000, wall_deadline - started)
                receiving = asyncio.ensure_future(sandbox.receive())
                try:
                    done, _ = await asyncio.wait({receiving, cancelled}, timeout=max(0.0, remaining),
                                                 return_when=asyncio.FIRST_COMPLETED)
                finally:
                    if not receiving.done():
                        receiving.cancel()
                run.script_ms += (time.monotonic() - started) * 1000
                if cancelled in done:
                    run.ended = "cancelled"
                    return
                if receiving not in done:
                    run.ended = "timeout"
                    run.errors.append({"code": "CODE_MODE_TIMEOUT", "error": f"The script exceeded its time limit "
                                       f"({self.limits.timeout_ms} ms of script time, {self.limits.wall_ms} ms in total)."})
                    return
                message = receiving.result()
                kind = message.get("t")
                if kind == "done":
                    run.result, run.logs, run.ended = message.get("result"), _strings(message.get("logs")), "finished"
                    return
                if kind == "error":
                    run.logs = _strings(message.get("logs"))
                    run.errors.append({"code": message.get("code") or "SCRIPT_ERROR",
                                       "error": f"{message.get('name')}: {message.get('message')}"})
                    run.ended = "failed"
                    return
                if kind == "check":
                    if len(run.checks) >= self.limits.max_calls:
                        raise SandboxError(f"More than {self.limits.max_calls} checks in one run.", "CALL_LIMIT")
                    self._record_check(run, message)
                elif kind == "call":
                    reply = await self._dispatch(run, message.get("tool"), message.get("args"))
                    if self._cancel.is_set():
                        run.ended = "cancelled"
                        return
                    await asyncio.wait_for(sandbox.send({"t": "reply", "id": message.get("id"), "result": self._fit(reply)}),
                                           timeout=max(0.1, budget - run.script_ms / 1000))
                else:
                    raise SandboxError("The sandbox broke the message protocol.", "SANDBOX_PROTOCOL")
        except asyncio.TimeoutError:
            run.ended = "timeout"
            run.errors.append({"code": "CODE_MODE_TIMEOUT", "error": "The script stopped reading replies."})
        finally:
            cancelled.cancel()

    def _fit(self, reply: dict) -> dict:
        size = len(json.dumps(reply, ensure_ascii=False, default=str).encode("utf-8"))
        if size <= self.limits.message_bytes // 2:
            return reply
        return {"ok": False, "code": "RESULT_TOO_LARGE", "error": f"This result is {size} bytes, over the sandbox limit.",
                "hint": "Call the tool directly, or narrow it (one track, one source)."}

    @staticmethod
    def _record_check(run: Run, message: dict) -> None:
        check = {"label": str(message.get("label"))[:200], "passed": message.get("passed") is True,
                 "details": _bounded_text(message.get("details"), 500)}
        run.checks.append(check)
        run.contradicted = run.contradicted or not check["passed"]

    async def _dispatch(self, run: Run, tool: Any, args: Any) -> dict:
        record: dict[str, Any] = {"seq": len(run.calls) + 1, "tool": str(tool)[:80]}
        run.calls.append(record)
        if len(run.calls) > self.limits.max_calls:
            return self._blocked(record, policy.SYSTEM, f"More than {self.limits.max_calls} calls in one run.", "CALL_LIMIT", run)
        if not isinstance(tool, str) or not isinstance(args, dict):
            return self._blocked(record, policy.SYSTEM, "A capability call needs a tool name and an arguments object.", "CODE_MODE_DENIED", run)
        decision = policy.decide(tool, args, tool in await self.previewable())
        record["risk"] = decision.risk
        if decision.effect == "deny":
            return self._blocked(record, decision.risk, decision.reason, "CODE_MODE_DENIED", run)
        if decision.effect == "approve":
            handler = self._plan_operation if run.stage == "plan" else self._apply_operation
            return await handler(run, record, tool, args, decision)
        record["effect"] = decision.effect
        reply = await self._invoke(run, record, tool, args)
        if tool == "preflight_render" and reply.get("technical_passed") is True:
            run.preflight_passed.add(args.get("format"))
        return reply

    @staticmethod
    def _blocked(record: dict, risk: str, reason: str, code: str, run: Run) -> dict:
        record.update(risk=risk, effect="deny", status="blocked", code=code)
        run.errors.append({"code": code, "error": reason, "tool": record["tool"]})
        return {"ok": False, "code": code, "error": reason}

    def _preflight_refusal(self, run: Run, tool: str, args: dict) -> str | None:
        if tool == "render_for" and args.get("format") not in run.preflight_passed:
            return "Call preflight_render with the same format first, and fix what it reports, before render_for."
        return None

    async def _plan_operation(self, run: Run, record: dict, tool: str, args: dict, decision: policy.Decision) -> dict:
        if refusal := self._preflight_refusal(run, tool, args):
            return self._blocked(record, decision.risk, refusal, "PREFLIGHT_REQUIRED", run)
        record["effect"] = "planned"
        operation = {"seq": len(run.operations) + 1, "tool": tool, "risk": decision.risk, "args": args,
                     "key": policy.operation_key(tool, args)}
        run.operations.append(operation)
        if tool not in await self.previewable():
            record["status"] = "planned"
            return {"ok": True, "planned": True, "applied": False, "preview": None,
                    "note": f"{tool} has no dry run; it will execute after approval."}
        reply = await self._invoke(run, record, tool, {**args, "dry_run": True})
        if reply.get("ok") is False:
            run.operations.pop()
            return reply
        record["status"] = "planned"
        operation["preview"] = _bounded_text(reply)
        return {**reply, "planned": True, "applied": False, "preview": True}

    async def _apply_operation(self, run: Run, record: dict, tool: str, args: dict, decision: policy.Decision) -> dict:
        record["effect"] = "apply"
        if run.halted:
            return self._blocked(record, decision.risk, "An earlier approved step failed; later edits were not attempted.", "RUN_HALTED", run)
        expected = run.operations[run.next_operation] if run.next_operation < len(run.operations) else None
        if expected is None or expected["key"] != policy.operation_key(tool, args):
            run.halted = True
            return self._blocked(record, decision.risk, f"{tool} with these arguments is not the next approved operation.",
                                 "NOT_APPROVED", run)
        if refusal := self._preflight_refusal(run, tool, args):
            run.halted = True
            return self._blocked(record, decision.risk, refusal, "PREFLIGHT_REQUIRED", run)
        refusal = None if self._touches_projects(run) else await self._environment_refusal(run)
        if refusal:
            run.halted = True
            return self._blocked(record, decision.risk, refusal, "STALE_STATE", run)
        run.next_operation += 1
        reply = await self._invoke(run, record, tool, {**args, "dry_run": False} if tool in await self.previewable() else args)
        expected["status"] = record["status"]
        if reply.get("ok") is False:
            run.halted = True
            if reply.get("code") == "READBACK_FAILED":
                run.contradicted = True
                expected["verification"] = "contradictory"
            return reply
        expected["verification"] = "by_tool_readback" if tool in policy.VERIFIED_BY_TOOL else "unverified"
        record["verification"] = expected["verification"]
        expected["outcome"] = _bounded_text({key: reply[key] for key in ("timeline", "source", "file", "job_id", "project") if key in reply})
        return reply

    @staticmethod
    def _touches_projects(run: Run) -> bool:
        return any(op["tool"] == "project_workflow" and op["args"].get("action") in {"create", "load"} for op in run.operations)

    async def _environment_refusal(self, run: Run) -> str | None:
        now = await self.resolve_thread(fingerprint, self.session)
        if now.get("project") != run.state_before.get("project"):
            return f"The open project changed to {now.get('project')!r} during the run."
        if now.get("rendering"):
            return "A render started during the run."
        return None

    async def _invoke(self, run: Run, record: dict, tool: str, args: dict) -> dict:
        """The one path to a handler: FastMCP's schema validation, then the tool's own error envelope and thread."""
        started = time.monotonic()
        token = _host_dispatch.set(True)
        try:
            reply = _unwrap(await self.engine.call_tool(tool, args))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # FastMCP reports schema violations by raising
            reply = {"ok": False, "code": E.INVALID_ARGUMENT, "error": str(exc)[:1000]}
        finally:
            _host_dispatch.reset(token)
        record["ms"] = round((time.monotonic() - started) * 1000, 1)
        record["status"] = "failed" if reply.get("ok") is False else "ok"
        if record["status"] == "failed":
            record["code"] = reply.get("code")
            run.errors.append({"code": reply.get("code"), "error": str(reply.get("error"))[:1000], "tool": tool})
        return reply

    # ---- reporting ---------------------------------------------------------------------------------------------

    @staticmethod
    def _applied(run: Run) -> list[dict]:
        return [op for op in run.operations if op.get("status") == "ok"] if run.stage == "apply" else []

    def _status(self, run: Run) -> str:
        applied = self._applied(run)
        calls = run.calls
        return policy.overall_status(
            stage=run.stage, ended=run.ended, operations=len(run.operations), applied=len(applied),
            not_run=len(run.operations) - run.next_operation if run.stage == "apply" else 0,
            blocked=sum(c.get("status") == "blocked" for c in calls),
            failed=sum(c.get("status") == "failed" for c in calls), contradicted=run.contradicted,
            unverified=sum(op.get("verification") == "unverified" for op in applied),
            checks_passed=sum(check["passed"] for check in run.checks))

    def _report(self, run: Run, state_after: dict) -> dict:
        status = self._status(run)
        report: dict[str, Any] = {
            "ok": status in {"success", "needs_approval"}, "status": status, "execution_id": run.execution_id,
            "stage": run.stage, "result": run.result, "calls": run.calls, "started_at": run.started_at,
            "ended_at": _now(), "duration_ms": round((time.monotonic() - run.started) * 1000, 1),
            "script_ms": round(run.script_ms, 1), "cancelled": run.ended == "cancelled"}
        for key, value in (("logs", run.logs), ("checks", run.checks), ("warnings", run.warnings), ("errors", run.errors)):
            if value:
                report[key] = value
        if run.errors:
            report["code"] = run.errors[0]["code"]
        if run.stage == "apply":
            done = self._applied(run)
            report |= {"approved_by": run.approved_by, "atomic": False, "applied": [{key: op.get(key) for key in ("tool", "verification", "outcome")} for op in done],
                       "not_run": [op["tool"] for op in run.operations[run.next_operation:]],
                       "semantic_changes": _changes(run.state_before, state_after)}
            if status != "success":
                report["recovery"] = ("Nothing is rolled back: applied steps stay. Timeline edits are on the copies named in "
                                      "`applied`; the source timeline was not edited. Select it with timeline_versions.")
        return report

    def _finish(self, run: Run, state_after: dict) -> dict:
        report = self._report(run, state_after)
        if report["status"] == "needs_approval":
            while len(self._plans) >= MAX_PLANS:
                del self._plans[next(iter(self._plans))]
            plan = Plan(secrets.token_hex(8), run.code, run.operations, run.state_before, time.monotonic())
            self._plans[plan.plan_id] = plan
            report["plan"] = {"plan_id": plan.plan_id, "expires_in_s": PLAN_TTL_S,
                              "project": plan.state.get("project"), "timeline": plan.state.get("timeline"),
                              "operations": [{key: op[key] for key in ("seq", "tool", "risk", "args", "preview") if key in op}
                                             for op in run.operations],
                              "next": "Show this to the user, then call approve_execution(plan_id). Nothing was changed."}
        self._trace(run, report)
        return self._bounded(report)

    def _bounded(self, report: dict) -> dict:
        """Fit the model's limit by shedding the most repetitive parts first; the trace on disk keeps everything."""
        limit = self.limits.output_bytes
        def size() -> int:
            return len(json.dumps(report, ensure_ascii=False, default=str).encode("utf-8"))
        if size() <= limit:
            return report
        result_bytes = len(json.dumps(report.get("result"), ensure_ascii=False, default=str).encode("utf-8"))
        report["result"] = {"truncated": True, "bytes": result_bytes,
                            "head": json.dumps(report.get("result"), ensure_ascii=False, default=str)[:limit // 4]}
        for key in ("logs", "calls"):
            if size() > limit and key in report:
                report[key] = f"omitted; {len(report[key])} entries in {self.trace_path.name}"
        if size() > limit and "plan" in report:
            for operation in report["plan"]["operations"]:
                operation["preview"] = "omitted"
                operation["args"] = _bounded_text(operation["args"], 300)
        if size() > limit:
            report["result"] = {"truncated": True, "bytes": result_bytes}
            report["errors"] = report.get("errors", [])[:3]
        return report

    def _trace(self, run: Run, report: dict) -> None:
        """Append-only audit line, including what the bounded reply may omit. Losing it never fails an edit."""
        entry = {key: report.get(key) for key in ("execution_id", "status", "stage", "started_at", "ended_at", "duration_ms",
                                                  "script_ms", "cancelled", "calls", "checks", "warnings", "errors",
                                                  "approved_by", "applied", "not_run", "semantic_changes")}
        entry["code"] = run.code
        entry["plan_id"] = run.plan.plan_id if run.plan else None
        try:
            self.trace_path.parent.mkdir(parents=True, exist_ok=True)
            if self.trace_path.exists() and self.trace_path.stat().st_size > TRACE_BYTES:
                self.trace_path.replace(self.trace_path.with_suffix(".1.jsonl"))
            with self.trace_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except OSError as exc:
            report.setdefault("warnings", []).append(f"Audit trace not written: {exc}")


def _unwrap(result: Any) -> dict:
    """FastMCP returns (content, structured) or content; the handlers' dict is what the sandbox should see."""
    if isinstance(result, tuple):
        if isinstance(result[1], dict):
            return result[1]
        result = result[0]
    try:
        reply = json.loads(result[0].text)
    except (IndexError, AttributeError, TypeError, ValueError):
        return {"ok": False, "code": "BAD_TOOL_RESULT", "error": "The tool returned no JSON result."}
    return reply if isinstance(reply, dict) else {"ok": True, "value": reply}


def _strings(value: Any) -> list[str]:
    return [str(item)[:2000] for item in value][:200] if isinstance(value, list) else []


def _changes(before: dict, after: dict) -> dict:
    return {key: {"before": before.get(key), "after": after.get(key)} for key in _stale_fields(before, after)}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
