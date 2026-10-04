---
name: color-audio-finishing
description: "Acabar audio, color y LUT de una edición en DaVinci Resolve: presets suaves, mezcla inteligible, medición LUFS/true peak y comparación visual. Úsala para mejorar sonido, aplicar looks/LUT o preparar el acabado que encarga el productor."
---

# Acabado de audio y color

El productor fija género y referencia; esta especialización mejora la legibilidad de voz e imagen y devuelve
evidencia de comparación. Usa `davinci-resolve-mcp` y `forge_status`; modifica copias y escribe archivos nuevos.

## Audio

- Escucha voz, música y SFX separados y juntos. `analyse_audio` mide; no demuestra inteligibilidad.
- Para rumble y dinámica irregular: preview `enhance_audio(source, preset="dialogue"|"podcast"|"entertainment")`.
  Revisa mediciones/filtros; `dry_run=false` escribe WAV 48 kHz/24 bits nuevo. Escucha antes/después a volumen
  comparable. No elimina reverberación, separa voces ni recupera audio ya saturado. Importa/reemplaza la fuente
  solo sobre una versión si la escucha confirma mejora; no desplaza sus tiempos.
- `add_music_bed` conserva voz clara mediante ducking. SFX con motivo y ganancia moderada: `place_sound_effects`.
- El limitador de `enhance_audio` controla picos, no entrega automáticamente el LUFS de plataforma. Mide la
  mezcla final y usa `normalise_audio` con el objetivo de `list_formats`; comprueba el WAV final y escucha.

## Color, presets y LUT

- Antes del look, comprueba gestión de color y espacio de entrada. Un preset creativo no convierte Log/HDR a SDR.
  Si no sabes la cámara/espacio, inspecciona metadata y referencia antes de aplicar una conversión.
- `review_shots`/`review_video` orientan exposición y dominante; confirma visualmente piel, blancos y altas luces.
- `apply_grade_preset(preset="natural"|"warm"|"crisp"|"muted", intensity=.5)` es preview. Aplica solo tras comparar:
  `dry_run=false` crea copia y reemplaza CDL del nodo 1. No acumules varias correcciones sobre el master.
- LUT del usuario: `prepare_lut` valida la tabla y permite mezcla con identidad; conserva la original.
  Lee su espacio de entrada/salida. Una LUT creativa y una conversión técnica no son intercambiables.
  Usa `grade_clips`/`inspect_grade` según sus schemas y comprueba readback, sin afirmar que demuestra buen color.
- Compara frames del mismo tiempo antes/después. Rechaza piel naranja, negros empastados, altas luces recortadas
  o saturación que reduce legibilidad. No fuerces una LUT cuando un CDL suave basta.

## Cierre

`preflight_render(format)` debe quedar sin errores técnicos pendientes. Mira la hoja de encuadres, escucha
la mezcla y verifica texto/carátulas/safe zones antes de guardar y renderizar. Después usa `review_video`, mira
la hoja y mide el audio del archivo final. Reporta qué mediste y qué revisaste con ojos/oídos.
