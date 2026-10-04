"""Forge's explicit native-call boundary and path policy; standard library only."""
import math
import re
from pathlib import Path

METHODS = frozenset("""
GetVersion GetVersionString GetProductName GetProjectManager GetCurrentPage OpenPage
GetCurrentProject GetProjectListInCurrentFolder CreateProject LoadProject CloseProject SaveProject ExportProject
GetName SetName GetCurrentTimeline SetCurrentTimeline GetTimelineCount GetTimelineByIndex
GetMediaPool GetMediaStorage GetRootFolder GetCurrentFolder SetCurrentFolder GetClipList GetSubFolderList
AddSubFolder ImportMedia MoveClips SetMetadata GetMetadata GetClipProperty SetClipProperty
GetSetting SetSetting GetStartFrame GetEndFrame GetStart GetEnd GetDuration GetLeftOffset GetRightOffset GetUniqueId
GetSourceStartFrame GetSourceEndFrame
GetTrackCount GetItemListInTrack GetMediaPoolItem DuplicateTimeline CreateEmptyTimeline CreateTimelineFromClips AppendToTimeline
AddTrack GetTrackName SetTrackName GetIsTrackEnabled SetTrackEnable GetIsTrackLocked SetTrackLock
GetMarkers AddMarker DeleteMarkerAtFrame GetClipColor SetClipColor GetFlagList AddFlag ClearFlags
GetProperty SetProperty GetClipEnabled SetClipEnabled GetCurrentTimecode SetCurrentTimecode
GetCurrentVideoItem GetNodeGraph SetCDL SetLUT GetLUT GetNumNodes GetNodeLabel SetNodeEnabled
ApplyGradeFromDRX CopyGrades ExportLUT GetColorVersionList AddVersion LoadVersion RenameVersion
GetFusionCompCount GetFusionCompByIndex AddFusionComp GetToolList FindTool AddTool DeleteTool
Lock Unlock StartUndo EndUndo GetAttrs SetAttrs GetInput SetInput ConnectInput AddModifier Delete
AddKeyframe GetKeyframeCount GetKeyframeAtIndex DeleteKeyframe SetKeyframeInterpolation
SetCurrentRenderFormatAndCodec SetRenderSettings AddRenderJob StartRendering GetRenderJobStatus
GetRenderFormats GetRenderCodecs GetRenderJobList IsRenderingInProgress StopRendering
GetRenderPresetList LoadRenderPreset SaveAsNewRenderPreset Export ExportCurrentFrameAsStill
GetGallery GetGalleryStillAlbums GetCurrentStillAlbum SetCurrentStillAlbum CreateGalleryStillAlbum
GetAlbumName GetStills GetLabel SetLabel ImportStills ExportStills GrabStill GrabAllStills
GetFusion SmartReframe TranscribeAudio CreateSubtitlesFromAudio DetectSceneCuts AutoSyncAudio
SetClipsLinked CreateCompoundClip CreateFusionClip SetStartTimecode
""".split())


class OperationError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class PathPolicy:
    def __init__(self, media_roots, output_roots):
        self.media = tuple(Path(root).expanduser().resolve() for root in media_roots)
        self.output = tuple(Path(root).expanduser().resolve() for root in output_roots)

    def check(self, path, write=False):
        candidate = Path(path).expanduser().resolve()
        if not any(candidate.is_relative_to(root) for root in (self.output if write else self.media)):
            raise OperationError("PATH_REFUSED", "Path is outside configured bridge roots.")
        return str(candidate)

    def validate(self, method, args):
        if method == "ImportMedia":
            for entry in args[0]:
                self.check(entry["FilePath"] if isinstance(entry, dict) else entry)
        if method in {"SetLUT", "ApplyGradeFromDRX", "ImportStills"}:
            paths = args[1] if method == "SetLUT" else args[0]
            for path in paths if isinstance(paths, list) else [paths]:
                self.check(path)
        if method in {"ExportProject", "ExportLUT"}:
            self.check(args[1], write=True)
        if method == "ExportStills":
            self.check(args[1], write=True)
        if method in {"Export", "ExportCurrentFrameAsStill"}:
            self.check(args[0], write=True)
        if method == "SetRenderSettings" and "TargetDir" in args[0]:
            self.check(args[0]["TargetDir"], write=True)
        if method == "SetInput" and args[0] in {"Clip", "Filename", "FileName"}:
            self.check(args[1])
        if method == "SetClipProperty" and args[0] == "File Path":
            self.check(args[1])


class ResolveOperations:
    OPERATIONS = ("health", "call", "list_methods", "get_attribute", "release_handles", "reload", "shutdown")

    def __init__(self, resolve, media_roots, output_roots, lifecycle=None):
        self.objects = {"resolve": resolve}
        self.identities = {id(resolve): "resolve"}
        self.policy = PathPolicy(media_roots, output_roots)
        self.lifecycle = lifecycle
        self.sequence = 0

    def object(self, handle):
        try:
            return self.objects[handle]
        except KeyError:
            raise OperationError("STALE_HANDLE", "Re-fetch the project/timeline after reconnecting.")

    def encode(self, value, depth=0):
        if depth > 32:
            raise OperationError("REPLY_TOO_DEEP", "Result exceeds nesting capacity.")
        if value is None or isinstance(value, (str, bool, int, float)):
            if isinstance(value, float) and not math.isfinite(value):
                raise OperationError("NONFINITE_RESULT", "Native API returned a non-finite number.")
            return value
        if isinstance(value, dict):
            return {str(key): self.encode(item, depth + 1) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.encode(item, depth + 1) for item in value]
        key = self.identities.get(id(value))
        if key is None:
            if len(self.objects) >= 10000:
                raise OperationError("HANDLE_CAPACITY", "Reconnect to release stale object handles.")
            self.sequence += 1
            key = "forge-" + str(self.sequence)
            self.objects[key], self.identities[id(value)] = value, key
        return {"__handle__": key}

    def decode(self, value):
        if isinstance(value, dict):
            if set(value) == {"__handle__"}:
                return self.object(value["__handle__"])
            # Fusion tables use numeric input keys; restore the JSON wire representation.
            return {int(key) if str(key).isdigit() else key: self.decode(item) for key, item in value.items()}
        return [self.decode(item) for item in value] if isinstance(value, list) else value

    def dispatch(self, operation, args):
        if not isinstance(args, dict) or operation not in self.OPERATIONS:
            raise OperationError("INVALID_OPERATION", "Unsupported bridge operation.")
        if operation == "health":
            return {"implementation": "resolve-forge", "protocol": "1.0", "operations": self.OPERATIONS}
        if operation in {"reload", "shutdown"}:
            if self.lifecycle is None:
                raise OperationError("LIFECYCLE_UNAVAILABLE", "Restart the Scripts entry.")
            return self.lifecycle("reload" if operation == "reload" else "exit")
        if operation == "release_handles":
            for handle in args.get("handles", list(self.objects)):
                if handle != "resolve" and handle in self.objects:
                    self.identities.pop(id(self.objects.pop(handle)), None)
            return {"remaining": len(self.objects)}
        target = self.object(args.get("target", "resolve"))
        # Native proxies may report an empty dir() (seen on Resolve 21 Free); then probe the allowlist directly.
        listed = METHODS.intersection(dir(target)) or METHODS
        methods = {name for name in listed if callable(getattr(target, name, None))}
        if methods & {"AddTool", "ConnectInput", "FindTool"}:
            methods |= {name for name in ("GetAttrs", "SetAttrs") if callable(getattr(target, name, None))}
        if operation == "list_methods":
            return {"methods": sorted(methods)}
        if operation == "get_attribute":
            name = args.get("name", "")
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
                return {"kind": "missing"}
            value = getattr(target, name, None)
            return {"kind": "value", "value": self.encode(value)} if value is not None and not callable(value) else {"kind": "missing"}
        name = args.get("method")
        if name not in methods:
            raise OperationError("BACKEND_UNSUPPORTED", "Method is absent or outside Forge's native-call boundary.")
        arguments = self.decode(args.get("args", []))
        self.policy.validate(name, arguments)
        return {"value": self.encode(getattr(target, name)(*arguments))}


def resolve_alive(resolve):
    """True while the Resolve session that launched the script still answers."""
    try:
        version = getattr(resolve, "GetVersionString", None)
        return callable(version) and bool(version())
    except Exception:
        return False


def make_dispatch(operations):
    return operations.dispatch
