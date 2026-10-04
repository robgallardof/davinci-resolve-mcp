"""Speech EQ/dynamics baked into a new WAV, with source and output loudness evidence."""
from pathlib import Path

from ..domain.audio_presets import filter_chain
from ..errors import ForgeError
from . import audio_service
from .analysis_service import source_path


def enhance(session, source, preset="dialogue", output_path=None, dry_run=True):
    filters = filter_chain(preset)
    source_file = source_path(session, source)
    output = Path(output_path or Path.home() / "Movies/resolve-forge" / (Path(source_file).stem + f"_{preset}_enhanced.wav")).expanduser().resolve()
    if output.exists() or output.suffix.lower() != ".wav":
        raise ValueError("Enhancement requires a new .wav destination; existing media is never overwritten.")
    executable = audio_service.ffmpeg_executable()
    meter = "loudnorm=I=-14:TP=-1:LRA=11"
    before = audio_service._measure(executable, source_file, meter)
    summary = {"source": source_file, "preset": preset, "filters": filters,
               "measured_source": before, "output": str(output),
               "scope": "Gentle highpass, compression and peak limiting. No voice isolation, denoise, clipped-source recovery or LUFS normalization. Listen for tonal/dynamics changes."}
    if dry_run:
        return {**summary, "applied": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    audio_service.run([executable, "-hide_banner", "-nostdin", "-n", "-i", source_file,
                       "-map", "0:a:0", "-vn", "-af", filters, "-ar", "48000", "-c:a", "pcm_s24le", str(output)])
    if not output.is_file() or output.stat().st_size < 44:
        raise ForgeError("Enhanced WAV is absent or empty.", code="AUDIO_PROCESSING_FAILED")
    after = audio_service._measure(executable, str(output), meter)
    return {**summary, "file": str(output), "applied": True, "measured_output": after,
            "peak_target_met": after["input_tp"] <= -.8,
            "next": "Listen to the new WAV and compare with source. Use normalise_audio if a delivery LUFS target is needed; import explicitly with ingest_media."}
