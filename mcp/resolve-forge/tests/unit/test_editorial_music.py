import pytest

from resolve_forge.domain.editorial import RECIPES, plan


@pytest.mark.parametrize("content_type", RECIPES)
def test_brief_uses_actual_story_moments_and_no_automatic_cut(content_type):
    kind = RECIPES[content_type]["moments"][0]
    result = plan("Conservar emoción y claridad", content_type, "reels", 30,
                  [dict(time_s=2, kind=kind, reason="Momento revisado en la fuente")])
    assert result["caption_style"] and result["direction"] and result["avoid"]
    assert result["confirmed_story_moments"][0]["time_s"] == 2
    assert result["automation_boundary"] and result["needs_review"]


def test_comedy_and_music_briefs_protect_meaning():
    assert "punchline" in plan("Un chiste", "comedy", "shorts", 20)["avoid"]
    music = plan("Mi canción", "music", "youtube_1080", 240)
    assert "master song intact" in music["direction"] and "singing" in music["avoid"]
    with pytest.raises(ValueError):
        plan("Chiste", "comedy", "reels", 20, [dict(time_s=3, kind="drop", reason="x")])
    with pytest.raises(ValueError):
        plan("x", "music", "reels", 30, [dict(time_s=30, kind="intro", reason="x")])


def test_spectral_music_grid_tracks_a_known_click_pattern():
    np = pytest.importorskip("numpy")
    from resolve_forge.analysis.music import rhythm
    rate = 16000
    samples = np.zeros(rate * 12, dtype=np.float32)
    rng = np.random.default_rng(20)
    click = rng.normal(size=1600) * np.exp(-np.arange(1600) / 180) * .4
    for seconds in np.arange(.2, 11.8, .5):
        index = round(seconds * rate)
        samples[index:index + len(click)] += click
    result = rhythm(samples)
    assert result["tempo_bpm"] == pytest.approx(120, abs=3)
    assert result["confidence"] >= .5
    assert len(result["onsets_s"]) >= 20
    assert all(abs(a - b) < .05 for a, b in zip(result["onsets_s"], np.arange(.2, 11.8, .5)))
    assert all(0 <= time_s < 12 for time_s in result["beats_s"])
    silence = rhythm(np.zeros(rate * 5))
    assert silence["tempo_bpm"] is None and silence["beats_s"] == []
