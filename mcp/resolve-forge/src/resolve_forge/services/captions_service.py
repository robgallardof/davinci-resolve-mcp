"""Use case: burned-in captions on any edition (Studio's auto-subtitles do not exist on Free)."""

from __future__ import annotations

from pathlib import Path

from ..analysis import transcribe
from ..domain.text_design import DESIGNS, accent_rgba, cues, provided_words, resolve_animation, resolve_style, srt
from ..gateway import Session
from . import overlay_service, transcript_service
from .context import current


def add_captions(session: Session, *, style: str = "auto", position: str = "bottom", max_words: int | None = None,
                 language: str | None = None, track: int = 1,
                 animation: str = "auto", accent: str | None = None,
                 emphasis_words: list[str] | None = None, reduced_motion: bool = False,
                 words: list[dict] | None = None,
                 transcriber: transcribe.Transcriber | None = None) -> dict:
    ctx = current(session)
    style = resolve_style(style, ctx.width, ctx.height)
    resolve_animation(animation, style, reduced_motion)
    accent_rgba(accent, style)
    max_words = max_words if max_words is not None else (DESIGNS[style].max_words if style in DESIGNS else 4)
    cues([], max_words)  # validate before transcription/model download
    if words is not None:
        speech = transcript_service.TimelineSpeech(provided_words(words), language or "", "provided")
    else:
        if transcriber is None:
            transcript_service.require_speech_stack()
        speech = transcript_service.timeline_words(ctx, transcriber or transcript_service._DEFAULT,
                                                   track=track, language=language)
    end_s = (int(ctx.timeline.GetEndFrame()) - ctx.start_frame) / ctx.fps
    chunks = cues(speech.words, max_words=max_words, end_s=end_s)
    if not chunks:
        return {"placed": 0, "note": "No speech detected: nothing to caption. Use add_text_overlay for on-screen text."}
    result = overlay_service.place_cards(session, chunks, style=style, position=position, label="cap",
                                         animation=animation, accent=accent, emphasis_words=emphasis_words,
                                         reduced_motion=reduced_motion)
    subtitle = Path(result["files"]) / "captions.srt"
    subtitle.write_text(srt(chunks), encoding="utf-8")
    return {**result, "language": speech.language, "model": speech.model, "srt_file": str(subtitle),
            "preview": [c.as_dict() for c in chunks[:5]]}
