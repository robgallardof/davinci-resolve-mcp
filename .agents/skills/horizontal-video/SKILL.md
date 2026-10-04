---
name: horizontal-video
description: "Edit horizontal 16:9 video for any destination — YouTube, Facebook, LinkedIn, X, web/Vimeo, courses, video podcasts, interviews, presentations — in DaVinci Resolve with pacing that retains: punch-ins, B-roll, jump cuts, chapters, captions and 1080p/4K export. Use it when asked for horizontal, 16:9, landscape, YouTube, long-form, podcast, course, webinar or converting a vertical into horizontal."
---

# Horizontal video (16:9)

One method for every 16:9 destination. Per-platform specs come from
`list_formats(orientation="horizontal")`; the full table is in `../resolve-delivery/references/platforms.md`.

## Flow

1. **State**: `forge_status` and `list_clips`.
2. **Format**. If the source is vertical: `make_platform_version(format="youtube_1080" | "facebook_1080" | ...)`.
   The clip is scaled to fill 16:9 around the subject. If cropping that much ruins the shot, use a
   blurred background (Fusion or `resolve-forge`) with the vertical on top.
3. **Assembly** (with `resolve-forge`): order takes, remove retakes and silences, and mark chapters with markers.
   Depending on the genre (podcast, comedy, music video, film), apply the `editorial-direction` skill (`plan_edit`).
4. **Pacing**: a visual change every **3–7 s**. From most to least valuable: B-roll that *shows* what is said,
   graphic or text, punch-in, camera change.
5. **Movement** (skill `dynamic-zoom-talking-head`):
   - First `transcribe_timeline()`: it gives you `cuts_s` (sentence starts) and `hits_s` (data and punchlines) in timeline seconds.
   - Talking head: `apply_motion("youtube_dynamic", cuts_s=<cuts_s>)`. Despite the name, it works for any 16:9.
   - Emotional moments or testimonials: `warm_push` with intensity 0.6–0.8. Endings: `warm_pull`.
   - Data and punchlines: `emphasis` with `hits_s`.
   - Multicam: the cut between cameras is already the change. Use a gentle `warm_push` on the wide shot.
6. **Hook per destination**:
   - YouTube / web: the title's promise in 5–10 s, plus a preview of the best moment.
   - Facebook / LinkedIn / X: muted autoplay, so the message must work with captions
     in the first 3 s: `add_captions(style="studio", position="bottom")` (or `auto`; check first with `preview_text_style`).
     Also consider a `square` or `feed_4x5` version.
   - Titles, names or lower thirds: `add_text_overlay(..., style="studio" | "editorial", position="bottom")`.
7. **Audio**: Voice Isolation; music under the voice with `add_music_bed(music_source)` (ducking from the transcript,
   preview first); −14 LUFS and −1 dBTP.
8. **YouTube**: keep the last 20 s free for the end screen; chapters come from the markers.
9. **Delivery** (skill `resolve-delivery`): `render_for(format=...)`.

## Common mistakes

- Punch-in after punch-in with no B-roll: feels like a "stretched TikTok". Alternate.
- Zoom above ×1.2 on 1080p footage in a 1080p timeline: the softness shows.
- Cutting the final breath of sentences: sounds anxious. Leave 3–6 frames.

## Checklist

- [ ] Correct resolution and master intact
- [ ] Visual change every 3–7 s, with B-roll wherever something can be shown
- [ ] Captions if the destination autoplays muted
- [ ] Audio at −14 LUFS
- [ ] Render complete and verified
