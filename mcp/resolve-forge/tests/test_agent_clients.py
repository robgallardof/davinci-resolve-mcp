"""Real installer subprocesses in disposable workspaces; no user config writes."""
import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "scripts/install-mcp.py").is_file())

@pytest.mark.parametrize("client", ["opencode", "deepseek"])
def test_agent_install_remove_and_dry_run(tmp_path, client):
    root = tmp_path / "workspace with spaces"
    (root / "config").mkdir(parents=True)
    spec = {"command": sys.executable, "args": [(root / "mcp/server.py").as_posix()], "env": {"TEST_FLAG": "yes"}}
    (root / "config/mcp.servers.json").write_text(json.dumps({"servers": {"test-server": spec}}))
    path = root / ("opencode.json" if client == "opencode" else ".dsh/mcp.cordis.yml")
    path.parent.mkdir(parents=True, exist_ok=True)
    original = {"model": "deepseek/example", "mcp": {"other": {"type": "remote", "url": "http://localhost:1234/mcp"}}} if client == "opencode" else [{"id": "other", "name": "example"}]
    before = json.dumps(original)
    path.write_text(before)
    command = [sys.executable, str(ROOT / "scripts/install-mcp.py"), "--clients", client, "--workspace", str(root)]
    subprocess.run([*command, "--dry-run"], check=True, capture_output=True)
    assert path.read_text() == before
    subprocess.run(command, check=True, capture_output=True)
    installed = path.read_text()
    data = json.loads(installed)
    if client == "opencode":
        assert data["model"] == original["model"]
        entry = data["mcp"]["test-server"]
        assert entry["command"] == [sys.executable, *spec["args"]]
        assert entry["environment"]["TEST_FLAG"] == "yes"
        assert data["mcp"]["other"] == original["mcp"]["other"]
    else:
        assert data[0] == original[0]
        assert data[1]["config"]["command"] == sys.executable
        assert data[1]["config"]["transport"] == "stdio"
    subprocess.run(command, check=True, capture_output=True)
    assert path.read_text() == installed
    assert path.with_name(path.name + ".bak").read_text() == before
    subprocess.run([*command, "--remove"], check=True, capture_output=True)
    assert json.loads(path.read_text()) == original
    path.write_text("invalid config")
    result = subprocess.run(command, capture_output=True)
    assert result.returncode != 0
    assert path.read_text() == "invalid config"

    if client == "opencode":
        version_two = '{"mcp":{"servers":{}}}'
        path.write_text(version_two)
        assert subprocess.run(command, capture_output=True).returncode != 0
        assert path.read_text() == version_two
        path.with_suffix(".jsonc").write_text("// user comments\n{}")
        path.write_text(before)
        assert subprocess.run(command, capture_output=True).returncode != 0
        assert path.read_text() == before
