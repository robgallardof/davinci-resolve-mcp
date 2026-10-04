# davinci-agents

**[English](#english)** · **[Español](#español)**

## English

Edit DaVinci Resolve by talking to an AI agent that works like a producer and a professional editor. One MCP of our own
(**resolve-forge**, 58 tools), a Free-edition bridge, portable editor roles and skills. Works with Claude Code, Codex,
Cursor, Gemini CLI and VS Code.

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

### What it does

- **Editorial**: motion for talking heads, vertical/horizontal platform versions, highlights, source-range assembly,
  local transcription, designed animated captions (Creator / Studio / Editorial / Impact) and text overlays, delivery.
- **Entertainment pacing**: detects where the action is (pets, hands, jumps), faces and dead time, and rebuilds
  long shots as 1.2–2.8 s shots with alternating wide / x1.25 / x1.5 / crash-zoom framings that pull the subject
  to the centre — the screen never sits still.
- **Self-review**: before building, a contact sheet of what each shot really shows (crop, faces, subject, text
  boxes) with flagged problems, text positions that avoid faces and an exposure/colour check with a gentle CDL;
  after rendering, a sheet of the delivered file with black/frozen detection. Bad zooms are downgraded automatically.
- **Multi-person layouts** (optional, on request): frame whoever is speaking (faces + mouth motion + voice) and
  split the screen when several talk at once — stacked in vertical, side by side in horizontal, 2+1 for three.
- **Production by genre**: an editorial brief per genre (comedy, music, electronic, interview, cinematic, education,
  product, gaming, vlog); candidate punchlines, reactions and questions; beat grid and phrase-aligned music cuts;
  music videos and visualizers; exact lyrics/script timing; motivated sound effects; music beds ducked under the voice.
- **Authoring**: projects/backups, bins and metadata, versioned clip/track edits, markers, interchange, CDL/LUT,
  gallery stills, Fusion graphs, silence/scene/sync/loudness, native AI capabilities and QC.
- **Safety**: edits run on new working copies, previews default to `dry_run=true`, render saves first, original media
  is never overwritten. No project/media deletion and no arbitrary Python/Lua execution.

### Verification

```powershell
cd mcp/resolve-forge
uv run pytest -q          # no Resolve needed
uv run pytest -m live     # Resolve open + bridge running; preserves its scratch projects
uv run resolve-forge-doctor
```

## Español

Edita video en DaVinci Resolve hablando con un agente que trabaja como productor y editor profesional. Un solo MCP
propio (**resolve-forge**, **58 herramientas**), bridge propio para Free, roles `vertical-editor`, `horizontal-editor`
y `video-director`, y skills portables.

Las mejores capacidades de los MCP públicos se reimplementaron a nuestra manera: reglas puras, servicios por
responsabilidad, transporte aislado y tools MCP finas. No se importa ni empaqueta código de otros MCP.
[Selección, mejoras y estado](docs/third-party-migration.md).

### Herramientas

| Trabajo | Herramientas |
|---|---|
| Estado y planificación | forge_status, list_clips, list_styles, list_formats, preview_motion, list_capabilities, audit_timeline, open_resolve_page |
| Edición editorial | apply_motion, clear_motion, make_platform_version, locate_subject, find_highlights, assemble_timeline |
| Voz, texto y entrega | transcribe_timeline, align_text, list_text_styles, preview_text_style, add_captions, add_text_overlay, render_for, render_status |
| Ritmo y enfoque (entretenimiento) | plan_energized_edit, energize_timeline |
| Autorrevisión (antes y después de render) | review_shots, review_video |
| Varias personas (podcast, entrevista) | plan_speaker_layout, build_speaker_layout |
| Producción por género | plan_edit, find_story_moments, analyse_music, plan_beat_cuts, assemble_montage, create_music_visualizer |
| Sonido | add_music_bed, place_sound_effects, analyse_audio, normalise_audio, sync_audio |
| Proyectos y media | project_workflow, configure_project, list_media, ingest_media, organise_media, media_metadata |
| Timeline | timeline_versions, edit_clips, timeline_markers, configure_track, export_interchange |
| Color y Fusion | grade_clips, inspect_grade, prepare_lut, gallery_stills, apply_fusion_graph, inspect_fusion |
| Análisis y AI nativa | analyse_scenes, native_ai |

### Uso

1. Ejecuta `scripts/bootstrap.ps1` y abre Resolve con un proyecto.
2. Free 21.0.x: Workspace → Scripts → resolve_bridge (cada vez que abres Resolve). Studio: External scripting using = Local.
3. Abre tu agente en esta carpeta y pide `forge_status`.
4. Pide como a un editor: el agente propone mejoras, revisa los momentos que detectan las tools y trabaja sobre copias.

Ejemplos:

- "Haz una versión Reels con movimiento y subtítulos bonitos con mi color de marca."
- "Es un stand-up: encuentra los remates y arma un TikTok sin cortar las pausas ni las risas."
- "Haz un videoclip de mi canción electrónica con cortes al beat, más rápidos en el drop, y la letra exacta."
- "Pon música de fondo bajo la voz del podcast y un whoosh en cada cambio de tema."
- "Analiza los silencios y arma una selección nueva conservando respiraciones."
- "Organiza la media por cámara, prepara una LUT al 40 % y exporta OTIO."

### Estructura

- `mcp/resolve-forge/src/resolve_forge/domain`: reglas puras (encuadre, cortes, ritmo, ducking, alineación, diseño de texto).
- `analysis` y `services`: señales y casos de uso, uno por responsabilidad.
- `gateway`, `native_paths`, `bridge`: conexión y protocolo propio (HMAC, antireplay, lista explícita de métodos).
- `tools.py`, `authoring_tools.py`, `production_tools.py`: schemas MCP finos sobre el mismo executor serial.
- `config/mcp.servers.json` → `python scripts/sync.py`: un solo servidor en todos los clientes.
- `.agents/skills` y `.agents/agents`: fuente canónica de skills y roles.
- `config/provenance.json`: commits estudiados. `docs/api-behavior.md`: trampas verificadas de la API.

Pruebas: `uv run pytest` (sin Resolve) y `uv run pytest -m live` (con Resolve y el bridge). La suite live conserva sus
proyectos y archivos sintéticos para inspección y vuelve a abrir tu proyecto al terminar.

[Primeros pasos](docs/FIRST-STEPS.md) · [Instalación](docs/install.md) · [Arquitectura](docs/architecture.md) ·
[Playbook de edición](docs/editing-playbook.md) · [Estado de la migración](docs/third-party-migration.md)
