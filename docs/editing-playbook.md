# Playbook de edición (investigación, octubre 2026)

Resumen accionable de las fuentes consultadas. Las skills en `.agents/skills/` aplican esto.

## Retención en short-form

- Un hook que se gane el primer segundo, pattern interrupts que reseteen la atención cada pocos segundos y un loop
  que lleve el watch time por encima del 100 %. Recorta el aire inicial para llegar al hook de inmediato.
  Apila visuales (texto, overlays, B-roll) y subtitula siempre, porque gran parte se ve sin sonido.
- Duración: lo más seguro es 15–35 s; 30–60 s funciona si la idea lo necesita. "Haz que la idea se sienta completa
  lo antes posible y corta antes de que haya motivo para deslizar."
- Fuentes: [Splice — retention apps](https://spliceapp.com/blog/which-apps-enhance-viewer-retention),
  [ShortGenius — Shorts best practices](https://shortgenius.com/blog/youtube-shorts-best-practices),
  [Revid — how to edit](https://www.revid.ai/blog/how-to-make-and-edit-videos).

## Talking heads (horizontal)

- Cambia el encuadre o un elemento visual cada **3–7 s** (zoom, texto, B-roll).
- Punch-in: zoom leve sobre el A-roll en puntos importantes o cada pocas frases.
- Jump cuts + frases cortas + B-roll aceleran el ritmo. El B-roll que *muestra* lo dicho es lo que más aporta.
- No te pases: planos de < 1–3 s de forma constante saturan.
- Fuentes: [Subscribr — engaging talking heads](https://subscribr.ai/p/editing-talking-head-videos-engaging),
  [Subscribr — workflow](https://subscribr.ai/youtube-strategy/talking-head-video-editing-workflow),
  [Jupitrr — edit talking head videos](https://jupitrr.com/how-to/edit-talking-head-videos).

## Subtítulos y texto que se vean diseñados

- Sincronía por palabra y jerarquía clara: una frase estable en pantalla y la palabra activa resaltada, en vez de
  texto que salta en cada palabra. Entradas cortas (fade, lift, pop) y una sola familia tipográfica por pieza.
- Modos según el tono: Creator (cercano, Reels/TikTok), Studio (limpio, entrevistas/educación), Editorial (cálido,
  historias), Impact (solo remates y mensajes de 1–4 palabras). Color de marca como acento, no en todo el texto.
- Texto, cámara y sonido no se animan a la vez: un acento por momento.
- En Forge: `list_text_styles` → `preview_text_style` → `add_captions(style, accent, words)`; la letra o el guion
  exactos con `align_text`.
- Fuentes: [School of Motion — typography for motion](https://schoolofmotion.com/blog/fonts-typefaces-typography-for-motion-design),
  [CapCut — types of captions](https://www.capcut.com/resource/types-of-captions),
  [TikTok — creative codes](https://ads.tiktok.com/business/en-US/creative-codes).

## Criterio por género

- **Comedia**: setup → pausa → remate → reacción. La pausa es parte del chiste; se corta después de la risa, nunca
  durante el remate, y el remate no se anticipa en un título. SFX solo si suman.
- **Música / videoclip**: la canción manda y no se toca. Cortes por frases (4–8 beats), motivos visuales que vuelven en
  el estribillo; la letra con tiempos reales, no transcripción de canto.
- **Electrónica**: contraste build / drop / breakdown. Más cortes y movimiento solo en el drop confirmado al oído;
  el breakdown respira. Sin flashes a pantalla completa.
- **Entrevista / podcast**: respetar el sentido de cada respuesta y las reacciones reales; música de fondo bajo la voz
  (−20 dB al hablar) y cortes cubiertos con B-roll relevante.
- **Cine / narrativo**: cortes motivados por la historia y la dirección de pantalla, nunca por un temporizador.
- Los detectores (pausas, energía, beats) dan **candidatos con evidencia**; el editor confirma viendo o escuchando.
  Detalle operativo: skill `editorial-direction`.

## Zoom en DaVinci Resolve

- **Dynamic Zoom** (Inspector): zoom lineal o con ease sin keyframes; rápido para un push por clip.
- **Keyframes** en Zoom/Position: control total del encuadre.
- **Fusion Transform**: Size + Center/Pivot con keyframes, para curvas finas.
- Fuentes: [Ripple Training — Dynamic Zoom](https://www.rippletraining.com/blog/davinci-resolve/use-dynamic-zoom-davinci-resolve-12-5/),
  [FireCut — fastest zoom](https://firecut.ai/blog/the-fastest-way-to-zoom-in-davinci-resolve/),
  [Miracamp — resize guide](https://www.miracamp.com/learn/davinci-resolve/how-to-resize-frames-and-videos-in-davinci-resolve).

## Safe zones 1080×1920

- TikTok: 240 px arriba, 660 px abajo y 120 px a cada lado, más los botones del rail derecho.
- Reels: 269 px arriba, 672 px abajo y 65 px a los lados.
- Son cifras conservadoras (nivel ads); en orgánico el overlay tapa algo menos.
- Fuentes: [House of Marketers — safe zones](https://www.houseofmarketers.com/guide-to-safe-zones-tiktok-facebook-instagram-stories),
  [Reap — short-form safe zones](https://reap.video/blog/short-form-video-safe-zones),
  [Upload-Post — checker](https://www.upload-post.com/tools/safe-zone-checker/).

## Export y loudness

- YouTube: −14 LUFS integrado y −1 dBTP (solo baja el volumen de lo que esté más fuerte). TikTok/Reels: alrededor de −10 a −12 LUFS.
- H.264 High: 1080p a 12–16 Mbps, 4K a 35–45 Mbps, Shorts/Reels a 10–14 Mbps. 30 fps para talking head con subtítulos.
- Shorts se reproduce como máximo a 1080p.
- Fuentes: [The Post Flow — export settings](https://thepostflow.com/post-production/post-production-workflows/export-settings-youtube-instagram-tiktok/),
  [Influenceflow — specs 2026](https://influenceflow.io/resources/the-ultimate-social-media-video-specs-guide-2026-edition/).

## Portabilidad de agentes

- `AGENTS.md` estandariza el contexto de proyecto. `SKILL.md` (agentskills.io) lo leen más de 30 herramientas
  (Claude Code, Codex, Cursor, Gemini CLI…). `.agents/skills/` es la convención de interoperabilidad.
  El formato es común; las rutas de instalación y el autoload todavía varían, de ahí `scripts/sync.py`.
- Fuentes: [Agent Skills open standard (D. Vaughan)](https://codex.danielvaughan.com/2026/05/05/agent-skills-open-standard-portable-skills-codex-cli-cross-agent/),
  [mcp.directory — cross-agent skills](https://mcp.directory/blog/cross-agent-skills-cursor-codex-cline-antigravity-gemini-mastra-portability).
