---
name: entertainment-pacing
description: "Editing to entertain on social (TikTok, Reels, Shorts, vlogs, pets, comedy, challenges): the screen never sits still, but every zoom has a reason — short shots, framing on the real subject, crash zooms only on action peaks, animated text and captions. Use it ALWAYS when the video is meant to entertain or when they say 'looks plain', 'more dynamic', 'more zooms', 'more animated', 'don't let it bore', 'focus on the pet/the face', or edit uncut phone clips. Spanish triggers: 'se ve simple', 'más dinámico', 'más zooms', 'más animado', 'que no aburra', 'enfoca a la mascota'."
---

# Entertainment pacing (with zooms that make sense)

Two rules that go together:
1. **The screen never sits still**: no stretch longer than ~2–3 s without a change (cut, reframe, text, caption).
2. **Every zoom has a reason and is well placed**: it moves closer to something that matters (the face in a reaction, the pet,
   the object of the action) and leaves it centred and complete. A zoom on a sleeve, a wall, the centre when the action
   is in a corner, or during a camera move, is worse than no zoom.

The story and the user decide the duration: if they ask for more than a minute, keep the story and gain pace
inside it, rather than over-trimming.

## Flow (with mandatory self-review)

1. **Watch the source** before deciding: a contact sheet of frames (or `find_highlights`/`analyse_scenes`). Identify
   who the protagonist of each part is (person, pet, object) and where it is in the frame.
2. **Story**: ranges in SOURCE seconds (voice: `find_story_moments`; music: `analyse_music`).
3. **Plan**: `plan_energized_edit(source, ranges, format=<platform>, hints=[...])`.
   - The detector follows the largest motion — often the person, not the pet. If something else matters,
     correct it with `hints`: `{start_s, end_s, focus: [x, y]}` (where the real subject is) or
     `{start_s, end_s, framing: "wide"}` (moving camera, reveal, a shot that must breathe).
   - The plan self-reviews: it drops to medium/wide any zoom that leaves the subject at the edge, crops the action,
     cuts a face or exceeds what the resolution allows (`format` computes the maximum sharp zoom). Read `self_review`.
4. **Visual review BEFORE building**: `review_shots(source, shots, format, texts=[...])` and **open the `sheet`
   image** (read it as an image). Check every shot: does the framing show what matters? Is the subject complete
   and centred? Does any text cover a face? Red = problem. Fix with `hints`/framing and repeat until
   everything is green **and** looks right to your eyes. Use `text_positions` to place text.
5. **Build**: `energize_timeline(source, name, format, shots=..., dry_run=false)`.
6. **Layers** (not covering each other or faces):
   - Captions of what is said with verified words (`transcribe_timeline(include_words=true)` / `align_text`);
     if Whisper is unsure, isolate the fragment and verify; if it cannot be understood, do not caption it.
   - Narration text at the turns (`add_text_overlay`, `creator`, `pop`), one at a time, in the position
     `review_shots` indicated.
   - Color: if `look.cdl` brings corrections, apply them with `grade_clips` (on a copy) only if they improve the frames.
   - Sound: `add_music_bed` / `place_sound_effects` if the user provides the files.
7. **Render and final review**: `render_for` → `review_video(file)` and **open the sheet**. If there is black, freezes,
   text over faces, odd framing or ugly color, fix and render again. Never deliver without this.

## No interaction, cut it

In this project, a confirmed range with no people or animals is cut even if the camera or background moves:
`hints: [{start_s, end_s, subject: "none"}]`. For a confirmed pet use `subject: "animal"` and `focus`;
for a person use `subject: "person"`. Motion does not prove an animal is present: look at the source.
A still face or pet can matter; these ranges are protected from low-energy trimming.
Wide shots stay static; do not force zooms to alternate if they make the framing worse.

A person **from behind**, with no visible face, and nothing else happening (pet still, nobody looking, nothing
moving with intent) is dead time even if there is motion. `plan_energized_edit` (drop_dull=true) cuts them and
lists them in `cut_dull` with the reason. If such a shot matters to the story, protect it with
`hints: [{start_s, end_s, keep: true}]` or with `focus` on what does happen (the pet). Always review `cut_dull`.

## Framing criteria

| Moment | Framing |
|---|---|
| Scene opening, reveal, moving camera | wide (no zoom) |
| Single-subject action (pet jumping, hand grabbing) | medium/close centred on the subject |
| Reaction, look to camera, calm face | close on the face |
| Clear, concentrated action peak | crash zoom (fast punch) — never two in a row |
| Nothing happens / subject out of frame | wide or cut that stretch |

## Details the user notices

- Correct gender and number in text (in Spanish, a female squirrel is "la supervisora", "la jefa").
- No text over faces or the action; inside the format's safe zone.
- Low-resolution sources (WhatsApp 576×1024): the plan limits zoom so it does not look blurry; if more
  zoom is needed, ask for the phone's original.
- One accent per moment: do not stack crash zoom + text + SFX in the same second except at the climax.
