"""Decode once and compute energy features; keep editorial thresholds in domain/."""
import numpy as np
from .media import load_audio


def levels(path, step_s=.05):
    samples = load_audio(path)
    if not len(samples):
        raise ValueError("Source contains no decodable audio.")
    size = max(1, round(16000 * step_s))
    energy = [20 * np.log10(max(float(np.sqrt(np.mean(samples[offset:offset + size] ** 2))), 1e-9))
              for offset in range(0, len(samples), size)]
    return energy, len(samples) / 16000, size / 16000
