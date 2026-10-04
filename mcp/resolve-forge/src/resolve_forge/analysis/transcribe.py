"""Local speech-to-text (Free-edition replacement for Studio's AI transcription).

faster-whisper on the GPU when CUDA is usable (large-v3-turbo), otherwise CPU int8 (small).
Results are cached per (file, size, mtime, model, language) for the life of the server, so
captions + motion analysis of the same media cost one transcription.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Protocol

from ..domain.transcript import Word
from . import media


class Transcriber(Protocol):
    name: str

    def transcribe(self, path: str, language: str | None = None) -> tuple[list[Word], str]: ...


def available() -> bool:
    """Checked without importing: ctranslate2/CUDA DLLs must never load inside the MCP server."""
    return importlib.util.find_spec("faster_whisper") is not None and media.available()


class WhisperTranscriber:
    """Runs faster-whisper in a child process (see whisper_worker) and caches results.

    A child keeps CUDA/ctranslate2 DLL loading out of the MCP server (on Windows, loading DLLs
    while the stdio thread blocks on the pipe can deadlock), frees VRAM when done, and a GPU
    crash cannot take the server down.
    """

    def __init__(self, model: str = "auto", timeout_s: float = 1800) -> None:
        self.requested, self.timeout_s = model, timeout_s
        self.name = model
        self._cache: dict[tuple, tuple[list[Word], str]] = {}

    def transcribe(self, path: str, language: str | None = None) -> tuple[list[Word], str]:
        stat = Path(path).stat()
        key = (str(Path(path).resolve()), stat.st_size, stat.st_mtime, self.requested, language)
        if key in self._cache:
            return self._cache[key]
        cmd = [sys.executable, "-m", "resolve_forge.analysis.whisper_worker", str(path), "--model", self.requested]
        if language:
            cmd += ["--language", language]
        proc = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                              timeout=self.timeout_s, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout).strip()[-800:])
        data = json.loads(proc.stdout.strip().splitlines()[-1])
        self.name = data["model"]
        words = [Word(w["text"], w["start"], w["end"], w.get("prob", 1.0)) for w in data["words"]]
        self._cache[key] = (words, data["language"])
        return self._cache[key]
