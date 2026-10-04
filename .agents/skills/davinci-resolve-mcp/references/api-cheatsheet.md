# Resolve scripting API — cheatsheet (sin MCP)

Referencia oficial instalada: `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\README.txt`.

## Conectar (Windows)

```python
import os, sys
os.environ.setdefault("RESOLVE_SCRIPT_API", r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting")
os.environ.setdefault("RESOLVE_SCRIPT_LIB", r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll")
sys.path.append(os.environ["RESOLVE_SCRIPT_API"] + r"\Modules")
import DaVinciResolveScript as dvr      # ⚠ segfault si Resolve.exe no está corriendo: compruébalo antes
resolve = dvr.scriptapp("Resolve")
project = resolve.GetProjectManager().GetCurrentProject()
tl = project.GetCurrentTimeline()
```

Usa Python 3.10–3.12 (el venv del upstream usa 3.12).

## Timeline e items

```python
fps = float(tl.GetSetting("timelineFrameRate"))
items = tl.GetItemListInTrack("video", 1)
it = items[0]; it.GetStart(); it.GetDuration(); it.GetSourceStartFrame()
it.GetMediaPoolItem().GetClipProperty("Resolution")      # "1920x1080"
it.GetMediaPoolItem().GetClipProperty("File Path")
```

## Transform estático (Inspector)

```python
it.SetProperty("ZoomX", 1.15); it.SetProperty("ZoomY", 1.15)
it.SetProperty("Pan", -120.0)    # px, + derecha
it.SetProperty("Tilt", 40.0)     # px, + arriba
it.SetProperty("RotationAngle", 0.5)
```

## Keyframes nativos (Resolve 20+)

```python
it.AddKeyframe("ZoomX", 0, 1.0)            # frame relativo al clip
it.AddKeyframe("ZoomX", 90, 1.12)
it.SetKeyframeInterpolation("ZoomX", 0, "EaseInOut")   # Linear | Bezier | EaseIn | EaseOut | EaseInOut
it.GetKeyframeCount("ZoomX"); it.GetKeyframeAtIndex("ZoomX", 0); it.DeleteKeyframe("ZoomX", 90)
```

## Fusion Transform con keyframes (cualquier versión)

```python
comp = it.GetFusionCompByIndex(1) if it.GetFusionCompCount() else it.AddFusionComp()
mi, mo = comp.FindTool("MediaIn1"), comp.FindTool("MediaOut1")
comp.Lock()                                   # SOLO estructura dentro del lock
tf = comp.AddTool("Transform", -32768, -32768)
tf.ConnectInput("Input", mi); mo.ConnectInput("Input", tf)
comp.Unlock()
t0 = comp.GetAttrs()["COMPN_RenderStart"]     # offset de tiempo del comp
comp.StartUndo("zoom")
tf.SetInput("Pivot", {1: 0.5, 2: 0.62})       # Fusion: origen abajo-izquierda
tf.AddModifier("Size", "BezierSpline")        # sin spline, SetInput(t) no crea keyframes
tf.SetInput("Size", 1.0, t0); tf.SetInput("Size", 1.1, t0 + 90)
comp.EndUndo(True)
```

## Timeline vertical

```python
copy = tl.DuplicateTimeline("Master [tiktok]")       # ⚠ pasa a ser el current
copy.SetSetting("useCustomSettings", "1")
copy.SetSetting("timelineResolutionWidth", "1080")
copy.SetSetting("timelineResolutionHeight", "1920")
# Studio: it.SmartReframe()
```

## Render

```python
project.SetCurrentRenderFormatAndCodec("mp4", "H264")
project.SetRenderSettings({"SelectAllFrames": True, "TargetDir": r"D:\exports",
                           "CustomName": "clip_tiktok", "FormatWidth": 1080, "FormatHeight": 1920})
job = project.AddRenderJob(); project.StartRendering([job], False)
project.GetRenderJobStatus(job)
```
