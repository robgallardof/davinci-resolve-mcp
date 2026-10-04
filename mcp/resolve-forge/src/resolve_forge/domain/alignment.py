"""Pure alignment of a known text (lyrics, script) to recognised word timings.

The supplied text is the truth; recognition only provides timing. Matched words take the recognised
times, unmatched runs are spread evenly between their matched neighbours. No audio, no Whisper here.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from .transcript import Word

_TOKEN = re.compile(r"\S+")


def _key(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in plain if c.isalnum())


def align(text: str, recognised: list[Word], *, minimum_word_s: float = .08) -> tuple[list[Word], float]:
    """(words of `text` with times, fraction of words matched to recognition)."""
    tokens = _TOKEN.findall(text)
    if not tokens:
        raise ValueError("text has no words to align")
    if not recognised:
        raise ValueError("No recognised speech/singing to take timing from")
    keys, heard = [_key(t) for t in tokens], [_key(w.text) for w in recognised]
    times: list[tuple[float, float] | None] = [None] * len(tokens)
    matcher = SequenceMatcher(a=keys, b=heard, autojunk=False)
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            if keys[block.a + offset]:
                w = recognised[block.b + offset]
                times[block.a + offset] = (w.start, w.end)
    matched = sum(t is not None for t in times)
    start_all, end_all = recognised[0].start, recognised[-1].end
    index = 0
    while index < len(tokens):
        if times[index] is not None:
            index += 1
            continue
        run_end = index
        while run_end < len(tokens) and times[run_end] is None:
            run_end += 1
        left = times[index - 1][1] if index > 0 else start_all
        right = times[run_end][0] if run_end < len(tokens) else end_all
        count = run_end - index
        if right - left < minimum_word_s * count:  # no room: borrow time after the left neighbour
            right = left + minimum_word_s * count
        step = (right - left) / count
        for k in range(count):
            times[index + k] = (left + k * step, left + (k + 1) * step)
        index = run_end
    words = []
    for token, (a, b) in zip(tokens, times):
        if words and a < words[-1].end:
            a = words[-1].end
        words.append(Word(token, round(a, 3), round(max(b, a + minimum_word_s), 3)))
    return words, round(matched / len(tokens), 3)
