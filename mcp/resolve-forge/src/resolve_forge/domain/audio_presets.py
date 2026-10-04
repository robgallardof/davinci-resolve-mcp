"""Small speech-oriented dynamics chains. No noise/voice isolation claims."""
PRESETS = {
    "dialogue": {"highpass_hz": 70, "threshold": .125, "ratio": 2., "attack_ms": 20, "release_ms": 200},
    "podcast": {"highpass_hz": 65, "threshold": .15, "ratio": 2., "attack_ms": 25, "release_ms": 250},
    "entertainment": {"highpass_hz": 80, "threshold": .125, "ratio": 2.5, "attack_ms": 15, "release_ms": 180},
}


def filter_chain(preset: str) -> str:
    if preset not in PRESETS:
        raise ValueError(f"Unknown audio preset; choose {', '.join(PRESETS)}.")
    p = PRESETS[preset]
    return (f"highpass=f={p['highpass_hz']}:poles=2,"
            f"acompressor=threshold={p['threshold']}:ratio={p['ratio']}:attack={p['attack_ms']}:release={p['release_ms']}:makeup=1,"
            "alimiter=limit=0.891251:level=false:attack=5:release=50:latency=true")
