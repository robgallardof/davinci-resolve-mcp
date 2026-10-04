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

Guardas correspondientes: tests/unit/test_bridge.py, test_edit_decisions.py, tests/integration/test_authoring_tools.py y test_story_and_beat_tools.py; render/Fusion cuentan además con la suite live existente.
