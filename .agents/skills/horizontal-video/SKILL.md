---
name: horizontal-video
description: "Editar video horizontal 16:9 para cualquier destino — YouTube, Facebook, LinkedIn, X, web/Vimeo, cursos, podcasts en video, entrevistas, presentaciones — en DaVinci Resolve con ritmo que retiene: punch-ins, B-roll, jump cuts, capítulos, subtítulos y export 1080p/4K. Úsala cuando pidan horizontal, 16:9, landscape, YouTube, long-form, podcast, curso, webinar o convertir un vertical en horizontal."
---

# Video horizontal (16:9)

Un solo método para todos los destinos 16:9. Las specs por plataforma salen de
`list_formats(orientation="horizontal")`; la tabla completa está en `../resolve-delivery/references/platforms.md`.

## Flujo

1. **Estado**: `forge_status` y `list_clips`.
2. **Formato**. Si la fuente es vertical: `make_platform_version(format="youtube_1080" | "facebook_1080" | ...)`.
   El clip se escala para llenar el 16:9 alrededor del sujeto. Si recortar demasiado arruina el plano, usa un
   fondo desenfocado (Fusion o `davinci-resolve`) con el vertical encima.
3. **Assembly** (con `davinci-resolve`): ordena tomas, quita retomas y silencios, y marca capítulos con markers.
4. **Ritmo**: un cambio visual cada **3–7 s**. De mayor a menor valor: B-roll que *muestra* lo dicho,
   gráfico o texto, punch-in, cambio de cámara.
5. **Movimiento** (skill `dynamic-zoom-talking-head`):
   - Primero `transcribe_timeline()`: te da `cuts_s` (inicios de frase) y `hits_s` (datos y remates) en segundos del timeline.
   - Talking head: `apply_motion("youtube_dynamic", cuts_s=<cuts_s>)`. Pese al nombre, sirve para cualquier 16:9.
   - Momentos emocionales o testimonios: `warm_push` con intensity 0.6–0.8. Cierres: `warm_pull`.
   - Datos y remates: `emphasis` con `hits_s`.
   - Multicam: el corte entre cámaras ya es el cambio. Usa `warm_push` suave en el plano abierto.
6. **Hook por destino**:
   - YouTube / web: la promesa del título en 5–10 s, más un preview del mejor momento.
   - Facebook / LinkedIn / X: autoplay sin sonido, así que el mensaje tiene que entenderse con subtítulos
     en los primeros 3 s: `add_captions(style="dark" | "outline", position="bottom", max_words=5)`.
     Considera también una versión `square` o `feed_4x5`.
   - Títulos, nombres o lower thirds: `add_text_overlay(..., style="dark", position="bottom")`.
7. **Audio**: Voice Isolation, música −18 a −24 dB bajo la voz, −14 LUFS y −1 dBTP.
8. **YouTube**: deja libres los últimos 20 s para el end screen; los capítulos salen de los markers.
9. **Entrega** (skill `resolve-delivery`): `render_for(format=...)`.

## Errores comunes

- Punch-in tras punch-in sin B-roll: se siente como "TikTok estirado". Alterna.
- Zoom por encima de ×1.2 sobre material 1080p en un timeline 1080p: se nota el blando.
- Cortar la respiración final de las frases: suena ansioso. Deja 3–6 frames.

## Checklist

- [ ] Resolución correcta y master intacto
- [ ] Cambio visual cada 3–7 s, con B-roll donde se pueda mostrar algo
- [ ] Subtítulos si el destino hace autoplay en mudo
- [ ] Audio a −14 LUFS
- [ ] Render completo y verificado
