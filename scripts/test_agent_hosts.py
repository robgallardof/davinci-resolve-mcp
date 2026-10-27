"""Real OpenCode discovery + DeepSeek MCP tool execution in temporary workspaces.

Prerequisites: Node 24.9+, uv-synced server; install opencode-ai@1.19.4 and
@deepseek-ai/dsh@0.2.1-rc.2 in an isolated npm prefix, then set OPENCODE_BIN
and AGENT_HOST_MODULES. No model inference, credentials, or personal data.
"""
from pathlib import Path
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TEST_TOOL = ('list_styles', {})


def main():
    modules = os.environ.get("AGENT_HOST_MODULES")
    opencode = os.environ.get("OPENCODE_BIN") or shutil.which("opencode")
    if not modules or not opencode:
        raise SystemExit("set AGENT_HOST_MODULES and OPENCODE_BIN; test NOT EXECUTED")
    with tempfile.TemporaryDirectory(prefix="mcp-hosts-") as folder:
        work = Path(folder)
        env = {**os.environ, "HOME": folder, "USERPROFILE": folder, "APPDATA": str(work / "appdata"),
               "LOCALAPPDATA": str(work / "local"), "XDG_CONFIG_HOME": str(work / "config"),
               "XDG_DATA_HOME": str(work / "data"), "XDG_CACHE_HOME": str(work / "cache"),
               "OPENCODE_DISABLE_AUTOUPDATE": "true", "OPENCODE_DISABLE_DEFAULT_PLUGINS": "true"}
        # Only public source paths are retained; all server-owned data roots are disposable.
        module_spec = importlib.util.spec_from_file_location("installer", ROOT / "scripts/install-mcp.py")
        installer = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(installer)
        name, spec = next(iter(installer.own_servers(ROOT).items()))
        spec["command"] = shutil.which(spec["command"]) or spec["command"]
        spec["env"].update({"SOCIAL_FORGE_ROOT": folder, "DECLARA_ROOT": folder})
        installer.edit_agent(work / "opencode.json", name, spec, "opencode", False)
        listed = subprocess.run([opencode, "mcp", "list"], cwd=work, env=env, text=True,
                                encoding="utf-8", errors="replace", capture_output=True, timeout=90)
        plain = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", listed.stdout + listed.stderr)
        assert listed.returncode == 0 and name in plain and "connected" in plain.lower(), plain
        print(f"OpenCode: {name} connected")
        tool, args = TEST_TOOL
        payload = {"config": {"serverName": name, "transport": "stdio", **spec, "cwd": folder}, "tool": tool, "args": args}
        config = work / "probe.json"
        config.write_text(json.dumps(payload), encoding="utf-8")
        subprocess.run(["node", str(ROOT / "scripts/agent_host_probe.mjs"), str(config)], cwd=work,
                       env=env, check=True, timeout=90)


if __name__ == "__main__":
    main()
