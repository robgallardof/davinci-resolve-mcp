# Migración: herramientas propias a partir del análisis de la competencia

Forge implementa 65 herramientas propias: edición editorial, producción por género, sonido y authoring de proyectos,
media, timeline, color, Fusion y QC. No importa ni empaqueta código de los MCP estudiados.

## ¿Cuánto lleva? (2026-10-04)

**Implementación propia ampliada; verificación final en Resolve pendiente de reconectar el bridge. Ver evidencia actual abajo antes de asumir cobertura.**

| Fase | Estado | Evidencia |
|---|---|---|
| 1. Estudio de los 7 MCP públicos y selección | ✅ Hecho | [mcp-landscape.md](mcp-landscape.md), [mcp-reviews.md](mcp-reviews.md), `config/provenance.json` |
| 2. Reimplementación propia (proyecto, media, timeline, color, Fusion, audio, QC) | ✅ Hecho | tools de authoring, tabla de abajo |
| 3. Bridge Free propio (HMAC, antireplay, métodos explícitos) e instalador | ✅ Hecho, verificado en Free 21.0.4.5 | `bridge/`, `bridge_install/`, `test_bridge*.py` |
| 4. Retiro del código de terceros (servidor, patches, third_party/, gestor de referencias) | ✅ Hecho | `test_workspace.py`; wheel sin módulos externos |
| 5. Textos con diseño y animación (Creator/Studio/Editorial/Impact, preview) | ✅ Código y live de captions | `test_designed_captions.py`, `test_live_editing.py` |
| 6. Producción por género (comedia, música, electrónica, entrevista…) | ✅ Código y live de montaje/align · parcial para material real | `plan_edit`, `find_story_moments`, `plan_beat_cuts`, `assemble_montage`, `create_music_visualizer`, `align_text` |
| 7. Sonido (música bajo la voz con ducking, SFX motivados) | ✅ Live de bed/SFX; enhance_audio nuevo pendiente en Resolve | `add_music_bed`, `place_sound_effects` |
| 8. Documentación, skills y roles al día | ✅ Hecho | README (tabla verificada por test), skill `editorial-direction` |
| 9. Repetición live de la versión ampliada | ⏳ Última pasada pendiente | `tests/live/test_live_production.py`, karaoke y encuadre lateral listos; requiere bridge de Resolve actual |

En números: 65 tools, 658 pruebas sin Resolve aprobadas en la revisión del 2026-10-04.
La suite live reúne 13 casos, incluyendo sujeto centrado y lateral en la prueba de zoom. Primera pasada conectada: 10 aprobadas y un fallo SFX; tras corregirlo,
la prueba aislada SFX aprobó, al igual que la nueva prueba de encuadre/zoom vertical por píxeles.
La segunda pasada encontró un bridge huérfano ligado a un Resolve anterior: no se cuenta como aprobada.
Se retiró únicamente ese fuscript tras verificar ejecutable, script, puerto y padre muerto. Último inventario
real: ningún helper huérfano. El bridge de la instancia nueva aún debe iniciarse para la última pasada; además siguen pendientes material real de múltiples personas y revisión editorial de comedia.

## Ampliación de entretenimiento y acabado (2026-10-04)

- Ronda de acabado: nuevas `preflight_render`, `apply_grade_preset`, `enhance_audio`, `repair_bridge_connection`.
- Zooms: wide realmente fijo; focus/crash no agregan drift por encima del zoom revisado. La animación
  se limita al pico aprobado. Keyframes nativos parciales se limpian antes de caer a Fusion;
  pivotes y rechazos de escritura se comprueban. Cover/encuadre del sujeto se aplican y leen de vuelta.
- Revisión horizontal → vertical: viewport con proporción real y aumento efectivo de fuente.
  Prueba live de píxeles: zoom ×1.20, sujeto centrado, plano fijo y círculo sin distorsión, aprobada.
- Cortes: hints `subject=none` eliminan rangos vacíos confirmados aunque se mueva la cámara;
  `subject=animal|person` conserva sujetos quietos. No se afirma reconocimiento automático de animales.
- Hablantes: composición con cinco o más personas sin truncar a cuatro; caras completas con padding
  cuando no caben, origen de paneles corregido y estabilidad durante pausas. Boca + energía son candidatos,
  no identificación de voz ni diarización; material real con múltiples personas sigue requiriendo revisión.
- Texto: `animation=karaoke`, progreso por palabra, layout estable y reduced_motion respetado.
- Acabado: CDL natural/warm/crisp/muted con intensidad y preview, aplicado sobre copia; audio dialogue/podcast/
  entertainment a WAV nuevo con medición LUFS/true peak. No convierte Log/HDR, separa voces ni normaliza la mezcla final.
- QA: revisión técnica de cobertura, fuentes y transforms; revisión visual/escucha todavía obligatorias.
  Especialización portable `color-audio-finishing` integrada al productor y skills sincronizadas.
- Hallazgo live: Free 21 no devuelve Frames para ciertos WAV. SFX usa duración real del PCM como fallback;
  cálculo de lanes respeta FPS de fuente y timeline. Limitador sin makeup automático; conserva ganancia prevista.
  Prueba de sonido aislada aprobada después de corregirlo.
- Conexión: bridge disponible primero, sin probe nativo adicional cuando está ocupado; timeouts devuelven
  `RESOLVE_BUSY`. Recuperación Windows de helper huérfano con identidad/puerto/padre verificados y preview.
  No se reinicia Resolve ni se detiene un bridge vivo. Un timeout de escritura no autoriza repetirla a ciegas.

## Arquitectura

- domain/: decisiones puras (cortes, grafos, LUT, diseño de texto, momentos de historia, cortes al beat, ducking, alineación de texto); no conoce Resolve, MCP ni archivos.
- analysis/: decodificación y extracción de señales; no modifica el proyecto.
- services/: un módulo por responsabilidad. native.py comparte capacidades, rechazos, readback y creación de copias; media_lookup.py comparte selección de fuentes sin ambigüedad.
- tools.py, authoring_tools.py y production_tools.py: schemas MCP y delegación. Todas las llamadas a Resolve pasan por el mismo executor serial; no se accede a managers privados de FastMCP.
- gateway.py y native_paths.py: selección de transporte y SDK por sistema operativo; probe nativo aislado.
- bridge/: protocolo, autenticación y proxy separados de la política de llamadas. Runtime estándar sin librerías nativas. La lista de métodos es explícita; no hay execute_python/execute_lua ni una tool de llamada arbitraria.
- bridge_install/: instala nuestros módulos y launcher, conserva token y raíces. No descarga otro servidor.

Session y los objetos nativos son dependencias inyectadas en los casos de uso; las mismas herramientas funcionan con fakes directos o JSON y con Resolve real. No hay un servidor entero adaptado mediante monkey-patching.

## Selección y mejoras

| Capacidad estudiada | Implementación propia y mejora |
|---|---|
| Proyecto y backup (apvlv/DWC/hitesh) | project_workflow, configure_project: backups nuevos, guardado previo, comprobación del archivo y readback |
| Bins, import y metadata (DWC/hitesh) | list_media, ingest_media, organise_media, media_metadata: deduplicación por ruta, rechazo de nombres ambiguos, restauración del bin current |
| Timeline y tracks (DWC/hitesh) | timeline_versions, edit_clips, configure_track: previews por defecto, versiones sin sobrescritura, edición de propiedades sobre copias y readback |
| Marcadores y QC (DWC/hitesh/samuelgursky) | timeline_markers, audit_timeline: segundos relativos, verificación de rangos, preservación de marcadores existentes, gaps/overlaps y visibilidad de fuentes |
| Interchange | export_interchange: OTIO/FCPXML/AAF/EDL/DRT mediante constantes observadas, guardado previo, destino nuevo y verificación de archivo |
| Color y LUT (DWC/hitesh/samuelgursky) | grade_clips, inspect_grade, prepare_lut, gallery_stills: CDL validado, copias, tablas .cube finitas y completas, mezcla con identidad, archivos originales preservados |
| Fusion (apvlv/lordhoell) | apply_fusion_graph, inspect_fusion: DAG validado, ids propios, palette acotada, conexiones sin duplicados; valores fuera de Lock para que sobrevivan al render |
| Audio y análisis | analyse_audio, analyse_scenes, normalise_audio, sync_audio: cortes con margen de respiración, tiempos de fuente explícitos, histogramas de escena, loudness en dos pasos y medición del WAV final; ffmpeg viene en la dependencia de Forge |
| AI nativa (DWC/hitesh) | native_ai: capacidades observadas; subtítulos/scene cuts sobre copias, rechazo real en edición/build no compatible; alternativas locales Free |
| Capabilities/resources/arquitectura (kerwilgil/DWC) | list_capabilities, resources existentes, servicios por responsabilidad, errores tipados y transportes intercambiables |
| Transcripción y subtítulos (hiteshK03/samuelgursky) | transcribe_timeline, align_text, add_captions, list_text_styles, preview_text_style: tiempos de timeline para cada clip, texto exacto de guion/letra, diseños animados con palabra activa y preview antes de quemar |
| Análisis de beats y silencios (samuelgursky) | analyse_music, plan_beat_cuts, assemble_montage, create_music_visualizer: grilla con confianza, cortes por frases y más rápidos solo en rangos confirmados, música maestra continua, visualizer estéreo |
| Momentos y dirección (sin equivalente en los MCP estudiados) | plan_edit, find_story_moments: criterio por género y candidatos con evidencia (pausa+remate, reacción, pregunta, acento) que el agente confirma |
| Mezcla (sin equivalente) | add_music_bed, place_sound_effects: ducking desde la transcripción y SFX con motivo obligatorio, horneados en WAV nuevos sobre copias |
| Compatibilidad y seguridad | MCP<2, paths multiplataforma, consola cp1252, probe aislado, HMAC, expiración, antireplay para el intervalo completo, raíz de archivos y límite de requests; ninguna ejecución arbitraria |

No se incorporan cientos de wrappers de getters, gestión de bases de datos/cloud, destrucción de proyectos/media, ejecución de código ni instaladores/actualizadores de otros repos. Esta selección cubre los flujos de edición útiles y hace explícitos los límites.

## Verificación y límites

Los contratos se prueban en cuatro configuraciones (Free/Studio, bridge/directo y keyframes presentes/ausentes). Hay pruebas de aislamiento de master, rechazos nativos, marcadores relativos, deduplicación, ambigüedad, DAG, autenticación/replay, audio/escenas sintéticos y loudness del archivo final. La conexión y las lecturas se verifican en Resolve Free 21.0.4.5 con el bridge propio.

Verificación actual sin Resolve: 628 pruebas aprobadas en la suite completa; 16 pruebas de recuperación verificadas después de corregir el inventario real Windows. Wheel construido e inspeccionado sin módulos externos. Evidencia histórica en Resolve real: render con comparación de píxeles, motion/clear, formato vertical, subtítulos, marcadores, CDL y grafos Fusion. Esa evidencia no implica que la suite live se haya vuelto a ejecutar en esta revisión. El paquete wheel se construye sin módulos de los servidores externos; los proyectos de prueba se conservan y se restaura el proyecto anterior.

La disponibilidad de un método no garantiza que la edición/licencia acepte su ejecución: se comprueba el retorno. CDL solo puede verificarse por aceptación nativa y revisión visual. Los onsets son candidatos de energía, no un modelo de tempo/downbeat. No se afirma cobertura universal de todas las APIs de Resolve.

## Limpieza

Se retiraron el segundo servidor, patches, config/references.json y scripts/references.py. Se conservan los commits consultados en config/provenance.json. Los 154 archivos de third_party/ se retiraron del índice de Git y del disco. Por decisión del usuario, vendor/ y los restos de resolve_forge/api/ quedan locales e ignorados por Git; no se importan ni empaquetan, y no son necesarios para ejecutar o distribuir Forge.

## Estado para el próximo agente (Claude, Codex…)

Lee esto antes de seguir. Última actualización: 2026-10-04.

### Hecho
- Migración: Forge propio (65 tools), bridge propio, sin código ni servidores de terceros; 658 pruebas sin Resolve aprobadas el 2026-10-04.
- Revisión inicial: Resolve estaba cerrado y las pruebas live se omitieron. Después se conectó Free 21.0.4.5,
  aprobaron 10 casos y falló SFX por Frames ausente en WAV. La prueba aislada SFX aprobó tras corregirlo.
  Las fixtures guardan proyectos; la prueba de sonido crea montaje independiente y preserva la edición de imagen.
  La prueba de render de subtítulos ahora usa Creator/karaoke y verifica píxeles del acento de marca #FF3366.
  Creator/pop y la prueba de píxeles centrada aprobaron en Resolve. Karaoke, encuadre lateral, nuevo preset y
  enhance_audio sobre script real siguen pendientes de la última pasada tras ampliar las pruebas.
  Se identificó y retiró el bridge huérfano anterior; herramienta de recuperación comprobada en Windows con preview.
- Diseño de textos (pedido: subtítulos "bonitos", animados, no simples): estilos `creator`, `studio`, `editorial`,
  `impact` con palabra activa, acento de marca, entradas `fade/lift/pop`, `reduced_motion`, preview PNG/WebP
  (`list_text_styles`, `preview_text_style`). Legacy `box/outline/yellow/dark` solo a pedido.
- Producción por género (pedido: editar como productor profesional, música/electrónica, comedia, YouTube, nada robótico):
  - `plan_edit`: dirección, qué evitar, estilo de texto/motion y tools según el género.
  - `find_story_moments`: candidatos de remate (pausa + línea corta), reacción/risa (audio sin voz tras una línea),
    pregunta y palabra acentuada, con evidencia. Son candidatos: el agente los revisa.
  - `analyse_music` (BPM/beats/energía), `plan_beat_cuts` (cortes por frase, más rápidos solo en rangos confirmados),
    `assemble_montage` (música maestra continua en A1), `create_music_visualizer` (espectro/anillos con audio estéreo).
  - `align_text`: letra o guion exactos con los tiempos de la voz, listos para `add_captions(words=...)`.
  - `place_sound_effects`: SFX del usuario en momentos confirmados, con motivo, ganancia horneada y pistas nuevas.
  - `add_music_bed`: música de fondo con ducking bajo la voz (−20 dB al hablar, −10 dB entre frases), WAV nuevo.
  - Ritmo de entretenimiento: `plan_energized_edit` / `energize_timeline` (detección de acción, caras y tiempo muerto;
    planos de 1.2–2.8 s con encuadres alternos y crash zooms) y skill `entertainment-pacing`.
  - Autorrevisión: el plan baja zooms que recortan la acción, dejan al sujeto en el borde, cortan caras o pasan la
    nitidez de la fuente; `review_shots` (antes) y `review_video` (después) generan hojas que el agente debe mirar;
    color/exposición con CDL suave y textos que no tapan caras. Skill `video-qa`.
  - Interacción: los planos de personas de espaldas sin cara ni acción se cortan (`cut_dull`).
  - Varias personas: `plan_speaker_layout` / `build_speaker_layout` (hablante activo, pantalla dividida).
    Falta prueba con material real de varias personas.
  - Composición multi-fuente (pedido: referencias con varias tomas, entrevista + foto + apoyo):
    `plan_composition` / `build_composition` — mosaico 1–5 o hero + apoyo, inicio independiente por fuente,
    fotos fijas, `subject`/`crop` manual y un único audio maestro explícito; preview + hoja antes de construir.
  - Encargos del productor: `plan_production` genera órdenes para composition-editor, audio-editor, colorist,
    titles-editor y qa-editor (dependencias, tools, aceptación, informe). Solo el productor escribe en Resolve.
    Roles nuevos en `.agents/agents/` y `editorial-direction/references/producer-coordination.md`.
  - `clear_motion` rechaza (BACKEND_UNSUPPORTED) grafos Fusion con efectos ajenos y conserva el grafo;
    `review_video` incluye el último frame. El fake de DuplicateTimeline copia ahora las comps Fusion.
  - Skill `editorial-direction` y roles actualizados para usar todo lo anterior.

### Pendiente (por prioridad)
1. **Verificación en vivo**: `uv run pytest -m live` con Resolve abierto y el bridge iniciado.
   `tests/live/test_live_production.py` ya cubre montaje al beat (cortes ±1 frame, música continua en A1),
   `align_text` con Whisper real, `add_music_bed` y `place_sound_effects`. `test_live_editing.py` incluye ahora
   render de captions Creator con color de marca; falta ejecutarlo y mirar el resultado.
   Falta además `find_story_moments` sobre material real de comedia, el layout sobre varias personas reales y
   `build_composition(into_resolve=true)` en Resolve real con las referencias del usuario (collage de tomas).
   Motion Fusion sobre comps con efectos existentes se rechaza; insertar sin romper el grafo queda pendiente.
2. **Letras sobre mezcla**: `align_text(focus_vocals=true)` ayuda (canal central en banda de voz) pero no separa stems.
   Separación real (Demucs/torch) no se añadió: dependencia pesada, requiere confirmación del usuario.
3. **Mezcla**: hoy la ganancia de SFX y el ducking se hornean en WAV nuevos (no hay API verificada de volumen por clip).
   Si Resolve expone volumen/keyframes de audio verificables, migrar a eso para que sea editable en Fairlight.
4. Restos locales ignorados por Git (`vendor/`, `mcp/resolve-forge/src/resolve_forge/api/`): borrar solo si el usuario lo pide.

Verificado fuera de Resolve con audio real y Whisper real: `align_text` (100 % de palabras) y `find_story_moments`
(remate tras pausa de 2.2 s y pregunta detectados en un chiste TTS).

### Reglas que el usuario fijó
- Nada copiado de la competencia: ideas mejoradas, a nuestra manera (SRP/SOLID/DRY, domain → services → tools).
- Herramientas que miden; el criterio editorial (chiste, drop, emoción) lo confirma el agente viendo/escuchando.
- El agente actúa como productor: propone mejoras a la idea y edita según el género, nada robótico.
- Al añadir una tool: tabla del README, conteos (test), skill correspondiente y esta sección.
- Ediciones sobre copias; el master no se toca.
