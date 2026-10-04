# Referencias y coordinación del productor

Lee esta referencia para piezas con varios especialistas, referencias visuales o composición de varios planos.
El productor posee las decisiones finales y la escritura MCP; los especialistas proponen sobre evidencia.

## Interpretar la referencia

Separa lo observado de su aplicación: fuentes/ángulos, sujetos reales, continuidad temporal, jerarquía de
paneles, texto y función narrativa. No deduzcas cuatro participantes porque haya cuatro imágenes: pueden
ser tomas diferentes de una misma persona. Entrevista + fotografía + plano con cámara puede sugerir apoyo,
contexto o historia; no obliga a mantener un collage toda la duración.

Para cada idea registra `observation`, `candidate`, `reason`, `use_when`, `avoid_when` y `available_sources`.
Si faltan tomas equivalentes, elige una adaptación honesta (recorte comprobado, B-roll disponible, otro layout);
no promete perspectiva nueva a partir de un único plano. El número de personas por sí solo no elige layout.
Dos hablantes horizontales en vertical pueden alternar caras con turnos confirmados y reacciones protegidas;
grupo numeroso puede funcionar mejor con rotación/plano general que con caras ilegibles en miniatura.

## Brief y contrato de propuesta

Entrega a cada especialista el mismo `job_id`, objetivo/género, referencias observadas, formato/dimensiones/FPS,
proyecto/timeline y versión, copia de trabajo, fuentes con identificadores estables/rangos, montaje confirmado,
límites de autoridad, dueño de tarea, dependencias y aceptación. Rangos fuente y timeline son distintos: usa
segundos relativos a su inicio declarado, intervalos `[start, end)`, y conserva offsets/FPS para conversión.
Al cambiar montaje actualiza versión y remapeo; un plan sobre versión anterior no se aplica.

Usa JSON para la propuesta; este es un contrato de coordinación, no una tool MCP ni un schema implementado:

```json
{
  "job_id": "reel-01",
  "owner": "composition-editor",
  "base_version": "cut-v2",
  "target": {"project": "Proyecto", "timeline": "Reel_COPY", "format": "vertical"},
  "depends_on": ["cut-v2"],
  "observations": [{"evidence": "frame-001.png", "finding": "La referencia reúne tomas de una persona"}],
  "proposals": [{
    "id": "composition-01",
    "source_id": "clip-A",
    "source_range_s": [4.0, 7.0],
    "timeline_range_s": [0.0, 3.0],
    "reason": "Acercar la reacción confirmada",
    "operation": {"tool": null, "args": {}, "schema_verified": false},
    "acceptance": ["Cara completa en inicio, mitad y final", "Sin salto de zoom"],
    "evidence_required": ["before_after_same_time", "readback"],
    "uncertainties": []
  }],
  "blockers": [],
  "status": "proposed"
}
```

`operation.tool` y `args` solo se completan con nombres/parámetros de tools disponibles y schemas inspeccionados;
si no están disponibles deja null y explica operación deseada. Nunca inventes una tool para satisfacer el contrato.
Para herramientas de planning existentes, adjunta sus resultados y avisos sin confundirlos con ejecución.
Personas/cajas/turnos incluyen evidencia y confianza; no etiquetas una detección como confirmada sin revisión.

## Aplicación serial y evidencia

Solo coordinador ejecuta mutaciones MCP y operaciones que seleccionen proyecto/timeline. Los especialistas
usan copias de artefactos locales para trabajo paralelo. Ni lectura de estado equivale a permiso para cambiarlo.
Antes de aplicar: target activo correcto, versión vigente, argumentos verificados, dependencias satisfechas y
preview/dry-run revisado si existe. Tras aplicar: registra resultado, readback, evidencia visual/sonora y versión
nueva. Distingue `planned`, `applied`, `verified`, `failed`; no declares verificado solo por retorno exitoso.
En timeout/fallo inspecciona estado para saber si hubo cambio antes de reintentar.

Composición/corte preceden texto y sincronía audio. Audio y color pueden analizarse en paralelo con geometría,
pero su aplicación se serializa. Recortes nuevos invalidan cues; paneles nuevos invalidan zonas de texto. QA
devuelve `severity`, `timeline_range_s`, `evidence`, `owner`, `fix`, `acceptance` y estado; productor resuelve
conflictos estéticos y reasigna defectos. No permite render final con bloqueantes. Guarda proyecto antes.

QA anterior al render: revisión visual de planos y animaciones, exactitud de texto, escucha de mezcla y
`preflight_render`. QA posterior: archivo real, specs/mediciones y `review_video` observado más escucha.
Reporta cobertura y pendientes, no una promesa de perfección. Un contacto de frames no prueba cada frame;
LUFS correcto no prueba inteligibilidad; readback de LUT no prueba piel natural.
