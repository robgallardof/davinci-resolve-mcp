"""Composition root: build the session, register tools, serve over stdio."""

from __future__ import annotations

import importlib
import logging
import os

from mcp.server.fastmcp import FastMCP

from . import tools
from .analysis import faces
from .gateway import Session

INSTRUCTIONS = """resolve-forge: intent-level editing for DaVinci Resolve (motion, platform versions, delivery).
Flow: forge_status -> (find_highlights -> assemble_timeline) -> make_platform_version (if changing aspect)
-> transcribe_timeline -> apply_motion(cuts_s, hits_s) -> add_captions / add_text_overlay -> render_for.
Errors carry a stable `code` and a `hint`.
Resources: resolve://status, resolve://timeline, forge://formats, forge://styles.
For granular work (media pool, color nodes, Fairlight, markers, transcription, Fusion graphs)
use the 'davinci-resolve' server, which runs alongside this one."""


def build() -> FastMCP:
    mcp = FastMCP("resolve-forge", instructions=INSTRUCTIONS)
    tools.register(mcp, Session())
    return mcp


def main() -> None:
    logging.basicConfig(level=os.environ.get("FORGE_LOG", "WARNING"))
    # Import native-heavy modules BEFORE stdio starts: on Windows, loading the
    # numpy/opencv/Pillow/PyAV DLLs while another thread blocks reading the stdin
    # pipe deadlocks the process (measured: the first forge_status hung forever).
    # Whisper/CUDA never load here at all: transcription runs in a worker process.
    faces.available()
    for module in ("numpy", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont", "av"):
        try:
            importlib.import_module(module)
        except ImportError:
            pass
    build().run()


if __name__ == "__main__":
    main()
