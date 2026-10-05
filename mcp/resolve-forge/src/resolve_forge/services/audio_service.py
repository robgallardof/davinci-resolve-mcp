"""Measured two-pass loudness normalisation to a new WAV; source media is preserved."""
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

from ..errors import ForgeError
from .analysis_service import source_path
from .native import number


def run(command):
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired as exc:
        raise ForgeError("Audio processing exceeded its time limit.", code="AUDIO_PROCESSING_TIMEOUT") from exc
    if result.returncode:
        raise ForgeError("Audio processing failed: " + result.stderr[-1000:], code="AUDIO_PROCESSING_FAILED")
    return result.stderr


def ffmpeg_executable():
    """System ffmpeg if present, else the one bundled with imageio-ffmpeg (a Forge dependency)."""
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise ForgeError("Audio processing requires the bundled ffmpeg dependency.", code="MISSING_DEPENDENCY",
                         hint="Run scripts/bootstrap.ps1 (Windows) or scripts/bootstrap.sh (macOS/Linux).") from exc


def _measure(executable, path, filter_base):
    stderr = run([executable, "-hide_banner", "-nostdin", "-i", path, "-vn", "-af", filter_base + ":print_format=json", "-f", "null", "-"])
    matches = re.findall(r'\{[^{}]*"input_i"[^{}]*\}', stderr, re.S)
    if not matches:
        raise ForgeError("Loudness measurement did not return statistics.", code="AUDIO_PROCESSING_FAILED")
    measured = json.loads(matches[-1])
    fields = {key: float(measured[key]) for key in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}
    if not all(math.isfinite(value) for value in fields.values()):
        raise ValueError("Silent or invalid audio cannot be normalised from these measurements.")
    return fields


def normalise(session, source, output_path=None, target_lufs=-14, peak_db=-1, dry_run=True):
    number(target_lufs, "integrated loudness", -70, -5)
    number(peak_db, "true peak", -9, 0)
    executable = ffmpeg_executable()
    source_file = source_path(session, source)
    filter_base = f"loudnorm=I={target_lufs}:TP={peak_db}:LRA=11"
    fields = _measure(executable, source_file, filter_base)
    if dry_run:
        return {"source": source_file, "measured": fields, "target_lufs": target_lufs, "applied": False}
    output = Path(output_path or Path.home() / "Movies/resolve-forge" / (Path(source_file).stem + "_normalised.wav")).expanduser().resolve()
    if output.exists() or output.suffix.lower() != ".wav":
        raise ValueError("Normalisation needs a new .wav output; it never overwrites media.")
    output.parent.mkdir(parents=True, exist_ok=True)
    second = filter_base + f":measured_I={fields['input_i']}:measured_TP={fields['input_tp']}:measured_LRA={fields['input_lra']}:measured_thresh={fields['input_thresh']}:offset={fields['target_offset']}:linear=true"
    run([executable, "-hide_banner", "-nostdin", "-n", "-i", source_file, "-vn", "-af", second, "-ar", "48000", "-c:a", "pcm_s24le", str(output)])
    if not output.is_file() or output.stat().st_size < 44:
        raise ForgeError("The normalised WAV is absent or empty.", code="AUDIO_PROCESSING_FAILED")
    measured_output = _measure(executable, str(output), filter_base)
    if abs(measured_output["input_i"] - target_lufs) > 1 or measured_output["input_tp"] > peak_db + .2:
        raise ForgeError("The output did not meet loudness/peak targets; inspect the new WAV.", code="LOUDNESS_VERIFICATION_FAILED")
    return {"file": str(output), "measured_source": fields, "measured_output": measured_output, "target_lufs": target_lufs, "applied": True,
            "next": "Import the new WAV with ingest_media; source and timeline remain unchanged."}
