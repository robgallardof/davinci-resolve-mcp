"""Tests for Forge's own wire protocol and native-call boundary."""
import pytest

from resolve_forge.bridge.resolve_bridge import Authenticator, Bridge, sign_request
from resolve_forge.bridge.resolve_bridge_ops import OperationError, PathPolicy, ResolveOperations, make_dispatch
from resolve_forge.bridge.client import Client, Proxy
from fakes import demo_resolve

TOKEN = "forge-test-token-" * 4


def message(timestamp=100, nonce="0123456789abcdef"):
    value = {"protocol": "1.0", "id": "test", "timestamp": timestamp, "nonce": nonce,
             "operation": "health", "arguments": {}}
    value["signature"] = sign_request(TOKEN, value)
    return value


def test_authentication_rejects_tampering_and_replays():
    auth = Authenticator(TOKEN, clock=lambda: 100)
    request = message()
    auth.verify(request)
    with pytest.raises(ValueError, match="Replay"):
        auth.verify(request)
    request = message(nonce="different_nonce_123")
    request["arguments"] = {"modified": True}
    with pytest.raises(ValueError, match="signature"):
        auth.verify(request)


def test_future_nonce_survives_the_full_acceptance_window():
    clock = [100]
    auth = Authenticator(TOKEN, clock=lambda: clock[0])
    request = message(timestamp=160)
    auth.verify(request)
    clock[0] = 219
    with pytest.raises(ValueError, match="Replay"):
        auth.verify(request)


@pytest.mark.parametrize("timestamp", [float("nan"), float("inf"), 0, 500, True])
def test_invalid_timestamps(timestamp):
    with pytest.raises(ValueError):
        Authenticator(TOKEN, clock=lambda: 100).verify(message(timestamp))


def test_paths_are_checked_after_resolution(tmp_path):
    policy = PathPolicy([str(tmp_path / "media")], [str(tmp_path / "outputs")])
    assert policy.check(tmp_path / "media" / "clip.mov")
    with pytest.raises(OperationError, match="outside"):
        policy.check(tmp_path / "media" / ".." / "private.txt")
    with pytest.raises(OperationError):
        policy.check(tmp_path / "media" / "clip.mov", write=True)


def test_methods_and_object_handles_do_not_enable_arbitrary_execution(tmp_path):
    resolve = demo_resolve(studio=False)
    surface = ResolveOperations(resolve, [str(tmp_path)], [str(tmp_path)])
    with pytest.raises(OperationError):
        surface.dispatch("call", {"target": "resolve", "method": "__getattribute__", "args": ["project"]})
    handle = surface.dispatch("call", {"target": "resolve", "method": "GetProjectManager", "args": []})["value"]["__handle__"]
    assert surface.object(handle).GetCurrentProject().GetName() == "Demo"
    surface.dispatch("release_handles", {"handles": [handle]})
    with pytest.raises(OperationError):
        surface.object(handle)


def test_wire_roundtrip_preserves_json_values_and_capability_absence(tmp_path):
    resolve = demo_resolve(studio=False, keyframes=False)
    surface = ResolveOperations(resolve, [str(tmp_path)], [str(tmp_path)])
    config = {"host": "127.0.0.1", "port": 0, "token": TOKEN}
    bridge = Bridge(resolve, config, make_dispatch(surface)).start()
    try:
        client = Client({**config, "port": bridge.port})
        root = Proxy(client, "resolve")
        assert root.GetVersionString() == "21.0.4.5"
        item = root.GetProjectManager().GetCurrentProject().GetCurrentTimeline().GetItemListInTrack("video", 1)[0]
        assert not hasattr(item, "AddKeyframe")
        assert item.SetProperty("ZoomX", 1.25)
        assert item.GetProperty("ZoomX") == 1.25
        health = client.request("health", {})
        assert health["implementation"] == "resolve-forge" and health["session"]
    finally:
        bridge.stop()
    assert bridge._thread.is_alive() is False


def test_native_objects_with_an_empty_dir_still_expose_allowlisted_methods(tmp_path):
    """Resolve 21 Free proxies can report dir() == []; the allowlist is then probed directly, nothing more."""
    class Opaque:
        def __dir__(self):
            return []

        def GetVersionString(self):
            return "21.0.4.5"

        def execute(self, code):  # outside the allowlist: must stay unreachable
            raise AssertionError("arbitrary execution")

    surface = ResolveOperations(Opaque(), [str(tmp_path)], [str(tmp_path)])
    assert surface.dispatch("list_methods", {"target": "resolve"})["methods"] == ["GetVersionString"]
    assert surface.dispatch("call", {"target": "resolve", "method": "GetVersionString", "args": []})["value"] == "21.0.4.5"
    with pytest.raises(OperationError):
        surface.dispatch("call", {"target": "resolve", "method": "execute", "args": ["x"]})


def test_blocking_bridge_runs_every_native_call_on_the_script_thread(tmp_path):
    """fuscript.exe only answers on the thread that launched the script; the listener must not call Resolve."""
    import threading
    seen = []
    resolve = demo_resolve(studio=False)
    surface = ResolveOperations(resolve, [str(tmp_path)], [str(tmp_path)])

    def dispatch(operation, arguments):
        seen.append(threading.current_thread().name)
        return surface.dispatch(operation, arguments)

    config = {"host": "127.0.0.1", "port": 0, "token": TOKEN}
    bridge = Bridge(resolve, config, dispatch)
    outcome = {}
    script = threading.Thread(target=lambda: outcome.update(bridge.serve({"blocking_required": True})), name="script")
    script.start()
    try:
        while bridge._server is None or not bridge._pumping:
            pass
        client = Client({**config, "port": bridge.port})
        assert Proxy(client, "resolve").GetVersionString() == "21.0.4.5"
        with pytest.raises(Exception, match="native-call boundary"):
            client.request("call", {"target": "resolve", "method": "NotAllowed", "args": []})
    finally:
        bridge.request_stop("exit")
        script.join(5)
    assert seen and set(seen) == {"script"}
    assert outcome == {"stop_reason": "exit"}


def test_bridge_releases_its_port_when_resolve_goes_away(tmp_path):
    """An orphaned fuscript from a closed Resolve session must not keep the port for the next one."""
    from resolve_forge.bridge.resolve_bridge_ops import resolve_alive
    resolve = demo_resolve(studio=False)
    assert resolve_alive(resolve) and not resolve_alive(object())
    state = {"alive": True}
    surface = ResolveOperations(resolve, [str(tmp_path)], [str(tmp_path)])
    bridge = Bridge(resolve, {"host": "127.0.0.1", "port": 0, "token": TOKEN}, make_dispatch(surface),
                    alive=lambda: state["alive"], alive_every_s=0.05)
    import threading
    outcome = {}
    script = threading.Thread(target=lambda: outcome.update(bridge.serve({"blocking_required": True})))
    script.start()
    while not bridge._pumping:
        pass
    answers = iter([False, True, False, False])  # one busy blip must not close the bridge
    state["alive"] = None
    bridge.alive = lambda: next(answers, False)
    script.join(5)
    assert outcome == {"stop_reason": "resolve_gone"} and bridge._server is None
    assert next(answers, "drained") == "drained"  # it needed three consecutive misses after the blip


def test_control_operations_answer_while_resolve_is_busy(tmp_path):
    """health/reload must not queue behind a Resolve call that is blocked (e.g. playback)."""
    import threading
    gate = threading.Event()
    resolve = demo_resolve(studio=False)
    surface = ResolveOperations(resolve, [str(tmp_path)], [str(tmp_path)])

    def dispatch(operation, arguments):
        if operation == "call":
            gate.wait(5)  # Resolve stuck
        return surface.dispatch(operation, arguments)

    config = {"host": "127.0.0.1", "port": 0, "token": TOKEN}
    bridge = Bridge(resolve, config, dispatch)
    script = threading.Thread(target=lambda: bridge.serve({"blocking_required": True}))
    script.start()
    try:
        while not bridge._pumping:
            pass
        busy = threading.Thread(target=lambda: Client({**config, "port": bridge.port}).request(
            "call", {"target": "resolve", "method": "GetVersionString", "args": []}))
        busy.start()
        assert Client({**config, "port": bridge.port}, timeout=2).request("health", {})["implementation"] == "resolve-forge"
    finally:
        gate.set()
        bridge.request_stop("exit")
        script.join(5)
        busy.join(5)
