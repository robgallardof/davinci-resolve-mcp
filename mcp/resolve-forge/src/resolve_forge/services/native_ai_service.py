"""Edition-aware AI workflows with explicit refusal and timeline isolation."""
from ..errors import ForgeError
from .context import current, video_items
from .media_lookup import walk_media
from .native import accepted, fork


def apply(session, action, source=None, copy_name=None, dry_run=True):
    methods = {"subtitles": "CreateSubtitlesFromAudio", "scene_cuts": "DetectSceneCuts", "transcribe_media": "TranscribeAudio"}
    if action not in methods:
        raise ValueError("Native AI action must be subtitles, scene_cuts or transcribe_media.")
    ctx = current(session, need_timeline=action != "transcribe_media")
    if action == "transcribe_media":
        candidates = [clip for clip in walk_media(ctx.media_pool.GetRootFolder()) if clip.GetName() == source or clip.GetClipProperty("File Path") == source]
        if len(candidates) != 1:
            raise ValueError("Specify one existing, unambiguous media source.")
        targets = candidates
    else:
        targets = [ctx.timeline] if action == "subtitles" else [item for item in video_items(ctx) if item.GetMediaPoolItem()]
    if not targets or any(not callable(getattr(target, methods[action], None)) for target in targets):
        raise ForgeError("Native AI workflow is absent on this build.", code="BACKEND_UNSUPPORTED",
                         hint="Use Forge's local transcribe_timeline/add_captions/analyse_scenes alternatives.")
    if dry_run:
        return {"action": action, "targets": len(targets), "applied": False}
    version = None
    if action != "transcribe_media":
        version = fork(session, "ai", copy_name)
        targets = [version.context.timeline] if action == "subtitles" else [item for item in video_items(version.context) if item.GetMediaPoolItem()]
    for target in targets:
        accepted(target, methods[action])
    return {"action": action, "targets": len(targets), "timeline": version.target if version else None, "applied": True}
