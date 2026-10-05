# davinci-agents — instructions for any agent

AI video-editing workspace on **DaVinci Resolve 21** (Windows, macOS and Linux; Free and Studio). Works with any agent that supports
`AGENTS.md`, Agent Skills (`SKILL.md`) and MCP: Claude Code, Codex, Cursor, Gemini CLI, VS Code, etc.
Skills and roles are written in English; always reply to the user in the user's language.

## What is here

| Path | What it is |
|---|---|
| `mcp/resolve-forge/` | Our own MCP server: intent-based editing, motion, captions, production by genre, finishing and render. Python 3.12 + uv |
| `.agents/skills/` | Portable skills (canonical source) |
| `.agents/agents/` | Portable roles/subagents (canonical source) |
| `config/mcp.servers.json` | Single source of MCP servers → `python scripts/sync.py` generates each client's config |
| `docs/` | First steps, install, architecture, editing playbook, API behaviour and migration status |

## How to work

1. Before touching Resolve, load the `davinci-resolve-mcp` skill and run `forge_status`.
   If it does not connect: `cd mcp/resolve-forge && uv run resolve-forge-doctor` tells you the next step
   (Free: Workspace → Scripts → resolve_bridge, every time Resolve is opened).
2. Pick the role by deliverable:
   - **9:16 / 4:5** (TikTok, Reels, FB Reels, Shorts, Stories, Snapchat, feed) → `.agents/agents/vertical-editor.md`
   - **16:9** (YouTube, Facebook, LinkedIn, X, web) → `.agents/agents/horizontal-editor.md`
   - Both, several deliverables, references or specialists → `.agents/agents/video-director.md` (the producer)
   - Specialists the producer briefs: `composition-editor`, `audio-editor`, `colorist`, `titles-editor`, `qa-editor`
   If your runtime has no subagents, read the role file and follow it yourself.
3. Skills:
   | Skill | Use it for |
   |---|---|
   | `davinci-resolve-mcp` | Connection, Free vs Studio, error codes, API pitfalls |
   | `editorial-direction` | Producer judgement by genre (comedy, music, interview…), several people, multi-source composition |
   | `entertainment-pacing` | Entertainment pacing: never >3 s without a change, zooms with a reason, cut dead time |
   | `vertical-video` / `horizontal-video` | Orientation method and checklist |
   | `dynamic-zoom-talking-head` | Motion for people talking to camera |
   | `captions-and-titles` | Exact words, caption/title design, karaoke, placement off faces |
   | `color-audio-finishing` | Color presets/LUTs, dialogue enhancement, measured mix |
   | `video-qa` | Look at the review sheets before building and after rendering |
   | `resolve-delivery` | Per-platform export specs, loudness and file verification |
4. **Quality**: no video is delivered without a visual review (`review_shots` before, `review_video` after)
   and `preflight_render` before rendering. Tools measure; the agent decides by watching and listening.
5. **Safety**: never modify the master without a copy; never delete media or projects without an explicit request;
   save the project before rendering. In Free, render inside `~/Movies`. Only one agent writes to Resolve at a time.

## Developing resolve-forge

- Layers: `domain/` (pure, no Resolve) → `services/` (use cases + backends) → thin MCP modules (`tools.py`,
  `authoring_tools.py`, `production_tools.py`, `qa_tools.py`, `producer_tools.py`, `composition_tools.py`) → `server.py`.
  `gateway.py` is the only module that knows how to connect to Resolve.
- New motion style: register a function with `@style(...)` in `domain/styles.py`. Nothing else to touch.
- New animation backend: implement `apply`/`clear` in `services/appliers.py` and register it in `APPLIERS`.
- Tests: `cd mcp/resolve-forge && uv run pytest` (no Resolve: Free/bridge, Studio and Resolve 19 fakes, real
  stdio, Windows/macOS/Linux simulation, workspace consistency; CI runs it on the three OSes) and `uv run pytest -m live` (end-to-end with render and pixel comparison).
- OS differences (SDK, Scripts folders, process name) live only in `native_paths.py`; never hard-code a
  Windows path elsewhere.
- Platform specs live in `domain/formats.py`; `references/platforms.md` is generated from there.
- Before "discovering" odd API behaviour, look it up in `docs/api-behavior.md`.
- After editing `config/` or `.agents/`, run `python scripts/sync.py`.
- When adding a tool: add it to the README table and update the counts (`test_workspace` checks them),
  mention it in the matching skill and log progress in the status section of `docs/third-party-migration.md`.
- Own implementations only: do not copy competitors' servers or modules. Keep domain → services → tools and isolated transports.
  Provenance and improvements log: `docs/third-party-migration.md`.
