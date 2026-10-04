---
name: vertical-video
description: "Edit vertical video (9:16 and 4:5) for any platform — TikTok, Instagram Reels, Facebook Reels, YouTube Shorts, Stories, Snapchat, 4:5 feed — in DaVinci Resolve: reframing from 16:9, hook, pacing, dynamic zooms, captions, safe zones and export. Use it when asked for vertical, 9:16, 4:5, reels, shorts, tiktok, stories, short clips or converting horizontal to vertical."
---

# Vertical video (9:16 / 4:5)

One way of working for every vertical platform. What changes per platform (safe zone,
maximum duration, loudness) comes from `list_formats(orientation="vertical")`. The full table is in
`../resolve-delivery/references/platforms.md`.

## Flow

1. **State**: `forge_status` and `list_clips`.
   Long unedited clip (e.g. a several-minute phone video): `find_highlights(source)` to
   see the best moments and `assemble_timeline(source, cuts=[[start, end], ...], name, format="reels")` to
   build the cut directly in 9:16. If you do this, skip step 2.
2. **Format**. If the source is 16:9: `make_platform_version(format=<platform>, subject="face")`.
   It creates a copy with the face centred and leaves the master untouched.
   - Several 9:16 platforms share a resolution: a single `reels` version serves TikTok, Shorts and FB Reels.
     Only the safe zone changes, so design for the most restrictive (TikTok bottom/right, Reels bottom).
   - `feed_4x5` for the Instagram/Facebook feed: less cropping, more context.
   - Two people: `center_bias` 0.6–0.8, or per clip with `subject=[x, y]`.
   - Studio: `smart_reframe=true`.
3. **Editorial cut** (with `resolve-forge`): remove silences, filler words and retakes.
   With genre intent (comedy, music, interview…), follow the `editorial-direction` skill:
   `find_story_moments` / `analyse_music` → you review → `plan_edit` → cut.
   Duration: 15–35 s is safest; 30–60 s if the idea needs it. Respect the format's `max_seconds`.
4. **Hook (0–3 s)**: the first line is the promise or the conflict. First visual change before 2 s.
5. **Pacing and focus** (skill `entertainment-pacing`): for phone footage, pets, vlogs or challenges,
   `plan_energized_edit` → `energize_timeline` replaces long shots with 1.2–2.8 s shots with zooms
   on the action. For a person talking to camera, continue with step 6.
6. **Movement** (skill `dynamic-zoom-talking-head`): `transcribe_timeline()` then
   `apply_motion("tiktok_punch" | "tiktok_smooth" | "vlog_mix", cuts_s=<cuts_s>, hits_s=<hits_s>)`.
   The `tiktok_*` styles work for any vertical; the name describes the pace, not the platform.
7. **Text** (most views are muted):
   - Design: `list_text_styles` and `preview_text_style(text, style, 1080, 1920)` before burning.
   - With voice: `add_captions(style="auto" | "creator" | "impact", accent="#RRGGBB")`. Active word highlighted,
     short entrance, inside the strictest safe zone. Works in Free.
     Exact text: `align_text(source, text=<script>)` or correct `transcribe_timeline(include_words=true)`; pass `words=`.
   - No voice (visual or music vlog): tell the story with `add_text_overlay(text, start_s, duration_s,
     style="creator", position="top")`, e.g. "POV: …" in the hook and a twist mid-video.
     Emoji allowed. `impact` only for punchlines or 1–4 word messages.
8. **Pattern interrupts** where the story changes (new idea, punchline, proof), typically every 2–4 s:
   punch-in, B-roll, text, SFX. Vary the type and never cut a comic pause or a moment that breathes.
9. **Audio**: music under the voice with `add_music_bed(music_source)` (automatic ducking); SFX only on
   confirmed moments with `place_sound_effects`.
10. **Loop**: make the ending connect to the start when possible.
11. **Delivery** (skill `resolve-delivery`): `render_for(format=<platform>)`, one per destination if specs differ.

## Base specs

1080×1920 (4:5: 1080×1350), 30 fps (or the footage fps), H.264 High 10–14 Mbps, AAC 48 kHz.
Loudness −12 to −14 LUFS, −1 dBTP. Shorts plays at 1080p at most.

## Checklist

- [ ] Timeline resolution = format (`forge_status`)
- [ ] Face and text inside the safe zone of the most restrictive platform
- [ ] Hook in 0–3 s, visual change before 2 s and never more than ~3 s without an on-screen change
- [ ] Pacing per genre (punchlines and reactions intact) and complete, corrected captions
- [ ] Render complete (`render_status`) and file verified
