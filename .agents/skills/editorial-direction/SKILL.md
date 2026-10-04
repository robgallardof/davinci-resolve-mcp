---
name: editorial-direction
description: "Criterio de productor y editor profesional por género en DaVinci Resolve: comedia (setup, pausa, remate, reacción), videoclips y música electrónica (frases, build/drop, cortes al beat), entrevistas, cine/narrativo, educación, producto, gaming y vlog. Úsala antes de cortar cualquier pieza con intención: cuando pidan 'que se vea profesional', 'no robótico', 'mejora mi idea', video para una canción, visualizer, edición de comedia, detectar partes graciosas o los mejores momentos, o subtítulos bonitos acordes al tono."
---

# Dirección editorial por género

Eres productor además de editor: entiendes la idea, la mejoras y la ejecutas. Las herramientas miden; tú decides.
Ningún pico de audio es un chiste ni un drop hasta que lo ves o lo escuchas.

## Flujo

1. **Brief**: qué quiere provocar la pieza (risa, ganas de bailar, confianza, aprender), para quién y dónde.
   Si la idea es floja, propón una mejora concreta (un hook más fuerte, otro orden, un remate visual) antes de cortar.
2. **Evidencia**:
   - Voz (comedia, entrevista, educación, vlog, gaming, producto, cine): `find_story_moments(source, content_type)`.
     Devuelve candidatos con evidencia: pausa antes de una línea corta (remate), audio sin voz justo después
     (risa/reacción), preguntas y palabras acentuadas. Tiempos en segundos de la FUENTE.
   - Música: `analyse_music(source)` → BPM, confianza, beats y cambios de energía (candidatos, no drops confirmados).
3. **Revisa cada candidato** (mira/escucha). Quédate solo con los reales y pásalos con tu motivo:
   `plan_edit(brief, content_type, platform, duration_s, moments=[{time_s, kind, reason}])`.
   Te devuelve dirección, qué evitar, estilo de subtítulos y de motion, y las tools del flujo.
4. **Corte**:
   - Voz: `assemble_timeline(source, cuts=[[ini, fin], ...], name, format)` protegiendo cada bloque completo.
   - Música: `plan_beat_cuts(music_source, shots, duration_s, beats_per_cut, intense=[[ini, fin]])` y luego
     `assemble_montage(shots, name, format, music_source, music_start_s, dry_run=false)`.
5. **Movimiento, texto y sonido** acordes al tono (abajo), sin apilar efectos: un acento por momento.
   SFX solo en momentos confirmados y con motivo: `place_sound_effects(cues=[{time_s, source, reason}])`
   (primero en preview; atiende sus avisos de densidad). Usa sonidos con licencia del usuario.
   Música de fondo bajo voz (entrevista, educación, vlog, producto): `add_music_bed(music_source)`; en videoclips no,
   ahí la canción es la protagonista (`assemble_montage`).
6. **QC**: `audit_timeline`, revisión visual de cada remate/drop y `render_for`.

## Por género

| Género | Protege | Ritmo | Texto / motion |
|---|---|---|---|
| **Comedia** | setup → pausa → remate → reacción. La pausa ES el chiste | Corta *después* de la risa, no durante el remate. Reacción solo si suma | `creator` o `impact` solo en el remate; `emphasis` con `hits_s` = remates confirmados. Nunca anticipes el chiste en un título. Sin SFX en cada broma |
| **Música / videoclip** | La canción intacta (A1 continuo); letra con tiempos dados por el artista | Cortes en frases (4–8 beats), motivos visuales que vuelven en el estribillo | `editorial`; `warm_push` lento. Letra exacta: `align_text(source=<voz aislada, o la canción con focus_vocals=true>, text=<letra>, timeline_offset_s=-music_start_s)` → `add_captions(words=...)`. Whisper solo da tiempos |
| **Electrónica** | Contraste build / drop / breakdown | Build: alarga planos y sube tensión; drop confirmado: `intense` con 1–2 beats por corte; breakdown: respira | `impact` corto en el drop; `tiktok_punch` solo ahí. Sin flashes a pantalla completa. Visualizer: `create_music_visualizer` |
| **Entrevista / podcast** | Sentido de la respuesta, miradas, reacciones genuinas | Deja respirar respuestas emotivas; cubre cortes con B-roll relevante | `studio`; `youtube_dynamic` / `warm_push` |
| **Cine / narrativo** | Dirección de pantalla, continuidad, silencios | Cortes motivados por la historia, nunca por un temporizador | `editorial`, sin animación o `fade` |
| **Educación** | La demostración completa y las pausas que hacen falta para entender | Corta en ideas terminadas; muestra lo que se explica | `studio` (16:9) / `creator` (9:16) |
| **Producto** | Beneficio primero, demo real, prueba legible, un solo CTA | Hook → problema → demo → prueba → CTA | `studio`; sin afirmaciones no verificadas |
| **Gaming** | Contexto espacial, HUD legible, la jugada que explica el resultado | Acelera la espera, nunca la jugada | `creator`; subtítulos fuera del HUD (`position="top"` si el HUD está abajo) |
| **Vlog** | Momentos auténticos, lugar | Alterna detalle y presencia; J/L cuts | `creator`; `vlog_mix` |

## Subtítulos y textos que se vean bien

- `list_text_styles` → `preview_text_style(texto, style, width, height)` para revisar antes de quemar nada.
- `add_captions(style="auto")`: Creator en vertical, Studio en horizontal. Estilos: `creator` (cercano, palabra
  activa), `studio` (limpio), `editorial` (cálido, discreto), `impact` (remates y mensajes breves).
- Color de marca con `accent="#RRGGBB"`; `emphasis_words` solo para las palabras que importan.
- Texto exacto: si hay guion o letra, `align_text(source, text)`; si no, corrige `transcribe_timeline(include_words=true)`.
  En ambos casos pasa `words=` a `add_captions` antes de quemar.
- `reduced_motion=true` para contenido sereno o accesible. Los estilos legacy (`box`, `outline`, `yellow`, `dark`) solo si el usuario los pide.

## Qué no hacer

- Cortar cada 2 s "porque sí", zooms en cada frase o animar texto, cámara y SFX a la vez.
- Etiquetar "drop", "chiste" o "momento emotivo" sin haberlo comprobado.
- Estirar o reencuadrar el master musical sin pedirlo.
