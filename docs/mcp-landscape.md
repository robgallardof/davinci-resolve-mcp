> Panorama histórico. Ahora se ejecuta un único MCP: resolve-forge. Véase [la integración](third-party-migration.md).

# Panorama de MCPs para DaVinci Resolve (octubre 2026)

Se revisaron los siete servidores públicos relevantes. Se consultaron como referencias de diseño. Actualmente solo se ejecuta resolve-forge; los clones locales pendientes de borrado no se utilizan.

| Repo | Tamaño / estado | Lo mejor | Lo que le falta | Qué tomamos |
|---|---|---|---|---|
| [samuelgursky/davinci-resolve-mcp](https://github.com/samuelgursky/davinci-resolve-mcp) | ~1.4k ⭐, v2.60 (jul 2026), 37 tools compuestas / 389 granulares | Cobertura total, bridge para la edición **Free**, instalador multi-cliente, `api_truth.py` con quirks verificados en vivo, análisis (transcripción, beats, silencios) | Sin motion de alto nivel: los keyframes son primitivas sueltas | Bridge y catálogo de quirks estudiados como referencia; Forge usa su propia implementación y registro de comportamientos |
| [lordhoell/davinci-resolve-mcp](https://github.com/lordhoell/davinci-resolve-mcp) | ~10k líneas, 440+ tools | API completa de Fusion: `BezierSpline`, `SetKeyFrames`, modificadores. Incluye skill | Tools 1:1 con la API (demasiadas para un agente) | Patrón `AddModifier → spline → SetKeyFrames` con handles |
| [kerwilgil/davinci-resolve-mcp](https://github.com/kerwilgil/davinci-resolve-mcp) | ~9.8k líneas, sep 2026 | Arquitectura limpia: `schemas/` + `tools/` + `bridge/` + `errors.py` | Alcance genérico | Separación por capas y errores tipados |
| [hiteshK03/davinci-resolve-mcp](https://github.com/hiteshK03/davinci-resolve-mcp) | 162 tools | Pionero del bridge in-app para Free y reemplazos locales de la IA de Studio | Mantenimiento menor (mar 2026) | Idea de "funciona en Free" como requisito |
| [DigitalWorkflowCompany/resolve-mcp](https://github.com/DigitalWorkflowCompany/resolve-mcp) | 88 tools + 20 resources, Resolve 21 | Resources MCP (estado legible) y workflows compuestos (dailies) | Solo macOS + Studio | Tools "de caso de uso" en vez de 1:1 |
| [Tooflex/davinci-resolve-mcp](https://github.com/Tooflex/davinci-resolve-mcp) | 32 tools + 6 resources | Probe protegido del módulo nativo | Básico | Comprobar el proceso antes de cargar `fusionscript` (evita el segfault) |
| [apvlv/davinci-resolve-mcp](https://github.com/apvlv/davinci-resolve-mcp) | ~1.3k líneas | Cadenas de nodos Fusion, `execute_python/lua` | Mínimo | — |

> Además de estudiarlos, les arreglamos bugs reales (segfaults en Windows, tiempos de transcripción, rutas solo de
> macOS, ejecución de código sin protección, mcp 2.x). Ver [mcp-reviews.md](mcp-reviews.md) (histórico; los patches ya se retiraron).

## Hueco que cubre `resolve-forge`

Ninguno ofrece **intención editorial**: "haz que esta persona no se vea estática", "versión TikTok de este master",
"render para Reels". Todos exponen la API y dejan al agente la matemática (zoom de cobertura, compensar Pan/Tilt
para que la cara no se mueva, easing, safe zones, offsets de comp de Fusion). `resolve-forge` encapsula eso en
tools de intención, con backends intercambiables y tests sin Resolve.

## Decisión: implementación propia

Primero se compuso con el upstream (bridge reutilizado mediante adaptador). Esa etapa terminó: Forge tiene su
propio bridge (`bridge/`, `bridge_install/`) y sus propias tools de authoring, sin código de los servidores
estudiados. Ver [third-party-migration.md](third-party-migration.md).
