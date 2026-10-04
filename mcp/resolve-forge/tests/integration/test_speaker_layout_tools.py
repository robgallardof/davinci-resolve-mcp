"""Speaker layouts composed for real from a synthetic two-person video."""
import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")
av = pytest.importorskip("av")


def two_people(path, seconds=6, fps=15):
    """Left person red, right person blue on a 16:9 frame, with an audio track."""
    out = av.open(str(path), "w")
    v = out.add_stream("mpeg4", rate=fps)
    v.width, v.height, v.pix_fmt = 320, 180, "yuv420p"
    a = out.add_stream("aac", rate=16000)
    a.layout = "mono"
    for _ in range(seconds * fps):
        img = np.full((180, 320, 3), 60, np.uint8)
        cv2.rectangle(img, (40, 40), (100, 140), (220, 40, 40), -1)    # person 0 (left), RGB red
        cv2.rectangle(img, (220, 40), (280, 140), (40, 40, 220), -1)   # person 1 (right), RGB blue
        for packet in v.encode(av.VideoFrame.from_ndarray(img, format="rgb24")):
            out.mux(packet)
    tone = (np.sin(np.arange(16000 * seconds) * 2 * np.pi * 220 / 16000) * 8000).astype(np.int16)
    for i in range(0, len(tone), 1024):
        frame = av.AudioFrame.from_ndarray(tone[i:i + 1024].reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate = 16000
        for packet in a.encode(frame):
            out.mux(packet)
    for stream in (v, a):
        for packet in stream.encode(None):
            out.mux(packet)
    out.close()


PEOPLE = [[0.125, 0.22, 0.3125, 0.55], [0.6875, 0.22, 0.875, 0.55]]
ACTIVE = [[t * 0.5, [0]] for t in range(4)] + [[2 + t * 0.5, [0, 1]] for t in range(4)] \
    + [[4 + t * 0.5, [1]] for t in range(4)]


def test_plan_and_compose_single_split_single_in_vertical(forge, tmp_path, monkeypatch):
    from resolve_forge.services import speaker_layout_service
    monkeypatch.setattr(speaker_layout_service, "DEFAULT_OUTPUT", tmp_path / "out")
    path = tmp_path / "podcast.mp4"
    two_people(path)
    plan = forge("plan_speaker_layout", source=str(path), format="tiktok", people=PEOPLE, active=ACTIVE)
    assert plan["ok"], plan
    assert [s["layout"] for s in plan["segments"]] == ["single", "split", "single"]
    built = forge("build_speaker_layout", source=str(path), name="Podcast vertical", format="tiktok",
                  segments=plan["segments"], into_resolve=False, dry_run=False)
    assert built["ok"], built
    cap = cv2.VideoCapture(built["file"])
    assert (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))) == (1080, 1920)

    def frame_at(t):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, f = cap.read()
        assert ok
        return f[:, :, ::-1].astype(int)  # RGB
    single0, split, single1 = frame_at(1.0), frame_at(3.0), frame_at(5.0)
    cap.release()
    assert single0[..., 0].mean() > single0[..., 2].mean()                    # person 0 (red) fills the frame
    assert split[:960, :, 0].mean() > split[:960, :, 2].mean()                # top: red person
    assert split[960:, :, 2].mean() > split[960:, :, 0].mean()                # bottom: blue person
    assert single1[..., 2].mean() > single1[..., 0].mean()                    # person 1 (blue)
    with av.open(built["file"]) as clip:
        assert clip.streams.audio and float(clip.duration / av.time_base) == pytest.approx(6, abs=0.2)
    assert path.is_file()


def test_build_into_resolve_creates_a_new_timeline(forge, tmp_path, monkeypatch):
    from resolve_forge.services import speaker_layout_service
    monkeypatch.setattr(speaker_layout_service, "DEFAULT_OUTPUT", tmp_path / "out")
    path = tmp_path / "podcast.mp4"
    two_people(path, seconds=4)
    plan = forge("plan_speaker_layout", source=str(path), format="youtube_1080", mode="split",
                 people=PEOPLE, active=ACTIVE[:6])
    assert {s["layout"] for s in plan["segments"]} == {"split"}
    master = forge.project.current
    built = forge("build_speaker_layout", source=str(path), name="Podcast split", format="youtube_1080",
                  segments=plan["segments"], dry_run=False)
    assert built["ok"], built
    assert built["timeline"] == "Podcast split" and forge.project.current is not master
