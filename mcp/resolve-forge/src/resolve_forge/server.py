"""Composition root: build the session, register tools, serve over stdio (default) or token-guarded HTTP."""

from __future__ import annotations

import importlib
import logging
import os
import sys
import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import tools
from .analysis import faces
from .gateway import Session

INSTRUCTIONS = """resolve-forge: intent-level editing for DaVinci Resolve (motion, platform versions, delivery).
Flow: forge_status -> (find_highlights -> assemble_timeline) -> make_platform_version (if changing aspect)
-> transcribe_timeline -> apply_motion(cuts_s, hits_s) -> add_captions / add_text_overlay -> render_for.
Design: list_text_styles -> preview_text_style -> add_captions(style='auto', words=corrected_words).
Default captions and overlays use coherent modern art direction, short entry animation and safe-zone layout.
Respect tone and brand colors; do not stack camera punches, titles and caption pops on every word.
Errors carry a stable `code` and a `hint`.
Resources: resolve://status, resolve://timeline, forge://formats, forge://styles, skill://<name> (playbooks).
Prompts: one per editor role (video-director, vertical-editor, ...).
For granular work (media pool, color nodes, Fairlight, markers, transcription, Fusion graphs)
use Forge-owned authoring tools: project_workflow, ingest_media, edit_clips, grade_clips, apply_fusion_graph."""


WORKSPACE = Path(os.environ.get("DAVINCI_AGENTS_ROOT") or Path(__file__).resolve().parents[3])
_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)


def _description(text: str) -> str:
    m = _FRONTMATTER.match(text)
    found = re.search(r'description:\s*"?(.*?)"?\s*$', m[1], re.M) if m else None
    return found[1] if found else ""


def _constant(text: str):
    return lambda: text  # no parameters, or FastMCP would expose them as arguments


def register_playbooks(mcp: FastMCP, root: Path = WORKSPACE) -> None:
    """Skills become resources (skill://<name>) and roles become prompts, so any MCP client gets the playbooks."""
    for skill in sorted(root.glob(".agents/skills/*/SKILL.md")):
        text = skill.read_text(encoding="utf-8")
        mcp.resource(f"skill://{skill.parent.name}", name=skill.parent.name, description=_description(text),
                     mime_type="text/markdown")(_constant(text))
    for role in sorted(root.glob(".agents/agents/*.md")):
        text = role.read_text(encoding="utf-8")
        mcp.prompt(name=role.stem, description=_description(text))(_constant(_FRONTMATTER.sub("", text, count=1)))


def build() -> FastMCP:
    mcp = FastMCP("resolve-forge", instructions=INSTRUCTIONS)
    session = Session()
    tools.register(mcp, session)
    register_playbooks(mcp)
    return mcp


TOKEN_ENV = "RESOLVE_FORGE_MCP_TOKEN"


def main(argv: list[str] | None = None) -> None:
    import argparse

    from . import http_transport

    parser = argparse.ArgumentParser(prog="resolve-forge", description="resolve-forge MCP server")
    http_transport.add_arguments(parser)
    args = parser.parse_args(argv)
    if args.http:  # fail fast on a bad token/address, before loading native modules
        try:
            http_transport.read_token(TOKEN_ENV)
            http_transport.parse_listen(args.listen)
        except http_transport.HttpConfigError as error:
            sys.exit(f"resolve-forge: {error}")
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
    if args.http:
        http_transport.serve(build(), args.listen, args.allow_host, TOKEN_ENV)
    else:
        build().run()


if __name__ == "__main__":
    main()
