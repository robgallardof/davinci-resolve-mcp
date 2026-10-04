# Editing playbook (research, October 2026)

Actionable summary of the sources consulted. The skills in `.agents/skills/` apply it.

## Short-form retention

- A hook that earns the first second, pattern interrupts that reset attention every few seconds and a loop
  that pushes watch time above 100 %. Trim the opening air to reach the hook immediately.
  Stack visuals (text, overlays, B-roll) and always caption, because much of it is watched muted.
- Duration: 15–35 s is safest; 30–60 s works if the idea needs it. "Make the idea feel complete
  as early as possible and cut before there is a reason to swipe."
- Sources: [Splice — retention apps](https://spliceapp.com/blog/which-apps-enhance-viewer-retention),
  [ShortGenius — Shorts best practices](https://shortgenius.com/blog/youtube-shorts-best-practices),
  [Revid — how to edit](https://www.revid.ai/blog/how-to-make-and-edit-videos).

## Entertainment footage (pets, vlogs, challenges)

- The screen never sits still for more than ~2–3 s, but every zoom must bring something that matters closer and keep
  it whole and centred. A zoom on the wrong thing is worse than no zoom.
- Cut stretches where nobody (person or animal) is present or nothing happens with intent, even if the camera moves.
- Never zoom past what the source resolution allows (WhatsApp-sized sources blur quickly).
- In Forge: `plan_energized_edit` → `review_shots` (look at the sheet) → `energize_timeline`. Skill `entertainment-pacing`.

## Talking heads (horizontal)

- Change the framing or a visual element every **3–7 s** (zoom, text, B-roll).
- Punch-in: a slight zoom on the A-roll at important points or every few sentences.
- Jump cuts + short sentences + B-roll speed up the pace. B-roll that *shows* what is said adds the most.
- Do not overdo it: shots constantly under 1–3 s are exhausting.
- Sources: [Subscribr — engaging talking heads](https://subscribr.ai/p/editing-talking-head-videos-engaging),
  [Subscribr — workflow](https://subscribr.ai/youtube-strategy/talking-head-video-editing-workflow),
  [Jupitrr — edit talking head videos](https://jupitrr.com/how-to/edit-talking-head-videos).

## Several people and multi-source layouts

- Two speakers from a horizontal source in a vertical: follow whoever speaks, keep relevant reactions.
- 3–5 people: a split or group shot only when the producer wants to show the group; faces complete, no tiny thumbnails.
- References with several panels may be several takes of one person, or interview + photo + B-roll: a composition
  choice (`plan_composition`), not a speaker count. One continuous audio master.

## Captions and text that look designed

- Per-word sync and a clear hierarchy: a stable phrase on screen with the active word highlighted, instead of
  text that jumps on every word. Short entrances (fade, lift, pop) and a single typeface family per piece.
- Modes by tone: Creator (friendly, Reels/TikTok), Studio (clean, interviews/education), Editorial (warm,
  stories), Impact (only punchlines and 1–4 word messages). Brand colour as an accent, not on all text.
- Text, camera and sound are not animated at the same time: one accent per moment.
- In Forge: `list_text_styles` → `preview_text_style` → `add_captions(style, accent, words)`; exact lyrics or script
  with `align_text`. Skill `captions-and-titles`.
- Sources: [School of Motion — typography for motion](https://schoolofmotion.com/blog/fonts-typefaces-typography-for-motion-design),
  [CapCut — types of captions](https://www.capcut.com/resource/types-of-captions),
  [TikTok — creative codes](https://ads.tiktok.com/business/en-US/creative-codes).

## Judgement by genre

- **Comedy**: setup → pause → punchline → reaction. The pause is part of the joke; cut after the laugh, never
  during the punchline, and never give the punchline away in a title. SFX only if they add.
- **Music / music video**: the song rules and is not touched. Cuts on phrases (4–8 beats), visual motifs that return in
  the chorus; lyrics with real timings, not sung-speech transcription.
- **Electronic**: build / drop / breakdown contrast. More cuts and movement only on the drop confirmed by ear;
  the breakdown breathes. No full-screen flashes.
- **Interview / podcast**: respect the meaning of each answer and real reactions; background music under the voice
  (−20 dB while speaking) and cuts covered with relevant B-roll.
- **Film / narrative**: cuts motivated by the story and screen direction, never by a timer.
- Detectors (pauses, energy, beats) give **candidates with evidence**; the editor confirms by watching or listening.
  Operational detail: skill `editorial-direction`.

## Finishing

- Dialogue first: gentle high-pass, compression and a limiter on a new file; measure LUFS/true peak and listen at
  comparable volume. No promise of separating voices or repairing distortion.
- Color: match shots and correct exposure/balance before any look; a creative LUT is not a Log/HDR conversion.
  Compare same-time frames; reject orange skin, crushed blacks and clipped highlights. Skill `color-audio-finishing`.

## Zoom in DaVinci Resolve

- **Dynamic Zoom** (Inspector): linear or eased zoom without keyframes; quick for a push per clip.
- **Keyframes** on Zoom/Position: full control of the framing.
- **Fusion Transform**: Size + Center/Pivot with keyframes, for fine curves.
- Sources: [Ripple Training — Dynamic Zoom](https://www.rippletraining.com/blog/davinci-resolve/use-dynamic-zoom-davinci-resolve-12-5/),
  [FireCut — fastest zoom](https://firecut.ai/blog/the-fastest-way-to-zoom-in-davinci-resolve/),
  [Miracamp — resize guide](https://www.miracamp.com/learn/davinci-resolve/how-to-resize-frames-and-videos-in-davinci-resolve).

## 1080×1920 safe zones

- TikTok: 240 px top, 660 px bottom and 120 px on each side, plus the right-rail buttons.
- Reels: 269 px top, 672 px bottom and 65 px on the sides.
- These are conservative (ads-level) figures; in organic posts the overlay covers slightly less.
- Sources: [House of Marketers — safe zones](https://www.houseofmarketers.com/guide-to-safe-zones-tiktok-facebook-instagram-stories),
  [Reap — short-form safe zones](https://reap.video/blog/short-form-video-safe-zones),
  [Upload-Post — checker](https://www.upload-post.com/tools/safe-zone-checker/).

## Export and loudness

- YouTube: −14 LUFS integrated and −1 dBTP (it only turns down what is louder). TikTok/Reels: around −10 to −12 LUFS.
- H.264 High: 1080p at 12–16 Mbps, 4K at 35–45 Mbps, Shorts/Reels at 10–14 Mbps. 30 fps for a captioned talking head.
- Shorts plays at 1080p at most.
- Sources: [The Post Flow — export settings](https://thepostflow.com/post-production/post-production-workflows/export-settings-youtube-instagram-tiktok/),
  [Influenceflow — specs 2026](https://influenceflow.io/resources/the-ultimate-social-media-video-specs-guide-2026-edition/).

## Agent portability

- `AGENTS.md` standardises project context. `SKILL.md` (agentskills.io) is read by more than 30 tools
  (Claude Code, Codex, Cursor, Gemini CLI…). `.agents/skills/` is the interoperability convention.
  The format is shared; install paths and autoload still vary, hence `scripts/sync.py`.
- Sources: [Agent Skills open standard (D. Vaughan)](https://codex.danielvaughan.com/2026/05/05/agent-skills-open-standard-portable-skills-codex-cli-cross-agent/),
  [mcp.directory — cross-agent skills](https://mcp.directory/blog/cross-agent-skills-cursor-codex-cline-antigravity-gemini-mastra-portability).
