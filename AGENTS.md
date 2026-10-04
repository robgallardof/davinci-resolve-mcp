# davinci-agents — instrucciones para cualquier agente

Workspace de edición de video con IA sobre **DaVinci Resolve 21** (Windows). Funciona con cualquier agente
compatible con `AGENTS.md`, Agent Skills (`SKILL.md`) y MCP: Claude Code, Codex, Cursor, Gemini CLI, VS Code, etc.

## Qué hay aquí

| Ruta | Qué es |
|---|---|
| `mcp/resolve-forge/` | MCP propio: motion para talking heads, versiones por plataforma y render. Python 3.12 + uv |
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
3. Skills: `vertical-video`, `horizontal-video`, `entertainment-pacing` (ritmo para entretener: nunca >3 s sin cambio,
   zooms con motivo), `video-qa` (mirar las hojas de revisión antes de construir y después de renderizar),
   `editorial-direction` (criterio por género: comedia, música, entrevista…),
   `dynamic-zoom-talking-head`, `resolve-delivery`, `davinci-resolve-mcp`.
4. **Calidad**: ningún video se entrega sin revisión visual (`review_shots` antes, `review_video` después).
5. **Seguridad**: nunca modifiques el master sin copia; no borres media ni proyectos sin un pedido explícito;
   guarda el proyecto antes de renderizar. En Free, renderiza dentro de `~/Movies`.

## Desarrollo de resolve-forge

- Capas: `domain/` (puro, sin Resolve) → `services/` (casos de uso + backends) → `tools.py`, `authoring_tools.py`,
  `production_tools.py` (MCP fino) → `server.py` (composición).
  `gateway.py` es lo único que sabe cómo se conecta con Resolve.
- Añadir un estilo de motion: registra una función con `@style(...)` en `domain/styles.py`. No hace falta tocar nada más.
- Añadir un backend de animación: implementa `apply`/`clear` en `services/appliers.py` y regístralo en `APPLIERS`.
- Tests: `cd mcp/resolve-forge && uv run pytest` (sin Resolve: fakes de Free/bridge, Studio y Resolve 19, stdio
  real, consistencia del workspace) y `uv run pytest -m live` (end-to-end con render y comparación de píxeles).
- Las specs de plataformas viven en `domain/formats.py`; `references/platforms.md` se genera desde ahí.
- Antes de "descubrir" un comportamiento raro de la API, búscalo en `docs/api-behavior.md`.
- Tras editar `config/` o `.agents/`, ejecuta `python scripts/sync.py`.
- Al añadir una tool: inclúyela en la tabla del README y actualiza los conteos (`test_workspace` lo comprueba),
  menciónala en la skill que corresponda y anota el avance en la sección de estado de `docs/third-party-migration.md`.
- Implementaciones propias: no copies servidores ni módulos de competidores. Mantén domain → services → tools y transportes aislados.
  Registro de procedencia y mejoras: `docs/third-party-migration.md`.
