---
name: dynamic-zoom-talking-head
description: "Bring talking-head shots to life (vertical or horizontal) — talking head, podcast, interview, vlog — so they do not look static: punch-ins, jump zooms, a warm slow push, emphasis bumps, handheld — in DaVinci Resolve via resolve-forge. Use it when asked for zoom, movement, dynamism, 'don't let it look boring/static', retention, or editing a talking head in horizontal or vertical."
---

> If it is not a person talking to camera (pets, action, vlog with movement), use the
> `entertainment-pacing` skill: `plan_energized_edit` detects where the action is and focuses there.

# Dynamic zoom for talking heads

Goal: change the framing every few seconds **with intent** (on sentences, ideas, key words), not at random,
and without the viewer noticing an "effect". The face rules: every zoom is anchored to the face.

## Recipe (MCP)

1. `forge_status` → check `native_keyframes`. If true, Inspector keyframes are used, editable by hand. In Free the `fusion` backend is used (a `ForgeMotion` node on the clip's Fusion page); it is automatic and verified at render.
2. `list_clips` → indices and durations.
3. Decide **where** shots change (better than automatic rhythm):
   - With voice: `transcribe_timeline()` returns `cuts_s` (sentence starts) and `hits_s` (numbers, exclamations,
     punchlines) already in timeline seconds. Pass them as-is, or trim them with judgement. It uses local Whisper and works in Free.
   - Without a transcript: omit `cuts_s` and the style generates an irregular rhythm (2.5–3.5 s vertical, 6–9 s horizontal).
4. `preview_motion` with the chosen style → check `peak_zoom` and the timings.
5. `apply_motion(style, cuts_s, hits_s, anchor="face", intensity)`.
6. QC (below). Adjust `intensity` or the style and run `apply_motion` again (it replaces its previous animation).

## Choosing a style

| Situation | Style | intensity |
|---|---|---|
| Energetic vertical (TikTok, Reels, Shorts, FB Reels) | `tiktok_punch` (hard cuts 1.00↔1.15) | 1.0–1.3 |
| Educational or calm vertical, Stories | `tiktok_smooth` (zoom with a 6-frame ease) | 0.8–1.0 |
| Horizontal talking head (YouTube, Facebook, LinkedIn, web) | `youtube_dynamic` (subtle push + punch every 6–9 s) | 0.8–1.0 |
| Documentary, testimonial, emotional, "warm" | `warm_push` (continuous 1.00→1.08) | 0.6–1.0 |
| Ending / reflection | `warm_pull` | 0.6–1.0 |
| Stressing words | `emphasis` with `hits_s` | 1.0 |
| Very rigid tripod | `handheld` (±0.4°) or `vlog_mix` | 0.5–1.0 |

Craft rules:
- Alternate levels (wide ↔ tight). Two punch-ins in a row at the same level go unnoticed.
- Never punch in mid-word: put it at the start of the sentence or idea.
- Shots constantly under 1–1.5 s are tiring. The healthy range is 2–4 s vertical and 3–7 s horizontal.
- With 1080p footage on a 1080p timeline, do not exceed ×1.20 (loss of sharpness). 4K on a 1080p timeline gives headroom up to ×2.
- In a vertical reframed from 16:9 you are already using a coverage zoom (~×3.16). Punch-ins add on top: use `intensity` ≤ 1.
- B-roll, text and graphics also count as a "shot change". Do not stack a zoom on top of each.

## QC before delivery

- Play the first 5 s: the hook must have a visual change before 2 s.
- The face never leaves the safe area (see `list_formats` → `safe_rect_px`).
- No black borders on rotations (`handheld` already adds the safety zoom).
- The tight level never cuts the forehead or the chin.

## Manual fallback in Resolve (no MCP)

- **Dynamic Zoom**: Inspector → Dynamic Zoom → ON, adjust the start/end rectangles in the viewer (Dynamic Zoom mode), Ease: In and Out.
- **Inspector keyframes**: Zoom + Position with keyframe diamonds; right-click the curve → Ease In/Out.
- **Fusion**: MediaIn → Transform (Size keyframed, Pivot on the face) → MediaOut. See `../davinci-resolve-mcp/references/api-cheatsheet.md`.

More technique and sources: `docs/editing-playbook.md`.
