"""Use case: reviewable story-moment candidates (punchlines, reactions, questions, stress) for one source."""

from __future__ import annotations

from ..analysis import transcribe
from ..domain.story_moments import candidates
from . import transcript_service
from .analysis_service import source_path


def find(session, source: str, content_type: str, language: str | None = None, limit: int = 40,
         transcriber: transcribe.Transcriber | None = None) -> dict:
    if transcriber is None:
        transcript_service.require_speech_stack()
    from ..analysis.audio_events import levels
    path = source_path(session, source)
    words, detected = (transcriber or transcript_service._DEFAULT).transcribe(path, language)
    energy, duration, step = levels(path)
    moments = candidates(words, energy, step, content_type, limit=limit)
    return {"source": source, "content_type": content_type, "language": language or detected, "duration_s": round(duration, 3),
            "candidates": moments, "time_basis": "source seconds",
            "method": "transcript pauses/questions + non-speech energy after lines + loudness above the speaker's median",
            "limitations": "Candidates, not recognised humor or emotion. Watch each one; keep only real beats and pass them "
                           "to plan_edit(moments=[{time_s, kind, reason}]) with your own reason.",
            "next": "plan_edit -> assemble_timeline(cuts protecting setup..reaction) -> apply_motion(hits_s=confirmed punchlines)"}
