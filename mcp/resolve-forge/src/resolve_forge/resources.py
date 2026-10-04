"""Read-only MCP resources: state an agent can read without calling a tool (idea from DWC/Tooflex).

Improvement over theirs: each resource runs on the dedicated Resolve thread, so a slow Resolve
never blocks the stdio loop, and failures come back as the same typed JSON error the tools use.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from .domain import formats, styles
from .errors import payload
from .gateway import Session
from .services.context import current, describe


def register(mcp: FastMCP, session: Session, run: Callable[..., Any]) -> None:
    def safely(fn: Callable[[], dict]) -> Callable[[], Any]:
        async def resource() -> str:
            try:
                return json.dumps(await run(fn), ensure_ascii=False, indent=1)
            except Exception as exc:  # no error envelope for resources: return ours
                return json.dumps(payload(exc), ensure_ascii=False)
        return resource

    def status() -> dict:
        ctx = current(session, need_timeline=False)
        out = {"version": ctx.resolve.GetVersionString(), "transport": session.transport_name,
               "project": ctx.project.GetName()}
        if ctx.timeline is not None:
            out |= {"timeline": ctx.timeline.GetName(), "fps": ctx.fps, "resolution": f"{ctx.width}x{ctx.height}"}
        return out

    def timeline() -> dict:
        ctx = current(session)
        tracks = {}
        for t in range(1, int(ctx.timeline.GetTrackCount("video")) + 1):
            items = [i for i in (ctx.timeline.GetItemListInTrack("video", t) or []) if i]
            tracks[f"V{t}"] = [describe(item, n) for n, item in enumerate(items, 1)]
        return {"timeline": ctx.timeline.GetName(), "start_frame": ctx.start_frame, "fps": ctx.fps, "tracks": tracks}

    def all_formats() -> dict:
        return {k: f.as_dict() for k, f in formats.FORMATS.items()}

    for uri, name, description, fn in (
        ("resolve://status", "status", "Resolve version, transport, project and timeline", status),
        ("resolve://timeline", "timeline", "Current timeline with every video track's clips", timeline),
        ("forge://formats", "formats", "Platform delivery specs and safe zones", all_formats),
        ("forge://styles", "styles", "Motion styles for apply_motion", styles.catalogue),
    ):
        mcp.resource(uri, name=name, description=description, mime_type="application/json")(safely(fn))
