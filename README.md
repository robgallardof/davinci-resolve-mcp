# davinci-agents

**[English](#english)** · **[Español](#español)**

## English

Edit DaVinci Resolve by talking to an AI agent that works like a producer and a professional editor. One MCP of our own
(**resolve-forge**, 65 tools), a Free-edition bridge, portable editor roles and skills. Works with Claude Code, Codex,
Cursor, Gemini CLI and VS Code. Skills and roles are written in English; the agent answers in your language.

We studied the public DaVinci Resolve MCPs and rebuilt the useful capabilities our own way (pure domain rules →
services → thin MCP tools). No competing implementation is imported or packaged. See
[selection, improvements and status](docs/third-party-migration.md).

### Install

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
```

Requires Resolve and uv. The bootstrap installs Python 3.12, Forge, speech/vision dependencies, bundled ffmpeg, the
Forge bridge and the agent configs. Free 21.0.x: open a project, then Workspace → Scripts → resolve_bridge (every time
Resolve starts). Studio: Preferences → System → General → External scripting using = Local. Then ask for `forge_status`.
New here? Start with [First steps](docs/FIRST-STEPS.md).

### What it does

- **Editorial**: motion for talking heads, vertical/horizontal platform versions, highlights, source-range assembly,
  local transcription, designed animated captions (Creator / Studio / Editorial / Impact, karaoke) and text overlays, delivery.
- **Entertainment pacing**: detects where the action is (pets, hands, jumps), faces and dead time, and rebuilds
  long shots as 1.2–2.8 s shots with alternating wide / x1.25 / x1.5 / crash-zoom framings that keep the subject
  centred. Confirmed ranges with no people or animals are cut.
- **Self-review**: before building, a contact sheet of what each shot really shows (crop, faces, subject, text
  boxes) with flagged problems, text positions that avoid faces and an exposure/colour check with a gentle CDL;
  after rendering, a sheet of the delivered file with black/frozen detection. Bad zooms are downgraded automatically.
- **Several people**: frame whoever is speaking (faces + mouth motion + voice) or split the screen for 2–5+
  participants with complete faces. A producer's choice, never an automatic rule.
- **Multi-source composition**: mosaics (1–5 panels) or hero + support from different videos and photos — several takes
  of one person, interview + photo + B-roll — with one explicit audio master, preview first.
- **Production by genre**: an editorial brief per genre (comedy, music, electronic, interview, cinematic, education,
  product, gaming, vlog); candidate punchlines, reactions and questions; beat grid and phrase-aligned music cuts;
  music videos and visualizers; exact lyrics/script timing; motivated sound effects; music beds ducked under the voice.
- **Producer and specialists**: `plan_production` turns a brief into work orders for composition, audio, color, titles
  and QA specialists; they propose, and only the producer writes to Resolve, serially.
- **Finishing**: color presets (natural/warm/crisp/muted) and LUTs on copies, dialogue enhancement to new WAVs with
  LUFS/true-peak measurement, pre-render checks.
- **Authoring**: projects/backups, bins and metadata, versioned clip/track edits, markers, interchange, CDL/LUT,
  gallery stills, Fusion graphs, silence/scene/sync/loudness, native AI capabilities and QC.
- **Safety**: edits run on new working copies, previews default to `dry_run=true`, render saves first, original media
  is never overwritten. No project/media deletion and no arbitrary Python/Lua execution.

### Tools

| Job | Tools |
|---|---|
| State and planning | forge_status, list_clips, list_styles, list_formats, preview_motion, list_capabilities, audit_timeline, open_resolve_page |
| Editorial | apply_motion, clear_motion, make_platform_version, locate_subject, find_highlights, assemble_timeline |
| Voice, text and delivery | transcribe_timeline, align_text, list_text_styles, preview_text_style, add_captions, add_text_overlay, render_for, render_status |
| Pacing and focus (entertainment) | plan_energized_edit, energize_timeline |
| Self-review (before and after render) | review_shots, review_video |
| Several people (podcast, interview) | plan_speaker_layout, build_speaker_layout |
| Multi-source composition and producer orders | plan_composition, build_composition, plan_production |
| Production by genre | plan_edit, find_story_moments, analyse_music, plan_beat_cuts, assemble_montage, create_music_visualizer |
| Sound | add_music_bed, place_sound_effects, analyse_audio, normalise_audio, sync_audio |
| Projects and media | project_workflow, configure_project, list_media, ingest_media, organise_media, media_metadata |
| Timeline | timeline_versions, edit_clips, timeline_markers, configure_track, export_interchange |
| Color and Fusion | grade_clips, inspect_grade, prepare_lut, gallery_stills, apply_fusion_graph, inspect_fusion |
| Finishing and pre-render checks | preflight_render, apply_grade_preset, enhance_audio |
| Connection recovery | repair_bridge_connection |
| Analysis and native AI | analyse_scenes, native_ai |

Notes:
- `preflight_render` checks sources, enabled tracks, gaps and properties before rendering; a visual review is still required.
- `apply_grade_preset` previews by default and applies CDL on a copy. `enhance_audio` writes a new WAV (gentle filter,
  compression, limiter) and measures LUFS/true peak; it does not separate voices or replace final-mix normalisation.
- Speaker detection uses mouth motion + audio energy: candidates, not diarization. Review the switches.
- `build_composition` requires `reviewed=true` after looking at the `plan_composition` sheet and preview.
- `repair_bridge_connection` (Windows) only retires an orphaned bridge helper whose identity, port and dead parent were verified.

### Roles and skills

| Role (`.agents/agents/`) | Job |
|---|---|
| `video-director` | Producer: brief, references, delegation, serial execution, final QA |
| `vertical-editor` / `horizontal-editor` | End-to-end editors for 9:16–4:5 and 16:9 |
| `composition-editor`, `audio-editor`, `colorist`, `titles-editor`, `qa-editor` | Specialists that analyse and propose to the producer |

Skills (`.agents/skills/`): `davinci-resolve-mcp`, `editorial-direction`, `entertainment-pacing`, `vertical-video`,
`horizontal-video`, `dynamic-zoom-talking-head`, `captions-and-titles`, `color-audio-finishing`, `video-qa`, `resolve-delivery`.

### Example requests

- "Make a Reels version with movement and nice captions in my brand colour."
- "It's stand-up: find the punchlines and build a TikTok without cutting the pauses or the laughs."
- "Make a music video for my electronic track with cuts on the beat, faster on the drop, and the exact lyrics."
- "Two people in a horizontal podcast → a Reel that follows whoever is speaking."
- "Combine the interview with these photos like this reference: interview on top, photo below."
- "Put background music under the podcast voice and a whoosh at each topic change."

### Structure

- `mcp/resolve-forge/src/resolve_forge/domain`: pure rules (framing, cuts, pacing, composition, ducking, alignment, text design).
- `analysis` and `services`: signals and use cases, one per responsibility.
- `gateway`, `native_paths`, `bridge`: connection and our own protocol (HMAC, anti-replay, explicit method list).
- `tools.py`, `authoring_tools.py`, `production_tools.py`, `qa_tools.py`, `producer_tools.py`, `composition_tools.py`:
  thin MCP schemas over the same serial executor.
- `config/mcp.servers.json` → `python scripts/sync.py`: one server in every client.
- `.agents/skills` and `.agents/agents`: canonical skills and roles.
- `config/provenance.json`: studied commits. `docs/api-behavior.md`: verified API pitfalls.

### Verification

```powershell
cd mcp/resolve-forge
uv run pytest -q          # no Resolve needed
uv run pytest -m live     # Resolve open + bridge running; preserves its scratch projects
uv run resolve-forge-doctor
```

The live suite keeps its projects and synthetic files for inspection and reopens your project at the end.

[First steps](docs/FIRST-STEPS.md) · [Install](docs/install.md) · [Architecture](docs/architecture.md) ·
[Editing playbook](docs/editing-playbook.md) · [Migration status](docs/third-party-migration.md)

## Español

Edita video en DaVinci Resolve hablando con un agente que trabaja como productor y editor profesional. Un solo MCP
propio (**resolve-forge**, **65 herramientas**), bridge propio para Free, roles y skills portables. Las skills y los roles
están en inglés para que sirvan a cualquier usuario, pero el agente te responde en español.

1. Ejecuta `scripts/bootstrap.ps1` y abre Resolve con un proyecto.
2. Free 21.0.x: Workspace → Scripts → resolve_bridge (cada vez que abres Resolve). Studio: External scripting using = Local.
3. Abre tu agente en esta carpeta y pide `forge_status`.
4. Pide como a un editor: el agente propone mejoras, revisa los momentos que detectan las tools y trabaja sobre copias.

Ejemplos: "Haz una versión Reels con movimiento y subtítulos bonitos con mi color de marca", "Es un stand-up:
encuentra los remates y arma un TikTok sin cortar las pausas", "Del podcast horizontal haz un Reel que siga a quien habla",
"Combina la entrevista con estas fotos como en esta referencia". Guía completa en [Primeros pasos](docs/FIRST-STEPS.md).
