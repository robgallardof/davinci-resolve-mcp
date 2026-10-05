# Migration: our own tools, built from the competitive analysis

Forge implements 65 tools of its own: editorial editing, production by genre, multi-source composition, sound,
finishing, project authoring, media, timeline, color, Fusion and QC. It neither imports nor packages code from the MCPs studied.

## How far along? (2026-10-04)

**Own implementation complete; the final live verification in Resolve is pending a bridge reconnect. Read the evidence below before assuming coverage.**

| Phase | Status | Evidence |
|---|---|---|
| 1. Study of the 7 public MCPs and selection | ✅ Done | [mcp-landscape.md](mcp-landscape.md), [mcp-reviews.md](mcp-reviews.md), `config/provenance.json` |
| 2. Own reimplementation (project, media, timeline, color, Fusion, audio, QC) | ✅ Done | authoring tools, table below |
| 3. Own Free bridge (HMAC, anti-replay, explicit methods) and installer | ✅ Done, verified on Free 21.0.4.5 | `bridge/`, `bridge_install/`, `test_bridge*.py` |
| 4. Third-party code removed (server, patches, third_party/, reference manager) | ✅ Done | `test_workspace.py`; wheel without external modules |
| 5. Designed, animated text (Creator/Studio/Editorial/Impact, karaoke, preview) | ✅ Code and live captions | `test_designed_captions.py`, `test_live_editing.py` |
| 6. Production by genre (comedy, music, electronic, interview…) | ✅ Code and live montage/align · partial on real footage | `plan_edit`, `find_story_moments`, `plan_beat_cuts`, `assemble_montage`, `create_music_visualizer`, `align_text` |
| 7. Sound (music under the voice with ducking, motivated SFX, dialogue enhancement) | ✅ Live bed/SFX; `enhance_audio` pending in Resolve | `add_music_bed`, `place_sound_effects`, `enhance_audio` |
| 8. Producer + specialists, multi-source composition | ✅ Code and unit tests with real ffmpeg renders | `plan_production`, `plan_composition`, `build_composition`, `.agents/agents/` |
| 9. Docs, skills and roles (English, agent replies in the user's language) | ✅ Done | README (table verified by test), 10 skills, 8 roles |
| 10. Live re-run of the extended version | ⏳ Pending | `tests/live/`; needs the current Resolve bridge |

In numbers: 65 tools, 677 tests without Resolve passing on 2026-10-04. The live suite has 13 cases. First connected
pass: 10 passed and one SFX failure; after the fix, the isolated SFX test passed, as did the vertical framing/zoom pixel
test. A second pass hit an orphaned bridge bound to a previous Resolve: not counted as passed. That helper was retired
after verifying executable, script, port and dead parent.

## What the latest rounds added (2026-10-04)

- Finishing: `preflight_render`, `apply_grade_preset` (natural/warm/crisp/muted CDL with intensity and preview, on a copy),
  `enhance_audio` (dialogue/podcast/entertainment chains to a new WAV with LUFS/true-peak measurement),
  `repair_bridge_connection` (Windows orphaned-helper recovery with verified identity/port/parent and preview).
- Zooms: wide shots really static; focus/crash add no drift above the reviewed zoom. Partial native keyframes are cleared
  before falling back to Fusion; pivots and write refusals are checked. Comps with foreign Fusion effects are refused and
  preserved (`BACKEND_UNSUPPORTED`).
- Cuts: `subject=none` hints remove confirmed empty ranges even with camera movement; `subject=animal|person` keeps
  still subjects. No claim of automatic animal recognition.
- Speakers: layouts for five or more people without truncating to four; complete faces with padding. Mouth + energy
  give candidates, not voice identification or diarization.
- Text: `animation=karaoke`, per-word progress, stable layout, `reduced_motion` respected.
- Multi-source composition (user request: references with several takes, interview + photo + support):
  `plan_composition` / `build_composition` — mosaic 1–5 or hero + support, independent start per source, stills,
  manual `subject`/`crop` and one explicit audio master; preview + sheet before building; `reviewed=true` required.
- Producer orders: `plan_production` generates work orders for composition-editor, audio-editor, colorist,
  titles-editor and qa-editor (dependencies, tools, acceptance, report). Only the producer writes to Resolve.
- QA: `review_video` includes the last frame and reports unreadable samples without aborting.
- Connection: an available bridge is tried first, with no extra native probe while it is busy; timeouts return
  `RESOLVE_BUSY`. A write timeout never authorises a blind retry.
- Live finding: Free 21 returns no Frames for some WAVs. SFX uses the real PCM duration as a fallback.
- Portability: skills, roles, AGENTS.md, README and docs in English; new skill `captions-and-titles`; doctor output in English.

## Architecture

- `domain/`: pure decisions (cuts, graphs, LUTs, text design, story moments, beat cuts, ducking, text alignment,
  composition, production orders, presets); knows nothing about Resolve, MCP or files.
- `analysis/`: decoding and signal extraction; never modifies the project.
- `services/`: one module per responsibility. `native.py` shares capabilities, refusals, readback and copy creation;
  `media_lookup.py` shares unambiguous source selection.
- Thin MCP modules: schemas and delegation. Every Resolve call goes through the same serial executor; FastMCP private
  managers are never touched.
- `gateway.py` and `native_paths.py`: transport and SDK selection per OS; isolated native probe.
- `bridge/`: protocol, authentication and proxy separated from call policy. Standard runtime without native libraries.
  The method list is explicit; there is no execute_python/execute_lua or arbitrary-call tool.
- `bridge_install/`: installs our modules and launcher, keeps token and roots. It downloads no other server.

Session and native objects are injected dependencies; the same tools work with direct or JSON fakes and with real
Resolve. No whole server is adapted through monkey-patching.

## Selection and improvements

| Capability studied | Own implementation and improvement |
|---|---|
| Project and backup (apvlv/DWC/hitesh) | project_workflow, configure_project: new backups, save first, file check and readback |
| Bins, import and metadata (DWC/hitesh) | list_media, ingest_media, organise_media, media_metadata: path dedup, ambiguous names refused, current bin restored |
| Timeline and tracks (DWC/hitesh) | timeline_versions, edit_clips, configure_track: previews by default, versions never overwritten, edits on copies with readback |
| Markers and QC (DWC/hitesh/samuelgursky) | timeline_markers, audit_timeline: relative seconds, range checks, existing markers preserved, gaps/overlaps and source visibility |
| Interchange | export_interchange: OTIO/FCPXML/AAF/EDL/DRT through observed constants, save first, new target and file check |
| Color and LUT (DWC/hitesh/samuelgursky) | grade_clips, inspect_grade, prepare_lut, gallery_stills, apply_grade_preset: validated CDL, copies, finite complete .cube tables, blend with identity, originals preserved |
| Fusion (apvlv/lordhoell) | apply_fusion_graph, inspect_fusion: validated DAG, own ids, bounded palette, no duplicate connections; values outside Lock so they survive render |
| Audio and analysis | analyse_audio, analyse_scenes, normalise_audio, sync_audio, enhance_audio: cuts with breathing margin, explicit source times, scene histograms, two-pass loudness and final-WAV measurement; ffmpeg ships with Forge |
| Native AI (DWC/hitesh) | native_ai: observed capabilities; subtitles/scene cuts on copies, real refusal on unsupported editions; local Free alternatives |
| Capabilities/resources/architecture (kerwilgil/DWC) | list_capabilities, resources, services per responsibility, typed errors and swappable transports |
| Transcription and captions (hiteshK03/samuelgursky) | transcribe_timeline, align_text, add_captions, list_text_styles, preview_text_style: timeline timing per clip, exact script/lyrics, animated designs with active word and preview before burning |
| Beats and silences (samuelgursky) | analyse_music, plan_beat_cuts, assemble_montage, create_music_visualizer: grid with confidence, phrase cuts and faster only in confirmed ranges, continuous music master, stereo visualizer |
| Moments and direction (no equivalent) | plan_edit, find_story_moments: judgement by genre and candidates with evidence that the agent confirms |
| Mix (no equivalent) | add_music_bed, place_sound_effects: ducking from the transcript and SFX with a mandatory reason, baked into new WAVs on copies |
| Composition and production (no equivalent) | plan_composition, build_composition, plan_production, speaker layouts: producer-chosen layouts, explicit audio master, serial writer |
| Compatibility and safety | MCP<2, cross-platform paths, cp1252 console, isolated probe, HMAC, expiry, anti-replay, file roots and request limit; no arbitrary execution |

Not included: hundreds of getter wrappers, database/cloud management, project/media destruction, code execution or
other repos' installers/updaters. This selection covers the useful editing flows and makes the limits explicit.

## Verification and limits

Contracts are tested in four configurations (Free/Studio, bridge/direct, keyframes present/absent): master isolation,
native refusals, relative markers, dedup, ambiguity, DAG, authentication/replay, synthetic audio/scenes, final-file
loudness and real ffmpeg composition renders checked by pixel colour and audio frequency. Connection and reads are
verified on Resolve Free 21.0.4.5 with our bridge. Historical evidence in real Resolve: render with pixel comparison,
motion/clear, vertical format, captions, markers, CDL and Fusion graphs; it does not mean the live suite was re-run in
this revision.

A method being available does not guarantee the edition/licence accepts it: the return value is checked. CDL can only
be verified by native acceptance and visual review. Onsets are energy candidates, not a tempo/downbeat model.
No universal coverage of every Resolve API is claimed.

## Cleanup

The second server, patches, config/references.json and scripts/references.py were removed. Studied commits are kept in
config/provenance.json. The 154 files in third_party/ were removed from Git and disk. By the user's decision, vendor/ and
the leftovers in resolve_forge/api/ stay local and ignored by Git; they are not imported or packaged.

## Status for the next agent (Claude, Codex…)

Read this before continuing. Last update: 2026-10-04. Reply to the user in Spanish (their language).

### Done
- Forge of our own (65 tools), own bridge, no third-party code or servers; 677 tests without Resolve passing.
- Designed text: `creator`, `studio`, `editorial`, `impact` styles with active word, brand accent, `fade/lift/pop/karaoke`,
  `reduced_motion`, PNG/WebP preview. Legacy `box/outline/yellow/dark` only on request.
- Production by genre: `plan_edit`, `find_story_moments`, `analyse_music`, `plan_beat_cuts`, `assemble_montage`,
  `create_music_visualizer`, `align_text`, `place_sound_effects`, `add_music_bed`.
- Entertainment pacing: `plan_energized_edit` / `energize_timeline`, `cut_dull`, `subject` hints; skill `entertainment-pacing`.
- Self-review: `review_shots` (before) and `review_video` (after) produce sheets the agent must look at; skill `video-qa`.
- Several people: `plan_speaker_layout` / `build_speaker_layout` (active speaker, split for 2–5+).
- Multi-source composition and producer orders: `plan_composition`, `build_composition`, `plan_production`;
  specialist roles in `.agents/agents/` and `editorial-direction/references/producer-coordination.md`.
- Finishing: `preflight_render`, `apply_grade_preset`, `enhance_audio`, `repair_bridge_connection`; skill `color-audio-finishing`.
- Everything portable is in English; new skill `captions-and-titles`.
- Windows, macOS and Linux: OS differences only in `native_paths.py` (SDK, Scripts folders, process name);
  installer, doctor and `pgrep -x` process check use it; macOS/Linux font folders; `scripts/bootstrap.sh`.
  `test_cross_platform.py` simulates each OS end to end; GitHub Actions runs the suite on all three.

### Pending (by priority)
1. **Live verification**: `uv run pytest -m live` with Resolve open and the bridge started (Free: Workspace → Scripts →
   resolve_bridge). Karaoke, side framing, the new preset and `enhance_audio` on a real script are still pending.
   Also: `find_story_moments` on real comedy footage, layouts on real multi-person footage and
   `build_composition(into_resolve=true)` with the user's references (collage of takes, interview + photo).
2. **Fusion motion on comps with existing effects**: refused today; inserting ForgeMotion without breaking the graph is pending.
3. **Lyrics over a full mix**: `align_text(focus_vocals=true)` helps but does not separate stems. Real separation
   (Demucs/torch) was not added: heavy dependency, needs user confirmation.
4. **Mix**: SFX gain and ducking are baked into new WAVs (no verified per-clip volume API). If Resolve exposes verifiable
   audio volume/keyframes, migrate so it stays editable in Fairlight.
5. **macOS/Linux with a real Resolve**: offline suite runs in CI on the three OSes; Resolve itself was only simulated. Run `sh scripts/bootstrap.sh`,
   `uv run resolve-forge-doctor` and `uv run pytest -m live` on a Mac and a Linux box; check whether `fusionscript.so`
   needs `PYTHONHOME` inside the venv like Windows does, and whether the Free bridge works in the Mac App Store build.
6. Local leftovers ignored by Git (`vendor/`, `mcp/resolve-forge/src/resolve_forge/api/`): delete only if the user asks.

Verified outside Resolve with real audio and real Whisper: `align_text` (100 % of words) and `find_story_moments`
(punchline after a 2.2 s pause and a question detected in a TTS joke).

### Rules the user set
- Nothing copied from competitors: improved ideas, our way (SRP/SOLID/DRY, domain → services → tools).
- Tools measure; editorial judgement (joke, drop, emotion) is confirmed by the agent watching/listening.
- The agent acts as a producer: proposes improvements to the idea and edits by genre, nothing robotic.
- Entertainment first: the screen keeps changing, zooms on the action, animated text; empty footage is cut.
- Layouts with several people/sources are the producer's choice, guided by the user's references, not fixed rules.
- When adding a tool: README table, counts (test), matching skill and this section.
- Edits on copies; the master is never touched.
- Skills/roles/docs in English for other users; the agent always answers in the user's language.
