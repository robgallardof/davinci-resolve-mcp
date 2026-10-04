---
name: entertainment-pacing
description: "Edición para entretener en redes (TikTok, Reels, Shorts, vlogs, mascotas, comedia, retos): la pantalla nunca queda quieta — planos cortos, zooms y enfoques sobre la acción, crash zooms en los picos, textos animados y subtítulos. Úsala SIEMPRE que el video sea para entretener o cuando digan 'se ve simple', 'más dinámico', 'más zooms', 'más animado', 'que no aburra', 'enfoca a la mascota/la cara', o editen clips de celular sin cortes."
---

# Ritmo de entretenimiento

Regla de oro: **la gente no puede pasar más de ~2–3 s sin un cambio en pantalla** (corte, zoom, reencuadre, texto,
subtítulo o efecto). Pocos empujes lentos sobre planos largos se ven "muy simples". La duración la decide la historia
y el usuario: si pide más de un minuto, se conserva la historia y se gana ritmo dentro, no recortando de más.

## Flujo

1. **Historia** (qué pasa y en qué orden): mira la fuente. Para voz, `find_story_moments`; para música, `analyse_music`.
   Elige los rangos de la historia (segundos de la FUENTE).
2. **Plan de ritmo**: `plan_energized_edit(source, ranges=[...])`. Detecta sin Resolve:
   - dónde está la acción en cada momento (mascota, manos, salto) y los picos de acción;
   - caras en momentos calmos (reacciones, miradas a cámara);
   - movimientos de cámara (se mantienen abiertos) y tiempo muerto (se recorta).
   Devuelve planos de 1.2–2.8 s con encuadre `wide` / `medium` ×1.25 / `close` ×1.5 / `crash` (punch rápido en el pico),
   sin repetir encuadre seguido, con el sujeto llevado hacia el centro.
3. **Revisa el plan** con criterio: un corte no debe partir un gesto ni anticipar el remate; las revelaciones van
   abiertas; un chiste visual puede pedir mantener el plano. Ajusta `shots` a mano si hace falta.
4. **Construye**: `energize_timeline(source, name, format, shots=..., dry_run=false)` — un clip por plano con su zoom.
5. **Capas que mantienen la atención** (sin taparse entre sí):
   - Subtítulos de lo que se dice: palabras verificadas (`transcribe_timeline(include_words=true)` o `align_text`),
     estilo `creator`. Si Whisper duda o detecta otro idioma, aísla el fragmento y verifica antes de quemar.
   - Textos de narración (`add_text_overlay`, `creator`, `pop`) en los giros: gancho 0–3 s, "mientras tanto…",
     el remate, el cierre. Uno a la vez; arriba si los subtítulos van abajo.
   - Sonido: música bajo la voz (`add_music_bed`) y SFX motivados (`place_sound_effects`) si el usuario los aporta.
6. **QC**: `audit_timeline`, revisa frames de cada encuadre y `render_for`.

## Detalles que el usuario nota

- Género y número correctos en los textos (una ardilla hembra es "la supervisora", "la jefa").
- Nada de texto sobre la cara ni sobre la acción; usa la safe zone del formato.
- Fuentes de baja resolución (WhatsApp 576×1024): zoom máximo ~×1.5–1.6 (`max_zoom`), o se verá borroso.
- Un acento por momento: no apiles crash zoom + texto + SFX en el mismo segundo salvo en el clímax.

## Qué no hacer

- Planos de 5–20 s sin cambio, un solo `warm_push` por clip largo, o zoom al centro cuando la acción está en una esquina.
- Inventar lo que se dice: si no se entiende, pregunta o usa texto de narración en vez de subtítulos.
