"""Decode audio straight from a media file (no ffmpeg binary needed). Optional `speech` extra."""

from __future__ import annotations

import importlib.util
from typing import Any


def available() -> bool:
    return all(importlib.util.find_spec(m) is not None for m in ("av", "numpy"))


def load_audio(path: str, sample_rate: int = 16000) -> Any:
    """Mono float32 samples in [-1, 1].

    Decodes with PyAV ourselves: faster-whisper's own loader breaks on recent PyAV
    (`open() got an unexpected keyword argument 'metadata_errors'`).
    """
    import av
    import numpy as np

    chunks = []
    with av.open(path) as container:
        if not container.streams.audio:
            return np.zeros(0, dtype=np.float32)
        resampler = av.AudioResampler(format="s16", layout="mono", rate=sample_rate)
        for frame in container.decode(audio=0):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32) / 32768.0


def loudness_per_second(samples: Any, sample_rate: int = 16000) -> list[float]:
    """RMS level in dBFS for each second (cheap activity measure, not LUFS)."""
    import numpy as np

    out = []
    for i in range(len(samples) // sample_rate):
        block = samples[i * sample_rate:(i + 1) * sample_rate]
        out.append(float(20 * np.log10(np.sqrt(np.mean(block ** 2)) + 1e-9)))
    return out
