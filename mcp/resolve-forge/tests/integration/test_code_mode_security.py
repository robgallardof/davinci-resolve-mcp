"""Hostile scripts against the real sandbox. Every attack is expected to fail, and the host to survive it."""

import json
import os
import socket
import subprocess
import sys
import threading
import time

import pytest

from code_mode_support import CodeForge, code_forge  # noqa: F401
from resolve_forge import tools
from resolve_forge.services import code_mode_sandbox
from resolve_forge.services.code_mode_sandbox import DENO_FLAGS, Limits, find_deno


PERMISSION_PROBE = """
const out = {};
async function attack(name, action) {
  try { out[name] = 'REACHED: ' + String(await action()).slice(0, 60); } catch (error) { out[name] = error.name; }
}
const TARGET = Deno.args[0], OUT = Deno.args[1], PY = Deno.args[2], PORT = Number(Deno.args[3]);
await attack('env', () => Deno.env.get('PATH'));
await attack('read', () => Deno.readTextFileSync(TARGET));
await attack('stat', () => Deno.statSync(TARGET).size);
await attack('readdir', () => [...Deno.readDirSync('.')].length);
await attack('write', () => Deno.writeTextFileSync(OUT, 'pwned'));
await attack('fetch', async () => (await fetch('http://127.0.0.1:' + PORT)).status);
await attack('connect', async () => (await Deno.connect({hostname: '127.0.0.1', port: PORT})).localAddr.port);
await attack('listen', () => Deno.listen({port: 0}).addr.port);
await attack('spawn', () => new Deno.Command(PY, {args: ['-c', 'print(1)']}).outputSync().code);
await attack('ffi', () => Deno.dlopen(PY, {}));
await attack('sys', () => Deno.hostname());
await attack('node_fs', async () => (await import('node:fs')).readFileSync(TARGET, 'utf8'));
await attack('node_env', async () => (await import('node:process')).default.env.PATH);
await attack('node_spawn', async () => (await import('node:child_process')).execFileSync(PY, ['-c', 'print(1)']));
await attack('node_net', async () => await new Promise(async (ok, no) => (await import('node:net')).connect(PORT, '127.0.0.1', () => ok('open')).on('error', no)));
await attack('import_file', async () => await import('file:///' + TARGET));
await attack('import_remote', async () => await import('https://example.com/x.js'));
await attack('worker_read', () => new Promise((ok, no) => {
  const code = `try { postMessage('READ:' + Deno.readTextFileSync(${JSON.stringify(TARGET)})); } catch (e) { postMessage('no:' + e.name); }`;
  const worker = new Worker('data:text/javascript,' + encodeURIComponent(code), {type: 'module'});
  worker.onmessage = (event) => { worker.terminate(); event.data.startsWith('READ') ? ok(event.data) : no(Object.assign(new Error(), {name: event.data})); };
  worker.onerror = (event) => { event.preventDefault(); worker.terminate(); no(new Error(event.message)); };
}));
console.log(JSON.stringify(out));
Deno.exit(0);
"""


def test_process_permissions_refuse_everything_by_themselves(tmp_path):
    """Deno's own permissions, with the runner's global clean-up out of the way: the real boundary, tested alone."""
    secret = tmp_path / "credentials.txt"
    secret.write_text("TOP-SECRET")
    out, script = tmp_path / "pwned.txt", tmp_path / "probe.js"
    script.write_text(PERMISSION_PROBE)
    with Listener() as listener:
        done = subprocess.run([find_deno(), *DENO_FLAGS, str(script), secret.as_posix(), out.as_posix(), sys.executable, str(listener.port)],
                              capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL, cwd=tmp_path,
                              env={"DENO_DIR": str(tmp_path / "cache"), "DENO_NO_UPDATE_CHECK": "1", "SystemRoot": os.environ.get("SystemRoot", ""),
                                   "HOST_SECRET": "TOP-SECRET"})
        time.sleep(0.2)
    assert done.returncode == 0, done.stderr
    results = json.loads(done.stdout)
    assert len(results) == 18
    reached = {name: value for name, value in results.items() if value.startswith("REACHED")}
    assert not reached, reached
    assert "TOP-SECRET" not in done.stdout and not out.exists() and listener.connections == 0
    # NotCapable is Deno's refusal; imports fail earlier as TypeError because --deny-import and --no-remote block loading.
    loads = {"import_file", "import_remote"}
    assert {name: value for name, value in results.items() if name not in loads and value != "NotCapable" and "no:NotCapable" not in value} == {}


def attempt(forge, expression: str) -> str:
    """Runs one attack and returns 'REACHED: ...' if it worked, or the error it died with."""
    reply = forge.run(f"try {{ return 'REACHED: ' + String(await (async () => {{ {expression} }})()); }}"
                      f" catch (error) {{ return 'refused: ' + error.name + ' ' + error.message; }}")
    assert reply["result"] is not None, reply
    return reply["result"]


NODE_FS = "const fs = await import('node:fs');"
NODE_PROCESS = "const process = (await import('node:process')).default;"
NODE_CP = "const cp = await import('node:child_process');"


@pytest.mark.parametrize("attack", [
    "return Deno.version.deno",  # the namespace itself is gone
    NODE_FS + " return fs.readFileSync({path!r}, 'utf8');",
    NODE_FS + " fs.writeFileSync({out!r}, 'pwned'); return 'written';",
    NODE_FS + " return fs.readdirSync('.').join();",
    "const mod = await import('file:///' + {path!r}); return mod;",
])
def test_files_cannot_be_read_or_written(code_forge, tmp_path, attack):
    secret = tmp_path / "credentials.txt"
    secret.write_text("TOP-SECRET")
    out = tmp_path / "pwned.txt"
    result = attempt(code_forge, attack.format(path=secret.as_posix(), out=out.as_posix()))
    assert result.startswith("refused"), result
    assert "TOP-SECRET" not in result and not out.exists()


def test_host_environment_secrets_are_invisible(code_forge, monkeypatch):
    monkeypatch.setenv("RESOLVE_FORGE_MCP_TOKEN", "TOP-SECRET")
    for attack in (" return process.env.RESOLVE_FORGE_MCP_TOKEN;", " return JSON.stringify(process.env);"):
        result = attempt(code_forge, NODE_PROCESS + attack)
        assert result.startswith("refused") and "TOP-SECRET" not in result
    assert attempt(code_forge, "return typeof Deno").startswith("REACHED: undefined")


@pytest.mark.parametrize("attack", [
    NODE_CP + " return cp.execSync('echo pwned').toString();",
    NODE_CP + " const r = cp.spawnSync('sh', ['-c', 'echo pwned']); if (r.error) throw r.error; return r.status;",
    NODE_CP + " return await new Promise((ok, no) => cp.spawn('sh', ['-c', 'echo pwned']).on('error', no).on('exit', ok));",
])
def test_shell_commands_cannot_run(code_forge, attack):
    assert attempt(code_forge, attack).startswith("refused")


class Listener:
    """A local port that records any connection: proof the network stayed closed, not just an error message."""

    def __enter__(self):
        self.socket = socket.create_server(("127.0.0.1", 0))
        self.socket.settimeout(0.1)
        self.port = self.socket.getsockname()[1]
        self.connections, self.running = 0, True
        self.thread = threading.Thread(target=self._accept, daemon=True)
        self.thread.start()
        return self

    def _accept(self):
        while self.running:
            try:
                self.socket.accept()[0].close()
                self.connections += 1
            except OSError:
                pass

    def __exit__(self, *_):
        self.running = False
        self.thread.join()
        self.socket.close()


@pytest.mark.parametrize("attack", [
    "return (await fetch('http://127.0.0.1:{port}/')).status;",
    "const net = await import('node:net'); return await new Promise((ok, no) => net.connect({port}, '127.0.0.1', () => ok('open')).on('error', no));",
    "const http = await import('node:http'); return await new Promise((ok, no) => http.get('http://127.0.0.1:{port}/', r => ok(r.statusCode)).on('error', no));",
    "const net = await import('node:net'); return await new Promise((ok, no) => net.createServer().listen(0, () => ok('listening')).on('error', no));",
])
def test_network_is_closed(code_forge, attack):
    with Listener() as listener:
        result = attempt(code_forge, attack.replace("{port}", str(listener.port)))
        time.sleep(0.2)
    assert result.startswith("refused"), result
    assert listener.connections == 0


def test_native_code_and_workers_are_unavailable(code_forge):
    assert attempt(code_forge, "const m = await import('node:module'); return m.createRequire('file:///x')('./a.node');").startswith("refused")
    assert attempt(code_forge, "return new Worker('data:text/javascript,1', {type: 'module'});").startswith("refused")
    worker = """const {Worker} = await import('node:worker_threads');
        return await new Promise((ok, no) => {
            const w = new Worker("const fs=require('fs');require('worker_threads').parentPort.postMessage(fs.readFileSync(process.argv[1]||'/etc/hosts','utf8'))", {eval: true});
            w.on('message', m => { w.terminate(); ok(m); }); w.on('error', no); });"""
    assert attempt(code_forge, worker).startswith("refused")


def test_remote_modules_are_refused(code_forge):
    assert attempt(code_forge, "return await import('https://example.com/x.js');").startswith("refused")


HOSTILE = """
const encoder = new TextEncoder();
const send = (line) => Deno.stdout.writeSync(encoder.encode(line + String.fromCharCode(10)));
const buffer = new Uint8Array(1 << 20);
await Deno.stdin.read(buffer); // the start message
"""


@pytest.fixture
def hostile(code_forge, tmp_path, monkeypatch):
    """Replace the runner: what a script could do after completely escaping the JavaScript layer, permissions aside."""
    def install(body: str):
        script = tmp_path / "hostile.js"
        script.write_text(HOSTILE + body)
        monkeypatch.setattr(code_mode_sandbox, "RUNNER", script)
        return code_forge
    return install


def _call_then_finish(tool: str, args: dict) -> str:
    message = json.dumps({"t": "call", "id": 1, "tool": tool, "args": args})
    done = json.dumps(json.dumps({"t": "done", "result": "forged"}))
    return f"send({json.dumps(message)}); await Deno.stdin.read(buffer); send({done}); Deno.exit(0);"


@pytest.mark.parametrize("tool,args", [("repair_bridge_connection", {"dry_run": False}), ("execute", {"code": "return 1"}),
                                       ("approve_execution", {"plan_id": "x"}), ("cancel_execution", {}), ("search", {}),
                                       ("no_such_tool", {})])
def test_a_forged_call_cannot_reach_forbidden_tools(hostile, tool, args):
    forge = hostile(_call_then_finish(tool, args))
    reply = forge.run("ignored")
    assert reply["status"] == "blocked" and reply["code"] == "CODE_MODE_DENIED", reply
    assert reply["calls"][0]["effect"] == "deny"


def test_a_forged_call_cannot_write_without_approval(hostile):
    forge = hostile(_call_then_finish("edit_clips", {"properties": {"ZoomX": 2}, "copy_name": "Forged", "dry_run": False}))
    reply = forge.run("ignored")
    assert reply["status"] == "needs_approval", reply
    assert {t.GetName() for t in forge.project.timelines} == {"Master"}


def test_a_forged_done_message_does_not_erase_the_record(hostile):
    forge = hostile(_call_then_finish("repair_bridge_connection", {}))
    reply = forge.run("ignored")
    assert reply["result"] == "forged" and reply["status"] == "blocked"  # the status comes from what the host saw
    assert forge.traces()[-1]["calls"][0]["tool"] == "repair_bridge_connection"


@pytest.mark.parametrize("arguments", ['"track=1"', "[1]", "null"])
def test_forged_malformed_calls_are_denied(hostile, arguments):
    message = '{"t":"call","id":1,"tool":"list_clips","args":%s}' % arguments
    forge = hostile(f"send({json.dumps(message)}); await Deno.stdin.read(buffer); Deno.exit(0);")
    assert forge.run("ignored")["code"] == "CODE_MODE_DENIED"


@pytest.mark.parametrize("line", ["not json", "[1,2,3]", '{"t":"unknown"}', "null"])
def test_garbage_on_the_channel_ends_the_run(hostile, line):
    forge = hostile(f"send({json.dumps(line)}); await new Promise(r => setTimeout(r, 5000));")
    reply = forge.run("ignored")
    assert reply["status"] == "failed" and reply["code"] == "SANDBOX_PROTOCOL", reply


def test_a_message_over_the_size_limit_ends_the_run(hostile):
    forge = hostile("send('x'.repeat(9000000)); await new Promise(r => setTimeout(r, 5000));")
    reply = forge.run("ignored")
    assert reply["status"] == "failed" and reply["code"] == "OUTPUT_LIMIT", reply


def test_a_sandbox_that_dies_is_reported_as_a_crash(hostile):
    forge = hostile("Deno.exit(3);")
    reply = forge.run("ignored")
    assert reply["status"] == "failed" and reply["code"] == "SANDBOX_CRASHED" and "code 3" in reply["errors"][0]["error"]


def test_a_sandbox_that_stops_reading_replies_times_out(hostile, monkeypatch):
    """A reply too large for the pipe, to a process that never reads: the host must not wait on it forever."""
    message = json.dumps({"t": "call", "id": 1, "tool": "list_formats", "args": {}})
    forge = hostile(f"send({json.dumps(message)}); for (;;) {{}}")
    forge.service.limits = Limits(timeout_ms=800)
    started = time.monotonic()
    assert forge.run("ignored")["status"] == "timeout"
    assert time.monotonic() - started < 5


def test_non_object_arguments_are_denied(code_forge):
    assert code_forge.run("await resolve.list_clips('track=1')")["code"] == "CODE_MODE_DENIED"


def test_scripts_have_no_way_to_write_to_the_channel_themselves(code_forge):
    assert attempt(code_forge, NODE_PROCESS + " process.stdout.write('garbage\\n'); return 'wrote';").startswith("refused")


def test_forged_approval_tokens_do_nothing(code_forge):
    plan = code_forge.run("await resolve.edit_clips({properties: {ZoomX: 1.2}, copy_name: 'A', dry_run: false});")
    plan_id = plan["plan"]["plan_id"]
    # Knowing a real plan id gives a script nothing: approval is not a capability, and a second plan changes nothing.
    reply = code_forge.run(f"await resolve.approve_execution({{plan_id: '{plan_id}'}});")
    assert reply["status"] == "failed" and "not a function" in reply["errors"][0]["error"]
    assert {t.GetName() for t in code_forge.project.timelines} == {"Master"}


def test_tampering_with_globals_does_not_bypass_the_gate(code_forge):
    reply = code_forge.run("""
        Object.defineProperty(run, 'mode', {value: 'apply'});
    """)
    assert reply["status"] == "failed"  # frozen
    spoof = code_forge.run("""
        JSON.stringify = () => '{"t":"done","result":"forged"}';
        await resolve.edit_clips({properties: {ZoomX: 1.2}, copy_name: 'A', dry_run: false});
    """)
    assert spoof["status"] == "needs_approval" and {t.GetName() for t in code_forge.project.timelines} == {"Master"}


# ---- exhausting resources: the sandbox dies, the host does not -----------------------------------------------------

def assert_alive(forge) -> None:
    """The host survived. With normal limits: the tight ones also cover process start-up, which varies under load."""
    forge.service.limits = Limits()
    assert forge.run("return 'alive'")["result"] == "alive"


@pytest.fixture
def tight(tmp_path):
    forge = CodeForge(tmp_path, limits=Limits(timeout_ms=800, memory_mb=64, max_calls=5, output_bytes=4096, message_bytes=1048576))
    yield forge
    tools.set_write_gate(None)


@pytest.mark.parametrize("code", ["while (true) {}", "await new Promise(() => {});", "for (;;) await null;",
                                  "await new Promise(r => setTimeout(r, 60000));"])
def test_scripts_that_never_finish_are_killed_on_time(tight, code):
    started = time.monotonic()
    reply = tight.run(code)
    assert reply["status"] == "timeout" and reply["code"] == "CODE_MODE_TIMEOUT"
    assert time.monotonic() - started < 5
    assert_alive(tight)


@pytest.mark.parametrize("code", [
    "const keep = []; for (;;) keep.push(new Array(1e6).fill(Math.random()));",  # JavaScript heap
    "const keep = []; for (;;) { const b = new Uint8Array(1 << 26); b.fill(1); keep.push(b); }",  # off-heap buffers
])
def test_memory_bombs_are_stopped(tight, code):
    tight.limits = Limits(timeout_ms=20000, memory_mb=64)
    tight.service.limits = tight.limits
    reply = tight.run(code)
    assert reply["ok"] is False and reply["status"] in {"failed", "timeout"}, reply
    assert reply["code"] in {"SANDBOX_MEMORY_LIMIT", "SANDBOX_CRASHED", "SCRIPT_ERROR", "CODE_MODE_TIMEOUT"}
    assert_alive(tight)


def test_excessive_output_is_bounded(tight):
    result = tight.run("return 'x'.repeat(500000)")
    assert result["result"]["truncated"] and len(json.dumps(result)) <= 4096
    logs = tight.run("for (let i = 0; i < 100000; i++) console.log('spam spam spam');")
    assert logs["status"] == "success" and len(json.dumps(logs)) <= 4096


def test_call_floods_are_cut_off(tight):
    reply = tight.run("for (let i = 0; i < 1000; i++) await resolve.list_styles();")
    assert reply["status"] in {"blocked", "failed"} and reply["code"] == "CALL_LIMIT"
    assert sum(c.get("status") == "ok" for c in reply["calls"]) == 5


def test_check_floods_are_cut_off(tight):
    reply = tight.run("for (let i = 0; i < 100000; i++) run.check('spam', true);")
    assert reply["code"] == "CALL_LIMIT"


def test_a_missing_runtime_fails_closed(code_forge, monkeypatch):
    monkeypatch.setattr("resolve_forge.services.code_mode_sandbox.find_deno", lambda: None)
    reply = code_forge.run("return 1")
    assert reply["status"] == "failed" and reply["code"] == "MISSING_DEPENDENCY" and "uv sync" in reply["errors"][0]["hint"]
    assert code_forge("list_clips")["ok"]  # direct tools are unaffected


def test_a_control_that_cannot_be_applied_fails_closed(code_forge, monkeypatch):
    from resolve_forge.services import code_mode_limits

    def refuse(*_):
        raise code_mode_limits.ContainmentError("no job object here")
    monkeypatch.setattr(code_mode_limits, "contain", refuse)
    reply = code_forge.run("return 'should not run'")
    assert reply["status"] == "failed" and reply["code"] == "SANDBOX_UNAVAILABLE" and reply["result"] is None
    assert code_forge("list_clips")["ok"]
