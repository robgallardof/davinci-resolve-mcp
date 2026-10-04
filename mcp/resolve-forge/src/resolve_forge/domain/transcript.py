"""Transcript model and the editorial decisions derived from it. Pure: no Whisper, no Resolve.

Improves on hiteshK03's transcribe_timeline, which returns SOURCE-file times of the first clip
only: here every clip's words are mapped into TIMELINE seconds, respecting the edit, so the
results feed apply_motion (cuts_s / hits_s) and add_captions directly.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Word:
    text: str
    start: float  # seconds
    end: float
    prob: float = 1.0


@dataclass(frozen=True)
class Span:
    text: str
    start: float
    end: float

    def as_dict(self) -> dict:
        return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def map_clip(words: list[Word], src_in: float, src_out: float, timeline_at: float) -> list[Word]:
    """Words spoken inside [src_in, src_out) of a source, re-timed to where the clip sits on the timeline."""
    shift = timeline_at - src_in
    out = []
    for w in words:
        mid = (w.start + w.end) / 2
        if src_in <= mid < src_out:
            out.append(Word(w.text, max(w.start, src_in) + shift, min(w.end, src_out) + shift, w.prob))
    return out


_SENTENCE_END = re.compile(r"[.!?¡¿…]$")


def sentences(words: list[Word], pause: float = 0.6) -> list[Span]:
    """Group words into sentences on punctuation or on a pause longer than `pause` seconds."""
    spans, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        if nxt is None or _SENTENCE_END.search(w.text) or nxt.start - w.end > pause:
            spans.append(Span(" ".join(x.text for x in cur), cur[0].start, cur[-1].end))
            cur = []
    return spans


def caption_chunks(words: list[Word], max_words: int = 4, max_chars: int = 22, max_gap: float = 0.5,
                   min_dur: float = 0.6) -> list[Span]:
    """Short-form caption blocks: 2–5 words, never across a pause, never across a sentence end.

    Each chunk lasts until the next one starts (no flicker), but at least `min_dur`.
    """
    chunks, cur = [], []

    def flush():
        if cur:
            chunks.append([cur[0].start, cur[-1].end, " ".join(x.text for x in cur)])
            cur.clear()

    for i, w in enumerate(words):
        text = " ".join([x.text for x in cur] + [w.text])
        if cur and (len(cur) >= max_words or len(text) > max_chars or w.start - cur[-1].end > max_gap):
            flush()
        cur.append(w)
        if _SENTENCE_END.search(w.text):
            flush()
    flush()
    out = []
    for i, (start, end, text) in enumerate(chunks):
        nxt = chunks[i + 1][0] if i + 1 < len(chunks) else None
        stop = max(end, start + min_dur)
        if nxt is not None:
            if nxt - end < max_gap:
                stop = nxt  # bridge short gaps: captions shouldn't blink between words
            stop = min(stop, nxt)
        out.append(Span(text, start, stop))
    return out


_FILLERS = {"eh", "em", "este", "o sea", "bueno", "like", "um", "uh", "so", "pues", "entonces", "y", "que"}


def emphasis_hits(words: list[Word], limit: int | None = None) -> list[float]:
    """Moments worth a zoom bump: numbers, exclamations, and the stressed last word of a sentence."""
    hits = []
    for i, w in enumerate(words):
        token = w.text.strip(".,!?¡¿…\"'").lower()
        if not token or token in _FILLERS:
            continue
        is_number = any(ch.isdigit() for ch in token)
        exclaimed = w.text.endswith("!")
        sentence_end = bool(_SENTENCE_END.search(w.text)) and len(token) >= 5
        if is_number or exclaimed or sentence_end:
            if not hits or w.start - hits[-1] >= 2.0:  # never two bumps closer than 2 s
                hits.append(round(w.start, 2))
    return hits[:limit] if limit else hits


def cut_points(spans: list[Span], min_gap: float = 2.0) -> list[float]:
    """Sentence starts usable as `cuts_s` (skips the very first and too-close ones)."""
    cuts = []
    for s in spans[1:]:
        if not cuts or s.start - cuts[-1] >= min_gap:
            cuts.append(round(s.start, 2))
    return cuts
