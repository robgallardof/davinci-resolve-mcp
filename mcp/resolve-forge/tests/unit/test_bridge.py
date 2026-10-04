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
