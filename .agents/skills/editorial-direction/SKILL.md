---
name: editorial-direction
description: "Professional producer and editor judgement by genre in DaVinci Resolve: comedy (setup, pause, punchline, reaction), music videos and electronic music (phrases, build/drop, cuts on the beat), interviews, film/narrative, education, product, gaming and vlog. Use it before cutting any piece with intent: when asked to 'make it look professional', 'not robotic', 'improve my idea', a video for a song, a visualizer, a comedy edit, finding the funny parts or best moments, or nice captions that match the tone. Spanish triggers: 'que se vea profesional', 'no robótico', 'mejora mi idea', 'partes graciosas', 'subtítulos bonitos'."
---

# Editorial direction by genre

You are a producer as well as an editor: you understand the idea, improve it and execute it. Tools measure; you decide.
No audio peak is a joke or a drop until you have seen or heard it.

## Flow

1. **Brief**: what the piece should provoke (laughter, the urge to dance, trust, learning), for whom and where.
   If the idea is weak, propose a concrete improvement (a stronger hook, another order, a visual punchline) before cutting.
2. **Evidence**:
   - Voice (comedy, interview, education, vlog, gaming, product, film): `find_story_moments(source, content_type)`.
     Returns candidates with evidence: a pause before a short line (punchline), voiceless audio right after
     (laugh/reaction), questions and stressed words. Times in SOURCE seconds.
   - Music: `analyse_music(source)` → BPM, confidence, beats and energy changes (candidates, not confirmed drops).
3. **Review every candidate** (watch/listen). Keep only the real ones and pass them with your reason:
   `plan_edit(brief, content_type, platform, duration_s, moments=[{time_s, kind, reason}])`.
   It returns direction, what to avoid, caption and motion styles, and the tools for the flow.
4. **Cut** (for entertainment also apply the `entertainment-pacing` skill: `plan_energized_edit` → `energize_timeline`):
   - Voice: `assemble_timeline(source, cuts=[[start, end], ...], name, format)` protecting each complete block.
   - Music: `plan_beat_cuts(music_source, shots, duration_s, beats_per_cut, intense=[[start, end]])` then
     `assemble_montage(shots, name, format, music_source, music_start_s, dry_run=false)`.
5. **Motion, text and sound** matching the tone (below), without stacking effects: one accent per moment.
   SFX only on confirmed, motivated moments: `place_sound_effects(cues=[{time_s, source, reason}])`
   (preview first; heed its density warnings). Use sounds the user has licensed.
   Background music under voice (interview, education, vlog, product): `add_music_bed(music_source)`; not in music videos,
   where the song is the star (`assemble_montage`).
6. **QC**: `audit_timeline`, visual review of each punchline/drop and `render_for`.

## By genre

| Genre | Protect | Pacing | Text / motion |
|---|---|---|---|
| **Comedy** | setup → pause → punchline → reaction. The pause IS the joke | Cut *after* the laugh, not during the punchline. Reaction only if it adds | `creator` or `impact` only on the punchline; `emphasis` with `hits_s` = confirmed punchlines. Never give the joke away in a title. No SFX on every gag |
| **Music / music video** | The song intact (continuous A1); lyrics with timing from the artist | Cuts on phrases (4–8 beats), visual motifs that return in the chorus | `editorial`; slow `warm_push`. Exact lyrics: `align_text(source=<isolated vocal, or the song with focus_vocals=true>, text=<lyrics>, timeline_offset_s=-music_start_s)` → `add_captions(words=...)`. Whisper only provides timing |
| **Electronic** | Build / drop / breakdown contrast | Build: lengthen shots and raise tension; confirmed drop: `intense` with 1–2 beats per cut; breakdown: breathe | Short `impact` on the drop; `tiktok_punch` only there. No full-screen flashes. Visualizer: `create_music_visualizer` |
| **Interview / podcast** | The meaning of the answer, eyelines, genuine reactions | Let emotional answers breathe; cover cuts with relevant B-roll | `studio`; `youtube_dynamic` / `warm_push` |
| **Film / narrative** | Screen direction, continuity, silences | Cuts motivated by the story, never by a timer | `editorial`, no animation or `fade` |
| **Education** | The complete demonstration and the pauses needed to understand | Cut on finished ideas; show what is being explained | `studio` (16:9) / `creator` (9:16) |
| **Product** | Benefit first, real demo, legible proof, a single CTA | Hook → problem → demo → proof → CTA | `studio`; no unverified claims |
| **Gaming** | Spatial context, legible HUD, the play that explains the outcome | Speed up the waiting, never the play | `creator`; captions away from the HUD (`position="top"` if the HUD is at the bottom) |
| **Vlog** | Authentic moments, place | Alternate detail and presence; J/L cuts | `creator`; `vlog_mix` |

## Several people (podcast, interview, two on a couch)

An editorial option, not a rule or an automatic effect based on the number of people. The producer decides from the
reference, story, format and legibility within the authorised scope; do not ask permission again for reversible
style changes already part of the edit. To coordinate specialists or interpret reference collages, read
[references/producer-coordination.md](references/producer-coordination.md).
- `plan_speaker_layout(source, format, mode)`: detects each person and who is speaking (mouth + voice).
  - `auto`: proposes framing from speaker candidates; inspect its result before accepting splits.
  - `split`: always split. `single`: always one person.
  - Stacked, grid or side by side are planner options, not obligations for the producer. Check the current
    schema and legibility; alternating close-ups, keeping the group or using visual support may work better.
- Review the segments (no flicker: at least 1.5 s per layout), then `build_speaker_layout` (new clip with the original
  audio + new timeline) and `review_video` before adding captions and text.
- Different sources on screen (several takes of the same person, interview + photo, reaction + B-roll):
  `plan_composition(segments, audio_master)` → look at the sheet and preview → `build_composition(..., reviewed=true)`.
  Each panel declares source, start and `subject` or `crop`; the audio master is single and explicit. Do not invent
  simultaneity or reactions: a collage is an editorial decision, not a rule based on the number of sources.
- If detection is wrong, pass `people` (face boxes) and `active` (who speaks and when) by hand.
- Two people in horizontal → Reel: `mode="single"` or `auto` to alternate to the speaker; protect relevant
  reactions. Three, four or five: `split` if the producer decides to show the group; do not drop the fifth face.
  Keep faces complete and check each panel's size. Mouth/energy detection is not diarization:
  verify the switches by listening, especially with laughter/music or moving participants.

## Captions and text that look good

- `list_text_styles` → `preview_text_style(text, style, width, height)` to review before burning anything.
- `add_captions(style="auto")`: Creator in vertical, Studio in horizontal. Styles: `creator` (friendly, active
  word), `studio` (clean), `editorial` (warm, discreet), `impact` (punchlines and short messages).
- Brand color with `accent="#RRGGBB"`; `emphasis_words` only for the words that matter.
- Exact text: if there is a script or lyrics, `align_text(source, text)`; otherwise correct `transcribe_timeline(include_words=true)`.
  In both cases pass `words=` to `add_captions` before burning.
- `reduced_motion=true` for calm or accessible content. Legacy styles (`box`, `outline`, `yellow`, `dark`) only if the user asks.
- `animation="karaoke"` animates a per-word progress underline using real timings, without jumping glyphs.
  Check the preview; keep pauses. For mix finishing and LUTs commission `color-audio-finishing`.

## What not to do

- Cut every 2 s "just because", zoom on every sentence, or animate text, camera and SFX at once.
- Label "drop", "joke" or "emotional moment" without having checked it.
- Stretch or reframe the music master without being asked.
