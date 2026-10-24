<div align="center">

# 🎬 davinci-agents

**Edita en DaVinci Resolve hablando con una IA que trabaja como productor y editor profesional.**<br>
Cortes verticales y horizontales, movimiento sin cortar caras, subtítulos con diseño, música al beat,<br>
color y audio terminados — revisado antes y después de cada render.

[![tests](https://github.com/robgallardof/davinci-resolve-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/robgallardof/davinci-resolve-mcp/actions/workflows/tests.yml)
![python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-65%20herramientas-8A2BE2)
![Resolve](https://img.shields.io/badge/DaVinci%20Resolve-Free%20y%20Studio-233A51)
![SO](https://img.shields.io/badge/Windows%20·%20macOS%20·%20Linux-555)

[English](README.md) · **Español**

</div>

---

## ✨ Qué lo hace distinto

| | |
|---|---|
| 🎯 **Intención, no botones** | "Haz una versión Reels con movimiento y subtítulos con mi color de marca" → reencuadre, movimiento, subtítulos, exportación. |
| 👀 **Mira antes de cortar** | Hojas de contacto de lo que muestra cada plano (caras, sujeto, textos) antes de armar, y del archivo final después. Los zooms malos se corrigen solos. |
| 🎭 **Criterio de productor por género** | En comedia respeta la pausa antes del remate; en música corta en la frase; en entrevistas sigue a quien habla. |
| 🆓 **Funciona en Resolve Free** | Bridge propio (HMAC, anti-replay, lista explícita de métodos) para la versión gratuita; scripting directo en Studio. |
| 🛡️ **Seguro por defecto** | Trabaja en copias, previsualiza con `dry_run=true`, guarda antes de renderizar y nunca borra medios ni proyectos. |
| 🧩 **Cualquier agente** | Claude Code, Codex, Antigravity, Cursor, Gemini CLI, VS Code, Windsurf, Claude Desktop; el servidor incluye sus skills (`skill://…`) y roles de editor (prompts). |

## 🚀 Inicio rápido

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

## 🎞️ Qué hace

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

La lista completa de las **65 herramientas** está en el [README en inglés](README.md#️-tools-65-tools).

## 👥 Roles y skills

| Rol | Trabajo |
|---|---|
| `video-director` | Productor: encargo, referencias, delegación, ejecución en serie, QA final |
| `vertical-editor` / `horizontal-editor` | Editores completos para 9:16–4:5 y 16:9 |
| `composition-editor`, `audio-editor`, `colorist`, `titles-editor`, `qa-editor` | Especialistas que analizan y proponen al productor |

**Skills:** `davinci-resolve-mcp` · `editorial-direction` · `entertainment-pacing` · `vertical-video` · `horizontal-video` ·
`dynamic-zoom-talking-head` · `captions-and-titles` · `color-audio-finishing` · `video-qa` · `resolve-delivery`.
Están en inglés para servir a cualquiera; el agente te responde en español.

## 💬 Pídelo como a un editor

> *"Haz una versión Reels con movimiento y subtítulos bonitos con mi color de marca."*
> *"Es un stand-up: encuentra los remates y arma un TikTok sin cortar las pausas."*
> *"Del podcast horizontal haz un Reel que siga a quien habla."*
> *"Combina la entrevista con estas fotos como en esta referencia."*

Combínalo con [social-publisher-mcp](https://github.com/robgallardof/social-publisher-mcp): renderiza aquí, programa allá.

## 🧪 Verificación

```sh
cd mcp/resolve-forge
uv run pytest -q          # sin Resolve
uv run pytest -m live     # con Resolve abierto y el bridge corriendo
uv run resolve-forge-doctor
```

<div align="center">

[Primeros pasos](docs/FIRST-STEPS.md) · [Instalación](docs/install.md) · [Arquitectura](docs/architecture.md) ·
[Clientes](docs/clients.md) · [Manual de edición](docs/editing-playbook.md) · [Estado de migración](docs/third-party-migration.md)

</div>
