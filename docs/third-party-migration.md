# Migración: herramientas propias a partir del análisis de la competencia

Forge implementa 52 herramientas propias: edición editorial, producción por género, sonido y authoring de proyectos,
media, timeline, color, Fusion y QC. No importa ni empaqueta código de los MCP estudiados.

## ¿Cuánto lleva? (2026-10-04)

**Código y pruebas sin Resolve: completo. Verificación en Resolve real: parcial (falta lo nuevo de producción).**

| Fase | Estado | Evidencia |
|---|---|---|
| 1. Estudio de los 7 MCP públicos y selección | ✅ Hecho | [mcp-landscape.md](mcp-landscape.md), [mcp-reviews.md](mcp-reviews.md), `config/provenance.json` |
| 2. Reimplementación propia (proyecto, media, timeline, color, Fusion, audio, QC) | ✅ Hecho | tools de authoring, tabla de abajo |
| 3. Bridge Free propio (HMAC, antireplay, métodos explícitos) e instalador | ✅ Hecho, verificado en Free 21.0.4.5 | `bridge/`, `bridge_install/`, `test_bridge*.py` |
| 4. Retiro del código de terceros (servidor, patches, third_party/, gestor de referencias) | ✅ Hecho | `test_workspace.py`; wheel sin módulos externos |
| 5. Textos con diseño y animación (Creator/Studio/Editorial/Impact, preview) | ✅ Código y live de captions | `test_designed_captions.py`, `test_live_editing.py` |
| 6. Producción por género (comedia, música, electrónica, entrevista…) | ✅ Código · ⏳ live pendiente | `plan_edit`, `find_story_moments`, `plan_beat_cuts`, `assemble_montage`, `create_music_visualizer`, `align_text` |
| 7. Sonido (música bajo la voz con ducking, SFX motivados) | ✅ Código · ⏳ live pendiente | `add_music_bed`, `place_sound_effects` |
| 8. Documentación, skills y roles al día | ✅ Hecho | README (tabla verificada por test), skill `editorial-direction` |
| 9. Prueba live de las fases 6–7 | ⏳ Pendiente | `tests/live/test_live_production.py` (listo, falta ejecutarlo con el bridge) |

En números: 52 tools, 497 pruebas sin Resolve aprobadas, lint sin errores. Lo único que falta para cerrar es ejecutar
la suite live con Resolve abierto y el bridge iniciado (Workspace → Scripts → resolve_bridge).

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

Verificación de esta migración: 497 pruebas sin Resolve aprobadas; pruebas en Resolve real de render con comparación de píxeles, motion/clear, formato vertical, subtítulos, marcadores, CDL y grafos Fusion. El paquete wheel se construye sin módulos de los servidores externos; los proyectos de prueba se conservan y se restaura el proyecto anterior.

La disponibilidad de un método no garantiza que la edición/licencia acepte su ejecución: se comprueba el retorno. CDL solo puede verificarse por aceptación nativa y revisión visual. Los onsets son candidatos de energía, no un modelo de tempo/downbeat. No se afirma cobertura universal de todas las APIs de Resolve.

## Limpieza

Se retiraron el segundo servidor, patches, config/references.json y scripts/references.py. Se conservan los commits consultados en config/provenance.json. Los 154 archivos de third_party/ se retiraron del índice de Git y del disco. Por decisión del usuario, vendor/ y los restos de resolve_forge/api/ quedan locales e ignorados por Git; no se importan ni empaquetan, y no son necesarios para ejecutar o distribuir Forge.

## Estado para el próximo agente (Claude, Codex…)

Lee esto antes de seguir. Última actualización: 2026-10-04.

### Hecho
- Migración: Forge propio (52 tools), bridge propio, sin código ni servidores de terceros; 497 pruebas sin Resolve.
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
  - Skill `editorial-direction` y roles actualizados para usar todo lo anterior.

### Pendiente (por prioridad)
1. **Verificación en vivo**: `uv run pytest -m live` con Resolve abierto y el bridge iniciado.
   `tests/live/test_live_production.py` ya cubre montaje al beat (cortes ±1 frame, música continua en A1),
   `align_text` con Whisper real, `add_music_bed` y `place_sound_effects`. Faltan además: render de captions de diseño
   con color de marca y `find_story_moments` sobre material real de comedia.
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
