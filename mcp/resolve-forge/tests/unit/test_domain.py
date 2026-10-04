import pytest

from resolve_forge.domain import formats, styles
from resolve_forge.domain.easing import Ease, ease
from resolve_forge.domain.framing import Sizing, cover_zoom, frame_subject, rezoom_keeping
from resolve_forge.domain.keyframes import Keyframe, Track
from resolve_forge.domain.motion import min_zoom_for_rotation, punch_cuts, rhythm_cuts, slow_push


@pytest.mark.parametrize("kind", [Ease.LINEAR, Ease.IN, Ease.OUT, Ease.IN_OUT])
def test_ease_endpoints_and_monotonic(kind):
    values = [ease(i / 50, kind) for i in range(51)]
    assert values[0] == pytest.approx(0, abs=1e-6) and values[-1] == pytest.approx(1, abs=1e-6)
    assert all(b >= a - 1e-9 for a, b in zip(values, values[1:]))


def test_ease_in_out_is_slow_at_edges():
    assert ease(0.1, Ease.IN_OUT) < 0.1 and ease(0.9, Ease.IN_OUT) > 0.9


def test_track_rejects_unsorted():
    with pytest.raises(ValueError):
        Track("zoom", (Keyframe(10, 1), Keyframe(5, 1)))


def test_slow_push_samples():
    t = slow_push(100, 1.0, 1.1)
    assert t.sample(0) == 1.0 and t.sample(99) == pytest.approx(1.1)
    assert 1.0 < t.sample(50) < 1.1


def test_punch_cuts_hard_steps():
    t = punch_cuts(300, [90, 180], (1.0, 1.15))
    assert t.sample(89) == 1.0 and t.sample(90) == pytest.approx(1.15)
    assert t.sample(179) == pytest.approx(1.15) and t.sample(180) == 1.0


def test_punch_cuts_ramp_eases_in():
    t = punch_cuts(300, [90], (1.0, 1.2), ramp=6)
    assert t.sample(90) == 1.0 and 1.0 < t.sample(93) < 1.2 and t.sample(96) == pytest.approx(1.2)


def test_expand_holds_has_no_hold_and_keeps_step_shape():
    t = punch_cuts(300, [90], (1.0, 1.15)).expand_holds()
    assert all(k.ease_out is not Ease.HOLD for k in t.keyframes[:-1])
    assert t.sample(89) == pytest.approx(1.0) and t.sample(90) == pytest.approx(1.15)


def test_rhythm_cuts_deterministic_and_in_range():
    a, b = rhythm_cuts(900, 30), rhythm_cuts(900, 30)
    assert a == b and all(0 < c < 900 - 24 for c in a)
    gaps = [y - x for x, y in zip([0] + a, a)]
    assert all(75 <= g <= 105 for g in gaps)


def test_dense_samples_follow_the_curve():
    track = slow_push(100, 1.0, 1.2)
    samples = track.dense(step=2)
    assert samples[0] == (0, 1.0) and samples[-1][0] == 99
    assert all(v == pytest.approx(track.sample(f)) for f, v in samples)
    assert len(samples) > 40  # eased segment is sampled, not left to the host's interpolation


def test_dense_keeps_hard_steps_tight():
    samples = dict(punch_cuts(300, [90], (1.0, 1.15)).dense(step=2))
    assert samples[89] == pytest.approx(1.0) and samples[90] == pytest.approx(1.15)
    assert len(samples) <= 5  # holds need no intermediate samples (keys only)


@pytest.mark.parametrize("name", list(styles.STYLES))
def test_every_style_builds(name):
    plan = styles.build(name, duration=600, fps=30, hits=[200])
    assert plan.tracks and plan.peak_zoom() >= 1.0
    for track in plan.tracks:
        track.sample(300)


def test_style_empty_cuts_means_no_cuts():
    plan = styles.build("tiktok_punch", duration=300, fps=30, cuts=[])
    assert {k.value for k in plan.track("zoom").keyframes} == {1.0}


def test_rotation_safety_zoom():
    assert min_zoom_for_rotation(1080, 1920, 0) == pytest.approx(1.0)
    assert 1.0 < min_zoom_for_rotation(1080, 1920, 0.5) < 1.03


def test_cover_zoom_16x9_into_9x16():
    assert cover_zoom(1920, 1080, 1080, 1920) == pytest.approx((1920 / 1080) / (1080 / 1920))


def test_frame_subject_centers_and_clamps():
    s = frame_subject((1920, 1080), (1080, 1920), (0.7, 0.5))
    disp_w = 1920 * (1080 / 1920) * s.zoom
    assert s.pan == pytest.approx(-0.2 * disp_w) and s.tilt == 0
    edge = frame_subject((1920, 1080), (1080, 1920), (0.99, 0.5))
    assert abs(edge.pan) == pytest.approx((disp_w - 1080) / 2)


def test_rezoom_keeps_subject_on_screen():
    src, dst, subject = (1920, 1080), (1920, 1080), (0.6, 0.4)
    base = Sizing(1.0, 0.0, 0.0)
    z = rezoom_keeping(src, dst, base, 1.2, subject)
    screen = lambda s: (s.pan + (subject[0] - .5) * 1920 * s.zoom, s.tilt + (.5 - subject[1]) * 1080 * s.zoom)  # noqa: E731
    assert screen(z) == pytest.approx(screen(base))


def test_formats_safe_rect():
    rect = formats.get("tiktok").safe.rect(1080, 1920)
    assert rect["y"] > 0 and rect["y"] + rect["height"] < 1920
    with pytest.raises(KeyError):
        formats.get("myspace")
