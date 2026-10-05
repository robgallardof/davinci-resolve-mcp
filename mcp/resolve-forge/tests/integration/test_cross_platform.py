"""The whole chain on simulated Windows, macOS and Linux machines.

Each test fakes one OS (sys.platform, home folder, Windows env vars and the process table) inside tmp_path and
runs the real code end to end: installer -> launcher run "inside Resolve" -> bridge -> gateway -> MCP tools,
the doctor, and the Studio direct path with a stand-in DaVinciResolveScript module.
"""
import asyncio
import os
import json
import runpy
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP

from fakes import demo_resolve
from resolve_forge import doctor, gateway, native_paths, tools
from resolve_forge.bridge.client import Client, config_path
from resolve_forge.bridge.resolve_bridge import load_config
from resolve_forge.bridge_install import install_resolve_bridge as installer

TOKEN = "cross-platform-token-" * 3
REAL_RUN = subprocess.run

# What each OS calls the Resolve process, next to this server and its interpreter.
PROCESS_TABLE = {"win32": ["Resolve.exe", "python.exe", "resolve-forge.exe"],
                 "darwin": ["Resolve", "Python", "resolve-forge"],
                 "linux": ["resolve", "python3", "resolve-forge"]}
SCRIPTS_UNDER_HOME = {"win32": "AppData/Roaming/Blackmagic Design/DaVinci Resolve/Support/Fusion/Scripts/Utility",
                      "darwin": "Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility",
                      "linux": ".local/share/DaVinciResolve/Fusion/Scripts/Utility"}
OPERATING_SYSTEMS = [pytest.param(name, id=name) for name in ("win32", "darwin", "linux")]


class Machine:
    """A simulated computer: its home, its Resolve folders and which processes are running."""

    def __init__(self, platform, root, monkeypatch):
        self.platform, self.home, self.resolve_open = platform, root / "home", True
        self.home.mkdir()
        monkeypatch.setattr(sys, "platform", platform)
        for name in ("HOME", "USERPROFILE"):
            monkeypatch.setenv(name, str(self.home))
        monkeypatch.setenv("APPDATA", str(self.home / "AppData/Roaming"))
        monkeypatch.setenv("PROGRAMDATA", str(root / "ProgramData"))
        monkeypatch.setenv("PROGRAMFILES", str(root / "Program Files"))
        monkeypatch.setenv("FORGE_BRIDGE_CONFIG", str(self.home / ".config/davinci-resolve-mcp/bridge.json"))
        for name in ("RESOLVE_SCRIPT_API", "RESOLVE_SCRIPT_LIB", "PYTHONHOME"):
            monkeypatch.setenv(name, "")  # remember the real value, then clear it for this machine
            monkeypatch.delenv(name)
        # The shared Scripts folder (/opt/resolve, /Library, ProgramData) is never the real one on the test host.
        self.shared = root / "shared-scripts"
        user, _ = native_paths.script_dirs()
        monkeypatch.setattr(installer, "script_dirs", lambda: (user, self.shared))
        monkeypatch.setattr(doctor, "script_dirs", lambda: (user, self.shared))
        monkeypatch.setattr(gateway.subprocess, "run", self.run)

    def run(self, cmd, **kwargs):
        """The OS process listing; anything else really runs."""
        running = PROCESS_TABLE[self.platform] if self.resolve_open else PROCESS_TABLE[self.platform][1:]
        if cmd[0] == "tasklist":
            assert self.platform == "win32"
            wanted = cmd[cmd.index("/FI") + 1].split(" eq ")[1]
            listed = "".join(f"{p}  1234 Console  1  10,000 K\n" for p in running if p.lower() == wanted.lower())
            return subprocess.CompletedProcess(cmd, 0, listed or "INFO: No tasks are running.\n", "")
        if cmd[0] == "pgrep":
            assert self.platform != "win32" and cmd[1] == "-x"
            return subprocess.CompletedProcess(cmd, 0 if cmd[2] in running else 1, b"", b"")
        return REAL_RUN(cmd, **kwargs)


@pytest.fixture(params=OPERATING_SYSTEMS)
def machine(request, tmp_path, monkeypatch):
    return Machine(request.param, tmp_path, monkeypatch)


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _call(mcp, tool, **args):
    result = asyncio.run(mcp.call_tool(tool, args))
    content = result[0] if isinstance(result, tuple) else result
    return json.loads(content[0].text)


def test_resolve_is_detected_by_its_exact_process_name(machine):
    assert gateway.resolve_process_running()
    machine.resolve_open = False  # only this server and Python left, both contain "resolve"/"python"
    assert not gateway.resolve_process_running()


def test_fresh_install_lands_in_this_os_folders_with_safe_defaults(machine):
    result = installer.install()
    user = machine.home / SCRIPTS_UNDER_HOME[machine.platform]
    assert result["installed"] == [str(user)] and (user / "resolve_bridge.py").exists()
    runtime = user.parents[1] / ".davinci_mcp_runtime"
    assert {p.name for p in runtime.iterdir()} == {"resolve_bridge.py", "resolve_bridge_ops.py", "bridge.json"}
    config = load_config(config_path())
    assert config_path().is_relative_to(machine.home) and config["host"] == "127.0.0.1"
    assert config["allowed_output_roots"] == [str(machine.home / "Movies")]
    assert config == json.loads((runtime / "bridge.json").read_text(encoding="utf-8"))
    machine.shared.mkdir()
    assert str(machine.shared) in installer.install()["installed"]  # writable shared folder also gets it


def test_free_edition_end_to_end_bridge_doctor_and_tools(machine, monkeypatch):
    config = {"host": "127.0.0.1", "port": _free_port(), "token": TOKEN, "auth_clock_skew_seconds": 60,
              "allowed_media_roots": [str(machine.home)], "allowed_output_roots": [str(machine.home / "Movies")]}
    config_path().parent.mkdir(parents=True)
    config_path().write_text(json.dumps(config), encoding="utf-8")
    launcher = Path(installer.install()["installed"][0]) / "resolve_bridge.py"

    # Resolve runs Workspace > Scripts > resolve_bridge with its own `resolve` global.
    monkeypatch.setattr(sys, "path", list(sys.path))
    resolve = demo_resolve(studio=False)
    inside_resolve = threading.Thread(target=runpy.run_path, args=(str(launcher),),
                                      kwargs={"init_globals": {"resolve": resolve}}, daemon=True)
    inside_resolve.start()
    client = Client(config)
    for _ in range(100):
        try:
            client.request("health", {})
            break
        except OSError:
            inside_resolve.join(.05)
    try:
        checks = {c.name: c for c in doctor.run()}
        assert checks["Bridge installed in Resolve (Free)"].ok
        assert checks["Resolve running"].ok and checks["Resolve running"].detail == native_paths.process_name()
        assert checks["Connection"].ok and "Free 21.0.4.5 via bridge" in checks["Connection"].detail
        assert checks["Project/timeline"].ok

        mcp = FastMCP("cross-platform")
        tools.register(mcp, gateway.Session())
        status = _call(mcp, "forge_status")
        assert status["transport"] == "bridge" and status["edition"] == "Free" and status["project"] == "Demo"
        assert len(_call(mcp, "list_clips")["clips"]) == 2
    finally:
        client.request("shutdown", {})
        inside_resolve.join(10)
    assert not inside_resolve.is_alive()


def test_studio_direct_scripting_through_this_os_sdk_layout(machine, tmp_path, monkeypatch):
    api = tmp_path / "Developer/Scripting"
    (api / "Modules").mkdir(parents=True)
    # Stand-in for Blackmagic's module: the isolated probe only needs an answer; in-process it returns a Studio fake.
    (api / "Modules/DaVinciResolveScript.py").write_text(
        "def scriptapp(name):\n"
        "    try:\n        import fakes\n    except ImportError:\n        return object()\n"
        "    return fakes.demo_resolve(studio=True)\n", encoding="utf-8")
    monkeypatch.setenv("RESOLVE_SCRIPT_API", str(api))
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delitem(sys.modules, "DaVinciResolveScript", raising=False)

    session = gateway.Session([gateway.DirectTransport()])
    resolve = session.resolve()
    assert session.transport_name == "direct" and doctor.edition(resolve) == "Studio"
    library = os.environ["RESOLVE_SCRIPT_LIB"]
    assert library.endswith("fusionscript.dll" if machine.platform == "win32" else "fusionscript.so")
    assert ("PYTHONHOME" in os.environ) == (machine.platform == "win32" and sys.prefix != sys.base_prefix)
    sys.modules.pop("DaVinciResolveScript", None)

    machine.resolve_open = False  # never import fusionscript while Resolve is closed: it would crash the server
    with pytest.raises(gateway.ResolveUnavailable):
        gateway.Session([gateway.DirectTransport()]).resolve()
