# First steps (10 minutes)

Step-by-step guide to your first video edited by an agent. Same for Resolve **Free** and **Studio**, on Windows, macOS and Linux.
The agent replies in your language: you can ask in English, Spanish or anything else.

## 1. Install (once)

```sh
cd ~/Documents/Projects/davinci-agents   # wherever you cloned it
pwsh scripts/bootstrap.ps1                # Windows
sh scripts/bootstrap.sh                   # macOS / Linux
```

When it finishes you should see `Done.` If DaVinci Resolve was open, **close it and open it again**
so it loads the bridge script.

## 2. Open Resolve and connect

1. Open DaVinci Resolve.
2. In the Project Manager open your project (or create one with **New Project**).
   > If you close the Project Manager without opening a project, Resolve quits.
3. **Free**: menu **Workspace → Scripts → resolve_bridge**. No window appears: the bridge listens in the background
   until Resolve closes. Repeat it every time you open Resolve.
   **Studio**: Preferences → System → General → *External scripting using* = **Local** (once).
4. Check the connection:

```sh
cd mcp/resolve-forge
uv run resolve-forge-doctor
```

It must say `[OK] Connection: Free 21.x via bridge` (or `Studio … via direct`). If something fails, the last line tells you what to do.

## 3. Prepare a timeline

In Resolve: import a clip of someone talking (Media Pool → right-click → Import Media) and drag it
into a new timeline. A 20–60 s clip is enough.

## 4. Open your agent in this folder

```sh
cd ~/Documents/Projects/davinci-agents
claude          # or codex / gemini, or open the folder in Cursor / VS Code
```

The first time, approve the `resolve-forge` MCP server (it is the only one).

## 5. First requests

Paste these one at a time and look at the result in Resolve after each:

```text
1) Tell me Resolve's status and which clips are on the timeline.
2) Show me how a youtube_dynamic style would look on this clip, without applying it.
3) Apply youtube_dynamic at intensity 0.8 anchored to the face.
4) Make a vertical Reels version of this timeline and give it tiktok_smooth.
5) Add nice captions in my brand colour #FF5A36; show me how they look first.
6) Put background music under the voice using this file: C:/path/music.mp3
7) Check everything before rendering, then export the vertical for Reels and the horizontal for YouTube 1080.
```

What you will see:

- Step 3: in Free, clips get a **ForgeMotion** node on the Fusion page. In Studio, keyframes appear in the Inspector.
- Step 4: a new `… [reels]` 1080×1920 timeline. The original does not change.
- Step 5: a preview (PNG and animated WebP), then a new track with animated captions and the active word highlighted.
- Step 6: a new audio track with the music dipping when you speak and rising between sentences (a new file; your original music is untouched).
- Step 7: `preflight_render` findings, then the files in `~/Movies/resolve-forge/` and a review sheet the agent looks at.

## 6. Ask like an editor, not a technician

Agents understand intent. Some examples and what they trigger:

| You say | The agent uses |
|---|---|
| "From the podcast, one YouTube video and three 30 s vertical clips with the best bits." | `video-director` role, `find_highlights`, platform versions |
| "Don't let it look static, but don't make me dizzy." | `warm_push` or `youtube_dynamic` at low intensity |
| "More energy, TikTok style." | `tiktok_punch` at intensity 1.2 |
| "Phone clips of my dog: make it fun, zoom on the dog, cut where nothing happens." | `plan_energized_edit` + `review_shots` (skill `entertainment-pacing`) |
| "Zoom when I say 'important' at 0:15 and 0:48." | `emphasis` with those seconds |
| "LinkedIn version." | `linkedin_1080` or `square`, with captions |
| "It's comedy: find the punchlines and don't cut the laughs." | `find_story_moments` + `plan_edit` (skill `editorial-direction`) |
| "Music video for my song with cuts on the beat and the exact lyrics." | `analyse_music`, `plan_beat_cuts`, `assemble_montage`, `align_text` |
| "Two people in a horizontal podcast → a Reel that follows whoever speaks." | `plan_speaker_layout` / `build_speaker_layout` |
| "Combine the interview with these photos like this reference." | `plan_composition` → `build_composition` |
| "Make the voice clearer and give it a warm look." | `enhance_audio`, `apply_grade_preset` (skill `color-audio-finishing`) |
| "A whoosh when I change topic." | `place_sound_effects` with your sound file |

The agent proposes improvements to your idea, but it confirms moments (joke, drop, emotion) by watching or listening:
the tools give candidates with evidence; they do not decide alone. You can attach reference screenshots — the producer
treats them as inspiration for this piece, not as fixed rules.

## 7. If something goes wrong

- Always run `uv run resolve-forge-doctor` first.
- Remove the motion: "remove forge motion from every clip" (`clear_motion`).
- Back to the original: the master is never touched; versions are new timelines you can delete.
- "Cannot reach DaVinci Resolve": open a project (the Project Manager is not enough) and run Workspace → Scripts → resolve_bridge again.
- The bridge still holds its port after restarting Resolve: ask for `repair_bridge_connection` (preview first).
- Missing transcription or audio analysis (`MISSING_DEPENDENCY`): `cd mcp/resolve-forge && uv sync --extra speech --extra vision`.
- In Free, rendering only writes inside `~/Movies`.

## 8. Check everything works on your machine

```sh
cd mcp/resolve-forge
uv run pytest            # no Resolve needed
uv run pytest -m live    # Resolve open + bridge running; creates forge_* projects kept for inspection
```
