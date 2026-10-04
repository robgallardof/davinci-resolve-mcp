from pathlib import Path
import wave

import pytest

from resolve_forge.domain.transcript import Word
from resolve_forge.services import sfx_service, transcript_service


def write_wav(path, samples, rate=16000):
    import numpy as np
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())


def click_track(path, bpm=120, seconds=16, rate=16000):
    np = pytest.importorskip("numpy")
    samples = np.zeros(rate * seconds, dtype=np.float32)
    click = np.random.default_rng(7).normal(size=1600) * np.exp(-np.arange(1600) / 180) * .4
    for at in np.arange(0, seconds - .2, 60 / bpm):
        index = round(at * rate)
        samples[index:index + len(click)] += click
    write_wav(path, samples, rate)


class FakeTranscriber:
    name = "fake"

    def transcribe(self, path, language=None):
        return [Word("Mi", 0, .3), Word("perro", .3, .8), Word("aprendió", .8, 1.4), Word("impuestos.", 1.4, 2.0),
                Word("Me", 3.2, 3.4), Word("debe.", 3.4, 3.9)], "es"


def test_beat_cuts_from_real_audio_feed_assemble_montage(forge, tmp_path):
    pytest.importorskip("av")
    music = tmp_path / "song.wav"
    click_track(music)
    shots = [dict(source=str(tmp_path / f"{name}.mp4"), start_s=0, end_s=6) for name in ("wide", "close")]
    for shot in shots:
        open(shot["source"], "wb").write(b"fake")
    plan = forge("plan_beat_cuts", music_source=str(music), shots=shots, duration_s=8, beats_per_cut=4)
    assert plan["ok"], plan
    assert plan["tempo_bpm"] == pytest.approx(120, rel=.05)
    assert plan["cuts"] == 4 and all(abs((s["end_s"] - s["start_s"]) - 2) < .1 for s in plan["shots"])
    assert [s["source"] for s in plan["shots"]] == [shots[0]["source"], shots[1]["source"]] * 2
    preview = forge("assemble_montage", shots=[{k: s[k] for k in ("source", "start_s", "end_s")} for s in plan["shots"]],
                    name="Beat cut", music_source=str(music), music_start_s=plan["music_start_s"])
    assert preview["ok"] and preview["duration_s"] == pytest.approx(plan["duration_s"], abs=.01)


def test_beat_cuts_accept_a_confirmed_grid_and_reject_short_footage(forge, tmp_path):
    beats = [i * .5 for i in range(32)]
    shots = [dict(source="a.mp4", start_s=0, end_s=1)]
    fast = forge("plan_beat_cuts", music_source="unused.wav", shots=shots, duration_s=4, beats_per_cut=2, beats_s=beats)
    assert fast["ok"] and fast["cuts"] == 4 and "tempo_bpm" not in fast
    slow = forge("plan_beat_cuts", music_source="unused.wav", shots=shots, duration_s=4, beats_per_cut=8, beats_s=beats)
    assert slow["code"] == "INVALID_ARGUMENT" and "long enough" in slow["error"]


def test_story_moments_tool_reports_candidates_in_source_seconds(forge, tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    pytest.importorskip("av")
    monkeypatch.setattr(transcript_service, "_DEFAULT", FakeTranscriber())
    monkeypatch.setattr(transcript_service, "require_speech_stack", lambda: None)
    rate = 16000
    t = np.arange(rate * 6) / rate
    voice = .3 * np.sin(2 * np.pi * 220 * t)
    mask = np.zeros_like(t)
    for a, b in [(0, 2.0), (3.2, 3.9), (4.0, 5.2)]:  # speech, punchline, then laughter
        mask[(t >= a) & (t < b)] = 1
    source = tmp_path / "standup.wav"
    write_wav(source, voice * mask, rate)
    result = forge("find_story_moments", source=str(source), content_type="comedy")
    assert result["ok"], result
    kinds = {m["kind"]: m for m in result["candidates"]}
    assert kinds["punchline"]["time_s"] == 3.2 and kinds["reaction"]["text"] == "Me debe."
    assert result["time_basis"] == "source seconds" and result["language"] == "es"
    plan = forge("plan_edit", brief="stand-up corto", content_type="comedy", platform="tiktok", duration_s=6,
                 moments=[{"time_s": m["time_s"], "kind": m["kind"], "reason": "revisado: " + m["evidence"]}
                          for m in result["candidates"]])
    assert plan["ok"] and "find_story_moments" in plan["tools"]


def test_align_text_returns_caption_ready_words_in_timeline_seconds(forge, tmp_path, monkeypatch):
    monkeypatch.setattr(transcript_service, "_DEFAULT", FakeTranscriber())
    monkeypatch.setattr(transcript_service, "require_speech_stack", lambda: None)
    source = tmp_path / "voz.wav"
    source.write_bytes(b"fake")
    result = forge("align_text", source=str(source), text="Mi perro aprendió impuestos. Me debe.", timeline_offset_s=-1)
    assert result["ok"] and result["coverage"] == 1
    # "Mi" and "perro" end before timeline zero and are dropped; the word straddling zero is clipped.
    assert [w["text"] for w in result["words"]][:2] == ["aprendió", "impuestos."]
    assert result["words"][0] == {"text": "aprendió", "start": 0, "end": .4}
    assert result["words"][-1] == {"text": "debe.", "start": 2.4, "end": 2.9}


def test_sound_effects_preview_then_place_on_new_tracks_of_a_copy(forge, tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    monkeypatch.setattr(sfx_service, "DEFAULT_OUTPUT", tmp_path / "out")
    whoosh = tmp_path / "whoosh.wav"
    import numpy as np
    write_wav(whoosh, np.sin(np.linspace(0, 2000, 16000)).astype(np.float32) * .5)
    cues = [dict(time_s=1, source=str(whoosh), reason="cambio de sección"),
            dict(time_s=1.2, source=str(whoosh), reason="remate confirmado", gain_db=0)]
    master = forge.project.current
    preview = forge("place_sound_effects", cues=cues)
    assert preview["ok"] and preview["dry_run"] and preview["warnings"]
    assert forge.project.current is master
    result = forge("place_sound_effects", cues=cues, dry_run=False)
    assert result["ok"], result
    copy = forge.project.current
    assert copy is not master and result["placed"] == 2 and len(result["tracks"]) == 2  # overlap -> two tracks
    assert all(len(track) == 1 for track in copy.audio_tracks[-2:])
    gained = [p for p in Path(result["files"]).glob("*.wav")]
    assert len(gained) == 1 and whoosh.is_file()  # only the -8 dB cue needed a new file; original untouched
    pytest.importorskip("av")
    from resolve_forge.analysis.media import load_audio
    rms = [float(np.sqrt(np.mean(load_audio(str(path)) ** 2))) for path in (whoosh, gained[0])]
    assert rms[1] / rms[0] == pytest.approx(10 ** (-8 / 20), rel=.05)
    assert forge("place_sound_effects", cues=[dict(time_s=1, source=str(whoosh))])["code"] == "INVALID_ARGUMENT"


def test_music_bed_ducks_under_voice_on_a_new_track_of_a_copy(forge, tmp_path, monkeypatch):
    pytest.importorskip("av")
    import numpy as np
    from resolve_forge.services import music_bed_service
    from resolve_forge.analysis.media import load_audio
    monkeypatch.setattr(music_bed_service, "DEFAULT_OUTPUT", tmp_path / "out")
    fps = forge("list_clips")["fps"]
    timeline = forge.project.current
    duration = (timeline.GetEndFrame() - timeline.GetStartFrame()) / fps
    rate = 48000
    t = np.arange(int(rate * (duration + 2))) / rate
    music = tmp_path / "bed.wav"
    with wave.open(str(music), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(rate)
        stereo = np.stack([np.sin(2 * np.pi * 330 * t), np.sin(2 * np.pi * 440 * t)], axis=1) * .5
        out.writeframes((stereo * 32767).astype("<i2").tobytes())
    words = [{"text": "hola", "start": 2.0, "end": 2.5}, {"text": "mundo.", "start": 2.6, "end": 3.0}]
    preview = forge("add_music_bed", music_source=str(music), words=words)
    assert preview["ok"] and preview["speech_regions"] == [[2.0, 3.0]] and forge.project.current is timeline
    result = forge("add_music_bed", music_source=str(music), words=words, dry_run=False)
    assert result["ok"], result
    assert forge.project.current is not timeline and len(forge.project.current.audio_tracks[result["track"] - 1]) == 1
    bed = load_audio(result["file"])
    def rms(a, b):
        return float(np.sqrt(np.mean(bed[int(a * 16000):int(b * 16000)] ** 2)))
    assert 20 * np.log10(rms(2.2, 2.9) / rms(5, 6)) == pytest.approx(-10, abs=1)  # -20 under voice vs -10 between
    too_long = forge("add_music_bed", music_source=str(music), music_start_s=duration, words=words, dry_run=False)
    assert too_long["code"] == "INVALID_ARGUMENT" and "no looping" in too_long["error"]


def test_vocal_focus_keeps_the_centre_voice_band_and_drops_side_content(tmp_path):
    pytest.importorskip("av")
    import numpy as np
    from resolve_forge.analysis.media import load_audio
    rate = 48000
    t = np.arange(rate * 2) / rate
    voice = np.sin(2 * np.pi * 800 * t) * .3            # centred, in the voice band
    side = np.sin(2 * np.pi * 1200 * t) * .3            # opposite polarity L/R: cancels in the centre
    mix = tmp_path / "mix.wav"
    with wave.open(str(mix), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(rate)
        stereo = np.stack([voice + side, voice - side], axis=1)
        out.writeframes((stereo * 32767).astype("<i2").tobytes())
    focused = load_audio(transcript_service.vocal_focus(str(mix)))
    spectrum = np.abs(np.fft.rfft(focused[4000:20000]))
    freqs = np.fft.rfftfreq(16000, 1 / 16000)
    assert freqs[np.argmax(spectrum)] == pytest.approx(800, abs=20)
    assert spectrum[np.argmin(np.abs(freqs - 1200))] < spectrum.max() * .05
