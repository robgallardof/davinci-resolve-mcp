# Instalación y estado

Instalado el 2026-10-03 en este equipo: DaVinci Resolve **21.0.4** (Windows 11), uv 0.12, Python 3.12 (gestionado por uv).

## Qué quedó instalado

| Pieza | Dónde | Cómo se reinstala |
|---|---|---|
| Upstream MCP + venv (py 3.12) | `vendor/davinci-resolve-mcp/venv` | `scripts/bootstrap.ps1` |
| Bridge dentro de Resolve (necesario en Free) | Carpeta Scripts de Resolve (`resolve_bridge`, probe, canary) | `install_resolve_bridge.py` (lo ejecuta el bootstrap) |
| resolve-forge + opencv (detección de cara) | `mcp/resolve-forge/.venv` | `uv sync --extra vision` |
| Configs MCP por cliente | `.mcp.json`, `.cursor/`, `.vscode/`, `.gemini/`, `.codex/` | `python scripts/sync.py` |
| Skills/agentes para Claude Code | `.claude/{skills,agents}` → junctions a `.agents/` | `python scripts/sync.py` |

## Primer uso

1. Abre DaVinci Resolve y un proyecto con un timeline.
2. Conexión:
   - **Studio**: Preferences → System → General → *External scripting using* = **Local**.
   - **Free** (21.0.x): reinicia Resolve una vez tras la instalación y ejecuta **Workspace → Scripts → resolve_bridge**.
     En Resolve **21.1+ Free**, Blackmagic movió el scripting Python a Studio: el bridge Python ya no aparece (issue #203 del upstream).
3. Abre tu agente **dentro de esta carpeta** (`davinci-agents/`):
   - Claude Code: `claude`. Aprueba los servidores de `.mcp.json` cuando lo pida.
   - Codex: `codex` (lee `AGENTS.md` y `.codex/config.toml` si el proyecto es de confianza).
   - Cursor / VS Code / Gemini CLI: abren sus configs de la carpeta.
4. Pide: "forge_status" y luego, por ejemplo, "haz una versión TikTok de este timeline con punch-ins en cada frase".

## Verificado en vivo (2026-10-03, Resolve Free 21.0.4.5 vía bridge)

- `forge_status`, `list_clips`, `apply_motion` (backend `fusion`), `clear_motion`, `make_platform_version` (9:16) y
  `render_for`/`render_status` contra Resolve real.
- El render prueba los píxeles: con movimiento, la diferencia entre el primer y el último frame es ~73 (de 0 a 255);
  sin movimiento, ~1.3.
- MCP upstream: lectura de versión y proyecto actual vía stdio.
- En Free 21.0.4 los keyframes nativos del Inspector no están expuestos por el bridge: forge usa Fusion automáticamente.

## Comprobaciones

```powershell
cd mcp/resolve-forge; uv run resolve-forge-doctor                      # diagnóstico con el siguiente paso
uv run pytest -q                                 # 132 tests, sin Resolve
uv run pytest -m live                            # end-to-end con Resolve abierto
python scripts/sync.py --check                   # configs/links al día
cd vendor/davinci-resolve-mcp; .\venv\Scripts\python.exe scripts\doctor.py   # extras del upstream
```

## Extras opcionales del upstream

`ffmpeg` en el PATH (detección de silencios y loudness; ahora **no está instalado**), `openai-whisper` (transcripción),
`librosa` (beats). Instálalos en `vendor/davinci-resolve-mcp/venv` según lo que reporte `doctor.py`.
