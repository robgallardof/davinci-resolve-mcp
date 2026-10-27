<a id="top"></a>

<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/banner-es-dark.svg">
  <img src="assets/readme/banner-es-light.svg" alt="davinci-resolve-mcp — Edita en DaVinci Resolve hablando con un productor de IA" width="100%">
</picture>

<br/>

[![tests](https://github.com/robgallardof/davinci-resolve-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/robgallardof/davinci-resolve-mcp/actions/workflows/tests.yml)
![python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-65%20herramientas-8A2BE2)
![Resolve](https://img.shields.io/badge/DaVinci%20Resolve-Free%20y%20Studio-233A51)
![SO](https://img.shields.io/badge/Windows%20·%20macOS%20·%20Linux-555)

[English](README.md) · **Español**

</div>

<p align="center">
<a href="#-qué-lo-hace-distinto"><img src="https://img.shields.io/badge/Qu%C3%A9%20lo%20hace%20distinto-6D28D9?style=for-the-badge" alt="Qué lo hace distinto" /></a>
<a href="#-inicio-rápido"><img src="https://img.shields.io/badge/Inicio%20r%C3%A1pido-5B21B6?style=for-the-badge" alt="Inicio rápido" /></a>
<a href="#-qué-hace"><img src="https://img.shields.io/badge/Qu%C3%A9%20hace-4F46E5?style=for-the-badge" alt="Qué hace" /></a>
<a href="#-herramientas-65"><img src="https://img.shields.io/badge/Herramientas%20%2865%29-4338CA?style=for-the-badge" alt="Herramientas (65)" /></a>
<a href="#-roles-y-skills"><img src="https://img.shields.io/badge/Roles%20y%20skills-2563EB?style=for-the-badge" alt="Roles y skills" /></a>
<a href="#-pídelo-como-a-un-editor"><img src="https://img.shields.io/badge/P%C3%ADdelo%20como%20a%20un%20editor-0284C7?style=for-the-badge" alt="Pídelo como a un editor" /></a>
<a href="#-arquitectura"><img src="https://img.shields.io/badge/Arquitectura-0EA5E9?style=for-the-badge" alt="Arquitectura" /></a>
<a href="#-verificación"><img src="https://img.shields.io/badge/Verificaci%C3%B3n-0891B2?style=for-the-badge" alt="Verificación" /></a>
</p>

<a id="-qué-lo-hace-distinto"></a>
## <img src="assets/readme-builder/icons/layers.svg" width="24" height="24" alt="" /> Qué lo hace distinto

| | |
|---|---|
| <img src="assets/readme-builder/icons/target.svg" width="20" height="20" alt="" /> **Intención, no botones** | "Haz una versión Reels con movimiento y subtítulos con mi color de marca" → reencuadre, movimiento, subtítulos, exportación. |
| <img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> **Mira antes de cortar** | Hojas de contacto de lo que muestra cada plano (caras, sujeto, textos) antes de armar, y del archivo final después. Los zooms malos se corrigen solos. |
| <img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> **Criterio de productor por género** | En comedia respeta la pausa antes del remate; en música corta en la frase; en entrevistas sigue a quien habla. |
| <img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> **Funciona en Resolve Free** | Bridge propio (HMAC, anti-replay, lista explícita de métodos) para la versión gratuita; scripting directo en Studio. |
| <img src="assets/readme-builder/icons/shield.svg" width="20" height="20" alt="" /> **Seguro por defecto** | Trabaja en copias, previsualiza con `dry_run=true`, guarda antes de renderizar y nunca borra medios ni proyectos. |
| <img src="assets/readme-builder/icons/spark.svg" width="20" height="20" alt="" /> **Cualquier agente** | Claude Code, Codex, Antigravity, Cursor, Gemini CLI, VS Code, Windsurf, Claude Desktop; el servidor incluye sus skills (`skill://…`) y roles de editor (prompts). |

<a id="-inicio-rápido"></a>
## <img src="assets/readme-builder/icons/rocket.svg" width="24" height="24" alt="" /> Inicio rápido

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1   # Windows
```
```sh
sh scripts/bootstrap.sh                                                     # macOS / Linux
```

El bootstrap instala Python 3.12, **resolve-forge**, los extras de voz y visión, ffmpeg, el bridge para Free, las
configs de cada cliente y registra el MCP para tu usuario en cada cliente instalado.

1. **Resolve Free 21.0.x**: abre un proyecto → *Workspace → Scripts → resolve_bridge* (cada vez que abres Resolve).
   **Studio**: *Preferences → System → General → External scripting using = Local*.
2. Pide a tu agente `forge_status`.
3. Háblale como a un editor. ¿Primera vez? → [Primeros pasos](docs/FIRST-STEPS.md).

### Instalar el MCP para tu usuario (cualquier cliente)

```powershell
python scripts/install-mcp.py --list         # qué clientes tienes
python scripts/install-mcp.py --with-skills  # Claude Code, Codex, Antigravity, Cursor, VS Code, Gemini, Windsurf, Claude Desktop
python scripts/install-mcp.py --remove       # deshacer (cada archivo editado se respalda como .bak)
```

### Conecta tu agente

Elige OpenCode o DeepSeek Harness para trabajar con este servidor desde tu agente. Primero revisa los cambios; después aplica la configuración.

```sh
python scripts/install-mcp.py --clients opencode --dry-run
python scripts/install-mcp.py --clients opencode
opencode mcp list
```

<details>
<summary>Usar DeepSeek Harness en su lugar</summary>

```sh
python scripts/install-mcp.py --clients deepseek --dry-run
python scripts/install-mcp.py --clients deepseek
dsh web --patch .dsh/mcp.cordis.yml
```

</details>

[Configuración, retirada y versiones comprobadas](scripts/CLIENTS.md).

### Docker (opcional)

¿Prefieres no instalar Python? La imagen es solo el servidor MCP; Resolve y su bridge siguen en tu PC y el contenedor
llega al bridge por `host.docker.internal` (Linux: `--network host`). Los medios se montan en `/media` y
`FORGE_PATH_MAP` los traduce a la ruta que usa Resolve.

```bash
docker build -t resolve-forge:local .
export RESOLVE_FORGE_MCP_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export FORGE_MEDIA='C:/Users/yo/Movies'
export RESOLVE_FORGE_PORT=8767
docker compose up -d --build --wait   # HTTP; Linux usa el override de docs/docker.md
```

Configuración stdio para tu cliente, variables y límites: [docs/docker.md](docs/docker.md) (en inglés).

<a id="-qué-hace"></a>
## <img src="assets/readme-builder/icons/layers.svg" width="24" height="24" alt="" /> Qué hace

- **Edición**: movimiento para gente hablando a cámara, versiones verticales/horizontales, mejores momentos,
  transcripción local, subtítulos animados con diseño (Creator / Studio / Editorial / Impact, karaoke), textos y entrega.
- **Ritmo para entretenimiento**: encuentra la acción (mascotas, manos, saltos), caras y tiempos muertos; rearma planos
  largos en planos de 1.2–2.8 s con encuadres abiertos, x1.25, x1.5 y crash zoom centrados en el sujeto, respetando
  pausas, acción y B-roll útil.
- **Autorrevisión**: antes de armar, qué muestra cada plano, problemas marcados, textos fuera de las caras y
  exposición/color con un CDL suave; después del render, hoja del archivo final con detección de negros y congelados.
- **Varias personas**: encuadra a quien habla (caras + boca + voz) o divide la pantalla para 2–5+ personas.
- **Composición multifuente**: mosaicos (1–5 paneles) o principal + apoyo con videos y fotos distintos, un solo audio maestro.
- **Producción por género**: comedia, música, electrónica, entrevista, cine, educación, producto, gaming y vlog;
  remates y reacciones; cortes al beat y por frase; videoclips y visualizadores; letra exacta; efectos con intención;
  música de fondo que baja bajo la voz.
- **Productor y especialistas**: `plan_production` convierte un encargo en órdenes para composición, audio, color,
  títulos y QA; proponen, y solo el productor escribe en Resolve, en serie.
- **Acabado**: presets de color y LUTs en copias; mejora de diálogo a WAV nuevos con medición LUFS/true peak.
- **Autoría**: proyectos y respaldos, bins y metadatos, ediciones versionadas, marcadores, intercambio, CDL/LUT,
  stills, Fusion, silencios/escenas/sincronía/loudness, IA nativa y QC.

La lista completa de las **65 herramientas** está en el [README en inglés](README.md#-tools-65-tools).

<a id="-pídelo-como-a-un-editor"></a>
## <img src="assets/readme-builder/icons/layers.svg" width="24" height="24" alt="" /> Pídelo como a un editor

> *"Haz una versión Reels con movimiento y subtítulos bonitos con mi color de marca."*
> *"Es un stand-up: encuentra los remates y arma un TikTok sin cortar las pausas."*
> *"Del podcast horizontal haz un Reel que siga a quien habla."*
> *"Combina la entrevista con estas fotos como en esta referencia."*

Combínalo con [social-publisher-mcp](https://github.com/robgallardof/social-publisher-mcp): renderiza aquí, programa allá.

<a id="-roles-y-skills"></a>
## <img src="assets/readme-builder/icons/layers.svg" width="24" height="24" alt="" /> Roles y skills

| Rol | Trabajo |
|---|---|
| `video-director` | Productor: encargo, referencias, delegación, ejecución en serie, QA final |
| `vertical-editor` / `horizontal-editor` | Editores completos para 9:16–4:5 y 16:9 |
| `composition-editor`, `audio-editor`, `colorist`, `titles-editor`, `qa-editor` | Especialistas que analizan y proponen al productor |

**Skills:** `davinci-resolve-mcp` · `editorial-direction` · `entertainment-pacing` · `vertical-video` · `horizontal-video` ·
`dynamic-zoom-talking-head` · `captions-and-titles` · `color-audio-finishing` · `video-qa` · `resolve-delivery`.
Están en inglés para servir a cualquiera; el agente te responde en español.

<a id="-herramientas-65"></a>
## <img src="assets/readme-builder/icons/terminal.svg" width="24" height="24" alt="" /> Herramientas (65)

| Trabajo | Herramientas |
|---|---|
| Estado y planeación | forge_status, list_clips, list_styles, list_formats, preview_motion, list_capabilities, audit_timeline, open_resolve_page |
| Edición | apply_motion, clear_motion, make_platform_version, locate_subject, find_highlights, assemble_timeline |
| Voz, texto y entrega | transcribe_timeline, align_text, list_text_styles, preview_text_style, add_captions, add_text_overlay, render_for, render_status |
| Ritmo y foco (entretenimiento) | plan_energized_edit, energize_timeline |
| Autorrevisión (antes y después del render) | review_shots, review_video |
| Varias personas (podcast, entrevista) | plan_speaker_layout, build_speaker_layout |
| Composición multifuente y órdenes del productor | plan_composition, build_composition, plan_production |
| Producción por género | plan_edit, find_story_moments, analyse_music, plan_beat_cuts, assemble_montage, create_music_visualizer |
| Sonido | add_music_bed, place_sound_effects, analyse_audio, normalise_audio, sync_audio |
| Proyectos y medios | project_workflow, configure_project, list_media, ingest_media, organise_media, media_metadata |
| Timeline | timeline_versions, edit_clips, timeline_markers, configure_track, export_interchange |
| Color y Fusion | grade_clips, inspect_grade, prepare_lut, gallery_stills, apply_fusion_graph, inspect_fusion |
| Acabado y revisiones antes del render | preflight_render, apply_grade_preset, enhance_audio |
| Recuperar la conexión | repair_bridge_connection |
| Análisis e IA nativa | analyse_scenes, native_ai |

<details>
<summary>Notas sobre algunas herramientas</summary>

- `preflight_render` revisa fuentes, pistas activas, huecos y propiedades; igual hace falta una revisión visual.
- `apply_grade_preset` muestra una vista previa por defecto y aplica CDL sobre una copia. `enhance_audio` escribe un WAV
  nuevo (filtro suave, compresión y limitador) y mide LUFS/true peak; no separa voces.
- La detección de quién habla usa movimiento de boca + energía del audio: son candidatos, no diarización. Revisa los cambios.
- `build_composition` exige `reviewed=true` después de ver la hoja y la vista previa de `plan_composition`.
- `repair_bridge_connection` (Windows) solo retira un helper del bridge huérfano cuya identidad, puerto y proceso padre
  muerto se verificaron.
</details>

<a id="-arquitectura"></a>
## <img src="assets/readme-builder/icons/layers.svg" width="24" height="24" alt="" /> Arquitectura

```
mcp/resolve-forge/src/resolve_forge/
  domain/      reglas puras: encuadre, cortes, ritmo, composición, ducking, alineación, diseño de texto, formatos
  analysis/    señales (caras, movimiento, audio)       services/  casos de uso, uno por responsabilidad
  gateway · native_paths · bridge                      conexión + nuestro protocolo propio para la edición Free
  tools.py · authoring_tools.py · production_tools.py · qa_tools.py · producer_tools.py · composition_tools.py
               esquemas MCP delgados sobre un solo ejecutor en serie       server.py  raíz de composición
```

Estudiamos los MCP públicos de DaVinci Resolve y reconstruimos a nuestra manera las capacidades útiles — no se importa
ninguna implementación de la competencia. [Selección, mejoras y estado](docs/third-party-migration.md) ·
[Problemas de la API verificados](docs/api-behavior.md).

<a id="-verificación"></a>
## <img src="assets/readme-builder/icons/shield.svg" width="24" height="24" alt="" /> Verificación

```sh
cd mcp/resolve-forge
uv run pytest -q          # sin Resolve
uv run pytest -m live     # con Resolve abierto y el bridge corriendo
uv run resolve-forge-doctor
python ../../scripts/test_docker.py   # imagen opcional contra un bridge real (sin Resolve)
```

<div align="center">

[Primeros pasos](docs/FIRST-STEPS.md) · [Instalación](docs/install.md) · [Arquitectura](docs/architecture.md) ·
[Clientes](docs/clients.md) · [Manual de edición](docs/editing-playbook.md) · [Estado de migración](docs/third-party-migration.md)

</div>

<br/>

<p align="center"><a href="#top">Volver al inicio</a></p>

<!-- readme-builder:signature:start -->
<p align="center"><a href="https://github.com/robgallardof"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/readme/brand/signature-es-dark.svg" /><img src="assets/readme/brand/signature-es-light.svg" alt="Resolve Forge / Roberto Gallardo" width="100%" /></picture></a></p>
<!-- readme-builder:signature:end -->
