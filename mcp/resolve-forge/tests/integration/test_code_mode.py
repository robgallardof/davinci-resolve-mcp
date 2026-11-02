"""Code Mode end to end against a fake Resolve: real sandbox, real tools, the five editing workflows, every status."""

import asyncio
import json
import time

import pytest

from code_mode_support import CodeForge, code_forge  # noqa: F401
from resolve_forge import tools
from resolve_forge.services import code_mode_service
from resolve_forge.services.code_mode_sandbox import Limits

MARK = "await resolve.timeline_markers({entries:[{seconds:1,name:'cut'}],copy_name:'Marked',dry_run:false});"


# ---- discovery ---------------------------------------------------------------------------------------------------

def test_search_is_generated_from_the_registered_tools(code_forge):
    top = code_forge("search")
    assert {"timeline", "media_pool", "render", "color", "fusion", "audio", "subtitles", "markers"} <= set(top["categories"])
    found = code_forge("search", query="markers")["tools"]
    assert found[0]["name"] == "timeline_markers" and found[0]["previewable"] and "input_schema" not in found[0]
    full = code_forge("search", names=["render_for", "nope"])
    assert full["tools"][0]["input_schema"]["required"] == ["format"]
    assert "edition" in full["tools"][0] and full["unknown"] == ["nope"]


def test_search_filters_and_answers_no_honestly(code_forge):
    assert all(t["risk"] == "read" for t in code_forge("search", query="timeline", risk="read")["tools"])
    assert any("transitions" in note for note in code_forge("search", query="transition")["unsupported"])
    assert "repair_bridge_connection" in {t["name"] for t in code_forge("search", category="system")["tools"]}


def test_search_works_without_resolve_or_a_sandbox(tmp_path):
    forge = CodeForge(tmp_path, reachable=False)
    assert forge("search", query="render")["tools"]
    tools.set_write_gate(None)


# ---- the workflows the feature exists for ------------------------------------------------------------------------

def test_workflow_a_timeline_analysis_is_read_only(code_forge):
    before = code_mode_service.fingerprint(code_forge.session)
    reply = code_forge.run("""
        const status = await resolve.forge_status();
        const audit = await resolve.audit_timeline();
        const clips = (await resolve.list_clips({track: 1})).clips;
        const gaps = audit.issues.filter(i => i.code === 'GAP' || i.code === 'OVERLAP');
        return {timeline: status.timeline, clips: clips.length, frames: clips.map(c => c.duration),
                ends: clips.map(c => timecode.frameToTimecode(c.start + c.duration, status.fps)), gaps};
    """)
    assert reply["status"] == "success" and "plan" not in reply
    assert reply["result"]["timeline"] == "Master" and reply["result"]["clips"] == 2 and reply["result"]["frames"] == [300, 300]
    assert {c["risk"] for c in reply["calls"]} == {"read"}
    assert code_mode_service.fingerprint(code_forge.session) == before


def test_workflow_b_short_form_edit_plans_then_applies_on_a_copy(code_forge):
    source = code_forge.project.current
    props = [dict(item.props) for item in source.tracks[0]]
    timelines = len(code_forge.project.timelines)
    script = """
        const format = (await resolve.list_formats({orientation: 'vertical'})).formats.tiktok;
        const clips = (await resolve.list_clips({track: 1})).clips;
        const long = clips.filter(c => c.duration >= 300).map(c => c.index);
        const edit = await resolve.edit_clips({properties: {ZoomX: 1.2, ZoomY: 1.2}, indices: long, copy_name: 'TikTok cut', dry_run: false});
        if (run.mode === 'apply') {
            const after = (await resolve.list_clips({track: 1})).clips;
            run.check('zoom applied to the chosen clips', after.every(c => Number(c.zoom) === 1.2), after.map(c => c.zoom));
            run.check('same clip count', after.length === clips.length);
        }
        return {target: [format.width, format.height], long, applied: edit.applied, timeline: edit.timeline};
    """
    plan = code_forge.run(script)
    assert plan["status"] == "needs_approval" and plan["ok"]
    assert plan["result"]["applied"] is False
    operation = plan["plan"]["operations"][0]
    assert operation["tool"] == "edit_clips" and operation["risk"] == "project_write" and operation["preview"]["applied"] is False
    assert plan["plan"]["project"] == "Demo" and plan["plan"]["timeline"] == "Master"
    assert code_forge.project.current is source and len(code_forge.project.timelines) == timelines  # the plan changed nothing

    done = code_forge.approve(plan)
    assert done["status"] == "success", done
    assert done["result"]["applied"] is True and done["result"]["timeline"] == "TikTok cut"
    assert done["atomic"] is False and done["applied"][0]["verification"] == "by_tool_readback"
    assert [c["passed"] for c in done["checks"]] == [True, True]
    assert done["semantic_changes"]["timeline"] == {"before": "Master", "after": "TikTok cut"}
    assert code_forge.project.current is not source
    assert [item.props for item in source.tracks[0]] == props  # the source timeline was not edited


def test_workflow_c_subtitles_from_corrected_words(code_forge):
    script = """
        const words = [{text: 'Hello', start: 0.1, end: 0.5}, {text: 'there', start: 0.45, end: 0.9}];
        const overlapping = words.filter((w, i) => i && w.start < words[i - 1].end);
        const fixed = words.map((w, i) => i && w.start < words[i - 1].end ? {...w, start: words[i - 1].end} : w);
        const placed = await resolve.add_captions({words: fixed, style: 'studio'});
        if (run.mode === 'apply') run.check('caption track exists', (await resolve.list_clips({track: 3})).clips.length > 0);
        return {overlapping: overlapping.length, planned: placed.planned === true};
    """
    plan = code_forge.run(script)
    assert plan["status"] == "needs_approval" and plan["result"] == {"overlapping": 1, "planned": True}
    assert plan["plan"]["operations"][0]["args"]["words"][1]["start"] == 0.5
    done = code_forge.approve(plan)
    assert done["status"] == "success", done
    assert done["result"]["planned"] is False


def test_workflow_d_media_organisation(code_forge, tmp_path):
    source = tmp_path / "take.mov"
    source.write_bytes(b"not really video")
    original = source.read_bytes()
    code_forge("ingest_media", paths=[str(source)], dry_run=False)
    script = """
        const media = await resolve.list_media();
        const moved = await resolve.organise_media({by: 'extension', dry_run: false});
        if (run.mode === 'apply') run.check('catalogue still lists the clip', JSON.stringify(await resolve.list_media()).includes('take.mov'));
        return {clips: JSON.stringify(media).includes('take.mov'), moved};
    """
    plan = code_forge.run(script)
    assert plan["status"] == "needs_approval" and plan["result"]["clips"]
    done = code_forge.approve(plan)
    assert done["status"] == "success", done
    assert source.read_bytes() == original  # sources are immutable


def _renderable(forge, tmp_path):
    media = tmp_path / "source.mp4"
    media.write_bytes(b"x")
    for track in forge.project.current.tracks:
        for item in track:
            if item.GetMediaPoolItem() is not None:
                item.GetMediaPoolItem().path = str(media)


def test_workflow_e_render_preparation_queues_after_approval_without_starting(code_forge, tmp_path):
    _renderable(code_forge, tmp_path)
    jobs = len(code_forge.project.jobs) if hasattr(code_forge.project, "jobs") else None
    script = f"""
        const check = await resolve.preflight_render({{format: 'youtube_1080'}});
        const spec = (await resolve.list_formats({{orientation: 'horizontal'}})).formats.youtube_1080;
        if (!check.technical_passed) return {{problems: check.issues}};
        const job = await resolve.render_for({{format: 'youtube_1080', target_dir: {json.dumps(str(tmp_path / 'out'))}, start: false}});
        return {{codec: spec.codec, job: job.job_id ?? null, planned: job.planned === true}};
    """
    plan = code_forge.run(script)
    assert plan["status"] == "needs_approval", plan
    assert plan["result"]["planned"] and plan["plan"]["operations"][0]["risk"] == "render"
    if jobs is not None:
        assert len(code_forge.project.jobs) == jobs  # planning queued nothing
    done = code_forge.approve(plan)
    assert done["status"] == "unverified", done  # a queued job is not a checked file: never reported as verified
    assert done["result"]["job"] and done["applied"][0]["outcome"]["job_id"]


# ---- render protection -------------------------------------------------------------------------------------------

def test_render_needs_a_passing_preflight_of_the_same_format(code_forge, tmp_path):
    reply = code_forge.run(f"return await resolve.render_for({{format: 'reels', target_dir: {json.dumps(str(tmp_path))}}})")
    assert reply["status"] == "blocked" and reply["code"] == "PREFLIGHT_REQUIRED" and "plan" not in reply
    _renderable(code_forge, tmp_path)
    other = code_forge.run(f"""await resolve.preflight_render({{format: 'youtube_1080'}});
        return await resolve.render_for({{format: 'youtube_4k', target_dir: {json.dumps(str(tmp_path))}}})""")
    assert other["code"] == "PREFLIGHT_REQUIRED"


def test_existing_render_output_is_refused_on_both_paths(code_forge, tmp_path):
    (tmp_path / "final.mp4").write_bytes(b"precious")
    direct = code_forge("render_for", format="youtube_1080", target_dir=str(tmp_path), name="final")
    assert direct["ok"] is False and direct["code"] == "RENDER_REFUSED" and "overwrite" in direct["hint"]
    _renderable(code_forge, tmp_path)
    plan = code_forge.run(f"""await resolve.preflight_render({{format: 'youtube_1080'}});
        return await resolve.render_for({{format: 'youtube_1080', target_dir: {json.dumps(str(tmp_path))}, name: 'final'}})""")
    done = code_forge.approve(plan)
    assert done["status"] == "failed" and done["code"] == "RENDER_REFUSED" and done["applied"] == []
    assert (tmp_path / "final.mp4").read_bytes() == b"precious"
    assert code_forge("render_for", format="youtube_1080", target_dir=str(tmp_path), name="final", overwrite=True)["ok"]


# ---- same policy as the direct tools -----------------------------------------------------------------------------

@pytest.mark.parametrize("args", [{"properties": {"Opacity": 200}}, {"properties": {"Execute": 1}}, {"indices": [99], "enabled": False}])
def test_invalid_arguments_fail_exactly_as_they_do_directly(code_forge, args):
    direct = code_forge("edit_clips", **args)
    assert direct["ok"] is False
    reply = code_forge.run(f"""try {{ await resolve.edit_clips({json.dumps({**args, "dry_run": False})}); }}
        catch (error) {{ return {{name: error.name, code: error.code, message: error.message}}; }}""")
    assert reply["result"] == {"name": "CapabilityError", "code": direct["code"], "message": direct["error"]}
    assert reply["status"] == "partial"  # catching the error must not turn the run into a success
    assert len(code_forge.project.timelines) == 1


def test_schema_violations_reach_the_script_as_invalid_argument(code_forge):
    reply = code_forge.run("return await resolve.list_clips({track: 'not a number'})")
    assert reply["status"] == "failed" and reply["code"] == "INVALID_ARGUMENT"


def test_unreachable_resolve_reports_the_same_code(tmp_path):
    forge = CodeForge(tmp_path, reachable=False)
    try:
        reply = forge.run("return await resolve.forge_status()")
        assert reply["status"] == "failed" and reply["code"] == "RESOLVE_UNREACHABLE"
        pure = forge.run("return Object.keys((await resolve.list_formats({orientation: 'vertical'})).formats).length")
        assert pure["status"] == "success" and pure["result"] > 3
    finally:
        tools.set_write_gate(None)


# ---- approval ----------------------------------------------------------------------------------------------------

def test_a_plan_is_one_shot_and_unknown_plans_are_refused(code_forge):
    plan = code_forge.run(MARK)
    assert code_forge.approve(plan)["status"] == "success"
    again = code_forge("approve_execution", plan_id=plan["plan"]["plan_id"])
    assert again["ok"] is False and again["code"] == "PLAN_NOT_FOUND"
    assert code_forge("approve_execution", plan_id="made-up")["code"] == "PLAN_NOT_FOUND"


def test_expired_plans_are_refused(code_forge, monkeypatch):
    plan = code_forge.run(MARK)
    now = time.monotonic()
    monkeypatch.setattr(code_mode_service.time, "monotonic", lambda: now + code_mode_service.PLAN_TTL_S + 1)
    assert code_forge.approve(plan)["code"] == "PLAN_NOT_FOUND"


def test_a_changed_timeline_makes_the_plan_stale(code_forge):
    plan = code_forge.run(MARK)
    assert code_forge("edit_clips", properties={"ZoomX": 1.1}, dry_run=False, copy_name="Someone else")["ok"]
    reply = code_forge.approve(plan)
    assert reply["ok"] is False and reply["code"] == "STALE_STATE"
    assert "Marked" not in {t.GetName() for t in code_forge.project.timelines}


def test_a_moved_clip_makes_the_plan_stale_even_with_the_same_counts(code_forge):
    plan = code_forge.run(MARK)
    code_forge.project.current.tracks[0][1].start += 5
    assert code_forge.approve(plan)["code"] == "STALE_STATE"


def test_a_running_render_blocks_the_plan(code_forge, monkeypatch):
    plan = code_forge.run(MARK)
    monkeypatch.setattr(type(code_forge.project), "IsRenderingInProgress", lambda self: True)
    assert code_forge.approve(plan)["code"] == "RESOLVE_BUSY"


def test_a_script_cannot_change_what_was_approved(code_forge):
    plan = code_forge.run("""
        await resolve.edit_clips({properties: {ZoomX: run.mode === 'apply' ? 9 : 1.1}, copy_name: 'A', dry_run: false});
    """)
    reply = code_forge.approve(plan)
    assert reply["status"] == "blocked" and reply["code"] == "NOT_APPROVED"
    assert {t.GetName() for t in code_forge.project.timelines} == {"Master"}


def test_a_script_cannot_add_an_operation_when_applying(code_forge):
    plan = code_forge.run(f"""{MARK}
        if (run.mode === 'apply') await resolve.render_for({{format: 'reels'}});""")
    reply = code_forge.approve(plan)
    assert reply["status"] == "partial" and reply["code"] == "NOT_APPROVED"
    assert [op["tool"] for op in reply["applied"]] == ["timeline_markers"]


def test_a_script_cannot_skip_ahead(code_forge):
    plan = code_forge.run(f"""if (run.mode === 'plan') {MARK}
        await resolve.edit_clips({{properties: {{ZoomX: 1.1}}, copy_name: 'B', dry_run: false}});""")
    reply = code_forge.approve(plan)
    assert reply["code"] == "NOT_APPROVED" and reply["applied"] == []


def test_a_script_that_stops_early_is_partial_and_names_what_did_not_run(code_forge):
    plan = code_forge.run(f"""{MARK}
        if (run.mode === 'apply') return 'stopping';
        await resolve.edit_clips({{properties: {{ZoomX: 1.1}}, copy_name: 'B', dry_run: false}});""")
    reply = code_forge.approve(plan)
    assert reply["status"] == "partial" and reply["not_run"] == ["edit_clips"]
    assert "rolled back" in reply["recovery"]


def test_failure_halts_later_edits_and_is_not_called_atomic(code_forge):
    """The second step reuses a timeline name, which only fails once the first step has really created it."""
    plan = code_forge.run("""
        await resolve.timeline_markers({entries: [{seconds: 1, name: 'one'}], copy_name: 'First', dry_run: false});
        try { await resolve.timeline_markers({entries: [{seconds: 2, name: 'two'}], copy_name: 'First', dry_run: false}); }
        catch (error) { console.log('coping', error.code); }
        await resolve.timeline_markers({entries: [{seconds: 3, name: 'three'}], copy_name: 'Third', dry_run: false});
    """)
    assert len(plan["plan"]["operations"]) == 3
    reply = code_forge.approve(plan)
    assert reply["status"] == "partial" and reply["ok"] is False and reply["atomic"] is False
    assert reply["code"] == "TIMELINE_EXISTS"
    assert [op["tool"] for op in reply["applied"]] == ["timeline_markers"]
    assert reply["not_run"] == ["timeline_markers"]
    assert "Third" not in {t.GetName() for t in code_forge.project.timelines}
    assert "rolled back" in reply["recovery"]


def test_readback_failure_is_contradictory_not_a_success(code_forge, monkeypatch):
    item_type = type(code_forge.project.current.tracks[0][0])
    plan = code_forge.run("await resolve.edit_clips({properties: {ZoomX: 1.3}, copy_name: 'C', dry_run: false});")
    original = item_type.GetProperty
    monkeypatch.setattr(item_type, "GetProperty", lambda self, key=None: 1.0 if key == "ZoomX" else original(self, key))
    reply = code_forge.approve(plan)
    assert reply["status"] == "contradictory" and reply["code"] == "READBACK_FAILED"
    assert not reply["ok"] and "rolled back" in reply["recovery"]


def test_an_edit_with_no_readback_is_unverified_until_the_script_checks_it(code_forge):
    unchecked = code_forge.run("await resolve.apply_grade_preset({preset: 'warm', copy_name: 'G1', dry_run: false});")
    reply = code_forge.approve(unchecked)
    assert reply["status"] == "unverified" and reply["applied"][0]["verification"] == "unverified"
    checked = code_forge.run("""await resolve.apply_grade_preset({preset: 'warm', copy_name: 'G2', dry_run: false});
        if (run.mode === 'apply') run.check('grade inspected', (await resolve.inspect_grade({})).ok === true);""")
    assert code_forge.approve(checked)["status"] == "success"


def test_a_failed_check_contradicts_the_run(code_forge):
    plan = code_forge.run(f"{MARK} if (run.mode === 'apply') run.check('marker on frame 99', false, {{found: 30}});")
    reply = code_forge.approve(plan)
    assert reply["status"] == "contradictory" and reply["checks"][0]["details"] == {"found": 30}


def _with_client_prompt(forge, monkeypatch, action, approve=True):
    class Answer:
        def __init__(self):
            self.action, self.data = action, type("D", (), {"approve": approve})()

    async def elicit(self, message, schema):
        forge.prompted = message
        return Answer()
    monkeypatch.setattr("mcp.server.fastmcp.Context.elicit", elicit)
    monkeypatch.setattr("resolve_forge.code_mode_tools._supports_elicitation", lambda ctx: True)


def test_a_client_prompt_is_used_when_available(code_forge, monkeypatch):
    plan = code_forge.run(MARK)
    _with_client_prompt(code_forge, monkeypatch, "accept")
    reply = code_forge.approve(plan)
    assert reply["status"] == "success" and reply["approved_by"] == "client prompt"
    assert "timeline_markers" in code_forge.prompted


@pytest.mark.parametrize("action,approve", [("decline", False), ("cancel", False), ("accept", False)])
def test_a_declined_prompt_applies_nothing_and_discards_the_plan(code_forge, monkeypatch, action, approve):
    plan = code_forge.run(MARK)
    _with_client_prompt(code_forge, monkeypatch, action, approve)
    reply = code_forge.approve(plan)
    assert reply["code"] == "APPROVAL_DECLINED" and len(code_forge.project.timelines) == 1
    assert code_forge("approve_execution", plan_id=plan["plan"]["plan_id"])["code"] == "PLAN_NOT_FOUND"


def test_a_mistyped_approval_policy_stops_the_server_instead_of_weakening(tmp_path):
    with pytest.raises(ValueError, match="APPROVAL"):
        CodeForge(tmp_path, env={"RESOLVE_FORGE_CODE_MODE_APPROVAL": "elicitaton"})
    tools.set_write_gate(None)


def test_strict_approval_fails_closed_on_a_client_that_cannot_prompt(tmp_path):
    forge = CodeForge(tmp_path, env={"RESOLVE_FORGE_CODE_MODE_APPROVAL": "elicitation"})
    try:
        plan = forge.run(MARK)
        reply = forge.approve(plan)
        assert reply["code"] == "APPROVAL_UNAVAILABLE" and len(forge.project.timelines) == 1
    finally:
        tools.set_write_gate(None)


# ---- concurrency, cancellation, tracing --------------------------------------------------------------------------

def test_only_one_run_at_a_time(code_forge):
    first, second = code_forge.together(("execute", {"code": "await new Promise(r => setTimeout(r, 600));"}),
                                         ("execute", {"code": "return 1"}))
    assert first["status"] == "success" and second["code"] == "CODE_MODE_BUSY"


def test_direct_writes_wait_while_approved_edits_apply(code_forge):
    plan = code_forge.run(f"{MARK} await new Promise(r => setTimeout(r, 800));")
    async def scenario():
        applying = asyncio.ensure_future(code_forge.mcp.call_tool("approve_execution", {"plan_id": plan["plan"]["plan_id"]}))
        await asyncio.sleep(0.5)
        write = await code_forge.mcp.call_tool("edit_clips", {"properties": {"ZoomX": 1.1}, "dry_run": False})
        preview = await code_forge.mcp.call_tool("edit_clips", {"properties": {"ZoomX": 1.1}})
        read = await code_forge.mcp.call_tool("list_clips", {"track": 1})
        return [json.loads((r[0] if isinstance(r, tuple) else r)[0].text) for r in (write, preview, read, await applying)]
    write, preview, read, applied = asyncio.run(scenario())
    assert write["ok"] is False and write["code"] == "RESOLVE_BUSY"
    assert preview["ok"] and read["ok"] and applied["status"] == "success"
    assert code_forge("edit_clips", properties={"ZoomX": 1.1}, dry_run=False)["ok"]  # released afterwards


def test_cancel_stops_the_script(code_forge):
    assert code_forge("cancel_execution")["cancelling"] is False
    async def scenario():
        running = asyncio.ensure_future(code_forge.mcp.call_tool("execute", {"code": "await new Promise(r => setTimeout(r, 8000));"}))
        await asyncio.sleep(0.4)
        cancelled = await code_forge.mcp.call_tool("cancel_execution", {})
        return [json.loads((r[0] if isinstance(r, tuple) else r)[0].text) for r in (cancelled, await running)]
    started = time.monotonic()
    cancelled, reply = asyncio.run(scenario())
    assert cancelled["cancelling"] and reply["status"] == "cancelled" and reply["cancelled"] is True
    assert time.monotonic() - started < 5


def test_cancelling_the_request_kills_the_sandbox_and_leaves_a_trace(code_forge):
    async def scenario():
        running = asyncio.ensure_future(code_forge.service.execute("while (true) {}"))
        await asyncio.sleep(0.4)
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running
    asyncio.run(scenario())
    assert code_forge.traces()[-1]["status"] == "cancelled"
    assert code_forge("execute", code="return 1")["status"] == "success"  # the lock was released


def test_edits_already_applied_are_reported_if_the_sandbox_dies(code_forge, monkeypatch):
    """The worst moment to lose a report: the sandbox vanishes after an approved edit went through."""
    plan = code_forge.run(f"{MARK} await resolve.list_clips({{track: 1}});")
    original = code_mode_service.Sandbox.send

    async def fail_after_the_edit(self, message):
        if message.get("t") == "reply":
            raise BrokenPipeError("sandbox gone")
        await original(self, message)
    monkeypatch.setattr(code_mode_service.Sandbox, "send", fail_after_the_edit)
    reply = code_forge.approve(plan)
    assert reply["status"] == "partial" and reply["code"] == "SANDBOX_CRASHED"
    assert [op["tool"] for op in reply["applied"]] == ["timeline_markers"]
    assert "Marked" in {t.GetName() for t in code_forge.project.timelines}
    assert code_forge.traces()[-1]["status"] == "partial"


def test_an_unreadable_resolve_never_counts_as_unchanged(code_forge, monkeypatch):
    plan = code_forge.run(MARK)
    monkeypatch.setattr(type(code_forge.project), "GetName", lambda self: (_ for _ in ()).throw(ConnectionError("gone")))
    assert code_forge.approve(plan)["code"] == "STALE_STATE"
    monkeypatch.undo()


def test_every_run_leaves_an_audit_trace(code_forge):
    plan = code_forge.run(f"await resolve.list_clips({{track: 1}}); {MARK}")
    done = code_forge.approve(plan)
    code_forge.run("await resolve.repair_bridge_connection({dry_run: true})")
    planned, applied, denied = code_forge.traces()
    assert planned["status"] == "needs_approval" and MARK in planned["code"]
    assert applied["execution_id"] == done["execution_id"] and applied["approved_by"] == "tool call"
    assert applied["plan_id"] == plan["plan"]["plan_id"] and applied["applied"][0]["tool"] == "timeline_markers"
    assert applied["started_at"] <= applied["ended_at"] and applied["duration_ms"] > 0
    assert [c["tool"] for c in applied["calls"]] == ["list_clips", "timeline_markers"]
    assert denied["status"] == "blocked" and denied["errors"][0]["code"] == "CODE_MODE_DENIED"


def test_an_unwritable_trace_warns_and_does_not_fail_the_edit(code_forge, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    code_forge.service.trace_path = blocker / "traces.jsonl"
    assert code_forge.run("return 1")["status"] == "success"


# ---- script behaviour --------------------------------------------------------------------------------------------

def test_scripts_filter_compose_and_handle_errors(code_forge):
    reply = code_forge.run("""
        const clips = (await resolve.list_clips({track: 1})).clips;
        let missing = null;
        try { await resolve.list_clips({track: 40}); } catch (e) { missing = e.code; }
        console.log('checked', {clips: clips.length});
        return {long: clips.filter(c => c.duration > 150).map(c => c.name), missing};
    """)
    assert reply["result"] == {"long": ["take1.mp4", "take2.mp4"], "missing": "EMPTY_TRACK"}
    assert reply["logs"] == ['checked {"clips":2}']
    assert reply["status"] == "partial"  # a capability failed, even though the script coped


def test_parallel_calls_are_served_one_at_a_time(code_forge):
    reply = code_forge.run("""
        const all = await Promise.all([1, 1, 1, 1].map(track => resolve.list_clips({track})));
        return all.map(r => r.clips.length);
    """)
    assert reply["result"] == [2, 2, 2, 2] and [c["seq"] for c in reply["calls"]] == [1, 2, 3, 4]


@pytest.mark.parametrize("code,error", [("throw new Error('boom')", "boom"), ("this is not javascript", "SyntaxError"),
                                        ("return resolve.no_such_tool()", "not a function")])
def test_script_errors_are_reported_as_failures(code_forge, code, error):
    reply = code_forge.run(code)
    assert reply["status"] == "failed" and error in reply["errors"][0]["error"]


def test_empty_or_oversized_code_is_refused_before_starting(code_forge):
    assert code_forge("execute", code="  ")["code"] == "INVALID_ARGUMENT"
    assert code_forge("execute", code="//" + "x" * 70000)["code"] == "INVALID_ARGUMENT"


def test_a_result_that_is_not_json_fails_clearly(code_forge):
    reply = code_forge.run("const a = {}; a.self = a; return a;")
    assert reply["status"] == "failed"


@pytest.mark.parametrize("frame,fps,drop,expected", [
    (0, 24, False, "00:00:00:00"), (86400, 24, False, "01:00:00:00"), (107892, 29.97, True, "01:00:00;00"),
    (1800, 29.97, True, "00:01:00;02"), (17982, 29.97, True, "00:10:00;00"), (108000, 30, False, "01:00:00:00"),
    (215784, 59.94, True, "01:00:00;00"), (86313, 23.976, False, "00:59:56:09"),
])
def test_timecode_uses_rational_rates(code_forge, frame, fps, drop, expected):
    reply = code_forge.run(f"return timecode.frameToTimecode({frame}, {fps}, {{dropFrame: {json.dumps(drop)}}})")
    assert reply["result"] == expected, reply


def test_seconds_and_frames_round_trip_exactly_over_a_long_timeline(code_forge):
    reply = code_forge.run("""
        const bad = [];
        for (const fps of [23.976, 24, 25, 29.97, 30, 59.94, 60])
            for (let frame = 0; frame < 1000000; frame += 997)
                if (timecode.secondsToFrame(timecode.frameToSeconds(frame, fps), fps) !== frame) bad.push([fps, frame]);
        return {bad: bad.length, rate: timecode.rate(29.97)};
    """)
    assert reply["result"] == {"bad": 0, "rate": [30000, 1001]}


def test_drop_frame_is_refused_where_it_does_not_exist(code_forge):
    assert code_forge.run("return timecode.frameToTimecode(10, 24, {dropFrame: true})")["status"] == "failed"
    assert code_forge.run("return timecode.rate(12.5)")["status"] == "failed"


def test_limits_shape_the_reply(tmp_path):
    forge = CodeForge(tmp_path, limits=Limits(output_bytes=2048))
    try:
        reply = forge.run("return 'x'.repeat(100000)")
        assert reply["result"]["truncated"] is True and reply["result"]["bytes"] > 100000
        assert len(json.dumps(reply)) <= 2048
    finally:
        tools.set_write_gate(None)
