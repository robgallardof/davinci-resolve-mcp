"""Use case: speaker layouts — frame whoever talks; split the screen when several talk at once.

Plans from the source (faces + mouth motion + voice) or from people/active given by the agent, then composes
the result with ffmpeg into a NEW clip (original audio kept) and, if asked, builds a timeline with it in
Resolve, where captions, texts and sound are added as usual. The source file is never modified.
"""

from __future__ import annotations

import secrets
import subprocess

from ..domain import formats, layouts
from ..errors import ForgeError
from .analysis_service import source_path
from .audio_service import ffmpeg_executable
from .render_service import DEFAULT_OUTPUT


def plan(session, source, format="tiktok", mode="auto", people=None, active=None, min_segment_s=1.5) -> dict:
    fmt = formats.get(format)
    path = source_path(session, source)
    if people is None or active is None:
        from ..analysis import speakers
        found, speaking, duration, aspect = speakers.scan(path)
        people = people if people is not None else [list(p) for p in found]
        active = active if active is not None else speaking
    else:
        duration, aspect = _probe(path)
    people = [tuple(float(v) for v in p) for p in people]
    active = [(float(t), tuple(int(i) for i in who)) for t, who in active]
    segments = layouts.layout_plan(people, active, duration, fmt.width, fmt.height, aspect, mode=mode,
                                   min_segment_s=min_segment_s)
    counts = {name: sum(1 for s in segments if s["layout"] == name) for name in ("single", "split", "wide")}
    return {"source": source, "format": fmt.key, "people": [list(p) for p in people], "segments": segments,
            "layouts": counts, "duration_s": round(duration, 3), "time_basis": "source seconds",
            "note": "Stylistic choice: use when the user asked for it or approved the suggestion.",
            "next": "build_speaker_layout(source, name, format, segments) — review the composed clip with review_video"}


def _probe(path):
    import cv2
    cap = cv2.VideoCapture(path)
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        w, h = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 16, cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 9
    finally:
        cap.release()
    return frames / fps, w / h


def _even(value):
    return max(2, int(round(value)) // 2 * 2)


def _graph(segments, sw, sh, out_w, out_h, fps):
    parts, labels = [], []
    for i, seg in enumerate(segments):
        a, b = seg["start_s"], seg["end_s"]
        tiles = []
        for j, panel in enumerate(seg["panels"]):
            x0, y0, x1, y1 = panel["crop"]
            px0, py0, px1, py1 = panel["screen"]
            pw, ph = _even((px1 - px0) * out_w), _even((py1 - py0) * out_h)
            cw, ch = _even((x1 - x0) * sw), _even((y1 - y0) * sh)
            cx, cy = min(int(x0 * sw), sw - cw), min(int(y0 * sh), sh - ch)
            parts.append(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS,fps={fps},crop={cw}:{ch}:{cx}:{cy},"
                         f"scale={pw}:{ph}:flags=lanczos,setsar=1[p{i}_{j}]")
            tiles.append((f"[p{i}_{j}]", panel["screen"]))
        if len(tiles) == 1:
            parts.append(f"{tiles[0][0]}scale={out_w}:{out_h}:flags=lanczos,setsar=1[v{i}]")
        else:
            layout = "|".join(f"{_even(r[0] * out_w)}_{_even(r[1] * out_h)}" for _, r in tiles)
            parts.append("".join(t for t, _ in tiles) + f"xstack=inputs={len(tiles)}:layout={layout}:fill=black,"
                         f"scale={out_w}:{out_h},setsar=1[v{i}]")
        parts.append(f"[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS[a{i}]")
        labels.append(f"[v{i}][a{i}]")
    parts.append("".join(labels) + f"concat=n={len(segments)}:v=1:a=1[vout][aout]")
    return ";".join(parts)


def build(session, source, name, format="tiktok", segments=None, mode="auto", into_resolve=True, dry_run=True) -> dict:
    fmt = formats.get(format)
    planned = plan(session, source, format, mode) if segments is None else None
    segments = segments if segments is not None else planned["segments"]
    if not segments:
        raise ValueError("No segments to compose")
    for seg in segments:
        if seg["end_s"] <= seg["start_s"] or not seg.get("panels"):
            raise ValueError("Each segment needs start_s < end_s and panels (use plan_speaker_layout)")
        for panel in seg["panels"]:
            if not all(0 <= float(v) <= 1 for v in (*panel["crop"], *panel["screen"])):
                raise ValueError("Panel crop/screen must be normalized 0..1")
    if dry_run:
        return {"dry_run": True, "segments": segments, "duration_s": round(sum(s["end_s"] - s["start_s"] for s in segments), 3)}
    import cv2
    path = source_path(session, source)
    cap = cv2.VideoCapture(path)
    sw, sh = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = round(cap.get(cv2.CAP_PROP_FPS) or fmt.fps)
    cap.release()
    out_dir = DEFAULT_OUTPUT / "speaker-layouts" / secrets.token_hex(4)
    out_dir.mkdir(parents=True, exist_ok=False)
    output = out_dir / f"{name}.mp4"
    result = subprocess.run([ffmpeg_executable(), "-hide_banner", "-nostdin", "-n", "-i", path,
                             "-filter_complex", _graph(segments, sw, sh, fmt.width, fmt.height, fps),
                             "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-crf", "17", "-preset", "medium",
                             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(output)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                            stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode or not output.is_file():
        raise ForgeError("Composing the speaker layout failed: " + result.stderr[-600:], code="AUDIO_PROCESSING_FAILED")
    out = {"dry_run": False, "file": str(output), "segments": len(segments),
           "duration_s": round(sum(s["end_s"] - s["start_s"] for s in segments), 3), "resolution": f"{fmt.width}x{fmt.height}"}
    if into_resolve:
        from . import assembly_service
        built = assembly_service.assemble(session, str(output), [[0.0, out["duration_s"]]], name=name, format=format)
        out.update(timeline=built["timeline"], fps=built.get("fps"))
    out["next"] = "review_video(file) and LOOK; then captions/texts on the new timeline"
    return out
