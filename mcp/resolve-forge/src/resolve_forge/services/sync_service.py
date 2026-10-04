"""Sync selected existing media, validating native constants and source uniqueness."""
from ..errors import ForgeError
from .context import current
from .media_lookup import walk_media
from .native import accepted


def sync(session, sources, mode="waveform", dry_run=True):
    if mode not in {"waveform", "timecode"} or len(set(sources)) < 2:
        raise ValueError("Sync needs at least two distinct existing sources and waveform or timecode mode.")
    ctx = current(session, need_timeline=False)
    candidates, clips = list(walk_media(ctx.media_pool.GetRootFolder())), []
    for source in sources:
        matches = [clip for clip in candidates if clip.GetName() == source or clip.GetClipProperty("File Path") == source]
        if len(matches) != 1:
            raise ValueError("Each sync source must identify exactly one existing media clip.")
        if matches[0] not in clips:
            clips.append(matches[0])
    if len(clips) < 2:
        raise ValueError("Sync sources resolved to fewer than two distinct clips.")
    constant = getattr(ctx.resolve, "AUDIO_SYNC_WAVEFORM" if mode == "waveform" else "AUDIO_SYNC_TIMECODE", None)
    if constant is None or not callable(getattr(ctx.media_pool, "AutoSyncAudio", None)):
        raise ForgeError("Native audio sync is unavailable on this build.", code="BACKEND_UNSUPPORTED")
    if not dry_run:
        accepted(ctx.media_pool, "AutoSyncAudio", clips, {"audioSyncMode": constant})
    return {"sources": [clip.GetName() for clip in clips], "mode": mode, "applied": not dry_run}
