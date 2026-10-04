# Resolve behaviours Forge must respect

- DuplicateTimeline can move the current timeline; services create a new copy and select the target explicitly.
  It copies each clip's Fusion comps (tools, values and connections).
- AppendToTimeline uses an exclusive endFrame and an absolute recordFrame; editorial decisions in tools use seconds and are converted once.
- Fusion: values written under comp.Lock can be read back but do not affect the render. The lock is reserved for structure; SetInput runs after Unlock.
- Fusion SetInput can return None even when it applies the change: it is verified with GetInput; False or a different value is reported as a failure.
- Fusion motion only edits comps that contain MediaIn/MediaOut, ForgeMotion and its splines; comps with other effects are refused (BACKEND_UNSUPPORTED) and preserved.
- Capabilities are observed through methods and return values, never assumed from a version number or Studio.
- In Free the bridge carries JSON. Remote objects are handles; no tool indexers or keyword arguments on native methods.
- Render: non-empty CustomName, SaveProject first, codecs depend on edition/hardware, files under the bridge roots.
- Timeline markers use frames relative to its start; assembly recordFrames are absolute.
- Audio: AppendToTimeline with mediaType=2 places audio only and mediaType=1 video only (montages with a continuous
  music master). There is no documented, verified method for a clip's volume, so SFX gain and music ducking
  are baked into a new WAV (ffmpeg/numpy) and placed on new audio tracks.
- Audio ranges: an audio clip's startFrame/endFrame uses the FPS the clip reports (or the timeline's);
  rounding to frames can move a beat cut by up to one frame.
- Frame rate: a new timeline inherits the PROJECT rate (often 24 fps). With useCustomSettings=1 and before
  adding clips, timelineFrameRate is set to the standard rate closest to the source (a phone reports 29.92 → 30).
- Image sequences (text/caption cards) are imported at the PROJECT rate: on a 30 fps timeline
  inside a 24 fps project they lasted 1.25× and the animation was slow. SetClipProperty("FPS") is set to the timeline
  rate after import (Resolve 21 Free accepts it) and, otherwise, endFrame is recomputed.
- Bridge in Free: scripts run in fuscript.exe and Resolve objects only respond on the script's thread.
  Calls are queued to the main thread. An orphaned fuscript from a previous Resolve session can hold the
  port (every object returns empty): the bridge exits on its own when its Resolve stops responding, and `health`
  reports `root_type`. Diagnosis: the process listening on the port vs Resolve's start time; `repair_bridge_connection` automates it.
- While Resolve plays the timeline (or renders, or has a dialog open) it does not serve script calls:
  the bridge blocks inside the call (the native API holds the GIL, so not even `health` responds).
  Stopping playback resolves it; Forge reports it as RESOLVE_BUSY instead of "cannot reach".
- Native proxies can return an empty dir(): the method list is probed against the allowlist.
- OpenCV 5 removed CascadeClassifier: `vision` pins opencv<5 and the face anchor falls back to the default position if missing.

Matching guards: tests/unit/test_bridge.py, test_edit_decisions.py, tests/integration/test_authoring_tools.py and test_story_and_beat_tools.py; render/Fusion are also covered by the live suite.

### WAV without Frames in Free 21 (2026-10-04)

In the live production test, an imported PCM WAV returned empty Frames. It does not mean zero duration: SFX reads getnframes/framerate from the WAV file and converts to the source FPS, and separately converts lane duration to the timeline FPS. See test_live_production.py.
