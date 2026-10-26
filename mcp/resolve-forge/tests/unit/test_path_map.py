"""Container <-> host path translation for Docker runs (FORGE_PATH_MAP, FORGE_BRIDGE_HOST)."""
import pytest

from resolve_forge.bridge.client import Client, Proxy, bridge_host
from resolve_forge.bridge.path_map import PathMap
from resolve_forge.bridge.resolve_bridge import Bridge
from resolve_forge.bridge.resolve_bridge_ops import ResolveOperations, make_dispatch
from fakes import demo_resolve

TOKEN = "forge-test-token-" * 4


def test_parse_and_round_trip_windows_host():
    m = PathMap.parse(r"/media=C:\Users\me\Movies; /out=C:/Users/me/Movies/renders")
    assert m.to_host("/media/a b.mp4") == "C:/Users/me/Movies/a b.mp4"
    assert m.to_host("/out/final.mp4") == "C:/Users/me/Movies/renders/final.mp4"
    assert m.to_container(r"C:\Users\me\Movies\a b.mp4") == "/media/a b.mp4"
    assert m.to_container("c:/users/ME/movies/renders/x.mov") == "/out/x.mov"  # longest prefix, case-insensitive


def test_only_whole_path_segments_and_nested_values():
    m = PathMap.parse("/media=/home/me/Videos")
    assert m.to_host("/mediafiles/x") == "/mediafiles/x"
    assert m.to_host("/media") == "/home/me/Videos"
    assert m.to_container("/home/me/VIDEOS/x") == "/home/me/VIDEOS/x"  # POSIX hosts stay case-sensitive
    value = {"args": [["/media/a.mp4", {"FilePath": "/media/b.mp4"}], "Clip"], "n": 3, "target": "resolve"}
    assert m.to_host(value) == {"args": [["/home/me/Videos/a.mp4", {"FilePath": "/home/me/Videos/b.mp4"}], "Clip"],
                                "n": 3, "target": "resolve"}


def test_empty_map_is_identity_and_bad_specs_fail():
    m = PathMap.parse(None)
    assert not m and m.to_host({"a": "/media/x"}) == {"a": "/media/x"}
    for bad in ("media=C:/x", "/media", "/media="):
        with pytest.raises(ValueError):
            PathMap.parse(bad)


def test_root_mounts_keep_exactly_one_separator():
    container_root = PathMap.parse("/=/home/me/Movies")
    assert container_root.to_host("/clip.mp4") == "/home/me/Movies/clip.mp4"
    assert container_root.to_container("/home/me/Movies/clip.mp4") == "/clip.mp4"
    host_root = PathMap.parse("/media=/")
    assert host_root.to_host("/media/clip.mp4") == "/clip.mp4"
    assert host_root.to_container("/clip.mp4") == "/media/clip.mp4"
    drive_root = PathMap.parse("/media=C:/")
    assert drive_root.to_host("/media") == "C:/"
    assert drive_root.to_host("/media/clip.mp4") == "C:/clip.mp4"
    assert drive_root.to_container("c:/clip.mp4") == "/media/clip.mp4"


def test_bridge_host_from_env(monkeypatch):
    monkeypatch.delenv("FORGE_BRIDGE_HOST", raising=False)
    assert bridge_host() == "127.0.0.1"
    monkeypatch.setenv("FORGE_BRIDGE_HOST", "host.docker.internal")
    assert bridge_host() == "host.docker.internal"


def test_real_bridge_sees_host_paths_and_client_sees_container_paths(tmp_path):
    """Wire-level: the bridge's path policy approves the translated host path."""
    media = tmp_path / "Movies"
    media.mkdir()
    (media / "clip.mp4").write_bytes(b"\0")
    resolve = demo_resolve(studio=False)
    surface = ResolveOperations(resolve, [str(media)], [str(media)])
    config = {"host": "127.0.0.1", "port": 0, "token": TOKEN}
    bridge = Bridge(resolve, config, make_dispatch(surface)).start()
    try:
        client = Client({**config, "port": bridge.port}, path_map=PathMap.parse(f"/media={media}"))
        pool = Proxy(client, "resolve").GetProjectManager().GetCurrentProject().GetMediaPool()
        items = pool.ImportMedia(["/media/clip.mp4"])
        assert items, "bridge refused or failed to import the translated path"
        path = items[0].GetClipProperty("File Path")
        assert path in ("", "/media/clip.mp4"), path
    finally:
        bridge.stop()
