"""Use case: what is said on the timeline, in timeline seconds (not source seconds)."""

from __future__ import annotations

from dataclasses import dataclass

from .. import errors as E
from ..analysis import transcribe
from ..domain.transcript import Word, cut_points, emphasis_hits, map_clip, sentences
from ..gateway import Session, call
from .context import Context, ForgeError, current, source_path, video_items

_DEFAULT = transcribe.WhisperTranscriber()


@dataclass
class TimelineSpeech:
    words: list[Word]
    language: str
    model: str


def require_speech_stack() -> None:
    if not transcribe.available():
        raise ForgeError("Local transcription is not installed.", code=E.MISSING_DEPENDENCY,
                         hint="cd mcp/resolve-forge && uv sync --extra speech")


def timeline_words(ctx: Context, transcriber: transcribe.Transcriber, *, track: int = 1,
                   language: str | None = None) -> TimelineSpeech:
    """Transcribe each source once and re-time the words of every clip to the edit."""
    words: list[Word] = []
    lang = language or ""
    for item in video_items(ctx, track):
        path = source_path(item)
        if not path:
            continue  # titles, generators, overlays
        mpi = item.GetMediaPoolItem()
        src_fps = float(call(mpi, "GetClipProperty", "FPS", default=0) or ctx.fps)
        # GetLeftOffset is the exact source in-point (GetSourceStartFrame can be off by one).
        left = call(item, "GetLeftOffset", default=None)
        src_in_frames = float(left if left is not None else call(item, "GetSourceStartFrame", default=0) or 0)
        src_in = src_in_frames / src_fps
        src_out = src_in + item.GetDuration() / ctx.fps
        at = (item.GetStart() - ctx.start_frame) / ctx.fps
        source_words, detected = transcriber.transcribe(path, language)
        lang = lang or detected
        words += map_clip(source_words, src_in, src_out, at)
    return TimelineSpeech(sorted(words, key=lambda w: w.start), lang, getattr(transcriber, "name", "?"))


def analyse(session: Session, *, track: int = 1, language: str | None = None, include_words: bool = False,
            transcriber: transcribe.Transcriber | None = None) -> dict:
    if transcriber is None:
        require_speech_stack()
    ctx = current(session)
    speech = timeline_words(ctx, transcriber or _DEFAULT, track=track, language=language)
    spans = sentences(speech.words)
    out = {"language": speech.language, "model": speech.model, "word_count": len(speech.words),
           "sentences": [s.as_dict() for s in spans], "cuts_s": cut_points(spans), "hits_s": emphasis_hits(speech.words),
           "next": "apply_motion(style, cuts_s=..., hits_s=...) and/or add_captions()"}
    if include_words:
        out["words"] = [{"text": w.text, "start": round(w.start, 2), "end": round(w.end, 2)} for w in speech.words]
    if not speech.words:
        out["note"] = "No speech detected (music, ambience or silent clip). Use on-screen text instead of captions."
    return out


def vocal_focus(source_file: str) -> str:
    """Centre channel band-passed to the voice range: helps recognition over a full mix (not true separation)."""
    import hashlib
    import tempfile
    from pathlib import Path

    from .audio_service import ffmpeg_executable, run
    stat = Path(source_file).stat()
    key = hashlib.sha1(f"{Path(source_file).resolve()}|{stat.st_size}|{stat.st_mtime}".encode()).hexdigest()[:16]
    output = Path(tempfile.gettempdir()) / "resolve-forge-vocal-focus" / f"{key}.wav"
    if not output.exists():
        output.parent.mkdir(parents=True, exist_ok=True)
        run([ffmpeg_executable(), "-hide_banner", "-nostdin", "-y", "-i", source_file, "-vn",
             "-af", "pan=mono|c0=0.5*c0+0.5*c1,highpass=f=150,lowpass=f=5000,dynaudnorm", "-ar", "16000", str(output)])
    return str(output)


def align_text(session: Session, source: str, text: str, *, language: str | None = None, timeline_offset_s: float = 0.0,
               focus_vocals: bool = False, transcriber: transcribe.Transcriber | None = None) -> dict:
    """Known lyrics/script timed against one source; the supplied text wins over recognition."""
    from ..domain.alignment import align
    from .analysis_service import source_path as resolve_source
    from .native import number
    number(timeline_offset_s, "timeline offset", -86400, 86400)
    if transcriber is None:
        require_speech_stack()
    path = resolve_source(session, source)
    recognised, detected = (transcriber or _DEFAULT).transcribe(vocal_focus(path) if focus_vocals else path, language)
    words, coverage = align(text, recognised)
    shifted = [w for w in words if w.end + timeline_offset_s > 0]
    out = {"source": source, "language": language or detected, "coverage": coverage, "focus_vocals": focus_vocals, "word_count": len(shifted),
           "words": [{"text": w.text, "start": round(max(0.0, w.start + timeline_offset_s), 3),
                      "end": round(w.end + timeline_offset_s, 3)} for w in shifted],
           "time_basis": "timeline seconds = source seconds + timeline_offset_s",
           "next": "add_captions(words=words, style=...) burns exactly this text"}
    if coverage < .6:
        out["warning"] = ("Under 60% of the text matched what was heard: check the language, the source range or "
                          "use isolated vocals or focus_vocals=true; unmatched words are evenly spaced between matches.")
    return out
