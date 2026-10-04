"""Typed, actionable errors. Every failure an agent sees has a stable `code` and a `hint`.

Agents branch on `code` (retry, ask the user, change an argument) instead of parsing prose.
"""

from __future__ import annotations


class ForgeError(RuntimeError):
    """A user-facing failure: message for humans, code for agents, hint for the next step."""

    code = "FORGE_ERROR"

    def __init__(self, message: str, *, code: str | None = None, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.code
        self.hint = hint


# Stable codes (documented in the skill `davinci-resolve-mcp`).
RESOLVE_UNREACHABLE = "RESOLVE_UNREACHABLE"
NO_PROJECT = "NO_PROJECT"
NO_TIMELINE = "NO_TIMELINE"
EMPTY_TRACK = "EMPTY_TRACK"
CLIP_NOT_FOUND = "CLIP_NOT_FOUND"
INVALID_ARGUMENT = "INVALID_ARGUMENT"
BACKEND_UNSUPPORTED = "BACKEND_UNSUPPORTED"
TIMELINE_EXISTS = "TIMELINE_EXISTS"
RESOLVE_REFUSED = "RESOLVE_REFUSED"
RENDER_REFUSED = "RENDER_REFUSED"
MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
MEDIA_NOT_FOUND = "MEDIA_NOT_FOUND"


def payload(exc: BaseException) -> dict:
    """Shape any expected exception as the tool's error response."""
    from .gateway import ResolveUnavailable  # local: gateway must not depend on this module's users

    if isinstance(exc, ForgeError):
        code, hint, message = exc.code, exc.hint, exc.message
    elif isinstance(exc, ResolveUnavailable):
        code, hint, message = RESOLVE_UNREACHABLE, "Run `uv run resolve-forge-doctor` for the exact next step.", str(exc)
    elif isinstance(exc, OSError):
        code, hint, message = "IO_FAILURE", "Check the path and access permissions.", str(exc)
    else:  # KeyError / ValueError from the pure domain layer = bad argument
        code, hint, message = INVALID_ARGUMENT, None, str(exc).strip("'\"")
    out = {"ok": False, "error": message, "code": code}
    if hint:
        out["hint"] = hint
    return out
