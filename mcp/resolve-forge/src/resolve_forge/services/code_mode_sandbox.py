"""The sandbox process: Deno with every permission denied, an empty environment and JSON lines as its only channel."""

from __future__ import annotations

import asyncio
import json
import math
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .. import errors as E
from ..errors import ForgeError
from . import code_mode_limits

RUNNER = Path(__file__).resolve().parents[1] / "sandbox" / "runner.js"
# No --allow-* flag exists on purpose. The denials repeat Deno's default so a surprising environment cannot widen it.
DENO_FLAGS = ("run", "--no-prompt", "--no-remote", "--no-npm", "--no-config", "--no-lock", "--no-code-cache",
              "--cached-only", "--deny-env", "--deny-read", "--deny-write", "--deny-net", "--deny-run", "--deny-ffi",
              "--deny-sys", "--deny-import")


@dataclass(frozen=True)
class Limits:
    timeout_ms: int = 10_000       # time the script may spend running; capability calls do not count
    wall_ms: int = 600_000         # time a whole run may take, capability calls included
    output_bytes: int = 65_536     # what the model receives
    memory_mb: int = 128
    max_calls: int = 200
    code_bytes: int = 65_536
    message_bytes: int = 8_388_608  # one message in either direction

    @classmethod
    def from_env(cls, env: dict | None = None) -> "Limits":
        env = os.environ if env is None else env
        values = {}
        for field, name in (("timeout_ms", "TIMEOUT_MS"), ("wall_ms", "WALL_MS"), ("output_bytes", "MAX_OUTPUT_BYTES"),
                            ("memory_mb", "MEMORY_MB"), ("max_calls", "MAX_CALLS")):
            raw = env.get(f"RESOLVE_FORGE_CODE_MODE_{name}")
            if raw is not None:
                try:
                    values[field] = int(raw)
                except ValueError:
                    raise ValueError(f"RESOLVE_FORGE_CODE_MODE_{name} must be an integer, got {raw!r}") from None
                if values[field] <= 0:
                    raise ValueError(f"RESOLVE_FORGE_CODE_MODE_{name} must be positive, got {raw!r}")
        return cls(**values)


def find_deno() -> str | None:
    """The binary from the `deno` dependency first, then one the user installed."""
    try:
        import deno
        return str(deno.find_deno_bin())
    except (ImportError, FileNotFoundError, AttributeError):
        return shutil.which("deno")


class SandboxError(RuntimeError):
    """The sandbox died or broke the protocol. `code` says how."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


class Sandbox:
    def __init__(self, limits: Limits) -> None:
        self.limits = limits
        self.exceeded_memory = False
        self._process: asyncio.subprocess.Process | None = None
        self._containment = None
        self._directory: str | None = None
        self._stderr = b""
        self._stderr_task: asyncio.Task | None = None

    async def start(self, code: str, mode: str, tools: list[str]) -> None:
        deno = find_deno()
        if deno is None:
            raise ForgeError("Code Mode needs the Deno runtime, which is not installed.", code=E.MISSING_DEPENDENCY,
                             hint="Run `uv sync` in mcp/resolve-forge (Deno is a dependency), then restart the server.")
        self._directory = tempfile.mkdtemp(prefix="forge-code-")
        env = {"DENO_DIR": self._directory, "DENO_NO_UPDATE_CHECK": "1", "NO_COLOR": "1"}
        if os.name == "nt":
            env["SystemRoot"] = os.environ.get("SystemRoot", r"C:\Windows")
        heap = f"--v8-flags=--max-old-space-size={self.limits.memory_mb}"
        # V8's helper threads burn CPU too, so the kernel's ceiling sits well above the script's own budget.
        cpu_seconds = 4 * math.ceil(self.limits.timeout_ms / 1000) + 10
        self._process = await asyncio.create_subprocess_exec(
            deno, *DENO_FLAGS, heap, str(RUNNER), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, env=env, cwd=self._directory, limit=self.limits.message_bytes,
            **code_mode_limits.spawn_options(cpu_seconds))
        try:
            self._containment = code_mode_limits.contain(self._process, self.limits.memory_mb, self._memory_exceeded)
        except (code_mode_limits.ContainmentError, OSError) as exc:
            await self.close()
            raise ForgeError(f"Sandbox limits could not be applied: {exc}", code="SANDBOX_UNAVAILABLE",
                             hint="Code Mode refuses to run without them; direct tools keep working.") from exc
        self._stderr_task = asyncio.ensure_future(self._drain_stderr())
        await self.send({"t": "start", "code": code, "mode": mode, "tools": tools})

    def _memory_exceeded(self) -> None:
        self.exceeded_memory = True

    async def _drain_stderr(self) -> None:
        while chunk := await self._process.stderr.read(65536):
            self._stderr = (self._stderr + chunk)[-4096:]

    async def send(self, message: dict) -> None:
        self._process.stdin.write(json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n")
        await self._process.stdin.drain()

    async def receive(self) -> dict:
        try:
            line = await self._process.stdout.readline()
        except ValueError as exc:  # asyncio's stream limit: one line larger than message_bytes
            raise SandboxError("The script sent a message over the size limit.", "OUTPUT_LIMIT") from exc
        if not line:
            await self._process.wait()
            if self._stderr_task:
                await self._stderr_task
            tail = self._stderr.decode("utf-8", "replace")
            if self.exceeded_memory or "out of memory" in tail.lower():
                raise SandboxError("The script exceeded the sandbox memory limit.", "SANDBOX_MEMORY_LIMIT")
            raise SandboxError(f"The sandbox exited early (code {self._process.returncode}). {tail[-500:]}".strip(),
                               "SANDBOX_CRASHED")
        try:
            message = json.loads(line)
        except ValueError as exc:
            raise SandboxError("The sandbox broke the message protocol.", "SANDBOX_PROTOCOL") from exc
        if not isinstance(message, dict):
            raise SandboxError("The sandbox broke the message protocol.", "SANDBOX_PROTOCOL")
        return message

    async def close(self) -> None:
        """Kill everything and remove the temporary directory. Safe to call at any point."""
        if self._containment is not None:
            self._containment.kill()
            self._containment = None
        process = self._process
        if process is not None:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
        try:
            if process is not None:
                await process.wait()
        finally:  # still runs when the wait itself is cancelled; the process has already been killed
            if process is not None and process.stdin is not None:
                process.stdin.close()
            if self._stderr_task is not None:
                self._stderr_task.cancel()
            if self._directory is not None:
                shutil.rmtree(self._directory, ignore_errors=True)
                self._directory = None
