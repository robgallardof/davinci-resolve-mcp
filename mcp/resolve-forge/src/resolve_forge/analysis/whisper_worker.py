"""Child process: transcribe one file and print one JSON line. Used by analysis.transcribe."""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys


def _expose_cuda_dlls() -> None:
    """pip's nvidia-* wheels ship DLLs that ctranslate2 cannot find on Windows by itself."""
    try:
        import nvidia
    except ImportError:
        return
    for root in list(getattr(nvidia, "__path__", [])):
        for d in glob.glob(os.path.join(root, "*", "bin")):
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(d)
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


def load_model(requested: str):
    from faster_whisper import WhisperModel
    import numpy as np

    _expose_cuda_dlls()
    names = ["large-v3-turbo", "small"] if requested == "auto" else [requested, requested]
    attempts = [(names[0], "cuda", "float16"), (names[1], "cpu", "int8")]
    last = None
    for name, device, compute in attempts:
        try:
            model = WhisperModel(name, device=device, compute_type=compute)
            if device == "cuda":  # model loading is lazy: prove CUDA really works with a tiny encode
                list(model.transcribe(np.zeros(16000, dtype=np.float32))[0])
            return model, f"{name}@{device}"
        except Exception as exc:  # no CUDA, missing cuBLAS/cuDNN, not enough VRAM...
            last = exc
    raise RuntimeError(f"could not load a Whisper model: {last}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--model", default="auto")
    ap.add_argument("--language", default=None)
    args = ap.parse_args()

    from resolve_forge.analysis.media import load_audio

    model, label = load_model(args.model)
    segments, info = model.transcribe(load_audio(args.path), language=args.language,
                                      word_timestamps=True, vad_filter=True)
    words = [{"text": w.word.strip(), "start": round(float(w.start), 3), "end": round(float(w.end), 3),
              "prob": round(float(w.probability), 3)}
             for s in segments for w in (s.words or []) if w.word.strip()]
    sys.stdout.write(json.dumps({"model": label, "language": info.language, "words": words}, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
