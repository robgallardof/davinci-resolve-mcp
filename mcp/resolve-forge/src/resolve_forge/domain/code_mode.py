"""Code Mode policy: what each tool may do when composed from a sandbox. Pure: no Resolve, no MCP, no processes.

Names, descriptions and schemas come from the registered tools; this table only adds what a schema cannot say.
A tool missing from it is denied, so a new tool stays out of the sandbox until someone classifies it.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

# Run immediately: no project state changes.
READ = "read"              # reads state, or pure computation
ANALYSIS = "analysis"      # reads media, may cache results and may import a named file into the Media Pool
ARTIFACT = "artifact"      # also writes NEW review files (sheets, previews) outside the project
# Run only after approval. Tools exposing dry_run preview first.
FILE_WRITE = "file_write"          # creates new files; sources are never touched
PROJECT_WRITE = "project_write"    # changes the open project; timeline edits go to a new copy
RENDER = "render"                  # starts a render job
# Never callable from the sandbox.
SYSTEM = "system"

IMMEDIATE = {READ, ANALYSIS, ARTIFACT}
RISKS = (READ, ANALYSIS, ARTIFACT, FILE_WRITE, PROJECT_WRITE, RENDER, SYSTEM)

# tool: (category, risk, needs a running Resolve)
CATALOG: dict[str, tuple[str, str, bool]] = {
    "forge_status": ("project", READ, True),
    "list_capabilities": ("project", READ, True),
    "project_workflow": ("project", PROJECT_WRITE, True),
    "configure_project": ("project", PROJECT_WRITE, True),
    "list_media": ("media_pool", READ, True),
    "ingest_media": ("media_pool", PROJECT_WRITE, True),
    "organise_media": ("media_pool", PROJECT_WRITE, True),
    "media_metadata": ("media_pool", PROJECT_WRITE, True),
    "sync_audio": ("media_pool", PROJECT_WRITE, True),
    "list_clips": ("timeline", READ, True),
    "audit_timeline": ("timeline", READ, True),
    "timeline_versions": ("timeline", PROJECT_WRITE, True),
    "configure_track": ("timeline", PROJECT_WRITE, True),
    "export_interchange": ("timeline", FILE_WRITE, True),
    "open_resolve_page": ("timeline", PROJECT_WRITE, True),
    "timeline_markers": ("markers", PROJECT_WRITE, True),
    "edit_clips": ("editing", PROJECT_WRITE, True),
    "apply_motion": ("editing", PROJECT_WRITE, True),
    "clear_motion": ("editing", PROJECT_WRITE, True),
    "make_platform_version": ("editing", PROJECT_WRITE, True),
    "assemble_timeline": ("editing", PROJECT_WRITE, True),
    "assemble_montage": ("editing", PROJECT_WRITE, True),
    "energize_timeline": ("editing", PROJECT_WRITE, True),
    "build_speaker_layout": ("editing", PROJECT_WRITE, True),
    "build_composition": ("editing", PROJECT_WRITE, True),
    "list_styles": ("editing", READ, False),
    "preview_motion": ("editing", READ, False),
    "locate_subject": ("editing", ANALYSIS, True),
    "plan_composition": ("editing", ARTIFACT, False),
    "grade_clips": ("color", PROJECT_WRITE, True),
    "apply_grade_preset": ("color", PROJECT_WRITE, True),
    "inspect_grade": ("color", READ, True),
    "gallery_stills": ("color", PROJECT_WRITE, True),
    "prepare_lut": ("color", FILE_WRITE, False),
    "apply_fusion_graph": ("fusion", PROJECT_WRITE, True),
    "inspect_fusion": ("fusion", READ, True),
    "add_music_bed": ("audio", PROJECT_WRITE, True),
    "place_sound_effects": ("audio", PROJECT_WRITE, True),
    "normalise_audio": ("audio", FILE_WRITE, False),
    "enhance_audio": ("audio", FILE_WRITE, False),
    "analyse_audio": ("audio", ANALYSIS, False),
    "transcribe_timeline": ("subtitles", ANALYSIS, True),
    "align_text": ("subtitles", ANALYSIS, False),
    "add_captions": ("subtitles", PROJECT_WRITE, True),
    "add_text_overlay": ("subtitles", PROJECT_WRITE, True),
    "list_text_styles": ("subtitles", READ, False),
    "preview_text_style": ("subtitles", ARTIFACT, False),
    "native_ai": ("subtitles", PROJECT_WRITE, True),
    "find_highlights": ("analysis", ANALYSIS, False),
    "find_story_moments": ("analysis", ANALYSIS, False),
    "analyse_scenes": ("analysis", ANALYSIS, False),
    "analyse_music": ("analysis", ANALYSIS, False),
    "plan_edit": ("planning", READ, False),
    "plan_production": ("planning", READ, False),
    "plan_beat_cuts": ("planning", ANALYSIS, False),
    "plan_energized_edit": ("planning", ANALYSIS, False),
    "plan_speaker_layout": ("planning", ANALYSIS, False),
    "create_music_visualizer": ("planning", FILE_WRITE, False),
    "review_shots": ("render", ARTIFACT, False),
    "review_video": ("render", ARTIFACT, False),
    "list_formats": ("render", READ, False),
    "preflight_render": ("render", READ, True),
    "render_status": ("render", READ, True),
    "render_for": ("render", RENDER, True),
    "repair_bridge_connection": ("system", SYSTEM, False),
}

# Argument shapes that make a state-changing tool read-only. Exact values only: anything else needs approval.
_READ_WHEN = {
    "project_workflow": lambda a: a.get("action", "inspect") in {"list", "inspect"},
    "timeline_versions": lambda a: a.get("action", "list") == "list",
    "gallery_stills": lambda a: a.get("action", "list") == "list",
    "timeline_markers": lambda a: a.get("entries") is None,
    "media_metadata": lambda a: a.get("values") is None,
}

# Tools that raise READBACK_FAILED themselves when Resolve did not retain what was written.
VERIFIED_BY_TOOL = {"edit_clips", "timeline_markers", "configure_track", "configure_project", "media_metadata",
                    "apply_fusion_graph", "energize_timeline", "export_interchange"}

# Asked for often, not offered by any tool. Better a clear no than an invented handler.
UNSUPPORTED = {
    "transition": "No tool inserts native transitions; the Resolve scripting API exposes no verified way to do it.",
    "trim": "Clips cannot be trimmed in place; build a new timeline with assemble_timeline or assemble_montage.",
    "delete": "Deleting projects, timelines, clips or media is deliberately not offered.",
    "relink": "Relinking source media is deliberately not offered.",
    "bin": "Bins are only created by ingest_media and organise_media (by extension or source directory).",
}

_ALIASES = {"subtitle": "captions", "subtitles": "captions", "caption": "captions", "bins": "media", "bin": "media",
            "pool": "media", "export": "render", "deliver": "render", "delivery": "render", "zoom": "motion",
            "grade": "color", "grading": "color", "lut": "color", "loudness": "audio", "marker": "markers",
            "gap": "audit", "gaps": "audit", "overlap": "audit", "clip": "clips", "vertical": "platform"}


@dataclass(frozen=True)
class Decision:
    effect: str  # run | preview | approve | deny
    risk: str
    reason: str = ""


def decide(tool: str, args: dict[str, Any], previewable: bool) -> Decision:
    """The single gate between sandbox and host. `previewable`: the tool's schema exposes dry_run."""
    entry = CATALOG.get(tool)
    if entry is None:
        return Decision("deny", SYSTEM, f"'{tool}' is not available in Code Mode.")
    risk = entry[1]
    if risk == SYSTEM:
        return Decision("deny", risk, f"'{tool}' is a system operation; call it directly.")
    if risk in IMMEDIATE:
        return Decision("run", risk)
    guard = _READ_WHEN.get(tool)
    try:
        if guard is not None and guard(args):
            return Decision("run", READ)
    except TypeError:  # e.g. an unhashable action: not one of the read-only shapes
        pass
    if previewable:
        dry_run = args.get("dry_run", True)
        if not isinstance(dry_run, bool):  # the tool layer would coerce "false" into a real write
            return Decision("deny", risk, "dry_run must be a literal true or false.")
        if dry_run:
            return Decision("preview", risk)
    return Decision("approve", risk)


def operation_key(tool: str, args: dict[str, Any]) -> str:
    """Identity of an approved operation. dry_run is excluded: approving a preview means running it for real."""
    canonical = {key: value for key, value in args.items() if key != "dry_run"}
    text = json.dumps([tool, canonical], sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tokens(text: str) -> list[str]:
    return [word for word in re.split(r"[^a-z0-9]+", text.lower()) if word]


def rank(entries: list[dict], query: str, *, category: str | None = None, risk: str | None = None,
         limit: int = 8) -> list[dict]:
    """Best matches for `query`: tool names weigh most, then category, then description and parameters."""
    wanted = _tokens(query)
    wanted += [_ALIASES[word] for word in wanted if word in _ALIASES]
    scored = []
    for position, entry in enumerate(entries):
        if (category and entry["category"] != category) or (risk and entry["risk"] != risk):
            continue
        name, group = set(_tokens(entry["name"])), set(_tokens(entry["category"]))
        text = set(_tokens(entry["summary"] + " " + " ".join(entry["params"])))
        score = sum(3 * (word in name) + 2 * (word in group) + (word in text) for word in wanted)
        if score or not wanted:
            scored.append((-score, position, entry))
    return [entry for _, _, entry in sorted(scored, key=lambda row: row[:2])[:limit]]


def unsupported_notes(query: str) -> list[str]:
    words = {word.rstrip("s") for word in _tokens(query)}
    return [note for key, note in UNSUPPORTED.items() if key in words]


def compact_params(schema: dict) -> list[str]:
    """`name:type=default` per parameter: enough to call a tool, far cheaper than its JSON schema."""
    required = set(schema.get("required", []))
    out = []
    for name, spec in schema.get("properties", {}).items():
        kinds = [option.get("type", "any") for option in spec.get("anyOf", [spec])]
        kind = "|".join(sorted({kind for kind in kinds if kind != "null"})) or "any"
        out.append(f"{name}:{kind}" if name in required else f"{name}:{kind}={json.dumps(spec.get('default'))}")
    return out


def overall_status(*, stage: str, ended: str, operations: int, applied: int, not_run: int, blocked: int,
                   failed: int, contradicted: bool, unverified: int, checks_passed: int) -> str:
    """One word for a whole composed run. It never reads better than its worst essential step."""
    if ended in {"cancelled", "timeout"}:
        return ended
    if contradicted:
        return "contradictory"
    if blocked:
        return "partial" if applied else "blocked"
    if ended == "failed":
        return "partial" if applied else "failed"
    if failed or not_run:
        return "partial"
    if stage == "plan" and operations:
        return "needs_approval"
    if applied and unverified and not checks_passed:
        return "unverified"
    return "success"
