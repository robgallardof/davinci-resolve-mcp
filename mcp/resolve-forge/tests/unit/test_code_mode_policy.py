"""Code Mode's pure policy and how the server is composed. No sandbox needed."""

import asyncio
import json
import os
import subprocess
import sys

import pytest
from mcp.server.fastmcp import FastMCP

from resolve_forge import tools
from resolve_forge.domain import code_mode as policy
from resolve_forge.gateway import Session
from resolve_forge.services.code_mode_sandbox import Limits


@pytest.fixture(scope="module")
def registered():
    mcp = FastMCP("policy")
    tools.register(mcp, Session([]))
    return {tool.name: tool for tool in asyncio.run(mcp.list_tools())}


def test_every_tool_is_classified_and_nothing_stale(registered):
    assert set(policy.CATALOG) == set(registered)
    assert {risk for _, risk, _ in policy.CATALOG.values()} <= set(policy.RISKS)


def test_previews_are_the_default_wherever_a_tool_offers_them(registered):
    """decide() treats a missing dry_run as a preview. That is only safe while every tool defaults it to true."""
    for name, tool in registered.items():
        spec = tool.inputSchema["properties"].get("dry_run")
        if spec is not None:
            assert spec.get("default") is True, name


def test_tools_without_a_preview_never_run_without_approval(registered):
    for name, (_, risk, _) in policy.CATALOG.items():
        previewable = "dry_run" in registered[name].inputSchema["properties"]
        if risk not in policy.IMMEDIATE and risk != policy.SYSTEM and name not in {"project_workflow", "timeline_versions", "gallery_stills"}:
            effect = policy.decide(name, {"entries": [], "values": {}}, previewable).effect
            assert effect == ("preview" if previewable else "approve"), name


@pytest.mark.parametrize("tool,args,previewable,effect", [
    ("no_such_tool", {}, False, "deny"),
    ("execute", {}, False, "deny"),
    ("approve_execution", {"plan_id": "x"}, False, "deny"),
    ("repair_bridge_connection", {"dry_run": True}, True, "deny"),
    ("list_clips", {}, False, "run"),
    ("project_workflow", {}, False, "run"),
    ("project_workflow", {"action": "list"}, False, "run"),
    ("project_workflow", {"action": "load", "project_name": "x"}, False, "approve"),
    ("project_workflow", {"action": ["list"]}, False, "approve"),
    ("project_workflow", {"action": "LIST"}, False, "approve"),
    ("timeline_versions", {"action": "duplicate"}, False, "approve"),
    ("gallery_stills", {"action": "capture"}, False, "approve"),
    ("timeline_markers", {}, True, "run"),
    ("timeline_markers", {"entries": [{"seconds": 1}]}, True, "preview"),
    ("timeline_markers", {"entries": [{"seconds": 1}], "dry_run": False}, True, "approve"),
    ("media_metadata", {"source": "a", "dry_run": False}, True, "run"),
    ("media_metadata", {"source": "a", "values": {"x": 1}, "dry_run": False}, True, "approve"),
    ("edit_clips", {"dry_run": "false"}, True, "deny"),
    ("edit_clips", {"dry_run": 0}, True, "deny"),
    ("render_for", {"format": "reels"}, False, "approve"),
    ("add_captions", {}, False, "approve"),
])
def test_decide(tool, args, previewable, effect):
    assert policy.decide(tool, args, previewable).effect == effect


def test_operation_identity_ignores_dry_run_and_key_order_but_not_values():
    key = policy.operation_key("edit_clips", {"track": 1, "indices": [1]})
    assert key == policy.operation_key("edit_clips", {"indices": [1], "track": 1, "dry_run": False})
    assert key != policy.operation_key("edit_clips", {"track": 1, "indices": [2]})
    assert key != policy.operation_key("grade_clips", {"track": 1, "indices": [1]})


ENTRIES = [
    {"name": "timeline_markers", "category": "markers", "risk": "project_write", "summary": "Read or add markers", "params": []},
    {"name": "audit_timeline", "category": "timeline", "risk": "read", "summary": "QC of gaps", "params": []},
    {"name": "add_captions", "category": "subtitles", "risk": "project_write", "summary": "Burned-in text", "params": ["style:string"]},
    {"name": "render_for", "category": "render", "risk": "render", "summary": "Queue a render", "params": []},
]


def test_rank_prefers_names_uses_aliases_and_filters():
    assert policy.rank(ENTRIES, "markers")[0]["name"] == "timeline_markers"
    assert policy.rank(ENTRIES, "subtitles")[0]["name"] == "add_captions"  # alias and category
    assert [e["name"] for e in policy.rank(ENTRIES, "timeline", risk="read")] == ["audit_timeline"]
    assert [e["name"] for e in policy.rank(ENTRIES, "", category="render")] == ["render_for"]
    assert policy.rank(ENTRIES, "zzz") == []
    assert len(policy.rank(ENTRIES, "", limit=2)) == 2


def test_unsupported_operations_get_a_clear_no():
    assert any("transitions" in note for note in policy.unsupported_notes("add a cross dissolve transition"))
    assert any("Deleting" in note for note in policy.unsupported_notes("delete clips"))
    assert policy.unsupported_notes("read the timeline") == []


def test_compact_params():
    schema = {"required": ["format"], "properties": {"format": {"type": "string"}, "name": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                                                     "start": {"type": "boolean", "default": True}}}
    assert policy.compact_params(schema) == ["format:string", "name:string=null", "start:boolean=true"]


BASE = dict(stage="apply", ended="finished", operations=2, applied=2, not_run=0, blocked=0, failed=0,
            contradicted=False, unverified=0, checks_passed=0)


@pytest.mark.parametrize("changes,status", [
    ({}, "success"),
    ({"unverified": 1}, "unverified"),
    ({"unverified": 1, "checks_passed": 1}, "success"),
    ({"contradicted": True, "checks_passed": 3}, "contradictory"),
    ({"failed": 1}, "partial"),
    ({"not_run": 1, "applied": 1}, "partial"),
    ({"blocked": 1}, "partial"),
    ({"blocked": 1, "applied": 0}, "blocked"),
    ({"ended": "failed"}, "partial"),
    ({"ended": "failed", "applied": 0}, "failed"),
    ({"ended": "timeout"}, "timeout"),
    ({"ended": "cancelled"}, "cancelled"),
    ({"stage": "plan", "applied": 0}, "needs_approval"),
    ({"stage": "plan", "applied": 0, "operations": 0}, "success"),
    ({"stage": "plan", "applied": 0, "blocked": 1}, "blocked"),
])
def test_overall_status_never_reads_better_than_the_worst_step(changes, status):
    assert policy.overall_status(**{**BASE, **changes}) == status


def test_limits_from_environment():
    assert Limits.from_env({}) == Limits()
    custom = Limits.from_env({"RESOLVE_FORGE_CODE_MODE_TIMEOUT_MS": "500", "RESOLVE_FORGE_CODE_MODE_MAX_OUTPUT_BYTES": "1024"})
    assert custom.timeout_ms == 500 and custom.output_bytes == 1024
    for bad in ("abc", "0", "-1"):
        with pytest.raises(ValueError):
            Limits.from_env({"RESOLVE_FORGE_CODE_MODE_MEMORY_MB": bad})


def test_server_lists_code_mode_beside_every_direct_tool_and_keeps_resources(registered):
    probe = ("import asyncio, json; from resolve_forge import server; mcp = server.build();"
             "print(json.dumps({'tools': [t.name for t in asyncio.run(mcp.list_tools())],"
             " 'resources': [str(r.uri) for r in asyncio.run(mcp.list_resources())]}))")
    done = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
    assert done.returncode == 0, done.stderr
    listing = json.loads(done.stdout)
    assert set(listing["tools"]) == set(registered) | {"search", "execute", "approve_execution", "cancel_execution"}
    assert {"resolve://status", "resolve://timeline"} <= set(listing["resources"])


def test_a_bad_limit_stops_the_server_with_a_clear_message():
    env = {**os.environ, "RESOLVE_FORGE_CODE_MODE_TIMEOUT_MS": "soon"}
    done = subprocess.run([sys.executable, "-m", "resolve_forge.server"], capture_output=True, text=True, env=env, timeout=120, stdin=subprocess.DEVNULL)
    assert done.returncode != 0 and "TIMEOUT_MS must be an integer" in done.stderr and "Traceback" not in done.stderr
