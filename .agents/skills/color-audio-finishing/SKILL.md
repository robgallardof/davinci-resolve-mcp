---
name: color-audio-finishing
description: "Finish the audio, color and LUTs of an edit in DaVinci Resolve: gentle presets, intelligible mix, LUFS/true-peak measurement and visual comparison. Use it to improve sound, apply looks/LUTs or prepare the finishing the producer commissions. Triggers (EN/ES): improve audio, color grade, LUT, look, mix, 'mejorar audio', 'colores', 'presets'."
---

# Audio and color finishing

The producer sets genre and reference; this specialisation improves the legibility of voice and image and returns
comparison evidence. Use `davinci-resolve-mcp` and `forge_status`; modify copies and write new files.

## Audio

- Listen to voice, music and SFX separately and together. `analyse_audio` measures; it does not prove intelligibility.
- For rumble and uneven dynamics: preview `enhance_audio(source, preset="dialogue"|"podcast"|"entertainment")`.
  Review measurements/filters; `dry_run=false` writes a new 48 kHz/24-bit WAV. Listen before/after at comparable
  volume. It does not remove reverb, separate voices or recover already-distorted audio. Import/replace the source
  only on a version and only if listening confirms the improvement; it does not shift timing.
- `add_music_bed` keeps the voice clear with ducking. Motivated SFX at moderate gain: `place_sound_effects`.
- The `enhance_audio` limiter controls peaks; it does not automatically deliver the platform LUFS. Measure the
  final mix and use `normalise_audio` with the target from `list_formats`; check the final WAV and listen.

## Color, presets and LUTs

- Before any look, check color management and input space. A creative preset does not convert Log/HDR to SDR.
  If you do not know the camera/space, inspect metadata and the reference before applying a conversion.
- `review_shots`/`review_video` guide exposure and cast; confirm skin, whites and highlights visually.
- `apply_grade_preset(preset="natural"|"warm"|"crisp"|"muted", intensity=.5)` is a preview. Apply only after comparing:
  `dry_run=false` creates a copy and replaces node 1's CDL. Do not stack corrections on the master.
- User LUT: `prepare_lut` validates the table and can blend with identity; it keeps the original.
  Read its input/output space. A creative LUT and a technical conversion are not interchangeable.
  Use `grade_clips`/`inspect_grade` per their schemas and check readback, without claiming it proves good color.
- Compare same-time frames before/after. Reject orange skin, crushed blacks, clipped highlights
  or saturation that hurts legibility. Do not force a LUT when a gentle CDL is enough.

## Wrap-up

`preflight_render(format)` must end with no open technical errors. Look at the framing sheet, listen to
the mix and verify text/cards/safe zones before saving and rendering. Afterwards use `review_video`, look at
the sheet and measure the final file's audio. Report what you measured and what you checked with eyes/ears.
