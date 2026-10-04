"""Composition root: build the session, register tools, serve over stdio."""

from __future__ import annotations

import logging
import os

from mcp.server.fastmcp import FastMCP

from . import tools
from .analysis import faces
from .gateway import Session

INSTRUCTIONS = """resolve-forge: intent-level editing for DaVinci Resolve (motion, platform versions, delivery).
Flow: forge_status -> list_clips -> make_platform_version (if changing aspect) -> preview_motion
-> apply_motion -> render_for -> render_status.
For granular work (media pool, color nodes, Fairlight, markers, transcription, Fusion graphs)
use the 'davinci-resolve' server, which runs alongside this one."""


def build() -> FastMCP:
    mcp = FastMCP("resolve-forge", instructions=INSTRUCTIONS)
    tools.register(mcp, Session())
    return mcp


def main() -> None:
    logging.basicConfig(level=os.environ.get("FORGE_LOG", "WARNING"))
    # Import native-heavy modules BEFORE stdio starts: on Windows, loading the
    # numpy/opencv DLLs while another thread blocks reading the stdin pipe
    # deadlocks the process (measured: the first forge_status hung forever).
    faces.available()
    build().run()


if __name__ == "__main__":
    main()
