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
