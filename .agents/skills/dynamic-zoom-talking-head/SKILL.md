---
name: dynamic-zoom-talking-head
description: "Dar vida (vertical u horizontal) a planos de personas hablando (talking head, podcast, entrevista, vlog) para que no se vean estáticos — punch-ins, jump zooms, slow push \"cálido\", bumps de énfasis, handheld — en DaVinci Resolve vía resolve-forge. Úsala cuando pidan zoom, movimiento, dinamismo, \"que no se vea aburrido/estático\", retención, o editar un talking head en horizontal o vertical."
---

# Zoom dinámico para talking heads

Objetivo: cambiar el encuadre cada pocos segundos **con intención** (en frases, ideas, palabras clave), no al azar,
y sin que el espectador note "efecto". La cara manda: todo zoom se ancla al rostro.

## Receta (MCP)

1. `forge_status` → mira `native_keyframes`. Si es true, se usan keyframes del Inspector, editables a mano. En Free se usa el backend `fusion` (nodo `ForgeMotion` en la página Fusion del clip); es automático y está verificado al render.
2. `list_clips` → índices y duraciones.
3. Decide **dónde** cambian los planos (mejor que el ritmo automático):
   - Con voz: `transcribe_timeline()` devuelve `cuts_s` (inicios de frase) y `hits_s` (números, exclamaciones,
     remates) ya en segundos del timeline. Pásalos tal cual, o recórtalos con criterio. Usa Whisper local y funciona en Free.
   - Sin transcripción: omite `cuts_s` y el estilo genera un ritmo irregular (2.5–3.5 s vertical, 6–9 s horizontal).
4. `preview_motion` con el estilo elegido → revisa `peak_zoom` y los tiempos.
5. `apply_motion(style, cuts_s, hits_s, anchor="face", intensity)`.
6. QC (abajo). Ajusta `intensity` o el estilo y vuelve a correr `apply_motion` (reemplaza su animación anterior).

## Elegir estilo

| Situación | Estilo | intensity |
|---|---|---|
| Vertical energético (TikTok, Reels, Shorts, FB Reels) | `tiktok_punch` (cortes duros 1.00↔1.15) | 1.0–1.3 |
| Vertical educativo o calmado, Stories | `tiktok_smooth` (zoom con ease de 6 frames) | 0.8–1.0 |
| Horizontal talking head (YouTube, Facebook, LinkedIn, web) | `youtube_dynamic` (push sutil + punch cada 6–9 s) | 0.8–1.0 |
| Documental, testimonio, emocional, "cálido" | `warm_push` (1.00→1.08 continuo) | 0.6–1.0 |
| Cierre / reflexión | `warm_pull` | 0.6–1.0 |
| Remarcar palabras | `emphasis` con `hits_s` | 1.0 |
| Trípode muy rígido | `handheld` (±0.4°) o `vlog_mix` | 0.5–1.0 |

Reglas de oficio:
- Alterna niveles (abierto ↔ cerrado). Dos punch-ins seguidos al mismo nivel no se notan.
- No hagas punch-in en mitad de una palabra: ponlo en el inicio de la frase o de la idea.
- Plano < 1–1.5 s de forma constante cansa. El rango sano es 2–4 s en vertical y 3–7 s en horizontal.
- Si el material es 1080p sobre timeline 1080p, no pases de ×1.20 (pérdida de nitidez). Con 4K en timeline 1080p tienes margen hasta ×2.
- En vertical reencuadrado desde 16:9 ya estás usando zoom de cobertura (~×3.16). Los punch-ins se suman encima: usa `intensity` ≤ 1.
- B-roll, texto y gráficos también cuentan como "cambio de plano". No apiles zoom encima de cada uno.

## QC antes de entregar

- Reproduce los primeros 5 s: el hook debe tener un cambio visual antes de los 2 s.
- La cara nunca sale del área segura (ver `list_formats` → `safe_rect_px`).
- Sin bordes negros en rotaciones (`handheld` ya añade el zoom de seguridad).
- El zoom no corta la frente ni el mentón en el nivel cerrado.

## Fallback manual en Resolve (sin MCP)

- **Dynamic Zoom**: Inspector → Dynamic Zoom → ON, ajusta los rectángulos inicio/fin en el visor (modo Dynamic Zoom), Ease: In and Out.
- **Keyframes Inspector**: Zoom + Position con diamantes de keyframe; clic derecho en la curva → Ease In/Out.
- **Fusion**: MediaIn → Transform (Size con keyframes, Pivot en la cara) → MediaOut. Ver `../davinci-resolve-mcp/references/api-cheatsheet.md`.

Más técnica y fuentes: `docs/editing-playbook.md`.
