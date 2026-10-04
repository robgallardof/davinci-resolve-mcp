"""Modern caption cues survive every transport, import and frame rounding boundary."""

from pathlib import Path

import pytest
from PIL import Image, ImageChops

from fakes import TIMELINE_START
from resolve_forge.services import overlay_service, text_preview_service


@pytest.fixture(autouse=True)
def output(monkeypatch, tmp_path):
    monkeypatch.setattr(overlay_service, "OVERLAY_ROOT", tmp_path / "overlays")
    monkeypatch.setattr(text_preview_service, "DEFAULT_OUTPUT", tmp_path)


def test_manual_designed_captions_have_real_motion_and_word_sync(forge):
    words = [dict(text="Hola", start=0.2, end=0.5), dict(text="México", start=0.6, end=1.0)]
    master = forge.project.current
    result = forge("add_captions", style="creator", words=words, accent="#C7F464")
    assert result["ok"] and result["animation"] == "pop" and result["model"] == "provided"
    assert forge.project.current is not master and len(master.tracks) == 2
    item = forge.project.current.tracks[result["track"] - 1][0]
    assert item.start == TIMELINE_START + 6
    sequence = sorted(Path(item.mpi.path).glob("*.png"))
    # Motion at entry and color switching to the next spoken word are encoded in imported pixels.
    with Image.open(sequence[0]) as first, Image.open(sequence[6]) as hold, Image.open(sequence[15]) as next_word:
        assert ImageChops.difference(first, hold).getbbox() is not None
        assert ImageChops.difference(hold, next_word).getbbox() is not None
    assert "Hola México" in Path(result["srt_file"]).read_text(encoding="utf-8")


def test_short_words_never_overlap_after_sequence_import(forge):
    result = forge("add_captions", style="impact", max_words=1, animation="none",
                   words=[dict(text="Sí", start=0, end=0.03), dict(text="vamos", start=0.04, end=0.1)])
    assert result["ok"]
    items = forge.project.current.tracks[result["track"] - 1]
    assert items[0].duration == 1
    assert items[0].start + items[0].duration <= items[1].start


def test_reduced_motion_and_invalid_options_have_no_side_effects(forge):
    master = forge.project.current
    result = forge("add_captions", style="creator", animation="spin", words=[dict(text="x", start=0, end=1)])
    assert result["code"] == "INVALID_ARGUMENT"
    assert forge.project.current is master and len(master.tracks) == 2
    result = forge("add_text_overlay", text="Una idea", start_s=0, duration_s=1, style="studio", reduced_motion=True)
    assert result["ok"] and result["animation"] == "none"
    sequence = sorted(Path(forge.project.current.tracks[result["track"] - 1][0].mpi.path).glob("*.png"))
    assert sequence[0].read_bytes() == sequence[-1].read_bytes()


def test_catalog_and_preview_work_without_changing_the_timeline(forge):
    master = forge.project.current
    result = forge("list_text_styles")
    assert {style["name"] for style in result["styles"]} == {"creator", "studio", "editorial", "impact"}
    result = forge("preview_text_style", text="Tu próxima idea", width=540, height=960)
    assert result["ok"] and Path(result["poster"]).exists()
    assert forge.project.current is master


def test_karaoke_encodes_word_progress_and_accessible_fallback(forge):
    words = [dict(text="Muy", start=0, end=1), dict(text="bien", start=1.3, end=2)]
    result = forge("add_captions", style="creator", animation="karaoke", words=words)
    assert result["ok"] and result["animation"] == "karaoke"
    sequence = sorted(next(Path(result["files"]).glob("cap*")).glob("*.png"))
    with Image.open(sequence[3]) as early, Image.open(sequence[24]) as late:
        assert ImageChops.difference(early.convert("RGB"), late.convert("RGB")).getbbox() is not None
        assert early.getchannel("A").getbbox() == late.getchannel("A").getbbox()
    assert sequence[32].read_bytes() == sequence[36].read_bytes()  # silent gap
    assert "Muy bien" in Path(result["srt_file"]).read_text(encoding="utf-8")
    preview = forge("preview_text_style", text="Muy bien", animation="karaoke", width=540, height=960)
    assert preview["ok"] and preview["animation"] == "karaoke"
    reduced = forge("add_captions", style="creator", animation="karaoke", words=words, reduced_motion=True)
    assert reduced["ok"] and reduced["animation"] == "none"
