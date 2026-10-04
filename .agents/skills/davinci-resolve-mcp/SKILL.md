---
name: davinci-resolve-mcp
description: "Operar DaVinci Resolve (Free o Studio) desde un agente vía MCP (resolve-forge + davinci-resolve). Úsala antes de cualquier tarea que toque Resolve — conectar, proyecto/timeline, media, edición, color, Fusion, render — para elegir el servidor y la tool correctos, arrancar el bridge en la versión Free y evitar las trampas conocidas de la API. Triggers: davinci, resolve, timeline, render, fusion, media pool, edit page."
---

# Operar DaVinci Resolve con MCP

Hay dos servidores que se usan juntos:

| Servidor | Para qué |
|---|---|
| `resolve-forge` (16 tools + 4 resources) | Intención: `apply_motion` (zooms y movimiento), `make_platform_version` (vertical ↔ horizontal), `transcribe_timeline`, `add_captions`, `add_text_overlay`, `find_highlights`, `assemble_timeline`, `render_for`, `list_formats`, `forge_status` |
| `davinci-resolve` (upstream, 37 tools) | Todo lo demás: media pool, markers, color, Fairlight, Fusion granular, transcripción, análisis |

## Arranque (siempre)

1. `forge_status` devuelve `edition` (Free/Studio), `transport` (`bridge` o `direct`), versión, timeline, fps, resolución y `native_keyframes`.
2. Si falla con "Cannot reach DaVinci Resolve":
   - Resolve tiene que estar abierto **con un proyecto** (desde el Project Manager no hay menú Workspace).
   - **Free**: Workspace → Scripts → `resolve_bridge`. Hay que repetirlo **cada vez que abres Resolve**.
   - **Studio**: Preferences → System → General → External scripting using = **Local** (o usa el bridge igual que en Free).
   - Diagnóstico completo: `cd mcp/resolve-forge && uv run resolve-forge-doctor`.
3. `list_clips` antes de mutar nada.

## Free vs Studio

| | Free (bridge) | Studio |
|---|---|---|
| Motion | Backend `fusion` (automático; los keyframes nativos no están expuestos en 21.0.4) | `keyframes` nativos si existen; si no, `fusion` |
| Reencuadre | Encuadre por cara/punto | Además `smart_reframe=true` |
| Codecs | H.264 (H.265 cae a H.264) | H.264/H.265 |
| Render | Solo dentro de `~/Movies` (raíces del bridge) | Cualquier carpeta |
| Subtítulos | `add_captions` (Whisper local, quemados en el video) | `add_captions`, o Create Subtitles from Audio de Studio |

## Errores: decide según `code`

Cada error de forge trae `code` y casi siempre `hint`. No interpretes el texto: usa el código.

| code | Qué hacer |
|---|---|
| `RESOLVE_UNREACHABLE` | Pide abrir Resolve con un proyecto (Free: arrancar `resolve_bridge`) y vuelve a intentar |
| `NO_PROJECT` / `NO_TIMELINE` | Abre o crea un proyecto o timeline (`assemble_timeline` crea uno) |
| `CLIP_NOT_FOUND` / `EMPTY_TRACK` | Vuelve a leer con `list_clips` (los índices empiezan en 1) |
| `INVALID_ARGUMENT` | Corrige el argumento (estilo, formato, ancla, rangos) |
| `TIMELINE_EXISTS` | Usa otro `name` |
| `MISSING_DEPENDENCY` | Ejecuta el `hint` (`uv sync --extra speech` o `--extra vision`) |
| `MEDIA_NOT_FOUND` / `RESOLVE_REFUSED` / `RENDER_REFUSED` | Sigue el `hint` (en Free: rutas dentro del perfil y `~/Movies`) |

Para leer estado sin tools: resources `resolve://status`, `resolve://timeline`, `forge://formats`, `forge://styles`.

## Reglas de seguridad

- No mutes el master: `make_platform_version` duplica. Para experimentos, duplica el timeline primero.
- `apply_motion` es idempotente (reemplaza su propia animación) y `clear_motion` la quita.
- Guarda el proyecto antes de renderizar. No borres media ni proyectos sin pedido explícito.

## Trampas verificadas de la API

- `DuplicateTimeline` cambia el timeline current a la copia sin avisar.
- `DeleteClips` solo funciona en la página Edit y no borra el audio enlazado.
- `AppendToTimeline`: `endFrame` es exclusivo y `recordFrame` es absoluto (el timeline suele empezar en 86400).
- `SetRenderSettings` hereda el preset cargado; un `CustomName` vacío invalida todo.
- Fusion: los valores escritos dentro de `comp.Lock()` se ignoran al render.
- Bridge (Free): todo viaja como JSON (las claves numéricas de los dicts llegan como string) y no hay indexación `tool["X"]`. Usa métodos.
- Media e import en Free: solo desde rutas dentro de las raíces del bridge (perfil del usuario; `AppData\Temp` se rechaza).
- Más quirks, con evidencia: `vendor/davinci-resolve-mcp/src/utils/api_truth.py`.

## Qué skill sigue

- Vertical (TikTok, Reels, FB Reels, Shorts, Stories, Snapchat, 4:5) → `vertical-video`
- Horizontal (YouTube, Facebook, LinkedIn, X, web) → `horizontal-video`
- Zooms y movimiento → `dynamic-zoom-talking-head`
- Export → `resolve-delivery`
- Sin MCP (scripts directos) → `references/api-cheatsheet.md`
