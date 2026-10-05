---
name: resolve-delivery
description: "Export from DaVinci Resolve (Free or Studio) with the right specs for any vertical or horizontal platform — TikTok, Reels, Facebook, Shorts, Stories, Snapchat, YouTube, LinkedIn, X, web: format, codec, bitrate, LUFS loudness, output path and file verification. Use it when asked to render, export, deliver, upload, specs or loudness."
---

# Delivery

Specs for each platform: `references/platforms.md`. It is generated from the code, so it is the source of truth.
It is also available live via `list_formats`.

## Steps

1. `forge_status`: the right timeline, at the target format's resolution. If it does not match, use `make_platform_version` first.
   Several platforms with the same resolution (e.g. TikTok, Reels and Shorts) can come from the same timeline.
2. Loudness in Fairlight (with `resolve-forge` or by hand): the target is in the LUFS column (−12 to −14) and true peak at −1 dBTP.
   Studio: Deliver → Audio → Normalize Audio.
3. `preflight_render(format)` and a visual review/listen: fix errors and review warnings. Save the project.
4. `render_for(format, name=...)`. Without `target_dir` it writes to `~/Movies/resolve-forge`.
   - **Free**: the bridge only writes inside `allowed_output_roots` (by default `~/Movies`). Use subfolders of `~/Movies`
     or add the path to `allowed_output_roots` in the runtime `bridge.json` (`…/Fusion/.davinci_mcp_runtime/bridge.json`;
     per-OS location in `docs/install.md`) and restart the bridge.
   - H.265 automatically falls back to H.264 if your edition or GPU does not support it.
5. `render_status(job_id)` until `Complete`.
6. Verify the file: exists, size > 0, resolution and duration. With ffprobe:
   `ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate -of compact <file>`.
7. Report the path and the real specs of each file.

## Pitfalls

- `SetRenderSettings` inherits the preset loaded in Deliver; `render_for` sets format and codec before applying it.
- An empty `CustomName` invalidates the whole payload (`render_for` always fills it in).
- Rendering to a folder outside the allowed roots in Free: a clear error with the fix in the message.
