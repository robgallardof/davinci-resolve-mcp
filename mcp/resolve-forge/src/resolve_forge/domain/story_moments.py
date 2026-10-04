"""Pure story-moment candidates from timed words and an audio level envelope.

Signals are evidence for review, not semantic understanding: a pause before a short line is where comic
timing often lives, a non-speech burst right after a line is where laughter or a reaction often lives.
The agent watches each candidate and only then hands confirmed moments to plan_edit.
"""

from __future__ import annotations

import math
import re
from statistics import median

from .transcript import Word, sentences

_END = re.compile(r"[.!?…]$")
_QUESTION = re.compile(r"\?$")

# Which signal maps to which story beat for each genre (kinds must exist in editorial.RECIPES).
KIND_BY_SIGNAL = {
    "comedy": {"pause_line": "punchline", "reaction": "reaction", "question": "setup", "stress": "punchline"},
    "interview": {"pause_line": "answer", "reaction": "reaction", "question": "question", "stress": "answer"},
    "education": {"pause_line": "idea", "reaction": "payoff", "question": "hook", "stress": "idea"},
    "vlog": {"pause_line": "turn", "reaction": "payoff", "question": "hook", "stress": "turn"},
    "gaming": {"pause_line": "payoff", "reaction": "reaction", "question": "setup", "stress": "action"},
    "product": {"pause_line": "proof", "reaction": "proof", "question": "problem", "stress": "hook"},
    "cinematic": {"pause_line": "turn", "reaction": "climax", "question": "development", "stress": "turn"},
}


def _speaking(words: list[Word], at: float, margin: float = .08) -> bool:
    return any(w.start - margin <= at <= w.end + margin for w in words)


def _level_at(levels: list[float], step_s: float, start: float, end: float) -> float:
    a, b = max(0, int(start / step_s)), max(int(start / step_s) + 1, int(math.ceil(end / step_s)))
    window = levels[a:b]
    return max(window) if window else -120.0


def candidates(words: list[Word], levels: list[float], step_s: float, content_type: str, *,
               pause_s: float = .6, max_line_words: int = 7, reaction_s: float = .4, limit: int = 40) -> list[dict]:
    """Ranked candidates [{time_s, end_s, kind, signal, score, evidence, text}] in the words' time basis."""
    if content_type not in KIND_BY_SIGNAL:
        raise ValueError(f"content_type must be one of {', '.join(KIND_BY_SIGNAL)} (music: use analyse_music)")
    if step_s <= 0 or pause_s <= 0 or reaction_s <= 0 or limit < 1:
        raise ValueError("Invalid story-moment parameters")
    kinds = KIND_BY_SIGNAL[content_type]
    spans = sentences(words)
    speech_levels = [_level_at(levels, step_s, w.start, w.end) for w in words] if levels else []
    speech_floor = median(speech_levels) if speech_levels else -30.0
    found: list[dict] = []

    for previous, span in zip(spans, spans[1:]):
        gap = span.start - previous.end
        count = len(span.text.split())
        if gap >= pause_s and count <= max_line_words and not _QUESTION.search(span.text):
            score = min(1.0, .35 + gap / 3 + (max_line_words - count) / (2 * max_line_words))
            found.append(dict(time_s=span.start, end_s=span.end, signal="pause_line", score=score, text=span.text,
                              evidence=f"{gap:.2f}s pause, then a {count}-word line"))
    for span in spans:
        if _QUESTION.search(span.text):
            found.append(dict(time_s=span.start, end_s=span.end, signal="question", score=.45, text=span.text,
                              evidence="line ends with a question mark"))

    if levels:
        # Reactions: sustained non-speech energy near speech level right after a line ends (laughs, applause, gasps).
        threshold = speech_floor - 6
        run_start = None
        for index, level in enumerate([*levels, -math.inf]):
            at = index * step_s
            active = level >= threshold and not _speaking(words, at)
            if active and run_start is None:
                run_start = at
            elif not active and run_start is not None:
                length = at - run_start
                after = [s for s in spans if s.end <= run_start + .05]
                if length >= reaction_s and after and run_start - after[-1].end <= 1.5:
                    found.append(dict(time_s=round(run_start, 3), end_s=round(at, 3), signal="reaction",
                                      score=min(1.0, .4 + length / 3), text=after[-1].text,
                                      evidence=f"{length:.2f}s of non-speech audio right after a line"))
                run_start = None
        # Stress: a word clearly louder than the speaker's usual level.
        for word, level in zip(words, speech_levels):
            if level - speech_floor >= 6:
                found.append(dict(time_s=word.start, end_s=word.end, signal="stress",
                                  score=min(1.0, .3 + (level - speech_floor) / 20), text=word.text,
                                  evidence=f"{level - speech_floor:.1f} dB above the speaker's median"))

    for moment in found:
        moment["kind"] = kinds[moment["signal"]]
        moment["time_s"], moment["end_s"], moment["score"] = round(moment["time_s"], 3), round(moment["end_s"], 3), round(moment["score"], 2)
    found.sort(key=lambda m: -m["score"])
    kept: list[dict] = []
    for moment in found:  # one candidate per signal per second; a punchline and its laugh are both kept
        if all(abs(moment["time_s"] - other["time_s"]) >= 1 or moment["signal"] != other["signal"] for other in kept):
            kept.append(moment)
        if len(kept) == limit:
            break
    return sorted(kept, key=lambda m: m["time_s"])
