"""Shared native-call contracts: capabilities, refusals, readback and copy isolation."""
from dataclasses import dataclass
import math
import secrets
from weakref import WeakKeyDictionary

from ..errors import ForgeError
from ..gateway import call
from .context import current, video_items

_WORKING = WeakKeyDictionary()


def _identity(ctx):
    return (ctx.project.GetName(), call(ctx.timeline, "GetUniqueId") or ctx.timeline.GetName())


def mark_working(session, ctx):
    _WORKING.setdefault(session, set()).add(_identity(ctx))


def working_copy(session, purpose):
    ctx = current(session)
    if _identity(ctx) in _WORKING.get(session, set()):
        return ctx
    return fork(session, purpose).context


def invoke(target, method, *args):
    function = getattr(target, method, None)
    if not callable(function):
        raise ForgeError(f"This Resolve build lacks {method}.", code="BACKEND_UNSUPPORTED")
    try:
        return function(*args)
    except ForgeError:
        raise
    except Exception as exc:
        raise ForgeError(f"{method} failed: {exc}", code="RESOLVE_REFUSED") from exc


def accepted(target, method, *args):
    result = invoke(target, method, *args)
    if result is False or result is None:
        raise ForgeError(f"Resolve refused {method}.", code="RESOLVE_REFUSED")
    return result


def number(value, label, low=None, high=None):
    value = float(value)
    if not math.isfinite(value) or (low is not None and value < low) or (high is not None and value > high):
        raise ValueError(f"Invalid {label}.")
    return value


def name(value):
    if not isinstance(value, str) or not value.strip() or any(character in value for character in "\r\n\x00"):
        raise ValueError("A non-empty single-line name is required.")
    return value.strip()


def timelines(project):
    return [project.GetTimelineByIndex(index) for index in range(1, int(project.GetTimelineCount()) + 1)]


@dataclass
class EditTarget:
    context: object
    source: str
    target: str


def fork(session, purpose, copy_name=None):
    """All timeline edits use a new copy; a refusal leaves the source current."""
    ctx = current(session)
    source = ctx.timeline.GetName()
    target = name(copy_name) if copy_name else f"{source} [forge {purpose} {secrets.token_hex(3)}]"
    if target in {timeline.GetName() for timeline in timelines(ctx.project)}:
        raise ForgeError("Timeline name already exists.", code="TIMELINE_EXISTS")
    duplicate = accepted(ctx.timeline, "DuplicateTimeline", target)
    try:
        accepted(ctx.project, "SetCurrentTimeline", duplicate)
    except Exception:
        ctx.project.SetCurrentTimeline(ctx.timeline)
        raise
    ctx.timeline = duplicate
    mark_working(session, ctx)
    return EditTarget(ctx, source, target)


def selected(session, track=1, indices=None):
    ctx = current(session)
    if type(track) is not int or track < 1:
        raise ValueError("Track numbers start at 1.")
    return ctx, video_items(ctx, track, indices)


def verify(expected, actual, label):
    if isinstance(expected, (list, tuple)):
        if isinstance(actual, dict):
            actual = [actual.get(index, actual.get(str(index))) for index in range(1, len(expected) + 1)]
        if not isinstance(actual, (list, tuple)) or len(actual) != len(expected):
            raise ForgeError(f"Resolve did not retain {label}.", code="READBACK_FAILED")
        for index, (wanted, observed) in enumerate(zip(expected, actual)):
            verify(wanted, observed, f"{label}[{index}]")
        return
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise ForgeError(f"Resolve did not retain {label}.", code="READBACK_FAILED")
        for key, value in expected.items():
            verify(value, actual.get(key, actual.get(str(key))), f"{label}.{key}")
        return
    try:
        same = math.isclose(float(expected), float(actual), rel_tol=1e-6, abs_tol=1e-6) if isinstance(expected, (float, int)) else expected == actual
    except (ValueError, TypeError):
        same = False
    if not same:
        raise ForgeError(f"Resolve did not retain {label}: expected {expected!r}, got {actual!r}.", code="READBACK_FAILED")
