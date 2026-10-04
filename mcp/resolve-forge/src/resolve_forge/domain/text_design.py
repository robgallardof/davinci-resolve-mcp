"""Text art direction and timed caption cues. Pure data and decisions, no renderer or SDK."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass

from .transcript import Span, Word, caption_chunks


@dataclass(frozen=True)
class TextDesign:
    name: str
    label: str
    description: str
    accent: str
    animation: str
    highlight: bool
    max_words: int
    motion_style: str
    intensity: float
    uppercase: bool = False


DESIGNS = {d.name: d for d in (
    TextDesign("creator", "Creator · cercano y dinámico", "Voz, tutoriales y Reels: palabra activa en lima, entrada pop breve.",
               "#C7F464", "pop", True, 3, "tiktok_smooth", 0.8),
    TextDesign("studio", "Studio · limpio y profesional", "Entrevistas y educación: blanco sobre placa oscura, acento lavanda y lift suave.",
               "#B8A4FF", "lift", True, 4, "youtube_dynamic", 0.7),
    TextDesign("editorial", "Editorial · cálido y discreto", "Historias y contenido pausado: crema, subrayado de énfasis y fade corto.",
               "#FFD19A", "fade", False, 5, "warm_push", 0.7),
    TextDesign("impact", "Impact · enérgico", "Remates y mensajes breves: mayúsculas, acento coral y pop contenido.",
               "#FF916F", "pop", True, 2, "tiktok_punch", 0.8, True),
)}
LEGACY_STYLES = ("box", "outline", "yellow", "dark")
ANIMATIONS = ("none", "fade", "lift", "pop", "karaoke")


def resolve_style(style: str, width: int, height: int) -> str:
    name = ("creator" if height > width else "studio") if style == "auto" else style
    if name not in DESIGNS and name not in LEGACY_STYLES:
        raise ValueError(f"Unknown text style '{style}'. Choose auto, {', '.join((*DESIGNS, *LEGACY_STYLES))}.")
    return name


def resolve_animation(animation: str, style: str, reduced_motion: bool = False) -> str:
    if animation != "auto" and animation not in ANIMATIONS:
        raise ValueError(f"animation must be auto or {', '.join(ANIMATIONS)}")
    if reduced_motion:
        return "none"
    return DESIGNS[style].animation if animation == "auto" and style in DESIGNS else ("none" if animation == "auto" else animation)


def accent_rgba(accent: str | None, style: str) -> tuple[int, int, int, int]:
    color = accent or (DESIGNS[style].accent if style in DESIGNS else "#C7F464")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("accent must be a six-digit color, for example #C7F464")
    return (*[int(color[i:i + 2], 16) for i in (1, 3, 5)], 255)


def catalog() -> dict:
    return {"styles": [asdict(d) for d in DESIGNS.values()], "legacy_styles": list(LEGACY_STYLES),
            "automatic": "creator for vertical, studio for horizontal/square",
            "animations": list(ANIMATIONS),
            "karaoke": "Word-timed growing underline; fixed typography, no inferred activity in silent gaps. Requires word timestamps for captions.",
            "brand_color": "accent=#RRGGBB",
            "workflow": "Choose a coherent style; preview it; review transcript; add captions; reserve motion and overlays for meaningful moments."}


@dataclass(frozen=True)
class CaptionCue:
    text: str
    start: float
    end: float
    words: tuple[Word, ...] = ()

    def as_dict(self) -> dict:
        return Span(self.text, self.start, self.end).as_dict()

    def active_at(self, seconds: float) -> int | None:
        # No colored word while the speaker pauses; short word gaps do not move the layout.
        return next((i for i, word in enumerate(self.words) if word.start <= seconds < word.end), None)

    def progress_at(self, seconds: float) -> float | None:
        """Spoken-word progress; silence has no moving underline or guessed timing."""
        active = self.active_at(seconds)
        if active is None:
            return None
        word = self.words[active]
        return max(0.0, min(1.0, (seconds - word.start) / (word.end - word.start)))


def cues(words: list[Word], max_words: int, *, end_s: float | None = None) -> list[CaptionCue]:
    if isinstance(max_words, bool) or not isinstance(max_words, int) or not 1 <= max_words <= 8:
        raise ValueError("max_words must be an integer from 1 to 8")
    previous = -1.0
    for word in words:
        if not word.text.strip() or not all(math.isfinite(x) for x in (word.start, word.end)) or word.start < 0 or word.end <= word.start:
            raise ValueError("Caption words need non-empty text and finite positive time ranges")
        if word.start < previous:
            raise ValueError("Caption words must be ordered by their start time")
        previous = word.start
    if end_s is not None and (not math.isfinite(end_s) or end_s <= 0):
        raise ValueError("Caption timeline duration must be positive")
    result, offset = [], 0
    for span in caption_chunks(words, max_words=max_words):
        # Match sequential tokens, never floating-point time guesses or text dictionaries.
        block_words = []
        while offset < len(words):
            block_words.append(words[offset])
            offset += 1
            if " ".join(word.text for word in block_words) == span.text:
                break
        block = tuple(block_words)
        stop = min(span.end, end_s) if end_s is not None else span.end
        if stop > span.start:
            result.append(CaptionCue(span.text, span.start, stop, block))
    return result


def provided_words(rows: list[dict]) -> list[Word]:
    """Corrected/manual transcript in timeline seconds, accepted without a Whisper installation."""
    result = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("text"), str) or "start" not in row or "end" not in row:
            raise ValueError("words must contain text, start and end for each spoken word")
        if any(isinstance(row[key], bool) or not isinstance(row[key], (int, float)) for key in ("start", "end")):
            raise ValueError("Word start/end must be numbers in timeline seconds")
        result.append(Word(row["text"].strip(), float(row["start"]), float(row["end"])))
    cues(result, 4)
    return result


def srt(captions: list[CaptionCue]) -> str:
    def timestamp(value):
        milliseconds = round(value * 1000)
        seconds, milliseconds = divmod(milliseconds, 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"
    return "\n\n".join(f"{index}\n{timestamp(caption.start)} --> {timestamp(caption.end)}\n{caption.text}"
                        for index, caption in enumerate(captions, 1)) + ("\n" if captions else "")


def motion_state(animation: str, frame: int, frames: int, fps: float) -> tuple[float, float, float]:
    """Opacity, scale and vertical offset in short-side fractions. Entry only; text holds at full strength."""
    if animation not in ANIMATIONS:
        raise ValueError("Unknown animation")
    if animation in ("none", "karaoke"):
        return 1.0, 1.0, 0.0
    ramp = max(1, min(round(fps * 0.18), frames - 1))
    t = min(1.0, frame / ramp)
    ease = 1 - (1 - t) ** 3
    opacity = 0.55 + 0.45 * ease  # readable from its first frame, even for fast speech
    if animation == "pop":
        return opacity, 0.94 + 0.06 * ease, 0.0
    if animation == "lift":
        return opacity, 1.0, 0.012 * (1 - ease)
    return opacity, 1.0, 0.0
