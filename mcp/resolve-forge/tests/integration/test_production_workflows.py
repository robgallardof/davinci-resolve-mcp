from pathlib import Path
import wave

import pytest

from resolve_forge.services import music_service


def test_montage_previews_offline_and_builds_a_separate_multi_source_timeline(forge, tmp_path):
    sources = [tmp_path / "wide.mp4", tmp_path / "detail.mp4"]
    for source in sources:
        source.write_bytes(b"fake")
    shots = [dict(source=str(sources[0]), start_s=1, end_s=3), dict(source=str(sources[1]), start_s=5, end_s=8)]
    master = forge.project.current
    result = forge("assemble_montage", shots=shots, name="Music montage", format="reels")
    assert result["ok"] and result["dry_run"] and result["duration_s"] == 5
    assert forge.project.current is master
    result = forge("assemble_montage", shots=shots, name="Music montage", format="reels", dry_run=False)
    assert result["ok"] and result["shots"] == 2 and result["resolution"] == "1080x1920"
    assert forge.project.current is not master
    assert [item.mpi.path for item in forge.project.current.tracks[0]] == [str(source) for source in sources]
    assert forge.project.current.tracks[0][0].start + forge.project.current.tracks[0][0].duration == forge.project.current.tracks[0][1].start
    assert forge("assemble_montage", shots=shots, name="Music montage", dry_run=False)["code"] == "TIMELINE_EXISTS"


def test_montage_validates_source_ranges_before_creating_timeline(forge, tmp_path):
    source = tmp_path / "short.mp4"
    source.write_bytes(b"fake")
    count = len(forge.project.timelines)
    result = forge("assemble_montage", shots=[dict(source=str(source), start_s=1, end_s=500)], name="Bad range", dry_run=False)
    assert result["code"] == "INVALID_ARGUMENT" and len(forge.project.timelines) == count
    for shot in [dict(source="x", start_s=float("nan"), end_s=1), dict(source="x"), dict(source="x", start_s=-1, end_s=1)]:
        assert forge("assemble_montage", shots=[shot], name="bad")["code"] == "INVALID_ARGUMENT"


def test_montage_keeps_master_music_separate_and_continuous(forge, tmp_path):
    sources = [tmp_path / "wide.mp4", tmp_path / "detail.mp4", tmp_path / "master.wav"]
    for source in sources:
        source.write_bytes(b"fake")
    shots = [dict(source=str(source), start_s=1, end_s=3) for source in sources[:2]]
    result = forge("assemble_montage", shots=shots, name="Song", music_source=str(sources[2]),
                   music_start_s=2, dry_run=False)
    assert result["ok"], result
    timeline = forge.project.current
    assert len(timeline.tracks[0]) == 2 and len(timeline.audio_tracks[0]) == 1
    music = timeline.audio_tracks[0][0]
    assert music.duration == sum(item.duration for item in timeline.tracks[0])
    assert music.left == 60 and music.mpi.path == str(sources[2])


def test_visualizer_render_retains_stereo_and_real_duration(tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    av = pytest.importorskip("av")
    monkeypatch.setattr(music_service, "DEFAULT_OUTPUT", tmp_path)
    rate = 48000
    time = np.arange(rate * 2) / rate
    stereo = np.stack([np.sin(2 * np.pi * 440 * time), np.sin(2 * np.pi * 880 * time)], axis=1) * .25
    source = tmp_path / "stereo.wav"
    with wave.open(str(source), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes((stereo * 32767).astype("<i2").tobytes())
    result = music_service.visualizer(None, str(source), "Una canción", "Forge", width=320, height=568,
                                      fps=12, start_s=.25, duration_s=1.0)
    assert result["audio_channels"] == 2 and result["duration_s"] == 1
    assert Path(result["poster"]).is_file()
    with av.open(result["video_file"]) as video:
        assert video.streams.video[0].width == 320
        assert float(video.duration / av.time_base) == pytest.approx(1, abs=.08)
        audio = next(video.decode(audio=0)).to_ndarray()
        assert audio.shape[0] == 2
        peaks = [np.fft.rfftfreq(audio.shape[1], 1 / rate)[np.argmax(np.abs(np.fft.rfft(channel)))] for channel in audio]
        assert peaks[0] == pytest.approx(440, abs=60)
        assert peaks[1] == pytest.approx(880, abs=60)
    assert source.is_file()
