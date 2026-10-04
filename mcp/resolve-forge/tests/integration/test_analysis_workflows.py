import math
import struct
import wave
import pytest

from resolve_forge.gateway import Session
from resolve_forge.services import analysis_service, audio_service


def wav(path, seconds=3):
    rate = 16000
    with wave.open(str(path), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(rate)
        file.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(2 * math.pi * 440 * index / rate)))
                               for index in range(seconds * rate)))


def test_audio_analysis_decodes_source_without_resolve(tmp_path):
    pytest.importorskip("av")
    path = tmp_path / "tone.wav"
    wav(path)
    result = analysis_service.audio(Session([]), str(path))
    assert result["duration_s"] == 3
    assert result["keep_ranges"] == [[0, 3]] and result["silences"] == []
    assert result["time_basis"] == "source seconds"


def test_two_pass_normalisation_measures_the_actual_output(tmp_path):
    path, output = tmp_path / "original.wav", tmp_path / "normalised.wav"
    wav(path)
    original = path.read_bytes()
    result = audio_service.normalise(Session([]), str(path), str(output), -14, -1, False)
    assert result["applied"]
    assert abs(result["measured_output"]["input_i"] + 14) <= 1
    assert result["measured_output"]["input_tp"] <= -.8
    assert path.read_bytes() == original


def test_scene_boundaries_are_measured_in_source_time(tmp_path):
    cv2, np = pytest.importorskip("cv2"), pytest.importorskip("numpy")
    path = tmp_path / "scenes.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 20, (160, 90))
    if not writer.isOpened():
        pytest.skip("MJPG encoder is absent")
    for color in ((0, 0, 255), (255, 0, 0)):
        for _ in range(20):
            writer.write(np.full((90, 160, 3), color, np.uint8))
    writer.release()
    result = analysis_service.scenes(Session([]), str(path), minimum_gap_s=.1)
    assert result["boundaries_s"] == pytest.approx([1])
    assert result["scenes"] == [[0, 1], [1, 2]]


def test_highlights_of_a_file_need_no_resolve(tmp_path):
    cv2 = pytest.importorskip("cv2")
    import numpy as np
    from resolve_forge.services import highlight_service
    path = tmp_path / "clip.mp4"
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 64))
    for i in range(60):  # 6 s: still, then motion in the middle
        frame = np.zeros((64, 64, 3), np.uint8)
        if 20 <= i < 40:
            frame[:, (i * 3) % 64:] = 255
        out.write(frame)
    out.release()
    result = highlight_service.find(Session([]), str(path), top=2, window_s=2)
    assert result["source"] == str(path.resolve()) and result["highlights"]
    assert 1 <= result["highlights"][0]["start_s"] <= 4
