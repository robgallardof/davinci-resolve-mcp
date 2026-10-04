import copy
import json
import base64
import sys
from types import SimpleNamespace

import pytest

from resolve_forge.services import bridge_recovery_service as recovery
from resolve_forge.errors import ForgeError

LAUNCHER = r"C:\Users\editor\AppData\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\resolve_bridge.py"
EXECUTABLE = r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fuscript.exe"


def inventory():
    return {"processes": [
        {"ProcessId": 50, "ParentProcessId": 40, "Name": "fuscript.exe", "ExecutablePath": EXECUTABLE,
         "CommandLine": f'fuscript.exe -q -l Py3 -a 49152 "{LAUNCHER}"', "CreationDate": "2026-10-04T15:00:00.0000000Z"},
        {"ProcessId": 60, "ParentProcessId": 1, "Name": "Resolve.exe"}],
        "listeners": [{"LocalPort": 49632, "LocalAddress": "127.0.0.1", "OwningProcess": 50}]}


def argv(command):
    return ["fuscript.exe", command.split('"')[1]]


def test_matching_orphan_is_eligible():
    data = inventory()
    assert recovery.eligible(data["processes"][0], data, 49632, LAUNCHER, EXECUTABLE, argv)


@pytest.mark.parametrize("case", ["parent_alive", "unrelated_listener", "other_launcher", "other_executable", "no_resolve", "no_created", "public_listener"])
def test_missing_or_unrelated_evidence_fails_closed(case):
    data = copy.deepcopy(inventory())
    if case == "parent_alive": data["processes"].append({"ProcessId": 40, "Name": "old.exe"})
    if case == "unrelated_listener": data["listeners"][0]["OwningProcess"] = 90
    if case == "other_launcher": data["processes"][0]["CommandLine"] = 'fuscript.exe "C:\\other\\resolve_bridge.py"'
    if case == "other_executable": data["processes"][0]["ExecutablePath"] = r"C:\other\fuscript.exe"
    if case == "no_resolve": data["processes"].pop()
    if case == "no_created": data["processes"][0].pop("CreationDate")
    if case == "public_listener": data["listeners"][0]["LocalAddress"] = "0.0.0.0"
    assert not recovery.eligible(data["processes"][0], data, 49632, LAUNCHER, EXECUTABLE, argv)


def setup_config(monkeypatch, tmp_path):
    config = tmp_path / "bridge.json"
    config.write_text(json.dumps({"port": 49632, "token": "secret-not-for-output"}))
    monkeypatch.setattr(recovery, "config_path", lambda: config)
    monkeypatch.setenv("APPDATA", r"C:\Users\editor\AppData\Roaming")
    monkeypatch.setenv("PROGRAMFILES", r"C:\Program Files")


def test_preview_does_not_send_stop_script(monkeypatch, tmp_path):
    setup_config(monkeypatch, tmp_path)
    calls = []
    def runner(script):
        calls.append(script)
        return inventory()
    result = recovery.repair(runner=runner, platform="win32", argv=argv)
    assert result["orphaned_helper_pids"] == [50]
    assert not result["applied"]
    assert len(calls) == 1
    assert "secret-not-for-output" not in json.dumps(result)


@pytest.mark.parametrize("stopped", [True, False])
def test_action_uses_revalidation_and_reports_only_actual_stop(monkeypatch, tmp_path, stopped):
    setup_config(monkeypatch, tmp_path)
    calls = []
    def runner(script):
        calls.append(script)
        return inventory() if len(calls) == 1 else {"stopped": stopped, "reason": "evidence_changed"}
    result = recovery.repair(False, runner=runner, platform="win32", argv=argv)
    assert result["applied"] is stopped
    assert len(calls) == 2
    assert "CreationDate.ToUniversalTime" in calls[1]
    assert "!$parentAlive" in calls[1]
    assert "Stop-Process -InputObject $handle" in calls[1]
    assert "secret-not-for-output" not in calls[1]


def test_non_windows_does_not_inspect_or_mutate():
    assert recovery.repair(platform="linux", runner=lambda _: pytest.fail("unexpected call"))["supported"] is False


def test_runner_decodes_utf8_and_sets_powershell_output_encoding(monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout='{"label":"José"}'.encode("utf-8"))
    monkeypatch.setattr(recovery.subprocess, "run", run)
    assert recovery._run("read-only") == {"label": "José"}
    script = base64.b64decode(calls[0][0][-1]).decode("utf-16-le")
    assert "[Console]::OutputEncoding" in script
    assert "text" not in calls[0][1]


@pytest.mark.parametrize("completed", [SimpleNamespace(returncode=1, stdout=b"", stderr=b"sensitive data"),
                                      SimpleNamespace(returncode=0, stdout=b"not json")])
def test_runner_failures_are_typed_and_sanitized(monkeypatch, completed):
    monkeypatch.setattr(recovery.subprocess, "run", lambda *args, **kwargs: completed)
    with pytest.raises(ForgeError) as error:
        recovery._run("read-only")
    assert error.value.code == "BRIDGE_RECOVERY_FAILED"
    assert "sensitive data" not in str(error.value)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process/network inventory")
def test_real_inventory_is_read_only_valid_json():
    # This intentionally exercises PowerShell parsing/encoding absent from runner fakes.
    # No config, bridge connection, Resolve API or Stop-Process is involved.
    result = recovery._run(recovery.INVENTORY)
    assert isinstance(result["processes"], list)
    assert isinstance(result["listeners"], list)
    assert all("ProcessId" in process for process in result["processes"])
    assert "Stop-Process" not in recovery.INVENTORY
