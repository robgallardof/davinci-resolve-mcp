# Primeros pasos (10 minutos)

Guía paso a paso para tu primer video editado por un agente. Vale igual para Resolve **Free** y **Studio**.

## 1. Instala (una sola vez)

```powershell
cd C:\Users\<tú>\Documents\Projects\davinci-agents
pwsh scripts/bootstrap.ps1
```

Al terminar deberías ver `Listo.`. Si DaVinci Resolve estaba abierto, **ciérralo y vuelve a abrirlo**
para que cargue el script del bridge.

## 2. Abre Resolve y conecta

1. Abre DaVinci Resolve.
2. En el Project Manager abre tu proyecto (o crea uno con **New Project**).
   > Si cierras el Project Manager sin abrir un proyecto, Resolve se cierra.
3. **Free**: menú **Workspace → Scripts → resolve_bridge**. No verás ninguna ventana: el bridge queda escuchando en segundo plano.
   **Studio**: Preferences → System → General → *External scripting using* = **Local** (una sola vez).
4. Comprueba la conexión:

```powershell
cd mcp/resolve-forge
uv run resolve-forge-doctor
```

Tiene que decir `[OK] Conexión: Free 21.x vía bridge` (o `Studio … vía direct`). Si algo falla, la última línea te dice qué hacer.

## 3. Prepara un timeline

En Resolve: importa un clip de alguien hablando (Media Pool → clic derecho → Import Media) y arrástralo
a un timeline nuevo. Con un clip de 20–60 s alcanza.

## 4. Abre tu agente en esta carpeta

```powershell
cd C:\Users\<tú>\Documents\Projects\davinci-agents
claude          # o codex / gemini, o abre la carpeta en Cursor / VS Code
```

La primera vez, aprueba el servidor MCP `resolve-forge` (es el único).

## 5. Primeros pedidos

Copia estos de a uno y mira el resultado en Resolve después de cada uno:

```text
1) Dime el estado de Resolve y qué clips hay en el timeline.
2) Muéstrame cómo quedaría un estilo youtube_dynamic en este clip, sin aplicarlo.
3) Aplica youtube_dynamic con intensidad 0.8 anclado a la cara.
4) Haz una versión vertical para Reels de este timeline y dale tiktok_smooth.
5) Ponle subtítulos bonitos con mi color de marca #FF5A36; muéstrame antes cómo se ven.
6) Pon música de fondo bajo la voz con este archivo: C:/ruta/musica.mp3
7) Exporta la versión vertical para Reels y la horizontal para YouTube 1080.
```

Qué vas a ver:

- Paso 3: en Free, los clips tienen un nodo **ForgeMotion** en la página Fusion. En Studio aparecen keyframes en el Inspector.
- Paso 4: un timeline nuevo `… [reels]` de 1080×1920. El original no cambia.
- Paso 5: un preview (PNG y WebP animado) y después una pista nueva con subtítulos animados, palabra activa resaltada.
- Paso 6: una pista de audio nueva con la música bajando cuando hablas y subiendo entre frases (archivo nuevo; tu música original no cambia).
- Paso 7: los archivos en `~/Movies/resolve-forge/`.

## 6. Pide como editor, no como técnico

Los agentes entienden intención. Algunos ejemplos:

- "Del podcast saca un video para YouTube y 3 clips verticales de 30 s con lo mejor." → `video-director`
- "Que no se vea estático, pero sin marear." → `warm_push` o `youtube_dynamic` con intensidad baja
- "Más energía, estilo TikTok." → `tiktok_punch` con intensidad 1.2
- "Haz zoom cuando dice 'importante' en 0:15 y 0:48." → `emphasis` con esos segundos
- "Versión para LinkedIn." → `linkedin_1080` o `square`, con subtítulos
- "Es comedia: encuentra los remates y no cortes las risas." → `find_story_moments` + `plan_edit` (skill `editorial-direction`)
- "Videoclip de mi canción con cortes al beat y la letra exacta." → `analyse_music`, `plan_beat_cuts`, `assemble_montage`, `align_text`
- "Un whoosh cuando cambio de tema." → `place_sound_effects` con tu archivo de sonido

El agente propone mejoras a tu idea, pero los momentos (chiste, drop, emoción) los confirma viendo o escuchando:
las herramientas dan candidatos con evidencia, no deciden solas.

## 7. Si algo sale mal

- `uv run resolve-forge-doctor` siempre primero.
- Quitar el movimiento: "quita el movimiento de forge de todos los clips" (`clear_motion`).
- Volver al original: el master nunca se toca; las versiones son timelines nuevos que puedes borrar.
- "Cannot reach DaVinci Resolve": abre un proyecto (no basta el Project Manager) y vuelve a lanzar Workspace → Scripts → resolve_bridge.
- Falta transcripción o análisis de audio (`MISSING_DEPENDENCY`): `cd mcp/resolve-forge && uv sync --extra speech --extra vision`.
- En Free, el render solo escribe dentro de `~/Movies`.

## 8. Comprueba que todo funciona en tu equipo

```powershell
cd mcp/resolve-forge
uv run pytest            # sin Resolve
uv run pytest -m live    # con Resolve abierto y el bridge activo; crea proyectos forge_* que se conservan para inspección
```
