---
name: entertainment-pacing
description: "Edición para entretener en redes (TikTok, Reels, Shorts, vlogs, mascotas, comedia, retos): la pantalla nunca queda quieta, pero cada zoom tiene motivo — planos cortos, enfoques sobre el sujeto real, crash zooms solo en picos de acción, textos animados y subtítulos. Úsala SIEMPRE que el video sea para entretener o cuando digan 'se ve simple', 'más dinámico', 'más zooms', 'más animado', 'que no aburra', 'enfoca a la mascota/la cara', o editen clips de celular sin cortes."
---

# Ritmo de entretenimiento (con zooms que tienen sentido)

Dos reglas que van juntas:
1. **La pantalla no queda quieta**: ningún tramo de más de ~2–3 s sin un cambio (corte, reencuadre, texto, subtítulo).
2. **Cada zoom tiene motivo y está bien puesto**: se acerca a algo que importa (la cara en una reacción, la mascota,
   el objeto de la acción) y lo deja centrado y completo. Un zoom a una manga, una pared, al centro cuando la acción
   está en una esquina, o durante un movimiento de cámara, es peor que no hacer zoom.

La duración la decide la historia y el usuario: si pide más de un minuto, se conserva la historia y se gana ritmo
dentro, no recortando de más.

## Flujo (con autorrevisión obligatoria)

1. **Mira la fuente** antes de decidir: contact sheet de frames (o `find_highlights`/`analyse_scenes`). Identifica
   quién es el protagonista de cada parte (persona, mascota, objeto) y dónde está en el cuadro.
2. **Historia**: rangos en segundos de la FUENTE (voz: `find_story_moments`; música: `analyse_music`).
3. **Plan**: `plan_energized_edit(source, ranges, format=<plataforma>, hints=[...])`.
   - El detector sigue el movimiento más grande — muchas veces la persona, no la mascota. Si lo que importa es otra
     cosa, corrige con `hints`: `{start_s, end_s, focus: [x, y]}` (donde está el sujeto real) o
     `{start_s, end_s, framing: "wide"}` (cámara en movimiento, revelación, plano que debe respirar).
   - El plan se autorrevisa: baja a medium/wide cualquier zoom que deje al sujeto en el borde, recorte la acción,
     corte una cara o pase lo que la resolución aguanta (`format` calcula el zoom máximo nítido). Lee `self_review`.
4. **Revisión visual ANTES de construir**: `review_shots(source, shots, format, texts=[...])` y **abre la imagen
   `sheet`** (léela como imagen). Revisa cada plano: ¿el encuadre muestra lo que importa? ¿el sujeto está completo
   y centrado? ¿algún texto tapa una cara? Rojo = problema. Corrige con `hints`/encuadres y repite hasta que
   todo esté verde **y** se vea bien a tus ojos. Usa `text_positions` para colocar textos.
5. **Construye**: `energize_timeline(source, name, format, shots=..., dry_run=false)`.
6. **Capas** (sin taparse entre sí ni tapar caras):
   - Subtítulos de lo que se dice con palabras verificadas (`transcribe_timeline(include_words=true)` / `align_text`);
     si Whisper duda, aísla el fragmento y verifica; si no se entiende, no lo subtitules.
   - Textos de narración en los giros (`add_text_overlay`, `creator`, `pop`), uno a la vez, en la posición que
     indicó `review_shots`.
   - Color: si `look.cdl` trae correcciones, aplícalas con `grade_clips` (en copia) solo si mejoran los frames.
   - Sonido: `add_music_bed` / `place_sound_effects` si el usuario aporta los archivos.
7. **Render y revisión final**: `render_for` → `review_video(file)` y **abre la hoja**. Si hay negro, congelados,
   textos sobre caras, encuadres raros o color feo, corrige y vuelve a renderizar. No entregues sin esto.

## Sin interacción, se corta

Una persona **de espaldas**, sin cara visible, y sin que pase nada más (la mascota quieta, nadie mira, nada se
mueve con intención) es tiempo muerto aunque haya movimiento. `plan_energized_edit` (drop_dull=true) los corta y
los lista en `cut_dull` con el motivo. Si un plano así importa para la historia, protégelo con
`hints: [{start_s, end_s, keep: true}]` o con `focus` sobre lo que sí pasa (la mascota). Revisa siempre `cut_dull`.

## Criterio de encuadre

| Momento | Encuadre |
|---|---|
| Apertura de escena, revelación, cámara moviéndose | wide (sin zoom) |
| Acción de un solo sujeto (mascota saltando, mano que agarra) | medium/close centrado en el sujeto |
| Reacción, mirada a cámara, cara en calma | close a la cara |
| Pico de acción claro y concentrado | crash zoom (punch rápido) — no más de uno seguido |
| Nada pasa / sujeto fuera de cuadro | wide o corta ese tramo |

## Detalles que el usuario nota

- Género y número correctos en los textos (una ardilla hembra es "la supervisora", "la jefa").
- Nada de texto sobre caras ni sobre la acción; dentro de la safe zone del formato.
- Fuentes de baja resolución (WhatsApp 576×1024): el plan limita el zoom para que no se vea borroso; si hace falta
  más zoom, pide el original del teléfono.
- Un acento por momento: no apiles crash zoom + texto + SFX en el mismo segundo salvo en el clímax.
