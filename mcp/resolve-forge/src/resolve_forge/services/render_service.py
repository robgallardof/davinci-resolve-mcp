"""Use case: queue (and optionally start) a platform-ready render of the current timeline."""

from __future__ import annotations

from pathlib import Path

from ..domain import formats
from ..gateway import Session
from .. import errors as E
from .context import ForgeError, current


DEFAULT_OUTPUT = Path.home() / "Movies" / "resolve-forge"  # inside the Free bridge's allowed roots


def queue(session: Session, format_key: str, target_dir: str | None = None, *, name: str | None = None,
          start: bool = True) -> dict:
    ctx = current(session)
    fmt = formats.get(format_key)
    target_dir = str(target_dir or DEFAULT_OUTPUT)
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    p = ctx.project
    from .native import accepted
    accepted(ctx.resolve.GetProjectManager(), "SaveProject")

    codec = fmt.codec
    if not p.SetCurrentRenderFormatAndCodec(fmt.container, codec):
        codec = "H264"  # H.265 is Studio/hardware-dependent
        if not p.SetCurrentRenderFormatAndCodec(fmt.container, codec):
            raise ForgeError(f"Resolve refused {fmt.container}/{fmt.codec} and {fmt.container}/H264.",
                             code=E.RENDER_REFUSED)

    # CustomName must be non-empty or Resolve rejects the whole payload.
    custom = name or f"{ctx.timeline.GetName()}_{fmt.key}"
    settings = {"SelectAllFrames": True, "TargetDir": str(target_dir), "CustomName": custom,
                "FormatWidth": fmt.width, "FormatHeight": fmt.height}
    try:
        accepted = p.SetRenderSettings(settings)
    except Exception as exc:  # the Free bridge refuses paths outside its allowed roots
        raise ForgeError(f"Render settings refused ({exc}).", code=E.RENDER_REFUSED,
                         hint=f"On Free, render under {DEFAULT_OUTPUT.parent} or add the folder to "
                              "allowed_output_roots in the bridge.json.") from exc
    if not accepted:
        raise ForgeError(f"SetRenderSettings rejected {settings}", code=E.RENDER_REFUSED)
    job = p.AddRenderJob()
    if not job:
        raise ForgeError("AddRenderJob failed.", code=E.RENDER_REFUSED,
                         hint="Check the Deliver page is reachable and the disk is writable.")
    started = bool(p.StartRendering([job], False)) if start else False
    return {"job_id": job, "codec": codec, "file": str(Path(target_dir) / custom), "started": started,
            "timeline_resolution": f"{ctx.width}x{ctx.height}",
            "warning": None if (ctx.width, ctx.height) == (fmt.width, fmt.height)
            else "timeline resolution differs from the format — run make_platform_version first"}


def status(session: Session, job_id: str) -> dict:
    ctx = current(session, need_timeline=False)
    return {"job_id": job_id, **(ctx.project.GetRenderJobStatus(job_id) or {}),
            "rendering": bool(ctx.project.IsRenderingInProgress())}
