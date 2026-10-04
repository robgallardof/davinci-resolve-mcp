"""Motion backends in isolation, against the fake API (direct and bridge-like transports)."""

import pytest

from fakes import BridgeLike, demo_resolve
from resolve_forge.domain import styles
from resolve_forge.services.appliers import FUSION_TOOL, EditKeyframeApplier, FusionTransformApplier, apply_plan
from resolve_forge.services.context import ForgeError

SRC = DST = (1920, 1080)


def item(*, keyframes=True, bridge=False):
    raw = demo_resolve(studio=False, keyframes=keyframes).project.current.tracks[0][0]
    return raw, (BridgeLike(raw) if bridge else raw)


def plan(name="tiktok_punch"):
    return styles.build(name, duration=300, fps=30, cuts=[90, 180], anchor=(0.6, 0.4))


@pytest.mark.parametrize("bridge", [False, True], ids=["direct", "bridge"])
def test_edit_keyframes_written_with_interpolation(bridge):
    raw, it = item(bridge=bridge)
    out = EditKeyframeApplier().apply(it, plan(), SRC, DST)
    assert out["backend"] == "keyframes" and out["keys_written"] > 0
    zoom = raw.keys["ZoomX"]
    assert zoom[0] == pytest.approx(1.0) and zoom[90] == pytest.approx(1.15)
    assert raw.keys["Pan"][90] != 0  # off-center anchor -> position compensates
    assert set(raw.interp.values()) <= {"Linear", "EaseIn", "EaseOut", "EaseInOut"}


def test_edit_keyframes_rerun_replaces():
    raw, it = item()
    EditKeyframeApplier().apply(it, plan(), SRC, DST)
    EditKeyframeApplier().apply(it, styles.build("warm_push", duration=300, fps=30), SRC, DST)
    assert sorted(raw.keys["ZoomX"]) == [0, 299]


@pytest.mark.parametrize("bridge", [False, True], ids=["direct", "bridge"])
def test_fusion_wires_transform_and_keys_outside_lock(bridge):
    raw, it = item(keyframes=False, bridge=bridge)
    out = FusionTransformApplier().apply(it, plan("warm_push"), SRC, DST)
    comp = raw.comps[0]
    tf = comp.FindTool(FUSION_TOOL)
    assert comp.FindTool("MediaOut1").connected["Input"] is tf
    assert tf.connected["Input"] is comp.FindTool("MediaIn1")
    keys = tf.timed["Size"]
    offset = out["comp_offset"]
    assert offset == 300.0 and min(keys) == offset and max(keys) == offset + 299
    assert keys[offset] == pytest.approx(1.0) and keys[offset + 299] == pytest.approx(1.08)
    assert len(keys) > 100  # eased curve is sampled densely
    pivot = tf.static["Pivot"]
    assert list(pivot.values() if isinstance(pivot, dict) else pivot) == [pytest.approx(0.6), pytest.approx(0.6)]
    assert comp.writes_under_lock == 0 and not comp.locked


def test_fusion_rerun_rebuilds_single_node_and_clear_restores_graph():
    raw, it = item(keyframes=False)
    FusionTransformApplier().apply(it, plan(), SRC, DST)
    FusionTransformApplier().apply(it, plan(), SRC, DST)
    comp = raw.comps[0]
    assert len(raw.comps) == 1 and [n for n in comp.tools if n.startswith(FUSION_TOOL)] == [FUSION_TOOL]
    assert FusionTransformApplier().clear(it) == 1
    assert comp.FindTool("MediaOut1").connected["Input"] is comp.FindTool("MediaIn1")


def test_auto_prefers_keyframes_then_falls_back_to_fusion():
    _, with_keys = item()
    _, without = item(keyframes=False)
    assert apply_plan(with_keys, plan(), SRC, DST)["backend"] == "keyframes"
    assert apply_plan(without, plan(), SRC, DST)["backend"] == "fusion"


def test_explicit_keyframes_backend_on_old_resolve_is_a_clear_error():
    _, it = item(keyframes=False)
    with pytest.raises(ForgeError, match="Resolve 20"):
        apply_plan(it, plan(), SRC, DST, backend="keyframes")


def test_unknown_backend():
    _, it = item()
    with pytest.raises(ForgeError):
        apply_plan(it, plan(), SRC, DST, backend="magic")
