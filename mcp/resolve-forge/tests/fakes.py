"""In-memory stand-ins for the Resolve/Fusion API surface resolve-forge touches.

Two editions are modelled because their differences are what break tools in practice:
  * studio — SmartReframe works, H.265 renders, reached directly.
  * free   — no SmartReframe, H.264 only, reached through the in-app bridge,
             which `BridgeLike` imitates: every argument and return value goes
             through JSON (numeric dict keys become strings), unknown attributes
             raise AttributeError, and there is no item indexing.
`keyframes=False` models Resolve 19 (no TimelineItem.AddKeyframe).
"""

from __future__ import annotations

import copy
import json
from typing import Any

TIMELINE_START = 86400  # 01:00:00:00 at 24 fps — Resolve's default origin


class MediaPoolItem:
    def __init__(self, name: str, width: int = 1920, height: int = 1080, path: str = "", frames: int = 300,
                 fps: float = 30):
        self.name, self.width, self.height, self.path, self.frames, self.fps = name, width, height, path, frames, fps
        self.metadata = {}

    def GetName(self): return self.name

    def GetMetadata(self): return dict(self.metadata)
    def SetMetadata(self, values):
        self.metadata.update(values)
        return True

    def GetClipProperty(self, key=None):
        props = {"Resolution": f"{self.width}x{self.height}", "File Path": self.path, "Frames": str(self.frames),
                 "FPS": str(self.fps)}
        return props if key is None else props.get(key, "")


class Folder:
    def __init__(self, name: str):
        self.name, self.clips, self.subfolders = name, [], []

    def GetName(self): return self.name
    def GetClipList(self): return list(self.clips)
    def GetSubFolderList(self): return list(self.subfolders)


class MediaPool:
    """ImportMedia, AppendToTimeline and folders, with Resolve's real quirks:
    a folder of numbered PNGs imports as ONE sequence clip; stills would ignore endFrame."""

    def __init__(self, project: "Project"):
        self.project, self.root = project, Folder("Master")
        self.current = self.root

    def GetRootFolder(self): return self.root
    def GetCurrentFolder(self): return self.current

    def SetCurrentFolder(self, folder):
        self.current = folder
        return True

    def AddSubFolder(self, parent, name):
        sub = Folder(name)
        parent.subfolders.append(sub)
        return sub

    def AutoSyncAudio(self, clips, options):
        self.synced = ([clip.GetName() for clip in clips], options)
        return True

    def ImportMedia(self, paths):
        from pathlib import Path
        out = []
        for raw in paths:
            p = Path(raw)
            if p.is_dir():
                frames = sorted(p.glob("*.png"))
                if not frames:
                    continue
                item = MediaPoolItem(f"{p.name}_[0000-{len(frames) - 1:04d}].png", path=str(p), frames=len(frames))
            elif p.is_file():
                item = MediaPoolItem(p.name, path=str(p), frames=self.project.resolve.import_frames)
            else:
                continue
            self.current.clips.append(item)
            out.append(item)
        return out

    def MoveClips(self, clips, destination):
        for clip in clips:
            for folder in [self.root, *self.root.subfolders]:
                if clip in folder.clips:
                    folder.clips.remove(clip)
            destination.clips.append(clip)
        return True

    def CreateEmptyTimeline(self, name):
        tl = Timeline(self.project, name, [[]])
        self.project.timelines.append(tl)
        return tl

    def AppendToTimeline(self, infos):
        tl, placed = self.project.current, []
        for info in infos:
            track = int(info.get("trackIndex", 1))
            target_tracks = tl.audio_tracks if info.get("mediaType") == 2 else tl.tracks
            while len(target_tracks) < track:
                target_tracks.append([])
            item = TimelineItem(info["mediaPoolItem"], int(info["recordFrame"]),
                                int(info["endFrame"]) - int(info["startFrame"]), edition=self.project.resolve,
                                left=int(info["startFrame"]))
            target_tracks[track - 1].append(item)
            placed.append(item)
        return placed


class FusionTool:
    def __init__(self, comp: "FusionComp", name: str, reg: str):
        self.comp, self.name, self.reg = comp, name, reg
        self.static: dict[str, Any] = {}
        self.timed: dict[str, dict[float, float]] = {}
        self.connected: dict[str, "FusionTool"] = {}
        self.animated: set[str] = set()

    def GetAttrs(self): return {"TOOLS_Name": self.name, "TOOLS_RegID": self.reg}

    def SetAttrs(self, attrs):
        self.comp.tools.pop(self.name)
        self.name = attrs["TOOLS_Name"]
        self.comp.tools[self.name] = self
        return True

    def ConnectInput(self, inp, tool):
        self.connected[inp] = tool
        return True

    def AddModifier(self, inp, reg):
        self.animated.add(inp)
        return True

    def SetInput(self, inp, value, time=None):
        if self.comp.locked and time is not None:
            self.comp.writes_under_lock += 1  # real Resolve ignores these at render
        if time is None:
            self.static[inp] = value
        elif inp in self.animated:
            self.timed.setdefault(inp, {})[float(time)] = value
        else:
            self.static[inp] = value  # no spline: a timed write is just a static write
        return True

    def GetInput(self, inp): return self.static.get(inp)

    def Delete(self):
        self.comp.tools.pop(self.name)


class FusionComp:
    def __init__(self, render_start: float = 0.0):
        self.tools: dict[str, FusionTool] = {}
        self.locked, self.writes_under_lock, self.render_start = False, 0, render_start
        for name, reg in (("MediaIn1", "MediaIn"), ("MediaOut1", "MediaOut")):
            self.tools[name] = FusionTool(self, name, reg)
        self.tools["MediaOut1"].connected["Input"] = self.tools["MediaIn1"]

    def FindTool(self, name): return self.tools.get(name)
    def Lock(self): self.locked = True
    def Unlock(self): self.locked = False
    def StartUndo(self, _name): return True
    def EndUndo(self, _keep): return True
    def GetAttrs(self): return {"COMPN_RenderStart": self.render_start}

    def AddTool(self, reg, _x=-32768, _y=-32768):
        n = 1
        while f"{reg}{n}" in self.tools:
            n += 1
        tool = FusionTool(self, f"{reg}{n}", reg)
        self.tools[tool.name] = tool
        return tool


class TimelineItem:
    def __init__(self, mpi: MediaPoolItem | None, start: int, duration: int, *, edition: "Resolve", left: int = 0):
        self.mpi, self.start, self.duration, self.edition, self.left = mpi, start, duration, edition, left
        self.props = {"ZoomX": 1.0, "ZoomY": 1.0, "Pan": 0.0, "Tilt": 0.0, "RotationAngle": 0.0}
        self.keys: dict[str, dict[int, float]] = {}
        self.interp: dict[tuple[str, int], str] = {}
        self.comps: list[FusionComp] = []
        self.smart_reframed = False
        self.cdl: list[dict] = []
        self.luts: dict[int, str] = {}

    def __getattr__(self, name):
        # Resolve 19 has no keyframe family; strict like the real proxy.
        if name in ("AddKeyframe", "SetKeyframeInterpolation", "GetKeyframeCount",
                    "GetKeyframeAtIndex", "DeleteKeyframe") and self.edition.keyframes:
            return getattr(self, "_" + name)
        raise AttributeError(name)

    def GetName(self): return self.mpi.GetName() if self.mpi else "Text+"
    def GetStart(self, *_): return self.start
    def GetEnd(self, *_): return self.start + self.duration
    def GetDuration(self, *_): return self.duration
    def GetMediaPoolItem(self): return self.mpi
    def GetSourceStartFrame(self): return self.left
    def GetLeftOffset(self, *_): return self.left
    def GetSourceEndFrame(self): return self.duration

    def GetProperty(self, key=None): return dict(self.props) if key is None else self.props.get(key)

    def SetProperty(self, key, value):
        self.props[key] = value
        return True

    def SmartReframe(self):
        self.smart_reframed = self.edition.studio
        return self.edition.studio

    def _AddKeyframe(self, prop, frame, value):
        self.keys.setdefault(prop, {})[int(frame)] = value
        return True

    def _SetKeyframeInterpolation(self, prop, frame, kind):
        self.interp[(prop, int(frame))] = kind
        return kind in ("Linear", "Bezier", "EaseIn", "EaseOut", "EaseInOut")

    def _GetKeyframeCount(self, prop): return len(self.keys.get(prop, {}))
    def _GetKeyframeAtIndex(self, prop, i): return {"frame": sorted(self.keys[prop])[i]}
    def _DeleteKeyframe(self, prop, frame): return self.keys.get(prop, {}).pop(int(frame), None) is not None

    def SetCDL(self, cdl):
        self.cdl.append(dict(cdl))
        return True

    def SetLUT(self, node, path):
        self.luts[int(node)] = path
        return True

    def GetNodeGraph(self): return NodeGraph(self)

    def GetFusionCompCount(self): return len(self.comps)
    def GetFusionCompByIndex(self, i): return self.comps[i - 1]

    def AddFusionComp(self):
        self.comps.append(FusionComp(render_start=float(self.duration)))  # non-zero on purpose
        return self.comps[-1]


class NodeGraph:
    def __init__(self, item: TimelineItem): self.item = item
    def GetNumNodes(self): return max([1, *self.item.luts])
    def GetNodeLabel(self, node): return f"Node {node}"
    def GetLUT(self, node): return self.item.luts.get(int(node), "")


class Still:
    def __init__(self, n: int): self.n = n


class Album:
    def __init__(self, name: str):
        self.name, self.stills, self.labels = name, [], {}

    def GetStills(self): return list(self.stills)

    def SetLabel(self, still, label):
        self.labels[still.n] = label
        return True

    def ExportStills(self, stills, folder, prefix, fmt):
        from pathlib import Path
        for still in stills:
            Path(folder, f"{prefix}_{still.n}.{fmt}").write_bytes(b"png")
        return True


class Gallery:
    def __init__(self): self.album = Album("Stills 1")
    def GetGalleryStillAlbums(self): return [self.album]
    def GetAlbumName(self, album): return album.name
    def GetCurrentStillAlbum(self): return self.album


class Timeline:
    def __getattr__(self, name):
        project = self.__dict__.get("project")
        if name == "CreateSubtitlesFromAudio" and project and project.resolve.native_ai:
            return lambda *_: self.__dict__.setdefault("subtitled", True)
        raise AttributeError(name)

    def Export(self, path, kind):
        from pathlib import Path
        Path(path).write_text(f"{kind}:{self.name}", encoding="utf-8")
        return True

    def GrabStill(self):
        gallery = self.project.gallery
        still = Still(len(gallery.album.stills) + 1)
        gallery.album.stills.append(still)
        return still

    def __init__(self, project: "Project", name: str, tracks: list[list[TimelineItem]], width=1920, height=1080, fps=30):
        self.project, self.name, self.tracks = project, name, tracks
        self.audio_tracks = []
        self.markers = {}
        self.track_names, self.track_enabled, self.track_locked = {}, {}, {}
        self.settings = {"timelineFrameRate": str(fps), "timelineResolutionWidth": str(width),
                         "timelineResolutionHeight": str(height), "useCustomSettings": "0"}

    def GetName(self): return self.name
    def GetStartFrame(self): return TIMELINE_START
    def GetEndFrame(self): return max([TIMELINE_START] + [item.start + item.duration for track in self.tracks for item in track])
    def GetMarkers(self): return copy.deepcopy(self.markers)
    def AddMarker(self, frame, color, name, note, duration, custom):
        self.markers[frame] = dict(color=color, name=name, note=note, duration=duration, customData=custom)
        return True
    def SetTrackName(self, kind, index, value): self.track_names[(kind,index)] = value; return True
    def GetTrackName(self, kind, index): return self.track_names.get((kind,index), "")
    def SetTrackEnable(self, kind, index, value): self.track_enabled[(kind,index)] = value; return True
    def GetIsTrackEnabled(self, kind, index): return self.track_enabled.get((kind,index), True)
    def SetTrackLock(self, kind, index, value): self.track_locked[(kind,index)] = value; return True
    def GetIsTrackLocked(self, kind, index): return self.track_locked.get((kind,index), False)

    def GetSetting(self, key=None): return self.settings.get(key, "")
    def GetTrackCount(self, kind): return len(self.tracks) if kind == "video" else len(self.audio_tracks)

    def AddTrack(self, kind, *_):
        if kind == "video":
            self.tracks.append([])
        elif kind == "audio":
            self.audio_tracks.append([])
        return True

    def SetSetting(self, key, value):
        if key.startswith("timelineResolution") and self.settings["useCustomSettings"] != "1":
            return False  # Resolve requires custom settings before per-timeline resolution
        self.settings[key] = str(value)
        return True

    def GetItemListInTrack(self, kind, index):
        return list(self.tracks[index - 1]) if kind == "video" and 1 <= index <= len(self.tracks) else []

    def DuplicateTimeline(self, name):
        if any(t.name == name for t in self.project.timelines):
            return None
        dup = copy.copy(self)
        dup.name, dup.settings = name, dict(self.settings)
        dup.markers = copy.deepcopy(self.markers)
        dup.track_names, dup.track_enabled, dup.track_locked = dict(self.track_names), dict(self.track_enabled), dict(self.track_locked)
        dup.tracks = [[_clone(i) for i in track] for track in self.tracks]
        self.project.timelines.append(dup)
        self.project.current = dup  # the documented surprise
        return dup


def _clone(item: TimelineItem) -> TimelineItem:
    new = TimelineItem(item.mpi, item.start, item.duration, edition=item.edition, left=item.left)
    new.props = dict(item.props)
    return new


class Project:
    def __init__(self, resolve: "Resolve", name="Demo"):
        self.resolve, self.name = resolve, name
        self.timelines: list[Timeline] = []
        self.current: Timeline | None = None
        self.render: dict[str, Any] = {}
        self.jobs: dict[str, dict] = {}
        self.pool = MediaPool(self)
        self.gallery = Gallery()
        self.settings = {"timelineFrameRate": "30", "timelineResolutionWidth": "1920", "timelineResolutionHeight": "1080"}

    def GetName(self): return self.name
    def GetGallery(self): return self.gallery
    def GetCurrentTimeline(self): return self.current
    def GetMediaPool(self): return self.pool
    def GetTimelineCount(self): return len(self.timelines)
    def GetTimelineByIndex(self, i): return self.timelines[i - 1]
    def GetSetting(self, key=None): return dict(self.settings) if key is None else self.settings.get(key, "")

    def SetSetting(self, key, value):
        if key == "readOnlySetting":
            return False
        self.settings[key] = str(value)
        return True

    def SetCurrentTimeline(self, timeline):
        self.current = timeline
        return True

    def SetCurrentRenderFormatAndCodec(self, fmt, codec):
        ok = fmt == "mp4" and (codec == "H264" or (codec == "H265" and self.resolve.studio))
        if ok:
            self.render.update(format=fmt, codec=codec)
        return ok

    def SetRenderSettings(self, settings):
        if not settings.get("CustomName"):
            return False
        self.render.update(settings)
        return True

    def AddRenderJob(self):
        job = f"job-{len(self.jobs) + 1}"
        self.jobs[job] = dict(self.render)
        return job

    def StartRendering(self, jobs, interactive=False): return all(j in self.jobs for j in jobs)
    def GetRenderJobStatus(self, job): return {"JobStatus": "Complete", "CompletionPercentage": 100}
    def IsRenderingInProgress(self): return False


class Resolve:
    def __init__(self, *, studio: bool, keyframes: bool = True, version: str = "21.0.4.5"):
        self.studio, self.keyframes, self.version = studio, keyframes, version
        self.import_frames = 900  # frames of any imported movie file
        self.native_ai = False
        self.AUDIO_SYNC_WAVEFORM, self.AUDIO_SYNC_TIMECODE = 0, 1
        self.EXPORT_OTIO, self.EXPORT_EDL = "otio", "edl"  # deliberately not every format
        self.projects: dict[str, Project] = {}
        self.project: Project | None = Project(self)

    def GetVersionString(self): return self.version
    def GetProductName(self): return "DaVinci Resolve Studio" if self.studio else "DaVinci Resolve"
    def GetProjectManager(self): return _PM(self)


class _PM:
    def __init__(self, resolve): self.resolve = resolve
    def GetCurrentProject(self): return self.resolve.project
    def SaveProject(self): return True
    def GetProjectListInCurrentFolder(self): return [self.resolve.project.name, *self.resolve.projects]

    def CreateProject(self, name):
        if name in self.resolve.projects or name == self.resolve.project.name:
            return None
        self.resolve.projects[name] = self.resolve.project = Project(self.resolve, name)
        return self.resolve.project

    def LoadProject(self, name):
        project = self.resolve.projects.get(name)
        if project:
            self.resolve.project = project
        return project

    def ExportProject(self, name, path):
        from pathlib import Path
        Path(path).write_bytes(b"DRP" + name.encode())
        return True


def demo_resolve(*, studio: bool, keyframes: bool = True, clips: int = 2, source=(1920, 1080)) -> Resolve:
    """A project with one 16:9 timeline: `clips` 10 s talking-head clips on V1 and a title on V2."""
    r = Resolve(studio=studio, keyframes=keyframes)
    p = r.project
    v1 = [TimelineItem(MediaPoolItem(f"take{i + 1}.mp4", *source, path=""), TIMELINE_START + i * 300, 300, edition=r)
          for i in range(clips)]
    v2 = [TimelineItem(None, TIMELINE_START, 90, edition=r)]
    p.current = Timeline(p, "Master", [v1, v2])
    p.timelines.append(p.current)
    return r


class BridgeLike:
    """Imitates the Free-edition bridge proxy (JSON transport, strict attributes, no indexing)."""

    def __init__(self, target: Any):
        object.__setattr__(self, "_t", target)

    def __getattr__(self, name):
        attr = getattr(self._t, name)  # AttributeError propagates, like the real proxy
        if not callable(attr):
            if isinstance(attr, (str, int, float, bool)) and name[:1].isupper():
                return attr  # the real bridge serves plain constants through get_attribute
            raise AttributeError(name)

        def call(*args):
            wire = json.loads(json.dumps([_unwrap(a) for a in args], default=_handle))
            return _wrap(attr(*[_rehydrate(a) for a in wire]))
        return call


_HANDLES: dict[str, Any] = {}


def _unwrap(value):
    if isinstance(value, BridgeLike):
        return value._t
    if isinstance(value, dict):
        return {k: _unwrap(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_unwrap(v) for v in value]
    return value


def _handle(obj):
    key = f"h{id(obj)}"
    _HANDLES[key] = obj
    return {"__handle__": key}


def _rehydrate(value):
    if isinstance(value, dict):
        if "__handle__" in value:
            return _HANDLES[value["__handle__"]]
        return {k: _rehydrate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_rehydrate(v) for v in value]
    return value


def _wrap(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return json.loads(json.dumps({str(k): _wrap(v) for k, v in value.items()}, default=_handle))
    if isinstance(value, list):
        return [_wrap(v) for v in value]
    return BridgeLike(value)


class FakeTransport:
    def __init__(self, name: str, handle: Any):
        self.name, self.handle = name, handle

    def connect(self):
        return self.handle
