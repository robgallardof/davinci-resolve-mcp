# Arquitectura de resolve-forge

```
tools.py ──► services/ ──► domain/          (puro: sin Resolve, 100 % testeable)
 (MCP fino)    │  motion_service   easing · keyframes · motion · styles · framing · formats
               │  format_service
               │  render_service
               │  appliers ─────► Strategy: EditKeyframeApplier | FusionTransformApplier
               │  subject  ─────► analysis/faces (opencv opcional)
               ▼
            gateway.py ──► DirectTransport (DaVinciResolveScript) | BridgeTransport (upstream, Free)
server.py = raíz de composición (crea Session, registra tools)
```

## Principios aplicados

- **SRP**: cada módulo tiene una razón para cambiar. La matemática de encuadre (`framing`) no sabe de MCP; las tools no saben de keyframes.
- **OCP**: estilos nuevos con `@style(...)`; backends nuevos en `APPLIERS`. No se edita el código existente.
- **LSP / ISP**: `Applier` es un `Protocol` mínimo (`apply`, `clear`). Cualquier backend que lo cumpla es intercambiable.
- **DIP**: los servicios dependen de `Session`, no del módulo nativo. Los tests inyectan fakes.
- **DRY**: una sola definición de cada curva de easing, de la que se derivan la interpolación de Resolve, los handles de Fusion y las muestras horneadas. Una sola fuente de configuración MCP (`config/mcp.servers.json`). Una sola copia de skills y agentes (`.agents/`, con links).
- **KISS**: 11 tools de intención. Lo granular lo hace el upstream.

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
