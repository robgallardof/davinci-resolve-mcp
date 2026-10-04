# Arquitectura de resolve-forge

```
tools.py ──► services/ ──► domain/          (puro: sin Resolve, 100 % testeable)
 (MCP fino)    │  motion_service   easing · keyframes · motion · styles · framing · formats
               │  format_service
               │  render_service
               │  appliers ─────► Strategy: EditKeyframeApplier | FusionTransformApplier
               │  subject  ─────► analysis/faces (opencv opcional)
               ▼
            gateway.py ──► DirectTransport (DaVinciResolveScript) | BridgeTransport (bridge/ propio, Free)
server.py = raíz de composición (crea Session, registra tools)
```

### Módulos agregados al estudiar los otros MCPs

```
errors.py                      ForgeError(code, hint) + payload(): contrato de error para tools y resources
resources.py                   resolve://status, resolve://timeline, forge://formats, forge://styles (hilo de Resolve)
domain/transcript.py           puro: map_clip (fuente→timeline), sentences, caption_chunks, emphasis_hits, cut_points
analysis/media.py              audio vía PyAV (sin binario ffmpeg)
analysis/transcribe.py         WhisperTranscriber: corre en un proceso hijo y cachea por archivo
analysis/whisper_worker.py     el proceso hijo: faster-whisper, GPU (large-v3-turbo) → CPU (small)
analysis/highlights.py         movimiento por segundo (cv2) + rank() puro de ventanas
graphics/cards.py              tarjetas PNG de cuadro completo: estilos, wrap balanceado, emoji, safe zone
services/transcript_service    palabras de cada clip re-temporizadas al timeline
services/overlay_service       tarjetas → secuencias PNG (hardlinks) → pista nueva, frame-exactas
services/captions_service      transcript → chunks → overlay_service
services/assembly_service      lista de cortes → timeline nuevo (opcionalmente a resolución de plataforma)
services/highlight_service     clip → ventanas destacadas
services/media_lookup          clip del media pool por nombre o ruta (importa si hace falta)
```

### Authoring y transporte propios

```
authoring_tools.py / production_tools.py   schemas MCP de proyecto, media, timeline, color, audio, Fusion, QC y montaje
domain/edit_decisions, editorial, fusion_graph, lut, text_design   reglas puras (cortes, DAG, tablas .cube, tipografía)
services/native.py             capacidades, rechazos nativos, readback y copias del timeline
bridge/                        protocolo HMAC + antireplay, lista explícita de métodos, cliente y ops dentro de Resolve
bridge_install/                instala nuestro bridge en Workspace → Scripts (conserva token y raíces)
native_paths.py                rutas del SDK por sistema operativo
production_tools.py            align_text, place_sound_effects, add_music_bed, plan_edit, find_story_moments, analyse_music, plan_beat_cuts, assemble_montage, create_music_visualizer
analysis/action.py             energía de movimiento y su centroide por ventana (dónde está la acción), sin Resolve
domain/energize.py             planos cortos, encuadres alternos (wide/medium/close/crash), pivote que centra al sujeto
services/energize_service      plan desde la fuente y timeline nuevo con motion por plano (focus_hold/crash_zoom)
domain/framing_review.py       qué queda visible con cada zoom; sujeto al borde, acción recortada, cara cortada, zoom borroso
domain/look.py, text_placement.py   exposición/contraste/saturación/dominante con CDL suave; textos que no tapan caras
services/review_service        hojas de revisión antes (planos con recorte real) y después del render (negro/congelado)
domain/sound_design            SFX con motivo obligatorio, densidad revisada, carriles sin solapes
services/sfx_service           ganancia horneada en WAV nuevo (ffmpeg) y pistas de audio nuevas en una copia
domain/ducking                 regiones de voz → curva de ganancia (ataque, release, fades)
services/music_bed_service     música estéreo 48 kHz con ducking horneado, en pista nueva de una copia
domain/alignment               texto conocido (letra/guion) alineado a los tiempos reconocidos
domain/story_moments, beat_cuts   candidatos de remate/reacción/pregunta/acento; slots de corte por frases del beat
services/story_service, music_service   transcripción + energía de la fuente; análisis rítmico, cortes al beat, visualizer
```

Detalle de la selección y procedencia: [third-party-migration.md](third-party-migration.md).

¿Por qué secuencias PNG para los textos? La API no puede recortar títulos ni stills (un still siempre dura 5 s e
ignora `endFrame`), pero una secuencia de N imágenes entra como un clip de exactamente N frames con alfa.
Los frames son hardlinks a un único PNG, así que casi no ocupan disco.

## Principios aplicados

- **SRP**: cada módulo tiene una razón para cambiar. La matemática de encuadre (`framing`) no sabe de MCP; las tools no saben de keyframes.
- **OCP**: estilos nuevos con `@style(...)`; backends nuevos en `APPLIERS`. No se edita el código existente.
- **LSP / ISP**: `Applier` es un `Protocol` mínimo (`apply`, `clear`). Cualquier backend que lo cumpla es intercambiable.
- **DIP**: los servicios dependen de `Session`, no del módulo nativo. Los tests inyectan fakes.
- **DRY**: una sola definición de cada curva de easing, de la que se derivan la interpolación de Resolve, los handles de Fusion y las muestras horneadas. Una sola fuente de configuración MCP (`config/mcp.servers.json`). Una sola copia de skills y agentes (`.agents/`, con links).
- **KISS**: 56 tools orientadas a casos de uso (intención editorial + authoring de proyecto, media, color, audio,
  Fusion y QC). Sin wrappers 1:1 de la API ni ejecución arbitraria de código.

## Modelo de motion

`MotionPlan = tracks (zoom multiplicador, ángulo en grados) + anchor (cara, normalizado)`.

- **keyframes** (preferido, Resolve 20+): `ZoomX/ZoomY/Pan/Tilt/RotationAngle` en el Inspector, con `SetKeyframeInterpolation`.
  Por cada keyframe de zoom se recalcula Pan/Tilt con `rezoom_keeping`, así la cara queda fija en pantalla mientras el zoom la "entra".
- **fusion** (fallback universal): `MediaIn → Transform(ForgeMotion) → MediaOut`, con `Pivot` en la cara y `BezierSpline` en Size/Angle.
  La curva se escribe muestreada cada 2 frames con `SetInput` (compatible con el bridge de Free). Los valores se escriben
  fuera de `comp.Lock()`, porque dentro el render los ignora.
- Los pasos duros (punch-in) se modelan como `HOLD` y cada backend los traduce a dos keys separadas por un frame.

## Coordenadas

- Puntos del sujeto: normalizados con origen arriba-izquierda (como una imagen).
- Inspector: Pan (+ derecha) y Tilt (+ arriba) en píxeles del timeline; el zoom multiplica el tamaño "fit".
- Fusion: origen abajo-izquierda (`y_fusion = 1 - y`). Los tiempos se desplazan por `COMPN_RenderStart`.

## Robustez en Windows (aprendido en pruebas en vivo)

- **Sonda nativa en subproceso**: `fusionscript.dll` hace segfault dentro de un venv si `PYTHONHOME` no apunta al
  Python base, y en Free rechaza el scripting externo. `gateway.direct_scripting_available()` lo prueba en un proceso
  hijo, así un crash nativo nunca tumba al servidor MCP. Después cae al bridge.
- **Precarga de opencv/numpy**: cargar esas DLLs mientras otro hilo lee el pipe stdin bloquea el proceso en Windows.
  `server.main()` las importa antes de abrir stdio.
- **Hilo dedicado para Resolve**: todas las tools corren en un único worker thread (las llamadas a Resolve se
  serializan) y el event loop de stdio queda libre.
- **Bridge (Free)**: los argumentos viajan como JSON, así que el backend Fusion solo usa `SetInput` con valores simples
  (curvas muestreadas cada 2 frames) y los puntos se prueban en varias codificaciones.
- Subprocesos con `stdin=DEVNULL`: no heredan el pipe del protocolo.
