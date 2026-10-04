"""Backends that turn a MotionPlan into real animation on a timeline item.

Strategy pattern: each applier owns one technique and says when it cannot run
(`Unsupported`), so `apply_plan` can fall back without knowing the details.

  keyframes — native Edit-page Inspector keyframes (Resolve 20+). Editable by
              hand afterwards, no Fusion render cost. Preferred.
  fusion    — a Transform node with BezierSpline keys inside the clip's Fusion
              comp. Works on any version/edition, heavier to render.
"""

from __future__ import annotations

from typing import Any, Protocol

from ..domain.easing import RESOLVE_INTERPOLATION
from ..domain.framing import Sizing, rezoom_keeping
from ..domain.keyframes import Track
from ..domain.motion import MotionPlan
from ..gateway import call
from .context import ForgeError

EDIT_PROPS = ("ZoomX", "ZoomY", "Pan", "Tilt", "RotationAngle")
FUSION_TOOL = "ForgeMotion"
FUSION_INPUTS = {"zoom": "Size", "angle": "Angle"}


class Unsupported(Exception):
    pass


class Applier(Protocol):
    name: str

    def apply(self, item: Any, plan: MotionPlan, src: tuple[int, int], dst: tuple[int, int]) -> dict: ...

    def clear(self, item: Any) -> int: ...


class EditKeyframeApplier:
    name = "keyframes"

    def apply(self, item, plan, src, dst):
        if not callable(getattr(item, "AddKeyframe", None)):
            raise Unsupported("TimelineItem.AddKeyframe needs Resolve 20+")
        self.clear(item)
        base = Sizing(
            float(call(item, "GetProperty", "ZoomX") or 1.0),
            float(call(item, "GetProperty", "Pan") or 0.0),
            float(call(item, "GetProperty", "Tilt") or 0.0),
        )
        written = 0
        if zoom := plan.track("zoom"):
            for k in zoom.expand_holds().keyframes:
                sizing = rezoom_keeping(src, dst, base, base.zoom * k.value, plan.anchor)
                for prop, value in sizing.as_props().items():
                    written += self._key(item, prop, k.frame, value, k.ease_out)
        if angle := plan.track("angle"):
            base_angle = float(call(item, "GetProperty", "RotationAngle") or 0.0)
            for k in angle.keyframes:
                written += self._key(item, "RotationAngle", k.frame, base_angle + k.value, k.ease_out)
        if written == 0:
            raise Unsupported("AddKeyframe accepted no keys on this item")
        return {"backend": self.name, "keys_written": written}

    @staticmethod
    def _key(item, prop, frame, value, ease) -> int:
        if not item.AddKeyframe(prop, int(frame), float(value)):
            return 0
        call(item, "SetKeyframeInterpolation", prop, int(frame), RESOLVE_INTERPOLATION[ease])
        return 1

    def clear(self, item) -> int:
        removed = 0
        for prop in EDIT_PROPS:
            count = int(call(item, "GetKeyframeCount", prop, default=0) or 0)
            frames = []
            for i in range(count):
                kf = call(item, "GetKeyframeAtIndex", prop, i)
                frames.append(kf.get("frame") if isinstance(kf, dict) else kf)
            for f in frames:
                if f is not None and call(item, "DeleteKeyframe", prop, f, default=False):
                    removed += 1
        return removed


class FusionTransformApplier:
    name = "fusion"

    def apply(self, item, plan, src, dst):
        comp = self._comp(item)
        media_in, media_out = comp.FindTool("MediaIn1"), comp.FindTool("MediaOut1")
        if media_in is None or media_out is None:
            raise Unsupported("clip comp has no MediaIn1/MediaOut1")
        self._remove(comp, media_in, media_out)

        # Structural edits under Lock; value writes must stay OUTSIDE it, or
        # Resolve reads them back but ignores them at render (upstream issue #196).
        comp.Lock()
        tf = comp.AddTool("Transform", -32768, -32768)
        tf.SetAttrs({"TOOLS_Name": FUSION_TOOL})
        tf.ConnectInput("Input", media_in)
        media_out.ConnectInput("Input", tf)
        comp.Unlock()

        attrs = comp.GetAttrs() or {}
        offset = float(attrs.get("COMPN_RenderStart", attrs.get("COMPN_RenderStartTime", 0)) or 0)
        comp.StartUndo("Forge motion")
        try:
            ax, ay = plan.anchor
            _set_point(tf, "Pivot", ax, 1.0 - ay)  # Fusion is bottom-left origin
            written = sum(self._animate(tf, track, offset) for track in plan.tracks)
        finally:
            comp.EndUndo(True)
        return {"backend": self.name, "tool": FUSION_TOOL, "comp_offset": offset, "keys_written": written}

    @staticmethod
    def _comp(item):
        if int(call(item, "GetFusionCompCount", default=0) or 0) > 0:
            return item.GetFusionCompByIndex(1)
        comp = call(item, "AddFusionComp")
        if comp is None:
            raise Unsupported("could not create a Fusion comp on this item")
        return comp

    @staticmethod
    def _remove(comp, media_in, media_out) -> bool:
        old = comp.FindTool(FUSION_TOOL)
        if old is None:
            return False
        comp.Lock()
        old.Delete()
        media_out.ConnectInput("Input", media_in)
        comp.Unlock()
        return True

    @staticmethod
    def _animate(tf, track: Track, offset: float) -> int:
        """Plain SetInput per sample: the only write that survives every transport.

        Spline handles (SetKeyFrames) are avoided on purpose — the Free-edition
        bridge serialises through JSON, turning numeric table keys into strings.
        """
        inp = FUSION_INPUTS.get(track.param)
        if inp is None:
            return 0
        tf.AddModifier(inp, "BezierSpline")  # without a spline, timed SetInput only sets a static value
        samples = track.dense(step=2)
        for frame, value in samples:
            tf.SetInput(inp, float(value), offset + frame)
        return len(samples)

    def clear(self, item) -> int:
        if int(call(item, "GetFusionCompCount", default=0) or 0) == 0:
            return 0
        comp = item.GetFusionCompByIndex(1)
        mi, mo = comp.FindTool("MediaIn1"), comp.FindTool("MediaOut1")
        return int(bool(mi and mo and self._remove(comp, mi, mo)))


def _set_point(tool, name: str, x: float, y: float) -> None:
    """Fusion Point inputs accept different encodings per transport; first that sticks wins."""
    for candidate in ([x, y], {1: x, 2: y}, {"1": x, "2": y}):
        try:
            tool.SetInput(name, candidate)
            return
        except Exception:
            continue
    raise Unsupported(f"could not set Fusion point input {name}")


APPLIERS: dict[str, Applier] = {a.name: a for a in (EditKeyframeApplier(), FusionTransformApplier())}


def apply_plan(item, plan: MotionPlan, src, dst, backend: str = "auto") -> dict:
    order = list(APPLIERS) if backend == "auto" else [backend]
    reasons = {}
    for name in order:
        if name not in APPLIERS:
            raise ForgeError(f"unknown backend '{name}'. Use one of: auto, {', '.join(APPLIERS)}")
        try:
            return APPLIERS[name].apply(item, plan, src, dst)
        except Unsupported as exc:
            reasons[name] = str(exc)
    raise ForgeError(f"no motion backend could animate '{item.GetName()}': {reasons}")
