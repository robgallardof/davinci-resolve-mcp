"""Repair only a proven orphaned Forge launcher holding the configured loopback port."""
import base64
import ctypes
import json
import os
from pathlib import Path, PureWindowsPath
import subprocess
import sys

from ..bridge.client import config_path
from ..errors import ForgeError


INVENTORY = r"""
$properties = @(
    'ProcessId','ParentProcessId','Name',
    @{Name='ExecutablePath';Expression={if ($_.Name -ieq 'fuscript.exe') {$_.ExecutablePath}}},
    @{Name='CommandLine';Expression={if ($_.Name -ieq 'fuscript.exe') {$_.CommandLine}}},
    @{Name='CreationDate';Expression={if ($_.Name -ieq 'fuscript.exe' -and $_.CreationDate) {$_.CreationDate.ToUniversalTime().ToString('o')}}}
)
$processes = @(Get-CimInstance Win32_Process -ErrorAction Stop | Select-Object -Property $properties)
$listeners = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Select-Object LocalPort,LocalAddress,OwningProcess)
@{processes=$processes;listeners=$listeners} | ConvertTo-Json -Depth 5 -Compress
"""


def _run(script):
    script = "$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)\n" + script
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        completed = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                                   stdin=subprocess.DEVNULL, capture_output=True, timeout=30,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ForgeError("Windows bridge recovery inventory/action could not run.", code="BRIDGE_RECOVERY_FAILED",
                         hint="Check PowerShell availability and process/network inventory permissions.") from exc
    if completed.returncode:
        raise ForgeError("Bridge recovery inventory/action failed; process details and credentials are withheld.",
                         code="BRIDGE_RECOVERY_FAILED", hint="Check Windows process/network inventory permissions.")
    try:
        return json.loads(completed.stdout.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise ForgeError("Bridge recovery returned invalid inventory JSON.", code="BRIDGE_RECOVERY_FAILED") from exc


def _argv(command):
    argc = ctypes.c_int()
    parser = ctypes.windll.shell32.CommandLineToArgvW
    parser.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    parser.restype = ctypes.POINTER(ctypes.c_wchar_p)
    pointer = parser(command, ctypes.byref(argc))
    if not pointer:
        return []
    try:
        return [pointer[i] for i in range(argc.value)]
    finally:
        free = ctypes.windll.kernel32.LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        free(ctypes.cast(pointer, ctypes.c_void_p))


def _path(value):
    return str(PureWindowsPath(value or "")).casefold()


def eligible(process, inventory, port, launcher, executable, argv=_argv):
    """All independent identity checks must agree; missing evidence fails closed."""
    pid, parent = process.get("ProcessId"), process.get("ParentProcessId")
    processes = inventory.get("processes") or []
    if (process.get("Name", "").casefold() != "fuscript.exe" or
            _path(process.get("ExecutablePath")) != _path(executable) or
            not process.get("CreationDate") or not pid or not parent):
        return False
    if any(p.get("ProcessId") == parent for p in processes):
        return False
    if not any(p.get("Name", "").casefold() == "resolve.exe" and p.get("ProcessId") != parent for p in processes):
        return False
    if not any(_path(arg) == _path(launcher) for arg in argv(process.get("CommandLine") or "")):
        return False
    return any(row.get("LocalPort") == port and row.get("OwningProcess") == pid and
               row.get("LocalAddress") in ("127.0.0.1", "::1") for row in inventory.get("listeners") or [])


def _stop_script(process, port, launcher, executable):
    # JSON encoded as data, never interpolated as executable shell strings.
    data = base64.b64encode(json.dumps({"process": process, "port": port, "launcher": str(launcher),
                                     "executable": str(executable)}).encode()).decode()
    return r"""
$ErrorActionPreference='Stop'
$expected = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('""" + data + r"""')) | ConvertFrom-Json
$targetId = [int]$expected.process.ProcessId
$p = Get-CimInstance Win32_Process -Filter "ProcessId=$targetId"
$parentAlive = Get-CimInstance Win32_Process -Filter "ProcessId=$($expected.process.ParentProcessId)"
$resolveNow = @(Get-CimInstance Win32_Process -Filter "Name='Resolve.exe'")
$ownsPort = @(Get-NetTCPConnection -State Listen -LocalPort $expected.port -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -eq $targetId -and $_.LocalAddress -in @('127.0.0.1','::1') })
$same = $p -and $p.Name -ieq 'fuscript.exe' -and $p.ExecutablePath -ieq $expected.executable -and $p.CommandLine -ceq $expected.process.CommandLine -and $p.CreationDate.ToUniversalTime().ToString('o') -ceq $expected.process.CreationDate -and $p.ParentProcessId -eq $expected.process.ParentProcessId
if ($same -and !$parentAlive -and $resolveNow.Count -gt 0 -and $ownsPort.Count -gt 0) {
    $handle = Get-Process -Id $targetId
    if ($handle.StartTime.ToUniversalTime() -ne $p.CreationDate.ToUniversalTime()) { @{stopped=$false;reason='identity_changed'} | ConvertTo-Json -Compress; exit }
    Stop-Process -InputObject $handle -ErrorAction Stop
    @{stopped=$true} | ConvertTo-Json -Compress
} else { @{stopped=$false;reason='evidence_changed'} | ConvertTo-Json -Compress }
"""


def repair(dry_run=True, *, runner=None, platform=None, argv=None):
    if (platform or sys.platform) != "win32":
        return {"supported": False, "applied": False, "reason": "Windows-only orphaned bridge recovery.",
                "next": "On macOS/Linux quit and reopen Resolve to free the bridge port, then run "
                        "Workspace > Scripts > resolve_bridge."}
    runner = runner or _run
    try:
        config = json.loads(config_path().read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ForgeError("Cannot read bridge recovery configuration.", code="IO_FAILURE",
                         hint="Check the bridge config exists and contains valid JSON.") from exc
    port = config.get("port")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Bridge configuration needs a valid TCP port.")
    launcher = Path(os.environ["APPDATA"]) / "Blackmagic Design/DaVinci Resolve/Support/Fusion/Scripts/Utility/resolve_bridge.py"
    executable = Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Blackmagic Design/DaVinci Resolve/fuscript.exe"
    inventory = runner(INVENTORY)
    candidates = [p for p in inventory.get("processes") or []
                  if eligible(p, inventory, port, launcher, executable, argv or _argv)]
    result = {"supported": True, "applied": False, "dry_run": dry_run, "port": port,
              "orphaned_helper_pids": [p["ProcessId"] for p in candidates],
              "next": "Run Workspace > Scripts > resolve_bridge in the current Resolve after repair."}
    if len(candidates) != 1:
        return {**result, "reason": "No unique verified orphan; nothing stopped."}
    if dry_run:
        return result
    action = runner(_stop_script(candidates[0], port, launcher, executable))
    return {**result, "applied": action.get("stopped") is True, "reason": action.get("reason")}
