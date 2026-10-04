# davinci-agents

**[English](#english)** · **[Español](#español)**

<a id="english"></a>

Edit video in **DaVinci Resolve** by talking to an AI agent. There are two specialised editors:

- **vertical-editor**: TikTok, Instagram Reels, Facebook Reels, YouTube Shorts, Stories, Snapchat and 4:5 feed.
- **horizontal-editor**: YouTube 1080p/4K, Facebook, LinkedIn, X, web/Vimeo, courses and podcasts.

Both know how to **bring people on camera to life** (punch-ins, smooth zooms, emphasis bumps, handheld feel),
convert between vertical and horizontal without losing the face, and export with each platform's specs.

It works the same on **Resolve Free and Studio** (verified live on Free 21.0.4) and with any agent:
Claude Code, Codex, Cursor, Gemini CLI and VS Code.

> First time? Go straight to **[docs/FIRST-STEPS.md](docs/FIRST-STEPS.md)** (Spanish): your first edited video in 10 minutes.

## Contents

1. [What's inside](#whats-inside)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Connecting Resolve (Free or Studio)](#connecting-resolve-free-or-studio)
5. [Daily use](#daily-use)
6. [Agents and skills](#agents-and-skills)
7. [resolve-forge tools](#resolve-forge-tools)
8. [Motion styles](#motion-styles)
9. [Platforms](#platforms)
10. [Tests](#testing)
11. [Troubleshooting](#troubleshooting)
12. [Improving the other MCPs](#improving-the-other-mcps)
13. [Credits and what we improved](#credits-and-what-we-improved)
14. [Repository layout](#repository-layout)

## What's inside

| Piece | What it does |
|---|---|
| **`resolve-forge`** (our MCP) | Intent-level editing: motion for talking heads, platform versions (vertical ↔ horizontal), spec-correct renders, captions/text on Free, transcription, highlights and assembly. 16 tools + 4 resources |
| **`davinci-resolve`** (upstream MCP, [samuelgursky](https://github.com/samuelgursky/davinci-resolve-mcp)) | The whole Resolve API: media pool, markers, color, Fairlight, Fusion, transcription, analysis. 37 tools |
| **Agents** | `vertical-editor`, `horizontal-editor` and `video-director` (coordinates both) |
| **Skills** | `vertical-video`, `horizontal-video`, `dynamic-zoom-talking-head`, `resolve-delivery`, `davinci-resolve-mcp` |
| **Doctor** | `resolve-forge-doctor`: checks the whole chain and tells you the next step |

Why there are two MCPs, and how they compare with the other five that exist: [docs/mcp-landscape.md](docs/mcp-landscape.md).

## Requirements

- Windows 10/11 (macOS/Linux should work but are untested)
- DaVinci Resolve **20 or 21**, Free or Studio
  - Free **21.1+**: Blackmagic moved Python scripting to Studio, so the Python bridge no longer shows up in the menu
- [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 by itself)
- git
- Optional: ffmpeg (silence detection and loudness in the upstream MCP)

## Installation

```powershell
git clone https://github.com/robgallardof/davinci-resolve-mcp.git davinci-agents
cd davinci-agents
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\bootstrap.ps1   # upstream + venv + bridge + forge + configs
```

`bootstrap.ps1` does all of this, and is idempotent (safe to re-run):

1. Fetches the upstream MCP at its pinned commit into `vendor/`, applies our patch (`scripts/references.py`) and
   creates its venv with Python 3.12.
2. Installs the **bridge** inside Resolve (Workspace → Scripts → `resolve_bridge`). This is what makes the Free edition work.
3. Installs `resolve-forge` with face detection (opencv) and runs the tests.
4. Runs `scripts/sync.py`, which generates every agent's MCP config and the skill/agent links.

Check:

```powershell
cd mcp/resolve-forge
uv run resolve-forge-doctor
```

## Connecting Resolve (Free or Studio)

| | Free | Studio |
|---|---|---|
| Once | Nothing extra (bootstrap installed the bridge). Restart Resolve after installing | Preferences → System → General → *External scripting using* = **Local** |
| Every time you open Resolve | Open a project → **Workspace → Scripts → resolve_bridge** | Nothing |
| Transport | `bridge` | `direct` (or `bridge` if you start it) |

The doctor tells you exactly what is missing.

## Daily use

1. Open Resolve with your project (on Free, start the bridge).
2. Open your agent **inside the `davinci-agents` folder**:
   - Claude Code: `claude` (approve the `.mcp.json` servers the first time)
   - Codex: `codex` · Cursor / VS Code: open the folder · Gemini CLI: `gemini`
3. Ask in plain language (English or Spanish):

```text
This podcast looks static. Give it subtle YouTube-style motion with emphasis at 0:42, 1:15 and 2:03.
Make a Reels version of the current timeline with punch-ins at the start of every sentence and export it.
From the master, make versions for TikTok, Shorts and LinkedIn 16:9.
I have a vertical TikTok: turn it into 16:9 for YouTube with the face centered.
```

Files are written to `~/Movies/resolve-forge/` (on Free, the bridge only writes inside `~/Movies`).

## Agents and skills

They are portable: `.agents/` is the single source ([AGENTS.md](https://agents.md) + [Agent Skills](https://agentskills.io) standards).
Claude Code sees them through `.claude/` (links); Codex, Cursor and Gemini read `AGENTS.md` and `.agents/skills`.

| Agent | When | Skills |
|---|---|---|
| `vertical-editor` | 9:16 / 4:5: TikTok, Reels, FB Reels, Shorts, Stories, Snapchat, feed | `vertical-video`, `dynamic-zoom-talking-head`, `resolve-delivery`, `davinci-resolve-mcp` |
| `horizontal-editor` | 16:9: YouTube, Facebook, LinkedIn, X, web, courses, podcasts | `horizontal-video`, `dynamic-zoom-talking-head`, `resolve-delivery`, `davinci-resolve-mcp` |
| `video-director` | Requests that mix orientations or several deliverables | Delegates to the two above |

The agent and skill files are written in Spanish; agents follow them in any language.

## resolve-forge tools

| Tool | What it does |
|---|---|
| `forge_status` | Edition (Free/Studio), transport, version, project, timeline, fps, resolution and backends |
| `list_clips` | Clips on a track with index, start, duration and zoom |
| `list_styles` / `preview_motion` | Style catalogue and dry run without touching Resolve |
| `apply_motion` | Animates clips: style, cuts/emphasis in seconds, intensity, anchor (face/center/point) |
| `clear_motion` | Removes forge's animation |
| `make_platform_version` | Duplicates the timeline into any format (vertical ↔ horizontal), keeping the subject in frame |
| `locate_subject` | Where the face is in a clip |
| `list_formats` | Per-platform specs, filterable by `orientation` |
| `render_for` / `render_status` | Render with the platform's specs, and its progress |
| `transcribe_timeline` | What is said, in **timeline** seconds (respects every cut). Local Whisper, GPU or CPU: works on Free. Returns `cuts_s`/`hits_s` for `apply_motion` |
| `add_captions` | Burned-in captions from the speech, inside the safe zone. Works on Free (no Studio AI) |
| `add_text_overlay` | On-screen text with emoji (hook, POV, labels) for an exact time range |
| `find_highlights` | Ranks the best moments of a long clip by motion + audio |
| `assemble_timeline` | Builds a timeline from source ranges (a cut list), optionally at a platform resolution |

Errors return a stable `code` (`RESOLVE_UNREACHABLE`, `NO_TIMELINE`, `CLIP_NOT_FOUND`, `MISSING_DEPENDENCY`...) plus a `hint`.
Read-only resources: `resolve://status`, `resolve://timeline`, `forge://formats`, `forge://styles`.

Technical details: [docs/architecture.md](docs/architecture.md).

## Motion styles

| Style | Effect | Best for |
|---|---|---|
| `tiktok_punch` | Hard 1.00↔1.15 jump-zooms every 2.5–3.5 s or on your cuts | Energetic vertical |
| `tiktok_smooth` | Same, but each zoom eases in over 6 frames | Educational vertical, Stories |
| `vlog_mix` | Push + punch-ins + handheld | Vertical vlogs |
| `youtube_dynamic` | Subtle push + a punch every 6–9 s | Horizontal talking head |
| `warm_push` / `warm_pull` | Slow, continuous eased push-in/out | Testimonials, emotional moments, endings |
| `emphasis` | Zoom bump on key words (`hits_s`) | Numbers, punchlines |
| `handheld` | Organic ±0.4° rotation with a safety zoom | Overly rigid tripod shots |

`intensity` goes from 0.5 (subtle) to 1.5 (aggressive). Zooms are anchored to the face so the subject never "jumps".

## Platforms

14 formats: tiktok, reels, facebook_reels, shorts, stories, snapchat, feed_4x5, square, youtube_1080,
youtube_4k, facebook_1080, linkedin_1080, x_1080 and web_1080. The full table with resolution, codec, bitrate,
LUFS and safe zones is generated from code:
[.agents/skills/resolve-delivery/references/platforms.md](.agents/skills/resolve-delivery/references/platforms.md).

<a id="testing"></a>

## Tests

```powershell
cd mcp/resolve-forge
uv run pytest            # 198 tests without Resolve: domain, backends, every tool on Free/Studio/R19, stdio, workspace
uv run pytest -m live    # end-to-end against your open Resolve (Free or Studio)
```

The `live` tests create a temporary `forge_live_*` project and generate synthetic clips. They apply motion through
both backends, render, and **compare pixels** (large difference with motion, near zero after `clear_motion`).
Then they build a 9:16 version, render it, check it is 1080×1920, delete the project and reopen yours.
The upstream MCP is exercised live too.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Cannot reach DaVinci Resolve` | Open a project. Free: Workspace → Scripts → resolve_bridge. Studio: Local scripting. Then run `resolve-forge-doctor` |
| No *Scripts* under Workspace | You must be inside a project, not the Project Manager. If you just installed, restart Resolve |
| Render refused on Free | Use a folder inside `~/Movies`, or add it to `allowed_output_roots` in the bridge's `bridge.json` |
| Media import refused on Free | Media must live inside your user profile (not `AppData\Temp`) |
| Motion uses `fusion`, not `keyframes` | Normal on Free 21.0.4: same result, verified at render time. The node is called `ForgeMotion` |
| H.265 comes out as H.264 | Your edition or GPU lacks H.265; the fallback to H.264 is automatic |
| The agent doesn't see the tools | Open the agent inside `davinci-agents/` and approve `.mcp.json`. If you moved the folder, run `uv run --no-project python scripts/sync.py` |

## Improving the other MCPs

We didn't only borrow ideas. We downloaded the seven public Resolve MCPs, reviewed them and **fixed real bugs in
their code**. Each bug was reproduced first and verified after, on Windows 11 + Resolve 21.0.4. The fixes are
`git format-patch` files in [`patches/`](patches), ready to send upstream as pull requests:

| Repo | What we fixed |
|---|---|
| samuelgursky | Bridge installer crashed on cp1252 Windows consoles (the step Free users run) |
| hiteshK03 | `transcribe_timeline` returned the first clip's source times; transcription crashed on recent PyAV; breaks with mcp 2.x |
| DigitalWorkflowCompany | macOS-only paths (now Windows/Linux too), Windows venv segfault, misleading errors, mcp 2.x |
| apvlv | Segfault on start on Windows, unrestricted `execute_python`/`execute_lua` (now opt-in, isolated), mcp 2.x |
| kerwilgil | Could not be installed with uv (conflicting extras), plain `pytest` broken, undefined name |
| lordhoell | Segfault on connect on Windows, `comp_lock` render trap documented, mcp 2.x |

From a clean clone, all 6 patches apply on the pinned commits and **97 tests pass** (theirs plus the ones we added):

```powershell
python scripts/references.py fetch   # vendor/<repo> at the pinned commit + our patches
python scripts/references.py test
```

Full review with evidence: [docs/mcp-reviews.md](docs/mcp-reviews.md). Tooflex has no license, so it gets a
written review only.

## Credits and what we improved

`resolve-forge` is original code. It runs next to
[samuelgursky/davinci-resolve-mcp](https://github.com/samuelgursky/davinci-resolve-mcp) (MIT): we use its
in-app bridge for the Free edition and its catalogue of verified API quirks, but we don't copy it into this repo
(bootstrap clones it). Ideas studied in the other public Resolve MCPs, and how we took them further:

| Source | Their idea | Our version |
|---|---|---|
| [hiteshK03](https://github.com/hiteshK03/davinci-resolve-mcp) | Local Whisper as the Free-edition replacement for Studio's AI | Their `transcribe_timeline` returns the **first clip's source** times. Ours maps every clip into **timeline** seconds (respects the edit), runs Whisper in an isolated worker (GPU→CPU fallback, no DLL deadlock), caches it, turns it into `cuts_s`/`hits_s` for motion, and **burns captions on Free** (`add_captions`) |
| [DigitalWorkflowCompany](https://github.com/DigitalWorkflowCompany/resolve-mcp), [Tooflex](https://github.com/Tooflex/davinci-resolve-mcp) | MCP resources for readable state; composite workflows | Resources run on the dedicated Resolve thread (never block stdio) and return typed errors. Composite tools are editorial: `find_highlights` → `assemble_timeline` → `apply_motion` → `add_captions` |
| [kerwilgil](https://github.com/kerwilgil/davinci-resolve-mcp) | Layered architecture, typed errors | Every error has a stable `code` and a `hint`; pure `domain/` with no Resolve dependency |
| [Tooflex](https://github.com/Tooflex/davinci-resolve-mcp) | Probe the native module before using it | Probe in a **child process**, plus the `PYTHONHOME` fix that stops `fusionscript.dll` from segfaulting inside a venv |
| [lordhoell](https://github.com/lordhoell/davinci-resolve-mcp) | Animate Fusion inputs with `BezierSpline` | Bridge-safe: dense `SetInput` samples outside `comp.Lock()`, verified at render time with a pixel diff |

## Repository layout

```
davinci-agents/
├── AGENTS.md · CLAUDE.md · GEMINI.md   instructions for any agent
├── .agents/skills/  .agents/agents/    skills and agents (single source)
├── config/mcp.servers.json             single source for MCP servers → scripts/sync.py
├── mcp/resolve-forge/                  our MCP (domain / services / tools / gateway) + tests
├── config/references.json             the 7 third-party MCPs: url, pinned commit, license, tests
├── patches/<repo>/                     our fixes to them (git format-patch) → scripts/references.py
├── vendor/                             those MCPs, fetched + patched (not versioned)
├── scripts/bootstrap.ps1 · sync.py     installation and config generation
└── docs/                               first steps, install, architecture, landscape, playbook
```

---

<a id="español"></a>

# Español

Edita video en **DaVinci Resolve** hablándole a un agente de IA. Hay dos editores especializados:

- **vertical-editor**: TikTok, Instagram Reels, Facebook Reels, YouTube Shorts, Stories, Snapchat y feed 4:5.
- **horizontal-editor**: YouTube 1080p/4K, Facebook, LinkedIn, X, web/Vimeo, cursos y podcasts.

Ambos saben **dar vida a las personas en plano** (punch-ins, zooms suaves, énfasis, handheld), convertir entre
vertical y horizontal sin perder la cara, y exportar con las specs de cada plataforma.

Funciona igual en **Resolve Free y Studio** (probado en vivo en Free 21.0.4) y con cualquier agente:
Claude Code, Codex, Cursor, Gemini CLI y VS Code.

> ¿Primera vez? Ve directo a **[docs/FIRST-STEPS.md](docs/FIRST-STEPS.md)**: en 10 minutos tienes tu primer video editado.

---

## Contenido

1. [Qué hay dentro](#qué-hay-dentro)
2. [Requisitos](#requisitos)
3. [Instalación](#instalación)
4. [Conectar Resolve (Free o Studio)](#conectar-resolve-free-o-studio)
5. [Uso diario](#uso-diario)
6. [Agentes y skills](#agentes-y-skills)
7. [Tools de resolve-forge](#tools-de-resolve-forge)
8. [Estilos de movimiento](#estilos-de-movimiento)
9. [Plataformas](#plataformas)
10. [Tests](#tests-1)
11. [Problemas comunes](#problemas-comunes)
12. [Mejoras a los otros MCPs](#mejoras-a-los-otros-mcps)
13. [Créditos y qué mejoramos](#créditos-y-qué-mejoramos)
14. [Estructura del repo](#estructura-del-repo)

---

## Qué hay dentro

| Pieza | Qué hace |
|---|---|
| **`resolve-forge`** (MCP propio) | Edición por intención: movimiento para talking heads, versiones por plataforma (vertical ↔ horizontal), render con specs, subtítulos y textos en Free, transcripción, highlights y armado. 16 tools + 4 resources |
| **`davinci-resolve`** (MCP upstream, [samuelgursky](https://github.com/samuelgursky/davinci-resolve-mcp)) | Toda la API de Resolve: media pool, markers, color, Fairlight, Fusion, transcripción, análisis. 37 tools |
| **Agentes** | `vertical-editor`, `horizontal-editor` y `video-director` (coordina a los dos) |
| **Skills** | `vertical-video`, `horizontal-video`, `dynamic-zoom-talking-head`, `resolve-delivery`, `davinci-resolve-mcp` |
| **Doctor** | `resolve-forge-doctor`: revisa toda la cadena y dice el siguiente paso |

Por qué hay dos MCPs, y la comparación con los otros 5 que existen: [docs/mcp-landscape.md](docs/mcp-landscape.md).

## Requisitos

- Windows 10/11 (macOS/Linux deberían funcionar, pero no están probados)
- DaVinci Resolve **20 o 21**, Free o Studio
  - Free **21.1+**: Blackmagic movió el scripting Python a Studio, así que el bridge Python no aparece en el menú
- [uv](https://docs.astral.sh/uv/) (instala Python 3.12 por su cuenta)
- git
- Opcional: ffmpeg (silencios y loudness en el upstream)

## Instalación

```powershell
git clone https://github.com/robgallardof/davinci-resolve-mcp.git davinci-agents
cd davinci-agents
powershell -NoProfile -ExecutionPolicy Bypass -File scriptsootstrap.ps1   # upstream + venv + bridge + forge + configs
```

`bootstrap.ps1` hace todo esto (es idempotente: puedes repetirlo):

1. Descarga el MCP upstream en su commit fijado dentro de `vendor/`, aplica nuestro patch (`scripts/references.py`)
   y crea su venv con Python 3.12.
2. Instala el **bridge** dentro de Resolve (Workspace → Scripts → `resolve_bridge`). Es lo que permite usar la versión Free.
3. Instala `resolve-forge` con detección de caras (opencv) y corre los tests.
4. Ejecuta `scripts/sync.py`, que genera los configs MCP de cada agente y los links de skills y agentes.

Comprobación:

```powershell
cd mcp/resolve-forge
uv run resolve-forge-doctor
```

## Conectar Resolve (Free o Studio)

| | Free | Studio |
|---|---|---|
| Una vez | Nada extra (el bootstrap ya instaló el bridge). Reinicia Resolve tras instalar | Preferences → System → General → *External scripting using* = **Local** |
| Cada vez que abres Resolve | Abre un proyecto → **Workspace → Scripts → resolve_bridge** | Nada |
| Conexión | `bridge` | `direct` (o `bridge`, si lo arrancas) |

El doctor te dice exactamente qué falta.

## Uso diario

1. Abre Resolve con tu proyecto (y en Free, arranca el bridge).
2. Abre tu agente **dentro de la carpeta `davinci-agents`**:
   - Claude Code: `claude` (aprueba los servidores de `.mcp.json` la primera vez)
   - Codex: `codex` · Cursor / VS Code: abre la carpeta · Gemini CLI: `gemini`
3. Pide en lenguaje natural:

```text
Este podcast se ve estático. Dale movimiento estilo YouTube, suave, con énfasis en 0:42, 1:15 y 2:03.
Haz una versión Reels del timeline actual con punch-ins al inicio de cada frase y expórtala.
Del master saca versiones para TikTok, Shorts y LinkedIn 16:9.
Tengo un vertical de TikTok: conviértelo a 16:9 para YouTube con la cara centrada.
```

Los archivos salen en `~/Movies/resolve-forge/` (en Free, el bridge solo escribe dentro de `~/Movies`).

## Agentes y skills

Son portables: `.agents/` es la fuente única (estándar [AGENTS.md](https://agents.md) + [Agent Skills](https://agentskills.io)).
Claude Code los ve vía `.claude/` (links), y Codex, Cursor y Gemini leen `AGENTS.md` y `.agents/skills`.

| Agente | Cuándo | Skills |
|---|---|---|
| `vertical-editor` | 9:16 / 4:5: TikTok, Reels, FB Reels, Shorts, Stories, Snapchat, feed | `vertical-video`, `dynamic-zoom-talking-head`, `resolve-delivery`, `davinci-resolve-mcp` |
| `horizontal-editor` | 16:9: YouTube, Facebook, LinkedIn, X, web, cursos, podcasts | `horizontal-video`, `dynamic-zoom-talking-head`, `resolve-delivery`, `davinci-resolve-mcp` |
| `video-director` | Pedidos que mezclan orientaciones o varias entregas | Delega en los dos anteriores |

## Tools de resolve-forge

| Tool | Qué hace |
|---|---|
| `forge_status` | Edición (Free/Studio), conexión, versión, proyecto, timeline, fps, resolución y backends |
| `list_clips` | Clips de una pista con índice, inicio, duración y zoom |
| `list_styles` / `preview_motion` | Catálogo de estilos y simulación sin tocar Resolve |
| `apply_motion` | Anima clips: estilo, cortes/énfasis en segundos, intensidad, ancla (cara/centro/punto) |
| `clear_motion` | Quita la animación de forge |
| `make_platform_version` | Duplica el timeline a cualquier formato (vertical ↔ horizontal) con el sujeto en cuadro |
| `locate_subject` | Dónde está la cara en un clip |
| `list_formats` | Specs por plataforma, filtrables por `orientation` |
| `render_for` / `render_status` | Render con las specs de la plataforma y su estado |
| `transcribe_timeline` | Lo que se dice, en segundos del **timeline** (respeta cada corte). Whisper local en GPU o CPU: funciona en Free. Devuelve `cuts_s`/`hits_s` para `apply_motion` |
| `add_captions` | Subtítulos quemados a partir de la voz, dentro de la safe zone. Funciona en Free (sin la IA de Studio) |
| `add_text_overlay` | Texto en pantalla con emoji (hook, POV, etiquetas) con duración exacta |
| `find_highlights` | Ordena los mejores momentos de un clip largo por movimiento y audio |
| `assemble_timeline` | Arma un timeline desde rangos de la fuente (lista de cortes), opcionalmente a la resolución de una plataforma |

Los errores devuelven un `code` estable (`RESOLVE_UNREACHABLE`, `NO_TIMELINE`, `CLIP_NOT_FOUND`, `MISSING_DEPENDENCY`...) y un `hint`.
Resources de solo lectura: `resolve://status`, `resolve://timeline`, `forge://formats`, `forge://styles`.

Detalle técnico: [docs/architecture.md](docs/architecture.md).

## Estilos de movimiento

| Estilo | Efecto | Ideal para |
|---|---|---|
| `tiktok_punch` | Saltos de zoom duros 1.00↔1.15 cada 2.5–3.5 s o en tus cortes | Vertical energético |
| `tiktok_smooth` | Igual, pero cada zoom entra con ease de 6 frames | Vertical educativo, Stories |
| `vlog_mix` | Push + punch-ins + handheld | Vlogs verticales |
| `youtube_dynamic` | Push sutil + punch cada 6–9 s | Talking head horizontal |
| `warm_push` / `warm_pull` | Push-in/out lento y continuo con ease | Testimonios, momentos emotivos, cierres |
| `emphasis` | Golpe de zoom en palabras clave (`hits_s`) | Datos, remates |
| `handheld` | Rotación orgánica ±0.4° con zoom de seguridad | Trípodes demasiado rígidos |

`intensity` va de 0.5 (sutil) a 1.5 (agresivo). Los zooms se anclan a la cara para que el sujeto no "salte".

## Plataformas

14 formatos: tiktok, reels, facebook_reels, shorts, stories, snapchat, feed_4x5, square, youtube_1080,
youtube_4k, facebook_1080, linkedin_1080, x_1080 y web_1080. Tabla completa con resolución, codec, bitrate, LUFS y
safe zones: [.agents/skills/resolve-delivery/references/platforms.md](.agents/skills/resolve-delivery/references/platforms.md)
(se genera desde el código).

## Tests

```powershell
cd mcp/resolve-forge
uv run pytest            # 198 tests sin Resolve: dominio, backends, todas las tools en Free/Studio/R19, stdio, workspace
uv run pytest -m live    # end-to-end contra tu Resolve abierto (Free o Studio)
```

Los tests `live` crean un proyecto temporal `forge_live_*` y generan clips sintéticos. Aplican motion por los dos
backends, renderizan y **comparan píxeles** (con movimiento la diferencia es alta, tras `clear_motion` es casi 0).
Después hacen una versión 9:16, la renderizan, verifican 1080×1920, borran el proyecto y vuelven a abrir el tuyo.
Además se prueba el MCP upstream en vivo.

## Problemas comunes

| Síntoma | Solución |
|---|---|
| `Cannot reach DaVinci Resolve` | Abre un proyecto. Free: Workspace → Scripts → resolve_bridge. Studio: scripting Local. Luego `resolve-forge-doctor` |
| No aparece *Scripts* en Workspace | Tienes que estar dentro de un proyecto, no en el Project Manager. Si instalaste recién, reinicia Resolve |
| Render rechazado en Free | Usa una carpeta dentro de `~/Movies`, o agrégala en `allowed_output_roots` del `bridge.json` del bridge |
| Import de media rechazado en Free | La media tiene que estar dentro de tu perfil de usuario (no en `AppData\Temp`) |
| Motion usa `fusion` y no `keyframes` | Normal en Free 21.0.4: el resultado es el mismo y está verificado al render. El nodo se llama `ForgeMotion` |
| H.265 sale como H.264 | Tu edición o GPU no soporta H.265; la caída a H.264 es automática |
| El agente no ve las tools | Abre el agente dentro de `davinci-agents/` y aprueba `.mcp.json`. Si moviste la carpeta, ejecuta `uv run --no-project python scripts/sync.py` |

## Mejoras a los otros MCPs

No solo tomamos ideas. Descargamos los siete MCPs públicos de Resolve, los revisamos y **arreglamos bugs reales en
su código**. Cada bug se reprodujo primero y se verificó después, en Windows 11 con Resolve 21.0.4. Los arreglos son
archivos `git format-patch` en [`patches/`](patches), listos para enviar upstream como pull requests:

| Repo | Qué arreglamos |
|---|---|
| samuelgursky | El instalador del bridge crasheaba en consolas Windows cp1252 (el paso que corren los usuarios de Free) |
| hiteshK03 | `transcribe_timeline` devolvía tiempos de la fuente del primer clip; la transcripción crasheaba con PyAV reciente; se rompe con mcp 2.x |
| DigitalWorkflowCompany | Rutas solo de macOS (ahora también Windows/Linux), segfault en venv de Windows, errores engañosos, mcp 2.x |
| apvlv | Segfault al arrancar en Windows, `execute_python`/`execute_lua` sin restricción (ahora opt-in y aislados), mcp 2.x |
| kerwilgil | No se podía instalar con uv (extras en conflicto), `pytest` a secas no funcionaba, nombre indefinido |
| lordhoell | Segfault al conectar en Windows, trampa de render de `comp_lock` documentada, mcp 2.x |

Desde un clon limpio, los 6 patches aplican sobre los commits fijados y **pasan 97 tests** (los suyos más los que
agregamos):

```powershell
python scripts/references.py fetch   # vendor/<repo> en el commit fijado + nuestros patches
python scripts/references.py test
```

Revisión completa con evidencia: [docs/mcp-reviews.md](docs/mcp-reviews.md). Tooflex no tiene licencia, así que
solo recibe una revisión escrita.

## Créditos y qué mejoramos

`resolve-forge` es código propio. Corre junto a
[samuelgursky/davinci-resolve-mcp](https://github.com/samuelgursky/davinci-resolve-mcp) (MIT): usamos su bridge
in-app para la versión Free y su catálogo de quirks verificados de la API, pero no lo copiamos en este repo
(lo clona el bootstrap). Ideas estudiadas en los otros MCPs públicos de Resolve, y cómo las llevamos más lejos:

| Fuente | Su idea | Nuestra versión |
|---|---|---|
| [hiteshK03](https://github.com/hiteshK03/davinci-resolve-mcp) | Whisper local como reemplazo de la IA de Studio en Free | Su `transcribe_timeline` devuelve tiempos **de la fuente del primer clip**. El nuestro mapea cada clip a segundos del **timeline** (respeta el corte), corre Whisper en un worker aislado (GPU→CPU, sin deadlock de DLLs), cachea, lo convierte en `cuts_s`/`hits_s` para el movimiento y **quema subtítulos en Free** (`add_captions`) |
| [DigitalWorkflowCompany](https://github.com/DigitalWorkflowCompany/resolve-mcp), [Tooflex](https://github.com/Tooflex/davinci-resolve-mcp) | Resources MCP con estado legible; workflows compuestos | Los resources corren en el hilo dedicado de Resolve (nunca bloquean stdio) y devuelven errores tipados. Las tools compuestas son editoriales: `find_highlights` → `assemble_timeline` → `apply_motion` → `add_captions` |
| [kerwilgil](https://github.com/kerwilgil/davinci-resolve-mcp) | Arquitectura por capas, errores tipados | Cada error tiene `code` estable y `hint`; `domain/` puro sin dependencia de Resolve |
| [Tooflex](https://github.com/Tooflex/davinci-resolve-mcp) | Revisar el módulo nativo antes de usarlo | Sonda en un **subproceso**, más el arreglo de `PYTHONHOME` que evita el segfault de `fusionscript.dll` dentro de un venv |
| [lordhoell](https://github.com/lordhoell/davinci-resolve-mcp) | Animar inputs de Fusion con `BezierSpline` | Compatible con el bridge: muestras densas de `SetInput` fuera de `comp.Lock()`, verificadas al render con diferencia de píxeles |

## Estructura del repo

```
davinci-agents/
├── AGENTS.md · CLAUDE.md · GEMINI.md   instrucciones para cualquier agente
├── .agents/skills/  .agents/agents/    skills y agentes (fuente única)
├── config/mcp.servers.json             fuente única de MCPs → scripts/sync.py
├── mcp/resolve-forge/                  MCP propio (domain / services / tools / gateway) + tests
├── config/references.json             los 7 MCPs de terceros: url, commit fijado, licencia, tests
├── patches/<repo>/                     nuestros arreglos a ellos (git format-patch) → scripts/references.py
├── vendor/                             esos MCPs, descargados y parchados (no se versiona)
├── scripts/bootstrap.ps1 · sync.py     instalación y generación de configs
└── docs/                               first steps, instalación, arquitectura, panorama, playbook
```
