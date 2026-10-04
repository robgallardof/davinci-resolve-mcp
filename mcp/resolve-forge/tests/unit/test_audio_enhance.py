from array import array
import math
import subprocess
import wave

import pytest

from resolve_forge.domain.audio_presets import filter_chain
from resolve_forge.services import audio_enhance_service, audio_service


def write_signal(path):
    rate = 48000
    samples = array("h", (int(32767 * max(-1, min(1,
        .4 * math.sin(2 * math.pi * 30 * i / rate) + .4 * math.sin(2 * math.pi * 1000 * i / rate))))
        for i in range(rate * 4)))
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(samples.tobytes())


def decode(path):
    result = subprocess.run([audio_service.ffmpeg_executable(), "-v", "error", "-nostdin", "-i", str(path),
                             "-f", "f32le", "-ac", "1", "-ar", "48000", "-"], capture_output=True, check=True)
    values = array("f")
    values.frombytes(result.stdout)
    return values


def spectral_amplitude(values, frequency):
    # Exclude filter startup and tail; exact whole-second harmonic projection.
    values = values[48000:144000]
    phase = 2 * math.pi * frequency / 48000
    real = sum(value * math.cos(phase * index) for index, value in enumerate(values))
    imag = sum(value * math.sin(phase * index) for index, value in enumerate(values))
    return math.hypot(real, imag) / len(values)


def test_enhancement_reduces_rumble_and_preserves_headroom(tmp_path):
    source, output = tmp_path / "source.wav", tmp_path / "enhanced.wav"
    write_signal(source)
    original = source.read_bytes()
    result = audio_enhance_service.enhance(None, str(source), output_path=str(output), dry_run=False)
    before, after = decode(source), decode(output)
    before_ratio = spectral_amplitude(before, 30) / spectral_amplitude(before, 1000)
    after_ratio = spectral_amplitude(after, 30) / spectral_amplitude(after, 1000)
    assert after_ratio < before_ratio * .35
    assert max(abs(v) for v in after) < .892
    assert len(after) == len(before)
    assert source.read_bytes() == original
    assert math.isfinite(result["measured_output"]["input_i"])
    assert result["measured_output"]["input_tp"] < 0


def test_preview_writes_nothing_and_reports_measurement(tmp_path):
    source, output = tmp_path / "source.wav", tmp_path / "enhanced.wav"
    write_signal(source)
    result = audio_enhance_service.enhance(None, str(source), "podcast", str(output))
    assert not result["applied"]
    assert not output.exists()
    assert math.isfinite(result["measured_source"]["input_i"])


def test_full_scale_transient_is_limited_without_inventing_recovery(tmp_path):
    source, output = tmp_path / "peaks.wav", tmp_path / "limited.wav"
    rate = 48000
    samples = array("h", (int(1500 * math.sin(2 * math.pi * 1000 * i / rate)) for i in range(rate * 4)))
    for position in (rate, rate * 2, rate * 3):
        samples[position] = 32767
        samples[position + 1] = -32767
    with wave.open(str(source), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(samples.tobytes())
    result = audio_enhance_service.enhance(None, str(source), "entertainment", str(output), False)
    assert max(abs(v) for v in decode(source)) > .99
    assert max(abs(v) for v in decode(output)) <= .892
    assert "clipped-source recovery" in result["scope"]


@pytest.mark.parametrize("preset", ["unknown", "dialogue,volume=10", ""])
def test_invalid_presets_do_not_reach_processor(preset):
    with pytest.raises(ValueError):
        filter_chain(preset)


def test_existing_output_cannot_be_overwritten(tmp_path):
    source, output = tmp_path / "source.wav", tmp_path / "enhanced.wav"
    write_signal(source)
    output.write_bytes(b"preserve")
    with pytest.raises(ValueError):
        audio_enhance_service.enhance(None, str(source), output_path=str(output), dry_run=False)
    assert output.read_bytes() == b"preserve"
