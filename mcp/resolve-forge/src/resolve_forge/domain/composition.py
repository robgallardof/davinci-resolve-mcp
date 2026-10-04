"""Pure multi-source geometry and independent source-time decisions."""
import math
from .layouts import panels, crop_for


def number(value, name, minimum=0):
    value = float(value)
    if not math.isfinite(value) or value < minimum:
        raise ValueError(f"{name} must be finite and >= {minimum}")
    return value


def rect(value, name):
    if len(value) != 4:
        raise ValueError(f"{name} needs four normalized coordinates")
    r = tuple(number(v, name) for v in value)
    if not (0 <= r[0] < r[2] <= 1 and 0 <= r[1] < r[3] <= 1):
        raise ValueError(f"{name} must be an ordered rectangle inside 0..1")
    return r


def plan(segments, audio_master, width, height):
    if not segments or len(segments) > 100:
        raise ValueError("Provide 1..100 reviewed composition segments")
    if not isinstance(audio_master, dict) or not audio_master.get("source"):
        raise ValueError("An explicit continuous audio_master.source is required")
    audio = {"source": str(audio_master["source"]), "start_s": number(audio_master.get("start_s", 0), "audio start")}
    result, time = [], 0.0
    for segment in segments:
        duration = number(segment["duration_s"], "segment duration", .04)
        sources = segment["sources"]
        if not 1 <= len(sources) <= 5:
            raise ValueError("Each segment needs 1..5 visual sources")
        mode = segment.get("layout", "mosaic")
        if mode not in ("mosaic", "hero_support"):
            raise ValueError("layout must be mosaic or hero_support")
        if mode == "hero_support" and len(sources) < 2:
            raise ValueError("hero_support needs a hero and at least one supporting source")
        screens = panels(len(sources), width, height)
        if mode == "hero_support":
            screens = [(0, 0, 1, .68)] + [(i/(len(sources)-1), .68, (i+1)/(len(sources)-1), 1) for i in range(len(sources)-1)]
        visual = []
        for item, screen in zip(sources, screens):
            if not item.get("source"):
                raise ValueError("Every panel needs source")
            if item.get("crop") is not None and item.get("subject") is not None:
                raise ValueError("Use crop or subject, not both")
            fit = item.get("fit", "contain")
            if fit not in ("contain", "cover"):
                raise ValueError("fit must be contain or cover")
            visual.append({"source": str(item["source"]), "start_s": number(item.get("start_s", 0), "visual start"),
                           "crop": list(rect(item.get("crop", [0,0,1,1]), "crop")),
                           "subject": list(rect(item["subject"], "subject")) if item.get("subject") is not None else None,
                           "screen": list(screen), "fit": fit})
        result.append({"start_s": time, "duration_s": duration, "layout": mode, "sources": visual})
        time += duration
    if time > 120:
        raise ValueError("Composition assets are limited to 120 seconds; split longer pieces")
    return {"segments": result, "duration_s": time, "audio_master": audio, "width": width, "height": height}
