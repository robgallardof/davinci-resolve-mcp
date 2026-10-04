---
name: davinci-resolve-mcp
description: "Operate DaVinci Resolve (Free or Studio) from an agent via MCP (resolve-forge). Use it before any task that touches Resolve — connecting, project/timeline, media, editing, color, Fusion, render — to pick the right server and tool, start the bridge in the Free edition and avoid the known API pitfalls. Triggers: davinci, resolve, timeline, render, fusion, media pool, edit page."
---

# Operating DaVinci Resolve with MCP

There is a single server with intent-based editing and API tools:

| Server | What for |
|---|---|
| `resolve-forge` — intent (of 65 tools + 4 resources) | Intent: `apply_motion` (zooms and movement), `make_platform_version` (vertical ↔ horizontal), `transcribe_timeline`, `add_captions`, `add_text_overlay`, `find_highlights`, `assemble_timeline`, `render_for`, `list_formats`, `forge_status` |
| `resolve-forge` — pacing and focus | `plan_energized_edit` (detects action, faces and dead time; plan of short shots with alternating framing) → `energize_timeline` (one clip per shot with its zoom/focus). Skill `entertainment-pacing` |
| `resolve-forge` — self-review | `review_shots` (before building: real crops, faces, text, color) and `review_video` (after rendering). Looking at the sheet is mandatory |
| `resolve-forge` — several people | `plan_speaker_layout` / `build_speaker_layout`: frames whoever speaks and splits the screen when several speak (only if the user wants it) |
| `resolve-forge` — multi-source composition | `plan_composition` / `build_composition`: mosaic or hero + support from different videos/photos with one explicit audio master; `plan_production`: work orders for the specialists |
| `resolve-forge` — production | Direction by genre and music (skill `editorial-direction`): `plan_edit`, `find_story_moments`, `analyse_music`, `plan_beat_cuts`, `assemble_montage`, `create_music_visualizer`, `align_text` (exact lyrics/script), `place_sound_effects` (motivated SFX), `add_music_bed` (music under the voice with ducking); text design: `list_text_styles`, `preview_text_style` |
| `resolve-forge` — authoring | Projects/backups, bins/media, markers/QC, tracks/versions, CDL/LUT, Fusion DAG, audio/scenes/loudness, capabilities |

## Startup (always)

1. `forge_status` returns `edition` (Free/Studio), `transport` (`bridge` or `direct`), version, timeline, fps, resolution and `native_keyframes`.
2. If it fails with "Cannot reach DaVinci Resolve":
   - Resolve must be open **with a project** (the Project Manager has no Workspace menu).
   - **Free**: Workspace → Scripts → `resolve_bridge`. Repeat it **every time you open Resolve**.
   - **Studio**: Preferences → System → General → External scripting using = **Local** (or use the bridge as in Free).
   - Full diagnosis: `cd mcp/resolve-forge && uv run resolve-forge-doctor`.
3. `list_clips` before mutating anything.

If after restarting Resolve the bridge keeps the port and does not respond: `repair_bridge_connection()`
inspects orphaned helpers on Windows. Only with a verified candidate use `dry_run=false`; then launch
Workspace → Scripts → resolve_bridge again in the current Resolve. It never stops Resolve or a bridge whose parent is alive.
Forge tries an available bridge first; if it is busy it avoids also launching a native SDK probe.

## Free vs Studio

| | Free (bridge) | Studio |
|---|---|---|
| Motion | `fusion` backend (automatic; native keyframes are not exposed in 21.0.4) | Native `keyframes` when available; otherwise `fusion` |
| Reframe | Framing by face/point | Plus `smart_reframe=true` |
| Codecs | H.264 (H.265 falls back to H.264) | H.264/H.265 |
| Render | Only inside `~/Movies` (bridge roots) | Any folder |
| Captions | `add_captions` (local Whisper, burned into the video) | `add_captions`, or Studio's Create Subtitles from Audio |

## Errors: decide by `code`

Every forge error carries a `code` and almost always a `hint`. Do not interpret the text: use the code.

| code | What to do |
|---|---|
| `RESOLVE_UNREACHABLE` | Ask to open Resolve with a project (Free: start `resolve_bridge`) and retry |
| `RESOLVE_BUSY` | Stop playback, wait for render/close dialogs and retry; if still blocked restart the bridge. Never blindly repeat a write |
| `NO_PROJECT` / `NO_TIMELINE` | Open or create a project or timeline (`assemble_timeline` creates one) |
| `CLIP_NOT_FOUND` / `EMPTY_TRACK` | Re-read with `list_clips` (indices start at 1) |
| `INVALID_ARGUMENT` | Fix the argument (style, format, anchor, ranges) |
| `TIMELINE_EXISTS` | Use another `name` |
| `MISSING_DEPENDENCY` | Run the `hint` (`uv sync --extra speech` or `--extra vision`) |
| `BACKEND_UNSUPPORTED` | Follow the `hint`; e.g. a Fusion comp with foreign effects is preserved, not rebuilt |
| `MEDIA_NOT_FOUND` / `RESOLVE_REFUSED` / `RENDER_REFUSED` | Follow the `hint` (Free: paths inside the user profile and `~/Movies`) |

To read state without tools: resources `resolve://status`, `resolve://timeline`, `forge://formats`, `forge://styles`.

## Safety rules

- Do not mutate the master: `make_platform_version` duplicates. For experiments, duplicate the timeline first.
- `apply_motion` is idempotent (it replaces its own animation) and `clear_motion` removes it.
- Save the project before rendering. Never delete media or projects without an explicit request.

## Verified API pitfalls

- `DuplicateTimeline` silently switches the current timeline to the copy.
- `DeleteClips` only works on the Edit page and does not delete linked audio.
- `AppendToTimeline`: `endFrame` is exclusive and `recordFrame` is absolute (timelines usually start at 86400).
- `SetRenderSettings` inherits the loaded preset; an empty `CustomName` invalidates everything.
- Fusion: values written inside `comp.Lock()` are ignored at render.
- Bridge (Free): everything travels as JSON (numeric dict keys arrive as strings) and there is no `tool["X"]` indexing. Use methods.
- Media and import in Free: only from paths inside the bridge roots (user profile; `AppData\Temp` is rejected).
- More quirks, with evidence: `docs/api-behavior.md`.

## Which skill next

- Audio, color, presets and LUTs → `color-audio-finishing`: `enhance_audio`, `apply_grade_preset` and `preflight_render`.
- Vertical (TikTok, Reels, FB Reels, Shorts, Stories, Snapchat, 4:5) → `vertical-video`
- Horizontal (YouTube, Facebook, LinkedIn, X, web) → `horizontal-video`
- Zooms and movement → `dynamic-zoom-talking-head`
- Captions, titles and lyrics → `captions-and-titles`
- Pacing for entertainment → `entertainment-pacing`; genre direction → `editorial-direction`; QA → `video-qa`
- Export → `resolve-delivery`
- Without MCP (direct scripts) → `references/api-cheatsheet.md`
