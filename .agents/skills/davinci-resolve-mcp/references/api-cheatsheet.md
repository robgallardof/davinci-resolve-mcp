# Resolve scripting API — cheatsheet (without MCP)

Official installed reference: `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\README.txt`.

## Connect (Windows)

```python
import os, sys
os.environ.setdefault("RESOLVE_SCRIPT_API", r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting")
os.environ.setdefault("RESOLVE_SCRIPT_LIB", r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll")
sys.path.append(os.environ["RESOLVE_SCRIPT_API"] + r"\Modules")
import DaVinciResolveScript as dvr      # ⚠ segfaults if Resolve.exe is not running: check first
resolve = dvr.scriptapp("Resolve")
project = resolve.GetProjectManager().GetCurrentProject()
tl = project.GetCurrentTimeline()
```

Use Python 3.10–3.12 (the resolve-forge venv uses 3.12).

## Timeline and items

```python
fps = float(tl.GetSetting("timelineFrameRate"))
items = tl.GetItemListInTrack("video", 1)
it = items[0]; it.GetStart(); it.GetDuration(); it.GetSourceStartFrame()
it.GetMediaPoolItem().GetClipProperty("Resolution")      # "1920x1080"
it.GetMediaPoolItem().GetClipProperty("File Path")
```

## Static transform (Inspector)

```python
it.SetProperty("ZoomX", 1.15); it.SetProperty("ZoomY", 1.15)
it.SetProperty("Pan", -120.0)    # px, + right
it.SetProperty("Tilt", 40.0)     # px, + up
it.SetProperty("RotationAngle", 0.5)
```

## Native keyframes (Resolve 20+)

```python
it.AddKeyframe("ZoomX", 0, 1.0)            # frame relative to the clip
it.AddKeyframe("ZoomX", 90, 1.12)
it.SetKeyframeInterpolation("ZoomX", 0, "EaseInOut")   # Linear | Bezier | EaseIn | EaseOut | EaseInOut
it.GetKeyframeCount("ZoomX"); it.GetKeyframeAtIndex("ZoomX", 0); it.DeleteKeyframe("ZoomX", 90)
```

## Fusion Transform with keyframes (any version)

```python
comp = it.GetFusionCompByIndex(1) if it.GetFusionCompCount() else it.AddFusionComp()
mi, mo = comp.FindTool("MediaIn1"), comp.FindTool("MediaOut1")
comp.Lock()                                   # ONLY structure inside the lock
tf = comp.AddTool("Transform", -32768, -32768)
tf.ConnectInput("Input", mi); mo.ConnectInput("Input", tf)
comp.Unlock()
t0 = comp.GetAttrs()["COMPN_RenderStart"]     # comp time offset
comp.StartUndo("zoom")
tf.SetInput("Pivot", {1: 0.5, 2: 0.62})       # Fusion: origin bottom-left
tf.AddModifier("Size", "BezierSpline")        # without a spline, SetInput(t) creates no keyframes
tf.SetInput("Size", 1.0, t0); tf.SetInput("Size", 1.1, t0 + 90)
comp.EndUndo(True)
```

## Timeline vertical

```python
copy = tl.DuplicateTimeline("Master [tiktok]")       # ⚠ becomes the current timeline
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
