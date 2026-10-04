---
name: resolve-delivery
description: "Exportar desde DaVinci Resolve (Free o Studio) con las specs correctas para cualquier plataforma vertical u horizontal — TikTok, Reels, Facebook, Shorts, Stories, Snapchat, YouTube, LinkedIn, X, web: formato, codec, bitrate, loudness LUFS, ruta de salida y verificación del archivo. Úsala cuando pidan render, exportar, entregar, subir, deliver, specs o loudness."
---

# Delivery

Specs de cada plataforma: `references/platforms.md`. Se genera desde el código, así que es la fuente de verdad.
También está disponible en vivo con `list_formats`.

## Pasos

1. `forge_status`: el timeline correcto, a la resolución del formato destino. Si no coincide, usa primero `make_platform_version`.
   Varias plataformas con la misma resolución (por ejemplo TikTok, Reels y Shorts) pueden salir del mismo timeline.
2. Loudness en Fairlight (con `resolve-forge` o a mano): el target está en la columna LUFS (−12 a −14) y el true peak en −1 dBTP.
   Studio: Deliver → Audio → Normalize Audio.
3. Guarda el proyecto.
4. `render_for(format, name=...)`. Sin `target_dir` escribe en `~/Movies/resolve-forge`.
   - **Free**: el bridge solo escribe dentro de `allowed_output_roots` (por defecto `~/Movies`). Usa subcarpetas de `~/Movies`
     o agrega la ruta en `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\.davinci_mcp_runtime\bridge.json`.
   - H.265 cae automáticamente a H.264 si tu edición o tu GPU no lo soportan.
5. `render_status(job_id)` hasta `Complete`.
6. Verifica el archivo: existe, tamaño > 0, resolución y duración. Con ffprobe:
   `ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate -of compact <archivo>`.
7. Reporta la ruta y las specs reales de cada archivo.

## Trampas

- `SetRenderSettings` hereda el preset cargado en Deliver; `render_for` fija formato y codec antes de aplicarlo.
- Un `CustomName` vacío invalida todo el payload (`render_for` siempre lo rellena).
- Render a una carpeta fuera de las raíces permitidas en Free: error claro y la solución en el mensaje.
