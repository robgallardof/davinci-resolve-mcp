"""MCP tool surface. Thin: delegate to services, shape errors, nothing else."""

from __future__ import annotations

import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from . import doctor
from .analysis import faces
from .domain import formats, styles
from .errors import payload
from .gateway import ResolveUnavailable, Session
from . import resources
from .domain.transcript import Span
from .services import (assembly_service, captions_service, format_service, highlight_service, motion_service,
                       overlay_service, render_service, transcript_service)
from .services.appliers import APPLIERS
from .services.context import ForgeError, current, describe, video_items
from .services.subject import resolve_anchor


# One dedicated thread: Resolve calls are serialised and always come from the same
# thread, and the stdio event loop stays free (a blocked loop on Windows holds
# finished responses until the next message arrives).
_RESOLVE_THREAD = ThreadPoolExecutor(max_workers=1, thread_name_prefix="resolve")


def _safe(fn: Callable[..., dict]) -> Callable[..., Any]:
    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> dict:
        try:
            result = await asyncio.get_running_loop().run_in_executor(
                _RESOLVE_THREAD, functools.partial(fn, *args, **kwargs))
            return {"ok": True, **result}
        except (ForgeError, ResolveUnavailable, KeyError, ValueError) as exc:
            return payload(exc)
    return wrapper


def run_in_resolve_thread(fn: Callable[..., Any], *args: Any) -> Any:
    """Await `fn` on the Resolve thread (resources use it; they have no error envelope of their own)."""
    return asyncio.get_running_loop().run_in_executor(_RESOLVE_THREAD, functools.partial(fn, *args))


def register(mcp: FastMCP, session: Session) -> None:
    @mcp.tool()
    @_safe
    def forge_status() -> dict:
        """Connection, Resolve version, current project/timeline and which motion backends this build supports."""
        ctx = current(session, need_timeline=False)
        info = {"transport": session.transport_name, "edition": doctor.edition(ctx.resolve),
                "version": ctx.resolve.GetVersionString(),
                "project": ctx.project.GetName(), "face_detection": faces.available(),
                "backends": list(APPLIERS)}
        if ctx.timeline is not None:
            items = ctx.timeline.GetItemListInTrack("video", 1) or []
            info |= {"timeline": ctx.timeline.GetName(), "fps": ctx.fps,
                     "resolution": f"{ctx.width}x{ctx.height}",
                     "native_keyframes": bool(items) and callable(getattr(items[0], "AddKeyframe", None))}
        return info

    @mcp.tool()
    @_safe
    def list_clips(track: int = 1) -> dict:
        """Clips on a video track with 1-based index, start frame, duration and current zoom."""
        ctx = current(session)
        return {"fps": ctx.fps, "timeline_start": ctx.start_frame,
                "clips": [describe(item, i) for i, item in enumerate(video_items(ctx, track), 1)]}

    @mcp.tool()
    @_safe
    def list_styles() -> dict:
        """Motion styles available to apply_motion, with what each looks like and when to use it."""
        return {"styles": styles.catalogue()}

    @mcp.tool()
    @_safe
    def list_formats(orientation: str = "all") -> dict:
        """Delivery formats for every platform, filterable by orientation (vertical | horizontal | square | all).

        Vertical: tiktok, reels, facebook_reels, shorts, stories, snapchat, feed_4x5.
        Horizontal: youtube_1080, youtube_4k, facebook_1080, linkedin_1080, x_1080, web_1080. Square: square.
        Each entry has resolution, fps, codec, bitrate, loudness target and UI safe zone in pixels.
        """
        return {"formats": {k: f.as_dict() for k, f in formats.by_orientation(orientation).items()}}

    @mcp.tool()
    @_safe
    def preview_motion(style: str, seconds: float = 10.0, fps: float = 30.0,
                       cuts_s: list[float] | None = None, hits_s: list[float] | None = None,
                       intensity: float = 1.0) -> dict:
        """Dry run: the keyframes a style would produce for a clip of `seconds`, without touching Resolve."""
        frames = int(seconds * fps)

        def to_frames(xs: list[float] | None) -> list[int] | None:
            return None if xs is None else [int(s * fps) for s in xs]

        plan = styles.build(style, duration=frames, fps=fps, cuts=to_frames(cuts_s),
                            hits=to_frames(hits_s), intensity=intensity)
        return {"style": style, "peak_zoom": round(plan.peak_zoom(), 3), "notes": list(plan.notes),
                "tracks": {t.param: [{"frame": k.frame, "s": round(k.frame / fps, 2), "value": round(k.value, 4),
                                      "ease": k.ease_out.value} for k in t.keyframes] for t in plan.tracks}}

    @mcp.tool()
    @_safe
    def apply_motion(style: str, track: int = 1, clips: list[int] | None = None,
                     cuts_s: list[float] | None = None, hits_s: list[float] | None = None,
                     intensity: float = 1.0, anchor: str | list[float] = "face",
                     backend: str = "auto", seed: int = 7) -> dict:
        """Animate clips so people never sit static: punch-ins, slow pushes, emphasis bumps, handheld.

        style: see list_styles (tiktok_punch, tiktok_smooth, warm_push, youtube_dynamic, emphasis, handheld, vlog_mix).
        clips: 1-based indices on `track` (default: every clip on the track).
        cuts_s / hits_s: timeline seconds for zoom changes / emphasis bumps (sentence starts, key words
          from the transcript). Omit cuts_s for an automatic, slightly irregular rhythm.
        intensity: 0.5 subtle, 1.0 default, 1.5 aggressive.
        anchor: 'face' (detect the speaker; needs opencv), 'talking_head', 'center' or [x, y] in 0..1 (top-left).
        backend: auto | keyframes (native Inspector keys, Resolve 20+) | fusion (Transform node).
        Re-running replaces the previous forge motion on those clips.
        """
        return motion_service.animate(session, style, track=track, clips=clips, cuts_s=cuts_s, hits_s=hits_s,
                                      intensity=intensity, anchor=anchor, backend=backend, seed=seed)

    @mcp.tool()
    @_safe
    def clear_motion(track: int = 1, clips: list[int] | None = None) -> dict:
        """Remove forge motion: Inspector zoom/position/rotation keyframes and the ForgeMotion Fusion node."""
        return motion_service.clear(session, track=track, clips=clips)

    @mcp.tool()
    @_safe
    def make_platform_version(format: str, subject: str | list[float] = "face", center_bias: float = 1.0,
                              name: str | None = None, smart_reframe: bool = False) -> dict:
        """Duplicate the current timeline as a platform version in any direction (see list_formats):
        16:9 master -> reels/tiktok/shorts/stories/feed_4x5, or a vertical master -> youtube_1080/facebook_1080.

        Every media clip is zoomed to fill the new frame and moved so the subject stays in shot.
        center_bias 1.0 centers the subject; lower values keep more of the original composition.
        smart_reframe uses Resolve's Smart Reframe (Studio only) when available.
        The source timeline is never modified; the copy becomes the current timeline.
        """
        return format_service.make_version(session, format, subject=subject, center_bias=center_bias,
                                           name=name, smart_reframe=smart_reframe)

    @mcp.tool()
    @_safe
    def locate_subject(track: int = 1, clip: int = 1) -> dict:
        """Where the speaker's face sits in a clip (normalized x, y; top-left origin). Needs the 'vision' extra."""
        item = video_items(current(session), track, [clip])[0]
        point, how = resolve_anchor("face", item)
        return {"clip": clip, "point": point, "source": how}

    @mcp.tool()
    @_safe
    def render_for(format: str, target_dir: str | None = None, name: str | None = None, start: bool = True) -> dict:
        """Queue a render of the current timeline with the platform's container, codec and resolution.

        target_dir defaults to ~/Movies/resolve-forge — on the Free edition the bridge only writes
        inside its allowed output roots (~/Movies by default), so keep renders under it.
        """
        return render_service.queue(session, format, target_dir, name=name, start=start)

    @mcp.tool()
    @_safe
    def render_status(job_id: str) -> dict:
        """Status and progress of a render job returned by render_for."""
        return render_service.status(session, job_id)

    @mcp.tool()
    @_safe
    def transcribe_timeline(language: str | None = None, include_words: bool = False, track: int = 1) -> dict:
        """What is said on the timeline, in TIMELINE seconds (respects every cut). Local Whisper: works on Free.

        Returns sentences, `cuts_s` (sentence starts) and `hits_s` (numbers, exclamations, stressed endings)
        ready for apply_motion. GPU when available, CPU otherwise; cached per source file.
        language: 'es', 'en', ... or omit to auto-detect.
        """
        return transcript_service.analyse(session, track=track, language=language, include_words=include_words)

    @mcp.tool()
    @_safe
    def add_captions(style: str = "outline", position: str = "bottom", max_words: int = 4,
                     language: str | None = None) -> dict:
        """Burned-in captions from the timeline's speech, on a new top track. Works on Free (no Studio AI needed).

        style: outline (white, black stroke) | yellow | box (TikTok-native) | dark.
        position: bottom | middle | top, always inside the safe zone of the timeline's resolution.
        max_words: words per caption block (2-5 is the short-form sweet spot).
        """
        return captions_service.add_captions(session, style=style, position=position, max_words=max_words,
                                             language=language)

    @mcp.tool()
    @_safe
    def add_text_overlay(text: str, start_s: float, duration_s: float, style: str = "box",
                         position: str = "top") -> dict:
        """On-screen text (hook, POV, labels; emoji supported) for an exact time range, inside the safe zone.

        start_s is in timeline seconds. style: box | outline | yellow | dark. position: top | middle | bottom.
        Each call adds a new top video track so it never collides with existing clips.
        """
        if duration_s <= 0:
            raise ValueError("duration_s must be > 0")
        return overlay_service.place_cards(session, [Span(text, start_s, start_s + duration_s)],
                                           style=style, position=position)

    @mcp.tool()
    @_safe
    def find_highlights(source: str, top: int = 6, window_s: float = 4.0) -> dict:
        """Rank the best moments of a long clip by visual motion + audio activity (needs the vision extra).

        source: media-pool clip name or absolute file path (imported if needed).
        Returns non-overlapping windows in SOURCE seconds, sorted by time, for assemble_timeline.
        """
        return highlight_service.find(session, source, top=top, window_s=window_s)

    @mcp.tool()
    @_safe
    def assemble_timeline(source: str, cuts: list[list[float]], name: str, format: str | None = None) -> dict:
        """Build a new timeline from source ranges: cuts=[[start_s, end_s], ...] in SOURCE seconds, in order.

        format (optional): set the timeline to a platform resolution (see list_formats), e.g. 'reels'.
        The new timeline becomes current; nothing existing is modified.
        """
        return assembly_service.assemble(session, source, cuts, name=name, format=format)

    resources.register(mcp, session, run_in_resolve_thread)
