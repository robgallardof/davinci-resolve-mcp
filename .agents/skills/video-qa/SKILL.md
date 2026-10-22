---
name: video-qa
description: "Mandatory quality control of any edit before delivery: visually review framing, zooms, text and captions (not covering faces or the action), color/exposure, cuts, black or frozen frames and file specs. Use it ALWAYS before building a timeline with zooms and ALWAYS after rendering, for any video (vertical or horizontal), even if the user does not ask."
---

# Video QA: look before you deliver

No video is delivered without you having **looked** at it. Tools measure and flag; you decide with your eyes.

## Before building (if there are zooms or reframes)

1. `review_shots(source, shots, format, texts)` → open the `sheet` image.
2. For every shot ask:
   - What does it show? Is it what matters at that moment (the face, the pet, the action)? If not, `hints.focus` or `wide`.
   - Is the subject complete and near the centre? Is a head, a tail or a key object cut off?
   - Does the zoom have a reason? If it is "just because", remove it.
   - Does any text/caption cover a face or the action? Use `text_positions`.
3. `flagged` must end up empty and the sheet must look right. If not, fix and repeat.

## Color and quality

- `look.issues` empty: do not touch the color. If it reports problems (underexposed, flat, cast, dull), apply
  `look.cdl` with `grade_clips` on a copy and compare frames before/after. No exaggerated looks.
- Do not zoom beyond what the source resolution allows (the plan limits it with `format`).

## After rendering

Before rendering run `preflight_render(format)`: fix video coverage errors, missing sources,
invalid transforms and resolution/duration. Review audio and zoom warnings; a vertical coverage zoom
can be large without being an error. `technical_passed` does not verify faces, captions, LUTs or real audio.
The `review_shots` crop accounts for the target aspect; a horizontal converted to vertical is not stretched.
For audio/color/LUTs use `color-audio-finishing`, with a before/after comparison.

1. `review_video(file)` → open the sheet.
2. Check: black, freezes, odd jumps, text over faces, correct and legible captions, color,
   duration and resolution (`render_status` + `review_video`).
3. If something fails, fix it in the timeline and render again. Tell the user what you reviewed.

## Temporal and audio continuity

For creator polish, also check camera sync, crop sharpness and subject placement across angle changes;
caption animation must remain readable in motion. For mixed camera/HDR/Log work, compare skin and
highlights across cuts and verify the rendered output against the intended color pipeline.

For designed transitions and repaired cuts, follow
[transition review](../editorial-direction/references/transitions-and-flow.md#watch-and-listen-across-the-boundaries).
Play each boundary with sound before and after rendering; sampled sheets cannot establish smoothness.
Check cut-off words, ambience/level jumps, unintended black gaps, ghosting and framing snaps.
Document intentional black/silence so it is distinguishable from defects. If playback or listening is
unavailable, report temporal/audio review as pending rather than passing it from static frames.

## What the user always notices

- Zooms on meaningless things or badly positioned.
- Text covering faces; captions with invented words.
- Wrong gender/number in text; spelling mistakes.
- Long dead stretches with no story/action purpose; a held shot is not automatically a defect.
