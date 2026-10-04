"""Use case: burned-in captions on any edition (Studio's auto-subtitles do not exist on Free)."""

from __future__ import annotations

from ..analysis import transcribe
from ..domain.transcript import caption_chunks
from ..gateway import Session
from . import overlay_service, transcript_service
from .context import current


def add_captions(session: Session, *, style: str = "outline", position: str = "bottom", max_words: int = 4,
                 language: str | None = None, track: int = 1,
                 transcriber: transcribe.Transcriber | None = None) -> dict:
    if transcriber is None:
        transcript_service.require_speech_stack()
    ctx = current(session)
    speech = transcript_service.timeline_words(ctx, transcriber or transcript_service._DEFAULT,
                                               track=track, language=language)
    chunks = caption_chunks(speech.words, max_words=max_words)
    if not chunks:
        return {"placed": 0, "note": "No speech detected: nothing to caption. Use add_text_overlay for on-screen text."}
    result = overlay_service.place_cards(session, chunks, style=style, position=position, label="cap")
    return {**result, "language": speech.language, "model": speech.model,
            "preview": [c.as_dict() for c in chunks[:5]]}
