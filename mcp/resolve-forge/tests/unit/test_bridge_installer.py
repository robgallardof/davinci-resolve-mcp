"""Packaged installation must preserve credentials and include only Forge runtime."""
import json
import os
import subprocess
import sys
from resolve_forge.bridge_install import install_resolve_bridge as installer


def test_legacy_console_help():
    env = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
    result = subprocess.run([sys.executable, "-m", "resolve_forge.bridge_install.install_resolve_bridge", "--help"],
                            capture_output=True, env=env, timeout=30)
    assert result.returncode == 0 and b"--target" in result.stdout


def test_installer_preserves_credentials_and_deploys_owned_modules(tmp_path):
    config = tmp_path / "bridge.json"
    token = "token-" * 16
    config.write_text(json.dumps({"host": "127.0.0.1", "port": 49632, "token": token,
        "allowed_media_roots": [str(tmp_path)], "allowed_output_roots": [str(tmp_path / "Movies")]}))
    target = tmp_path / "Fusion/Scripts/Utility"
    result = installer.install([target], config)
    assert json.loads(config.read_text())["token"] == token
    runtime = target.parents[1] / ".davinci_mcp_runtime"
    for name in ("resolve_bridge.py", "resolve_bridge_ops.py"):
        text = (runtime / name).read_text()
        compile(text, name, "exec")
        assert "resolve_forge.api" not in text
    launcher = (target / "resolve_bridge.py").read_text()
    assert "@@RUNTIME_LITERAL@@" not in launcher
    compile(launcher, "launcher", "exec")
    assert token not in json.dumps(result)
