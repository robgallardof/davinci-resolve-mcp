---
name: vertical-video
description: "Editar video vertical (9:16 y 4:5) para cualquier plataforma — TikTok, Instagram Reels, Facebook Reels, YouTube Shorts, Stories, Snapchat, feed 4:5 — en DaVinci Resolve: reencuadre desde 16:9, hook, ritmo, zooms dinámicos, subtítulos, safe zones y export. Úsala cuando pidan vertical, 9:16, 4:5, reels, shorts, tiktok, stories, clips cortos o convertir un horizontal en vertical."
---

# Video vertical (9:16 / 4:5)

Una sola forma de trabajo para todas las plataformas verticales. Lo que cambia por plataforma (safe zone,
duración máxima, loudness) lo da `list_formats(orientation="vertical")`. La tabla completa está en
`../resolve-delivery/references/platforms.md`.

## Flujo

1. **Estado**: `forge_status` y `list_clips`.
   Clip largo sin editar (por ejemplo un video del teléfono de varios minutos): `find_highlights(source)` para
   ver los mejores momentos y `assemble_timeline(source, cuts=[[ini, fin], ...], name, format="reels")` para
   armar el corte directamente en 9:16. Si haces esto, sáltate el paso 2.
2. **Formato**. Si la fuente es 16:9: `make_platform_version(format=<plataforma>, subject="face")`.
   Crea una copia con la cara centrada y el master no se toca.
   - Varias plataformas 9:16 comparten resolución: una sola versión `reels` sirve para TikTok, Shorts y FB Reels.
     Cambia solo la safe zone, así que diseña para la más restrictiva (TikTok abajo/derecha, Reels abajo).
   - `feed_4x5` para el feed de Instagram/Facebook: menos recorte, más contexto.
   - Dos personas: `center_bias` 0.6–0.8, o por clip con `subject=[x, y]`.
   - Studio: `smart_reframe=true`.
3. **Corte editorial** (con `davinci-resolve`): fuera silencios, muletillas y retomas.
   Duración: 15–35 s es lo más seguro; 30–60 s si la idea lo necesita. Respeta `max_seconds` del formato.
4. **Hook (0–3 s)**: la primera frase es la promesa o el conflicto. Primer cambio visual antes de los 2 s.
5. **Movimiento** (skill `dynamic-zoom-talking-head`): `transcribe_timeline()` y luego
   `apply_motion("tiktok_punch" | "tiktok_smooth" | "vlog_mix", cuts_s=<cuts_s>, hits_s=<hits_s>)`.
   Los estilos `tiktok_*` sirven para cualquier vertical; el nombre indica el ritmo, no la plataforma.
6. **Texto** (casi todo se ve sin sonido):
   - Hay voz: `add_captions(style="outline" | "yellow" | "box", position="bottom", max_words=3)`.
     Funciona en Free y queda dentro de la safe zone más estricta.
   - Sin voz (vlog visual o con música): cuenta la historia con `add_text_overlay(text, start_s, duration_s,
     style="box", position="top")`, por ejemplo "POV: …" en el hook y un giro a mitad del video.
     Emoji permitidos.
7. **Pattern interrupts** cada 2–4 s: punch-in, B-roll, texto, SFX. Varía el tipo.
8. **Loop**: que el final conecte con el inicio cuando se pueda.
9. **Entrega** (skill `resolve-delivery`): `render_for(format=<plataforma>)`, una por destino si cambian las specs.

## Specs base

1080×1920 (4:5: 1080×1350), 30 fps (o el fps del material), H.264 High 10–14 Mbps, AAC 48 kHz.
Loudness −12 a −14 LUFS, −1 dBTP. Shorts se reproduce como máximo a 1080p.

## Checklist

- [ ] Resolución del timeline = formato (`forge_status`)
- [ ] Cara y texto dentro de la safe zone de la plataforma más restrictiva
- [ ] Hook en 0–3 s, cambio visual antes de 2 s
- [ ] Ritmo de 2–4 s por plano y subtítulos completos
- [ ] Render completo (`render_status`) y archivo verificado
