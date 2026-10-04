"""How we reach a running DaVinci Resolve. Nothing else in the package knows.

Transports are tried in order; the first that yields a handle wins:
  1. direct  — Blackmagic's DaVinciResolveScript (Studio; Free <= 21.0 with local scripting)
  2. bridge  — the in-app loopback bridge from samuelgursky/davinci-resolve-mcp
               (works on the Free edition; run Workspace > Scripts > resolve_bridge)
Code above this layer only sees `Session.resolve()`.
"""

from __future__ import annotations

import importlib
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Protocol

log = logging.getLogger("resolve_forge.gateway")

WIN_API = r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting"
WIN_LIB = r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll"
DEFAULT_UPSTREAM = Path(__file__).resolve().parents[4] / "vendor" / "davinci-resolve-mcp" / "src"


class ResolveUnavailable(RuntimeError):
    pass


class Transport(Protocol):
    name: str

    def connect(self) -> Any | None: ...


def resolve_process_running() -> bool:
    """fusionscript segfaults the whole server when Resolve is closed, so ask the OS first."""
    try:
        if sys.platform == "win32":
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Resolve.exe", "/NH"],
                                 stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            return "resolve.exe" in out.lower()
        return subprocess.run(["pgrep", "-if", "resolve"], stdin=subprocess.DEVNULL, capture_output=True,
                              timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return True  # cannot tell: let the connection attempt decide


_PROBE = """
import os, sys
sys.path.append(os.path.join(os.environ["RESOLVE_SCRIPT_API"], "Modules"))
import DaVinciResolveScript as dvr
print("REACHABLE" if dvr.scriptapp("Resolve") is not None else "REFUSED")
"""


def _prepare_native_env() -> None:
    os.environ.setdefault("RESOLVE_SCRIPT_API", WIN_API)
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", WIN_LIB)
    # fusionscript embeds Python and segfaults inside a venv unless PYTHONHOME
    # names the base interpreter (measured on Resolve 21.0.4, Windows).
    os.environ.setdefault("PYTHONHOME", sys.base_prefix)


def direct_scripting_available() -> bool:
    """Probe the native module in a child process: a crash there cannot take the server down.

    Free refuses external scripting (scriptapp -> None); Studio with
    'External scripting: Local' answers.
    """
    _prepare_native_env()
    try:
        out = subprocess.run([sys.executable, "-c", _PROBE], stdin=subprocess.DEVNULL, capture_output=True,
                             text=True, timeout=30,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return "REACHABLE" in out


class DirectTransport:
    name = "direct"

    def __init__(self) -> None:
        self._available: bool | None = None

    def connect(self) -> Any | None:
        if not resolve_process_running():
            self._available = None  # re-probe after Resolve restarts
            return None
        if self._available is None:
            self._available = direct_scripting_available()
        if not self._available:
            return None
        modules = str(Path(os.environ["RESOLVE_SCRIPT_API"]) / "Modules")
        if modules not in sys.path:
            sys.path.append(modules)
        try:
            dvr = importlib.import_module("DaVinciResolveScript")
        except ImportError as exc:
            log.debug("DaVinciResolveScript not importable: %s", exc)
            return None
        return dvr.scriptapp("Resolve")


class BridgeTransport:
    name = "bridge"

    def __init__(self, upstream_src: Path | None = None) -> None:
        self.upstream_src = Path(os.environ.get("FORGE_UPSTREAM_SRC", upstream_src or DEFAULT_UPSTREAM))

    def connect(self) -> Any | None:
        if not self.upstream_src.is_dir() or not resolve_process_running():
            return None
        root = str(self.upstream_src.parent)  # upstream imports itself as `src.utils...`
        if root not in sys.path:
            sys.path.append(root)
        try:
            client = importlib.import_module("src.utils.resolve_bridge_client")
            return client.connect(require_enabled=False)
        except Exception as exc:  # BridgeUnavailable or import problems
            log.debug("bridge unavailable: %s", exc)
            return None


class Session:
    """Lazily connects and re-connects when Resolve was restarted."""

    def __init__(self, transports: list[Transport] | None = None) -> None:
        self.transports = transports if transports is not None else [DirectTransport(), BridgeTransport()]
        self._handle: Any | None = None
        self.transport_name: str | None = None

    def resolve(self) -> Any:
        if self._handle is not None and _alive(self._handle):
            return self._handle
        for transport in self.transports:
            handle = transport.connect()
            if handle is not None and _alive(handle):
                self._handle, self.transport_name = handle, transport.name
                return handle
        self._handle = None
        raise ResolveUnavailable(
            "Cannot reach DaVinci Resolve. Open Resolve and either enable "
            "Preferences > System > General > External scripting using: Local (Studio), "
            "or run Workspace > Scripts > resolve_bridge (Free)."
        )


def _alive(handle: Any) -> bool:
    try:
        return bool(handle.GetVersionString())
    except Exception:
        return False


def call(obj: Any, method: str, *args: Any, default: Any = None) -> Any:
    """Call an optional API method; `default` when this Resolve build lacks it."""
    fn: Callable[..., Any] | None = getattr(obj, method, None)
    if not callable(fn):
        return default
    return fn(*args)
