# resolve-forge architecture

```
tools.py ──► services/ ──► domain/          (pure: no Resolve, 100 % testable)
 (thin MCP)    │  motion_service   easing · keyframes · motion · styles · framing · formats
               │  format_service
               │  render_service
               │  appliers ─────► Strategy: EditKeyframeApplier | FusionTransformApplier
               │  subject  ─────► analysis/faces (optional opencv)
               ▼
            gateway.py ──► DirectTransport (DaVinciResolveScript) | BridgeTransport (our own bridge/, Free)
server.py = composition root (creates the Session, registers tools)
```

### Modules added while studying the other MCPs

```
errors.py                      ForgeError(code, hint) + payload(): error contract for tools and resources
resources.py                   resolve://status, resolve://timeline, forge://formats, forge://styles (Resolve thread)
domain/transcript.py           pure: map_clip (source→timeline), sentences, caption_chunks, emphasis_hits, cut_points
analysis/media.py              audio via PyAV (no ffmpeg binary)
analysis/transcribe.py         WhisperTranscriber: runs in a child process and caches per file
analysis/whisper_worker.py     the child process: faster-whisper, GPU (large-v3-turbo) → CPU (small)
analysis/highlights.py         motion per second (cv2) + pure rank() of windows
graphics/cards.py              full-frame PNG cards: styles, balanced wrap, emoji, safe zone
services/transcript_service    each clip's words re-timed to the timeline
services/overlay_service       cards → PNG sequences (hardlinks) → new track, frame-exact
services/captions_service      transcript → chunks → overlay_service
services/assembly_service      cut list → new timeline (optionally at platform resolution)
services/highlight_service     clip → highlight windows
services/media_lookup          media pool clip by name or path (imports when needed)
```

### Our own authoring and transport

```
authoring_tools.py / production_tools.py   MCP schemas for project, media, timeline, color, audio, Fusion, QC and montage
domain/edit_decisions, editorial, fusion_graph, lut, text_design   pure rules (cuts, DAG, .cube tables, typography)
services/native.py             capabilities, native refusals, readback and timeline copies
bridge/                        HMAC protocol + anti-replay, explicit method list, client and ops inside Resolve
bridge_install/                installs our bridge in Workspace → Scripts (keeps token and roots)
native_paths.py                SDK paths per operating system
production_tools.py            align_text, place_sound_effects, add_music_bed, plan_edit, find_story_moments, analyse_music, plan_beat_cuts, assemble_montage, create_music_visualizer
analysis/action.py             motion energy and its centroid per window (where the action is), no Resolve
domain/energize.py             short shots, alternating framing (wide/medium/close/crash), pivot that centres the subject
services/energize_service      plan from the source and a new timeline with per-shot motion (focus_hold/crash_zoom)
domain/framing_review.py       what stays visible at each zoom; subject at the edge, cropped action, cut face, blurry zoom
domain/look.py, text_placement.py   exposure/contrast/saturation/cast with a gentle CDL; text that avoids faces
services/review_service        review sheets before (shots with the real crop) and after render (black/frozen)
analysis/presence.py, speakers.py   faces (frontal/profile), bodies, who speaks (mouth + voice)
domain/layouts.py              single / split (2 stacked or side by side, 3 = 2+1, 4 = 2x2, 5+) / wide; per-panel crops
services/speaker_layout_service    composes the layout with ffmpeg into a new clip (original audio) and a new timeline
domain/composition.py          multi-source panels (mosaic 1–5, hero + support), independent source starts, explicit audio master
services/composition_service   preview + contact sheet, then a new composed asset (and optional timeline) with ffmpeg
domain/production.py           producer work orders: specialists, dependencies, allowed tools, acceptance, serial writer
domain/preflight, grade_presets, audio_presets   pre-render checks; natural/warm/crisp/muted CDL; dialogue/podcast/entertainment chains
services/preflight_service, grade_preset_service, audio_enhance_service, bridge_recovery_service
qa_tools.py / producer_tools.py / composition_tools.py   thin MCP schemas for finishing, production orders and composition
domain/sound_design            SFX with a mandatory reason, reviewed density, non-overlapping lanes
services/sfx_service           gain baked into a new WAV (ffmpeg) and new audio tracks on a copy
domain/ducking                 voice regions → gain curve (attack, release, fades)
services/music_bed_service     48 kHz stereo music with baked ducking, on a new track of a copy
domain/alignment               known text (lyrics/script) aligned to recognised timings
domain/story_moments, beat_cuts   punchline/reaction/question/stress candidates; cut slots on beat phrases
services/story_service, music_service   transcript + source energy; rhythm analysis, beat cuts, visualizer
```

Selection and provenance details: [third-party-migration.md](third-party-migration.md).

Why PNG sequences for text? The API cannot trim titles or stills (a still always lasts 5 s and
ignores `endFrame`), but a sequence of N images comes in as a clip of exactly N frames with alpha.
The frames are hardlinks to a single PNG, so they take almost no disk space.

## Principles applied

- **SRP**: each module has one reason to change. Framing maths (`framing`) knows nothing about MCP; tools know nothing about keyframes.
- **OCP**: new styles with `@style(...)`; new backends in `APPLIERS`. Existing code is not edited.
- **LSP / ISP**: `Applier` is a minimal `Protocol` (`apply`, `clear`). Any backend that satisfies it is interchangeable.
- **DIP**: services depend on `Session`, not the native module. Tests inject fakes.
- **DRY**: a single definition of each easing curve, from which Resolve interpolation, Fusion handles and baked samples derive. A single MCP config source (`config/mcp.servers.json`). A single copy of skills and agents (`.agents/`, with links).
- **KISS**: 65 use-case tools (editorial intent + authoring of project, media, color, audio,
  Fusion and QC). No 1:1 API wrappers and no arbitrary code execution.

## Motion model

`MotionPlan = tracks (zoom multiplier, angle in degrees) + anchor (face, normalised)`.

- **keyframes** (preferred, Resolve 20+): `ZoomX/ZoomY/Pan/Tilt/RotationAngle` in the Inspector, with `SetKeyframeInterpolation`.
  For each zoom keyframe Pan/Tilt is recomputed with `rezoom_keeping`, so the face stays fixed on screen while the zoom "moves in".
  If Resolve accepts only part of the keys, the partial animation is cleared and the Fusion backend is used.
- **fusion** (universal fallback): `MediaIn → Transform(ForgeMotion) → MediaOut`, with `Pivot` on the face and `BezierSpline` on Size/Angle.
  The curve is written sampled every 2 frames with `SetInput` (bridge-compatible in Free). Values are written
  outside `comp.Lock()`, because inside it the render ignores them. Comps with foreign effects are refused, never rebuilt.
- Hard steps (punch-in) are modelled as `HOLD` and each backend translates them into two keys one frame apart.

## Coordinates

- Subject points: normalised with a top-left origin (like an image).
- Inspector: Pan (+ right) and Tilt (+ up) in timeline pixels; zoom multiplies the "fit" size.
- Fusion: bottom-left origin (`y_fusion = 1 - y`). Times are offset by `COMPN_RenderStart`.

## Windows robustness (learned in live tests)

macOS and Linux share the same code paths; OS differences (SDK, Scripts folders, process name) live only in
`native_paths.py`.

- **Native probe in a subprocess**: `fusionscript.dll` segfaults inside a venv if `PYTHONHOME` does not point to the
  base Python, and Free rejects external scripting. `gateway.direct_scripting_available()` probes it in a child
  process, so a native crash never takes down the MCP server. It then falls back to the bridge.
- **Preloading opencv/numpy**: loading those DLLs while another thread reads the stdin pipe hangs the process on Windows.
  `server.main()` imports them before opening stdio.
- **Dedicated Resolve thread**: every tool runs on a single worker thread (Resolve calls are serialised) and the stdio
  event loop stays free.
- **Bridge (Free)**: arguments travel as JSON, so the Fusion backend only uses `SetInput` with simple values
  (curves sampled every 2 frames) and points are tried in several encodings, verified with `GetInput`.
- Subprocesses with `stdin=DEVNULL`: they do not inherit the protocol pipe.
