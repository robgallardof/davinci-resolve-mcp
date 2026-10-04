"""Local spectral rhythm evidence. No claim of semantic drop/downbeat recognition."""

from __future__ import annotations

import numpy as np

from .media import load_audio


def features(samples, rate=16000):
    hop, window = round(rate * 0.01), 1024
    if not len(samples):
        raise ValueError("No decodable music audio")
    padded = np.pad(samples, (0, window))
    count = int(np.ceil(len(samples) / hop))
    flux, rms, previous = [], [], np.zeros(window // 2 + 1)
    taper = np.hanning(window)
    for offset in range(count):
        block = padded[offset * hop:offset * hop + window]
        spectrum = np.abs(np.fft.rfft(block * taper))
        flux.append(float(np.maximum(np.log1p(spectrum) - np.log1p(previous), 0).mean()))
        rms.append(float(np.sqrt(np.mean(block ** 2))))
        previous = spectrum
    return np.asarray(flux), np.asarray(rms), hop / rate


def rhythm(samples, rate=16000):
    flux, energy, step = features(samples, rate)
    duration = len(samples) / rate
    center_offset = 1024 / (2 * rate)  # spectral windows are timestamped at their center
    peak = float(np.max(flux))
    if peak < 1e-8:
        return {"duration_s": duration, "onsets_s": [], "tempo_bpm": None, "confidence": 0.0,
                "beats_s": [], "section_candidates": []}
    novelty = flux / peak
    floor = np.convolve(novelty, np.ones(101) / 101, mode="full")[50:50 + len(novelty)]
    candidates = [i for i in range(1, len(novelty) - 1)
                  if novelty[i] > max(.08, floor[i] * 1.7) and novelty[i] >= novelty[i - 1] and novelty[i] > novelty[i + 1]]
    if novelty[0] > .08:
        candidates.insert(0, 0)
    selected = []
    for index in candidates:
        if not selected or (index - selected[-1]) * step >= .18:
            selected.append(index)
        elif novelty[index] > novelty[selected[-1]]:
            selected[-1] = index
    # FFT autocorrelation stays linearithmic for full songs; no quadratic correlate on long arrays.
    centered = np.maximum(novelty - floor, 0)
    length = 1 << (2 * len(centered) - 1).bit_length()
    spectrum = np.fft.rfft(centered, n=length)
    correlation = np.fft.irfft(spectrum * np.conjugate(spectrum), n=length)[:len(centered)]
    lags = np.arange(round(60 / (180 * step)), min(len(correlation), round(60 / (70 * step)) + 1))
    tempo, confidence, beats = None, 0.0, []
    if len(lags) and len(selected) >= 4 and correlation[0] > 1e-9 and duration >= 4:
        # Correct finite-duration attenuation; shorter excerpts must not favor shorter periods.
        scores = correlation[lags] / np.maximum(1, len(centered) - lags)
        lag = int(lags[np.argmax(scores)])
        confidence = min(1.0, max(0.0, float(correlation[lag] / correlation[0])))
        if confidence >= .2:
            tempo = round(60 / (lag * step), 2)
            phases = np.arange(lag)
            phase = int(max(phases, key=lambda p: float(novelty[p::lag].sum())))
            beats = [round(index * step + center_offset, 3) for index in range(phase, len(novelty), lag)
                     if index * step + center_offset < duration]
    # Sustained energy contrast is evidence for listening, never an automatic 'drop' label.
    seconds = [float(np.mean(energy[i:i + 100])) for i in range(0, len(energy), 100)]
    sections = []
    for index in range(2, len(seconds) - 2):
        before, after = float(np.mean(seconds[index - 2:index])), float(np.mean(seconds[index:index + 2]))
        contrast = abs(after - before) / max(before, after, 1e-6)
        if contrast > .45 and (not sections or index - sections[-1]["time_s"] >= 4):
            sections.append({"time_s": index, "evidence": "sustained energy change", "contrast": round(contrast, 3)})
    return {"duration_s": round(duration, 3), "onsets_s": [round(index * step + center_offset, 3) for index in selected
                                                           if index * step + center_offset < duration],
            "tempo_bpm": tempo, "confidence": round(confidence, 3), "beats_s": beats, "section_candidates": sections}


def analyse(path):
    result = rhythm(load_audio(path))
    return {**result, "time_basis": "source seconds", "method": "positive log-spectral flux, novelty autocorrelation and strongest phase",
            "limitations": "Estimated grid can be half/double time or drift on tempo changes. No bar/downbeat, genre or semantic drop detection. Listen and confirm sections before editing."}
