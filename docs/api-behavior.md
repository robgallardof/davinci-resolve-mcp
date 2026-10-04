# Comportamientos de Resolve que Forge debe respetar

- DuplicateTimeline puede mover el timeline current; los servicios crean una copia nueva y seleccionan explícitamente el destino.
- AppendToTimeline usa endFrame exclusivo y recordFrame absoluto; las decisiones editoriales de herramientas usan segundos y se convierten una sola vez.
- Fusion: los valores escritos bajo comp.Lock pueden leerse pero no afectar el render. El lock se reserva para estructura; SetInput se ejecuta tras Unlock.
- Fusion SetInput puede devolver None aunque aplique el cambio: se verifica con GetInput; False o un valor distinto se reportan como fallo.
- Las capacidades se observan por métodos y retornos, no por asumir que un número de versión o Studio basta.
- En Free el bridge transporta JSON. Los objetos remotos son handles; no se usan indexadores de tools ni argumentos keyword en métodos nativos.
- Render: CustomName no vacío, SaveProject previo, codecs dependientes de edición/hardware, archivos bajo las raíces del bridge.
- Marcadores de timeline usan frames relativos a su inicio; los recordFrame de assembly son absolutos.
- Audio: AppendToTimeline con mediaType=2 coloca solo audio y mediaType=1 solo video (montajes con música maestra
  continua). No hay un método documentado y verificado para el volumen de un clip, así que la ganancia de SFX y el
  ducking de música se hornean en un WAV nuevo (ffmpeg/numpy) y se colocan en pistas de audio nuevas.
- Rangos de audio: el startFrame/endFrame de un clip de audio usa el FPS que reporta el clip (o el del timeline);
  el redondeo a frames puede mover un corte al beat hasta un frame.

- Frame rate: un timeline nuevo hereda el rate del PROYECTO (a menudo 24 fps). Con useCustomSettings=1 y antes de
  añadir clips se fija timelineFrameRate al rate estándar más cercano a la fuente (un móvil reporta 29.92 → 30).
- Secuencias de imágenes (tarjetas de texto/subtítulos) se importan al rate del PROYECTO: en un timeline de 30 fps
  dentro de un proyecto de 24 duraban 1.25× y la animación iba lenta. Se fija SetClipProperty("FPS") al rate del
  timeline tras importar (Resolve 21 Free lo acepta) y, si no, se recalcula endFrame.
- Bridge en Free: los scripts corren en fuscript.exe y los objetos de Resolve solo responden en el hilo del script.
  Las llamadas se encolan al hilo principal. Un fuscript huérfano de una sesión anterior de Resolve puede retener el
  puerto (todos los objetos devuelven vacío): el bridge sale solo cuando su Resolve deja de responder, y `health`
  informa `root_type`. Diagnóstico: proceso que escucha en el puerto vs hora de inicio de Resolve.
- Mientras Resolve reproduce el timeline (o renderiza, o tiene un diálogo abierto) no atiende llamadas de script:
  el bridge queda bloqueado dentro de la llamada (la API nativa retiene el GIL, así que ni `health` responde).
  Se resuelve deteniendo la reproducción; Forge lo informa como "Resolve is busy" en vez de "cannot reach".
- Proxies nativos pueden devolver dir() vacío: la lista de métodos se sondea contra la allowlist.
- OpenCV 5 eliminó CascadeClassifier: `vision` fija opencv<5 y el ancla de cara cae a la posición por defecto si falta.

Guardas correspondientes: tests/unit/test_bridge.py, test_edit_decisions.py, tests/integration/test_authoring_tools.py y test_story_and_beat_tools.py; render/Fusion cuentan además con la suite live existente.

### WAV sin Frames en Free 21 (2026-10-04)

En la prueba live de producción, un WAV PCM importado devolvió Frames vacío. No significa duración cero: SFX lee getnframes/framerate del archivo WAV y convierte a FPS de fuente, y convierte aparte la duración de lanes a FPS de timeline. Ver test_live_production.py.
