---
name: captions-and-titles
description: "Design, time and place captions and on-screen titles in DaVinci Resolve via resolve-forge: exact words (script/lyrics alignment or corrected transcript), styles creator/studio/editorial/impact, brand accent, per-word karaoke, hooks, POV and lower thirds, safe zones and faces kept clear. Use it whenever captions, subtitles, titles, text overlays, lyrics or animated text are involved. Spanish triggers: 'subtítulos', 'subtítulos animados', 'textos', 'letra', 'títulos'."
---

# Captions and titles

Text is read before it is heard: most social views are muted. Every word must be right, readable on a phone
and placed where it never covers a face or the action. Animation supports the speech; it never competes with it.

## 1. Get the exact words

| Situation | Tool | Notes |
|---|---|---|
| Script, lyrics or names known | `align_text(source, text, timeline_offset_s)` | The supplied text is what is captioned; recognition only provides timing. Check the matched coverage |
| Song from a full mix | `align_text(..., focus_vocals=true)` | An aid, not stem separation; isolated vocals align best |
| Unscripted speech | `transcribe_timeline(include_words=true, language=...)` | Listen and correct names, numbers, slang and gender/number agreement |
| Inaudible fragment | — | Do not caption it. Never invent words |

Words are `{text, start, end}` in TIMELINE seconds. For a montage whose music starts at `music_start_s`,
pass `timeline_offset_s=-music_start_s`. Re-run alignment after any cut that moves the speech.

## 2. Choose a look

`list_text_styles` describes each art direction and the camera motion that matches it.

| Style | Tone | Typical use |
|---|---|---|
| `creator` | friendly, active word highlighted | TikTok/Reels/Shorts, vlogs, entertainment (vertical `auto`) |
| `studio` | clean, neutral | YouTube, interviews, education, muted-autoplay feeds (horizontal `auto`) |
| `editorial` | warm, discreet, chosen emphasis only | film, music, testimonials |
| `impact` | short and loud | punchlines, hooks, 1–4 word messages, drops |

- `accent="#RRGGBB"` for the brand; `emphasis_words` only for the words that carry the idea.
- `animation`: `fade`, `lift`, `pop` or `karaoke` (per-word progress with real timings). `reduced_motion=true`
  for calm or accessible content. Legacy `box/outline/yellow/dark` only on request.
- `max_words`: omit to use the design's phrase length; `1` only for brief impact moments.
- Always `preview_text_style(text, style, width, height, ...)` at the target resolution and look at the PNG/WebP
  before burning anything.

## 3. Place it

- Captions: `add_captions(style, position, accent, emphasis_words, words=<corrected>)` — new top track plus an SRT.
- Titles, hooks, POV, labels, lower thirds: `add_text_overlay(text, start_s, duration_s, style, position)`.
- Positions are inside the format's safe zone, but faces are your job: run `review_shots(..., texts=[...])` and use
  its `text_positions`. With split screens or `plan_composition` panels, recompute placement per panel layout.
- Gaming: keep text off the HUD (`position="top"` when the HUD is at the bottom).

## 4. Rhythm rules

- Hook text in the first 0–3 s states the promise or conflict; one twist line mid-video at most.
- One on-screen text at a time besides captions. Do not animate text, camera and SFX with equal force on the same beat.
- Never reveal a punchline before it is said; emphasise it when it lands.
- Captions follow phrases, not fixed word counts; keep pauses visible instead of filling them.

## 5. Check

After rendering, `review_video(file)` and look at the sheet: correct words, no text on faces, legible at phone size,
no flicker between cues. Report which fragments were corrected or left uncaptioned and why.
