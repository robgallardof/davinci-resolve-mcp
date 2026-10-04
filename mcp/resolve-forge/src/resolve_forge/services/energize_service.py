"""Use case: entertainment pacing — short shots, alternating framings, zooms that follow the action."""

from __future__ import annotations

from ..domain import energize
from ..errors import ForgeError
from . import assembly_service, motion_service
from .analysis_service import source_path

# framing -> (motion style, intensity for the plan's zoom, hits?)
_STYLE = {"wide": ("warm_push", lambda z: 0.5), "medium": ("focus_hold", lambda z: (z - 1) / 0.25),
          "close": ("focus_hold", lambda z: (z - 1) / 0.25), "crash": ("crash_zoom", lambda z: (z - 1) / 0.45)}


def _upscale(path, format):
    """How much the source is already enlarged to fit the platform frame (WhatsApp 576 px -> 1080: x1.875)."""
    if not format:
        return 1.0
    import cv2
    from ..domain import formats
    cap = cv2.VideoCapture(path)
    try:
        width, height = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    finally:
        cap.release()
    fmt = formats.get(format)
    return min(fmt.width / width, fmt.height / height) if width and height else 1.0


def plan(session, source, ranges=None, min_shot_s=1.2, max_shot_s=2.8, trim_dead=True, max_zoom=1.6,
         use_faces=True, hints=None, format=None, drop_dull=True) -> dict:
    try:
        import cv2  # noqa: F401
    except ImportError as exc:
        raise ForgeError("Action detection needs OpenCV.", code="MISSING_DEPENDENCY",
                         hint="cd mcp/resolve-forge && uv sync --extra vision") from exc
    from ..analysis import action, presence as people
    path = source_path(session, source)
    raw, duration, aspect = action.samples(path)
    samples = [energize.Sample(s.time_s, s.energy, s.x, s.y, s.spread, s.box) for s in raw]
    # One pass for faces (frontal + profiles) and bodies: reactions, and people seen from behind (dead time).
    scan = [(p.time_s, p.faces, p.people) for p in people.scan(path)] if use_faces else []
    result = energize.plan(samples, ranges, presence=scan if use_faces else None, drop_dull=drop_dull, hints=hints, min_shot_s=min_shot_s, max_shot_s=max_shot_s,
                           trim_dead=trim_dead, max_zoom=max_zoom, upscale=_upscale(path, format))
    return {"source": source, "source_duration_s": round(duration, 3), "faces_found": sum(len(f) for _, f, _ in scan), **result,
            "next": "review_shots(source, shots, format, texts) and LOOK at the sheet; fix; then energize_timeline",
            "review": "Watch it: move cuts that split a gesture, swap framings that hide the joke, keep reveals wide."}


def _validate(shots):
    if not shots or len(shots) > 400:
        raise ValueError("shots needs 1-400 planned shots")
    for shot in shots:
        if not isinstance(shot, dict) or shot.get("framing") not in _STYLE:
            raise ValueError("Each shot needs framing wide/medium/close/crash (use plan_energized_edit)")
        anchor = shot.get("anchor")
        if not (isinstance(anchor, (list, tuple)) and len(anchor) == 2 and all(0 <= float(v) <= 1 for v in anchor)):
            raise ValueError("Each shot anchor must be [x, y] in 0..1")
        if float(shot["end_s"]) <= float(shot["start_s"]):
            raise ValueError("Each shot needs end_s > start_s")


def apply(session, source, name, format=None, shots=None, dry_run=True, **plan_args) -> dict:
    planned = None if shots is not None else plan(session, source, format=format, **plan_args)
    shots = shots if shots is not None else planned["shots"]
    _validate(shots)
    if dry_run:
        return {"dry_run": True, "timeline": name, "shots": shots,
                "duration_s": round(sum(s["end_s"] - s["start_s"] for s in shots), 3)}
    built = assembly_service.assemble(session, source, [[s["start_s"], s["end_s"]] for s in shots], name=name, format=format)
    if built["clips"] != len(shots):
        raise ForgeError(f"Resolve placed {built['clips']} of {len(shots)} shots.", code="RESOLVE_REFUSED")
    applied, at = [], 0.0
    for index, shot in enumerate(shots, 1):
        style, strength = _STYLE[shot["framing"]]
        zoom = float(shot.get("zoom", energize.ZOOM[shot["framing"]]))
        hits = None
        if shot["framing"] == "crash" and shot.get("hit_s") is not None:
            hits = [at + max(0.0, float(shot["hit_s"]) - float(shot["start_s"]) - 0.1)]
        motion_service.animate(session, style, clips=[index], hits_s=hits, intensity=max(0.1, strength(zoom)),
                               anchor=[float(v) for v in shot["anchor"]])
        applied.append(shot["framing"])
        at += float(shot["end_s"]) - float(shot["start_s"])
    return {"dry_run": False, "timeline": built["timeline"], "shots": len(shots), "duration_s": built["duration_s"],
            "fps": built.get("fps"), "resolution": built["resolution"],
            "framings": {name: applied.count(name) for name in _STYLE},
            "next": "add_captions (real speech, verified words), add_text_overlay for beats, place_sound_effects, render_for"}
