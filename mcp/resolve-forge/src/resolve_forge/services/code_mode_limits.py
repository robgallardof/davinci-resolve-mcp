"""OS-enforced limits for the sandbox process. Any control that cannot be applied raises: the run is refused."""

from __future__ import annotations

import asyncio
import ctypes
import os
import signal
import subprocess
import sys
from ctypes import wintypes
from typing import Callable


class ContainmentError(RuntimeError):
    pass


OVERHEAD_MB = 256  # the Deno runtime itself, on top of what the script may use


class _WindowsJob:
    """Job object: memory ceiling, no child processes, low priority, and it dies with this server."""

    def __init__(self, pid: int, memory_mb: int) -> None:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self._kernel = kernel

        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class Counters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                        ("reads", "writes", "others", "read_bytes", "write_bytes", "other_bytes")]

        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", Counters),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        kill_on_close, die_on_exception, active_process, priority, process_memory = 0x2000, 0x400, 0x8, 0x20, 0x100
        info = Extended()
        info.BasicLimitInformation.LimitFlags = kill_on_close | die_on_exception | active_process | priority | process_memory
        info.BasicLimitInformation.ActiveProcessLimit = 1
        info.BasicLimitInformation.PriorityClass = 0x4000  # below normal: Resolve keeps the machine
        info.ProcessMemoryLimit = (memory_mb + OVERHEAD_MB) * 1024 * 1024

        self._job = kernel.CreateJobObjectW(None, None)
        if not self._job:
            raise ContainmentError(f"CreateJobObject failed ({ctypes.get_last_error()}).")
        if not kernel.SetInformationJobObject(self._job, 9, ctypes.byref(info), ctypes.sizeof(info)):
            raise ContainmentError(f"SetInformationJobObject failed ({ctypes.get_last_error()}).")
        handle = kernel.OpenProcess(0x0101, False, pid)  # PROCESS_TERMINATE | PROCESS_SET_QUOTA
        if not handle:
            raise ContainmentError(f"OpenProcess failed ({ctypes.get_last_error()}).")
        assigned = kernel.AssignProcessToJobObject(self._job, handle)
        kernel.CloseHandle(handle)
        if not assigned:
            raise ContainmentError(f"AssignProcessToJobObject failed ({ctypes.get_last_error()}).")

    def kill(self) -> None:
        if self._job:
            self._kernel.TerminateJobObject(self._job, 137)
            self._kernel.CloseHandle(self._job)
            self._job = None


def _rss_mb(pid: int) -> float | None:
    """Resident memory, or None when the process is gone."""
    if sys.platform == "linux":
        try:
            with open(f"/proc/{pid}/statm", encoding="ascii") as handle:
                return int(handle.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1048576
        except (OSError, IndexError, ValueError):
            return None
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], stdin=subprocess.DEVNULL, capture_output=True,
                         text=True, timeout=5).stdout.strip()
    return int(out) / 1024 if out else None


class _PosixGroup:
    """rlimits are set at spawn. A watchdog covers RSS: RLIMIT_AS would break V8's address-space reservations."""

    def __init__(self, process: asyncio.subprocess.Process, memory_mb: int, on_exceeded: Callable[[], None]) -> None:
        self._pid = process.pid
        if _rss_mb(self._pid) is None and process.returncode is None:
            raise ContainmentError("Cannot read the sandbox's memory use on this system.")
        self._task = asyncio.ensure_future(self._watch(memory_mb + OVERHEAD_MB, on_exceeded))

    async def _watch(self, ceiling_mb: int, on_exceeded: Callable[[], None]) -> None:
        while True:
            await asyncio.sleep(0.05)
            used = await asyncio.get_running_loop().run_in_executor(None, _rss_mb, self._pid)
            if used is None:
                return
            if used > ceiling_mb:
                on_exceeded()
                self.kill()
                return

    def kill(self) -> None:
        self._task.cancel()
        try:
            os.killpg(self._pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def spawn_options(cpu_seconds: int) -> dict:
    """Extra create_subprocess_exec arguments that apply limits before the process runs anything."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}

    def limit() -> None:
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1048576, 16 * 1048576))  # only Deno's own cache writes files

    return {"start_new_session": True, "preexec_fn": limit}


def contain(process: asyncio.subprocess.Process, memory_mb: int, on_exceeded: Callable[[], None]):
    """Attach the post-spawn controls. The script is only sent afterwards, so nothing runs uncontained."""
    if sys.platform == "win32":
        return _WindowsJob(process.pid, memory_mb)
    return _PosixGroup(process, memory_mb, on_exceeded)
