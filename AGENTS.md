# davinci-agents — instrucciones para cualquier agente

Workspace de edición de video con IA sobre **DaVinci Resolve 21** (Windows). Funciona con cualquier agente
compatible con `AGENTS.md`, Agent Skills (`SKILL.md`) y MCP: Claude Code, Codex, Cursor, Gemini CLI, VS Code, etc.

## Qué hay aquí

| Ruta | Qué es |
|---|---|
| `mcp/resolve-forge/` | MCP propio: motion para talking heads, versiones por plataforma y render. Python 3.12 + uv |
| `vendor/davinci-resolve-mcp/` | MCP upstream (samuelgursky, MIT) con cobertura total de la API. Instalado con venv propio |
| `vendor/ref-*` | Otros MCPs de Resolve clonados solo como referencia de diseño (no se ejecutan) |
| `.agents/skills/` | Skills portables (fuente canónica) |
| `.agents/agents/` | Roles/subagentes portables (fuente canónica) |
| `config/mcp.servers.json` | Fuente única de servidores MCP → `python scripts/sync.py` genera los configs de cada cliente |
| `docs/` | Instalación, arquitectura, panorama de MCPs y playbook de edición |

## Cómo trabajar

1. Antes de tocar Resolve, carga la skill `davinci-resolve-mcp` y ejecuta `forge_status`.
   Si no conecta: `cd mcp/resolve-forge && uv run resolve-forge-doctor` dice el siguiente paso
   (en Free: Workspace → Scripts → resolve_bridge, cada vez que se abre Resolve).
2. Elige el rol según la orientación del entregable:
   - **9:16 / 4:5** (TikTok, Reels, FB Reels, Shorts, Stories, Snapchat, feed) → `.agents/agents/vertical-editor.md`
   - **16:9** (YouTube, Facebook, LinkedIn, X, web) → `.agents/agents/horizontal-editor.md`
   - Ambas o varias entregas → `.agents/agents/video-director.md`
   Si tu runtime no tiene subagentes, lee el archivo del rol y síguelo tú mismo.
3. Skills: `vertical-video`, `horizontal-video`, `dynamic-zoom-talking-head`, `resolve-delivery`, `davinci-resolve-mcp`.
4. **Seguridad**: nunca modifiques el master sin copia; no borres media ni proyectos sin un pedido explícito;
   guarda el proyecto antes de renderizar. En Free, renderiza dentro de `~/Movies`.

## Desarrollo de resolve-forge

- Capas: `domain/` (puro, sin Resolve) → `services/` (casos de uso + backends) → `tools.py` (MCP fino) → `server.py` (composición).
  `gateway.py` es lo único que sabe cómo se conecta con Resolve.
- Añadir un estilo de motion: registra una función con `@style(...)` en `domain/styles.py`. No hace falta tocar nada más.
- Añadir un backend de animación: implementa `apply`/`clear` en `services/appliers.py` y regístralo en `APPLIERS`.
- Tests: `cd mcp/resolve-forge && uv run pytest` (sin Resolve: fakes de Free/bridge, Studio y Resolve 19, stdio
  real, consistencia del workspace) y `uv run pytest -m live` (end-to-end con render y comparación de píxeles).
- Las specs de plataformas viven en `domain/formats.py`; `references/platforms.md` se genera desde ahí.
- Antes de "descubrir" un comportamiento raro de la API, búscalo en `vendor/davinci-resolve-mcp/src/utils/api_truth.py`.
- Tras editar `config/` o `.agents/`, ejecuta `python scripts/sync.py`.
