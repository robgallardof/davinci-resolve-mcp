import json
import subprocess

import pytest

from resolve_forge.analysis import transcribe


def test_whisper_runs_once_per_file_version_and_reports_the_real_model(tmp_path, monkeypatch):
    audio = tmp_path / "voz.wav"
    audio.write_bytes(b"one")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        payload = {"model": "small", "language": "es", "words": [{"text": "hola", "start": 0, "end": .4}]}
        return subprocess.CompletedProcess(cmd, 0, stdout="log line\n" + json.dumps(payload), stderr="")

    monkeypatch.setattr(transcribe.subprocess, "run", fake_run)
    whisper = transcribe.WhisperTranscriber()
    words, language = whisper.transcribe(str(audio), "es")
    assert [w.text for w in words] == ["hola"] and language == "es" and whisper.name == "small"
    whisper.transcribe(str(audio), "es")
    assert len(calls) == 1 and "--language" in calls[0]
    audio.write_bytes(b"changed content")  # new size -> new cache key
    whisper.transcribe(str(audio), "es")
    assert len(calls) == 2


def test_whisper_failures_surface_the_worker_error(tmp_path, monkeypatch):
    audio = tmp_path / "voz.wav"
    audio.write_bytes(b"x")
    monkeypatch.setattr(transcribe.subprocess, "run",
                        lambda cmd, **_: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="CUDA exploded"))
    with pytest.raises(RuntimeError, match="CUDA exploded"):
        transcribe.WhisperTranscriber().transcribe(str(audio))
