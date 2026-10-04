# davinci-agents

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
10. [Tests](#tests)
11. [Problemas comunes](#problemas-comunes)
12. [Estructura del repo](#estructura-del-repo)

---

## Qué hay dentro

| Pieza | Qué hace |
|---|---|
| **`resolve-forge`** (MCP propio) | Edición por intención: movimiento para talking heads, versiones por plataforma (vertical ↔ horizontal), render con specs. 11 tools |
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
git clone <este repo> davinci-agents      # o copia la carpeta
cd davinci-agents
pwsh scripts/bootstrap.ps1                # upstream + venv + bridge en Resolve + forge + configs
```

`bootstrap.ps1` hace todo esto (es idempotente: puedes repetirlo):

1. Clona el MCP upstream en `vendor/` y crea su venv con Python 3.12.
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
uv run pytest            # 132 tests sin Resolve: dominio, backends, todas las tools en Free/Studio/R19, stdio, workspace
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
| El agente no ve las tools | Abre el agente dentro de `davinci-agents/` y aprueba `.mcp.json`. Si moviste la carpeta, ejecuta `python scripts/sync.py` |

## Estructura del repo

```
davinci-agents/
├── AGENTS.md · CLAUDE.md · GEMINI.md   instrucciones para cualquier agente
├── .agents/skills/  .agents/agents/    skills y agentes (fuente única)
├── config/mcp.servers.json             fuente única de MCPs → scripts/sync.py
├── mcp/resolve-forge/                  MCP propio (domain / services / tools / gateway) + tests
├── vendor/                             upstream MCP (se ejecuta) + 6 MCPs de referencia
├── scripts/bootstrap.ps1 · sync.py     instalación y generación de configs
└── docs/                               first steps, instalación, arquitectura, panorama, playbook
```
