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
from .. import errors as E
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
        expected = 0
        if zoom := plan.track("zoom"):
            for k in zoom.expand_holds().keyframes:
                sizing = rezoom_keeping(src, dst, base, base.zoom * k.value, plan.anchor)
                for prop, value in sizing.as_props().items():
                    expected += 1
                    written += self._key(item, prop, k.frame, value, k.ease_out)
        if angle := plan.track("angle"):
            base_angle = float(call(item, "GetProperty", "RotationAngle") or 0.0)
            for k in angle.keyframes:
                expected += 1
                written += self._key(item, "RotationAngle", k.frame, base_angle + k.value, k.ease_out)
        if written == 0 or written != expected:
            self.clear(item)
            raise Unsupported(f"AddKeyframe accepted {written}/{expected} keys; partial animation was cleared")
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
        self._require_owned_graph(comp)
        media_in, media_out = comp.FindTool("MediaIn1"), comp.FindTool("MediaOut1")
        if media_in is None or media_out is None:
            raise Unsupported("clip comp has no MediaIn1/MediaOut1")
        self._remove(comp, media_in, media_out)

        # Structural edits under Lock; value writes must stay OUTSIDE it, or
        # Resolve reads them back but ignores them at render (upstream issue #196).
        comp.Lock()
        try:
            tf = comp.AddTool("Transform", -32768, -32768)
            if tf is None:
                raise Unsupported("Fusion refused Transform creation")
            tf.SetAttrs({"TOOLS_Name": FUSION_TOOL})
            if tf.ConnectInput("Input", media_in) is False or media_out.ConnectInput("Input", tf) is False:
                raise Unsupported("Fusion refused motion connections")
        finally:
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
    def _require_owned_graph(comp):
        tools = call(comp, "GetToolList", False, default=None)
        if not isinstance(tools, dict) or not tools:
            raise Unsupported("cannot verify existing Fusion graph; motion must not replace unknown effects")
        for name, tool in tools.items():
            # Some transports serialize nested handles; reacquire by tool name.
            if not callable(getattr(tool, "GetAttrs", None)):
                tool = comp.FindTool(str(name))
            attrs = call(tool, "GetAttrs", default={}) or {}
            if attrs.get("TOOLS_Name") not in {"MediaIn1", "MediaOut1", FUSION_TOOL} and attrs.get("TOOLS_RegID") != "BezierSpline":
                raise Unsupported("Fusion motion requires a plain source graph; existing effects must be preserved")

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
        try:
            old.Delete()
            media_out.ConnectInput("Input", media_in)
        finally:
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
        if tf.AddModifier(inp, "BezierSpline") is False:
            raise Unsupported(f"Fusion refused animation modifier for {inp}")
        samples = track.dense(step=2)
        for frame, value in samples:
            if tf.SetInput(inp, float(value), offset + frame) is False:
                raise Unsupported(f"Fusion refused {inp} at frame {offset + frame}")
        return len(samples)

    def clear(self, item) -> int:
        if int(call(item, "GetFusionCompCount", default=0) or 0) == 0:
            return 0
        comp = item.GetFusionCompByIndex(1)
        mi, mo = comp.FindTool("MediaIn1"), comp.FindTool("MediaOut1")
        if comp.FindTool(FUSION_TOOL) is None:
            return 0
        self._require_owned_graph(comp)
        return int(bool(mi and mo and self._remove(comp, mi, mo)))


def _set_point(tool, name: str, x: float, y: float) -> None:
    """Fusion Point inputs accept different encodings per transport; first that sticks wins."""
    for candidate in ([x, y], {1: x, 2: y}, {"1": x, "2": y}):
        try:
            if tool.SetInput(name, candidate) is False:
                continue
            observed = tool.GetInput(name)
            if isinstance(observed, dict):
                observed = [observed.get(1, observed.get("1")), observed.get(2, observed.get("2"))]
            if not isinstance(observed, (tuple, list)) or len(observed) < 2:
                continue
            if any(abs(float(a) - b) > 1e-6 for a, b in zip(observed, (x, y))):
                continue
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
            raise ForgeError(f"unknown backend '{name}'. Use one of: auto, {', '.join(APPLIERS)}",
                             code=E.INVALID_ARGUMENT)
        try:
            return APPLIERS[name].apply(item, plan, src, dst)
        except Unsupported as exc:
            reasons[name] = str(exc)
    raise ForgeError(f"no motion backend could animate '{item.GetName()}': {reasons}",
                     code=E.BACKEND_UNSUPPORTED, hint="Use backend='auto' or 'fusion' (works on every edition).")
