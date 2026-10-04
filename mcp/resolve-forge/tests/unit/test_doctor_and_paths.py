import sys

import pytest

from resolve_forge import doctor, native_paths
from resolve_forge.gateway import ResolveUnavailable


def test_resolve_paths_follow_the_os_and_honour_env_overrides(monkeypatch):
    monkeypatch.delenv("RESOLVE_SCRIPT_API", raising=False)
    monkeypatch.delenv("RESOLVE_SCRIPT_LIB", raising=False)
    for platform, lib in (("win32", "fusionscript.dll"), ("darwin", "fusionscript.so"), ("linux", "fusionscript.so")):
        monkeypatch.setattr(sys, "platform", platform)
        paths = native_paths.get_resolve_paths()
        assert paths["lib_path"].endswith(lib) and "Scripting" in paths["api_path"]
    monkeypatch.setenv("RESOLVE_SCRIPT_API", "/custom/api")
    monkeypatch.setenv("RESOLVE_SCRIPT_LIB", "/custom/lib.so")
    assert native_paths.get_resolve_paths() == {"api_path": "/custom/api", "lib_path": "/custom/lib.so"}


class _Named:
    def __init__(self, name): self.name = name
    def GetName(self): return self.name


class _Project(_Named):
    def __init__(self, timeline): super().__init__("Demo"); self.timeline = timeline
    def GetCurrentTimeline(self): return self.timeline


class _Resolve:
    def __init__(self, product, timeline): self.product, self.project = product, _Project(timeline)
    def GetProductName(self): return self.product
    def GetVersionString(self): return "21.0.4.5"
    def GetProjectManager(self): return self
    def GetCurrentProject(self): return self.project


def _session(resolve=None):
    class Session:
        transport_name = "bridge"

        def resolve(self):
            if resolve is None:
                raise ResolveUnavailable("down")
            return resolve
    return Session


@pytest.mark.parametrize("product,expected", [("DaVinci Resolve Studio", "Studio"), ("DaVinci Resolve", "Free")])
def test_edition_reads_the_product_name(product, expected):
    assert doctor.edition(_Resolve(product, None)) == expected


def test_doctor_reports_connection_project_and_next_step(monkeypatch, capsys):
    monkeypatch.setattr(doctor, "resolve_process_running", lambda: True)
    monkeypatch.setattr(doctor, "Session", _session(_Resolve("DaVinci Resolve", _Named("Master"))))
    checks = {c.name: c for c in doctor.run()}
    assert checks["Connection"].ok and "Free 21.0.4.5 via bridge" in checks["Connection"].detail
    assert checks["Project/timeline"].ok and checks["Project/timeline"].detail == "Demo / Master"

    monkeypatch.setattr(doctor, "Session", _session(None))
    checks = {c.name: c for c in doctor.run()}
    assert not checks["Connection"].ok and "resolve_bridge" in checks["Connection"].fix
    assert doctor.main() == 1
    out = capsys.readouterr().out
    assert "[!!] Connection" in out and "Next step:" in out


def test_doctor_without_resolve_running_stops_before_connecting(monkeypatch):
    monkeypatch.setattr(doctor, "resolve_process_running", lambda: False)
    monkeypatch.setattr(doctor, "Session", lambda: pytest.fail("must not connect"))
    checks = {c.name: c for c in doctor.run()}
    assert not checks["Resolve running"].ok and "Connection" not in checks


def test_a_busy_resolve_is_reported_as_busy_not_missing():
    from resolve_forge.gateway import ResolveUnavailable, Session

    class Busy:
        name, busy = "bridge", False

        def connect(self):
            self.busy = True
            return None

    with pytest.raises(ResolveUnavailable, match="busy"):
        Session([Busy()]).resolve()


def test_busy_bridge_does_not_launch_native_probe_and_has_actionable_code():
    from resolve_forge.gateway import ResolveBusy, Session
    from resolve_forge.errors import payload

    class Busy:
        name, busy = "bridge", True
        def connect(self): return None

    class Native:
        name = "direct"
        def connect(self): pytest.fail("Do not probe the SDK while the bridge is stalled")

    with pytest.raises(ResolveBusy) as caught:
        Session([Busy(), Native()]).resolve()
    assert payload(caught.value)["code"] == "RESOLVE_BUSY"
    assert payload(TimeoutError("timed out"))["code"] == "RESOLVE_BUSY"
