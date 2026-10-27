"""Install this workspace's own MCP servers for your user in every agent client found on this machine, so they work from
any folder (not only inside this workspace). Skills and roles travel inside the server as MCP resources
(skill://<name>) and prompts (<role>); --with-skills also links them into Claude Code's user folders.

  python scripts/install-mcp.py                 # all detected clients
  python scripts/install-mcp.py --clients claude-code,codex,antigravity
  python scripts/install-mcp.py --dry-run | --remove | --list
  python scripts/install-mcp.py --workspace ../davinci-agents   # any workspace with config/mcp.servers.json

Only the workspace's own servers are installed (those launched from inside it); shared ones such as
@playwright/mcp are left to you so they are never duplicated.

OpenCode and DeepSeek are explicit project-only opt-ins (--clients opencode,deepseek).
They are excluded from the default all-detected install.
Every file it edits is backed up first as <file>.bak. Idempotent.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_clients import edit_agent

ROOT = Path(__file__).resolve().parents[1]
NAME = "resolve-forge"  # current server name; main() sets it per server
HOME = Path.home()
APPDATA = Path(os.environ.get("APPDATA", HOME / "AppData" / "Roaming"))


SERVERS: dict[str, dict] = {}


def own_servers(root: Path) -> dict[str, dict]:
    """Servers from <root>/config/mcp.servers.json whose launch points inside the workspace."""
    raw = (root / "config" / "mcp.servers.json").read_text(encoding="utf-8").replace("{ROOT}", root.as_posix())
    out = {}
    for name, spec in json.loads(raw)["servers"].items():
        if f"{root.as_posix()}/mcp/" in " ".join(spec.get("args", [])):
            env = {"PYTHONIOENCODING": "utf-8", **spec.get("env", {})}
            out[name] = {"command": spec["command"], "args": spec["args"], "env": env}
    return out


def server() -> dict:
    return SERVERS[NAME]


# client -> (config file, style). style: json (mcpServers), vscode (servers + type), toml (codex)
CLIENTS = {
    "opencode": (ROOT / "opencode.json", "opencode"),
    "deepseek": (ROOT / ".dsh" / "mcp.cordis.yml", "deepseek"),
    "claude-desktop": (APPDATA / "Claude" / "claude_desktop_config.json", "json"),
    "codex": (HOME / ".codex" / "config.toml", "toml"),
    "gemini-cli": (HOME / ".gemini" / "settings.json", "json"),
    "antigravity": (HOME / ".gemini" / "antigravity" / "mcp_config.json", "json"),
    "cursor": (HOME / ".cursor" / "mcp.json", "json"),
    "vscode": (APPDATA / "Code" / "User" / "mcp.json", "vscode"),
    "windsurf": (HOME / ".codeium" / "windsurf" / "mcp_config.json", "json"),
}


def detected(client: str) -> bool:
    if client in ("opencode", "deepseek"):
        return shutil.which("opencode" if client == "opencode" else "dsh") is not None
    if client == "claude-code":
        return shutil.which("claude") is not None
    path, _ = CLIENTS[client]
    return path.parent.exists()


def backup(path: Path) -> None:
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))


def edit_json(path: Path, key: str, remove: bool, extra: dict | None = None) -> str:
    data = json.loads(path.read_text(encoding="utf-8") or "{}") if path.exists() else {}
    servers = data.setdefault(key, {})
    if remove:
        if servers.pop(NAME, None) is None:
            return "not installed"
    else:
        servers[NAME] = {**(extra or {}), **server()}
    backup(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return "removed" if remove else "installed"


def toml_value(value) -> str:
    if isinstance(value, dict):
        return "{ " + ", ".join(f'"{k}" = {toml_value(v)}' for k, v in value.items()) + " }"
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(v) for v in value) + "]"
    return json.dumps(value)


def edit_toml(path: Path, remove: bool) -> str:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    section = re.compile(rf"\n?\[mcp_servers\.{re.escape(NAME)}\]\n(?:(?!\[).*\n?)*")
    had = bool(section.search(text))
    text = section.sub("\n", text).rstrip() + "\n"
    if remove and not had:
        return "not installed"
    if not remove:
        text += f"\n[mcp_servers.{NAME}]\n" + "".join(f"{k} = {toml_value(v)}\n" for k, v in server().items())
    backup(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return "removed" if remove else "installed"


def claude_code(remove: bool, dry: bool) -> str:
    base = ["claude", "mcp"]
    cmds = [[*base, "remove", NAME, "--scope", "user"]]
    if not remove:
        cmds.append([*base, "add-json", NAME, json.dumps(server()), "--scope", "user"])
    if dry:
        return " && ".join(" ".join(c[:4]) + " ..." for c in cmds)
    subprocess.run(cmds[0], capture_output=True)  # ignore "not found"
    if remove:
        return "removed"
    r = subprocess.run(cmds[1], capture_output=True, text=True)
    return "installed" if r.returncode == 0 else f"failed: {r.stderr.strip()[:200]}"


def link_claude_skills(remove: bool, root: Path) -> list[str]:
    """Junction/symlink every skill and role into ~/.claude so Claude Code loads them from any folder."""
    out = []
    for kind in ("skills", "agents"):
        if not (root / ".agents" / kind).exists():
            continue
        for src in sorted((root / ".agents" / kind).iterdir()):
            dst = HOME / ".claude" / kind / src.name
            if remove:
                if dst.is_symlink() or (dst.exists() and os.path.realpath(dst) == os.path.realpath(src)):
                    dst.unlink() if dst.is_file() or dst.is_symlink() else os.rmdir(dst)
                    out.append(f"unlinked {dst}")
                continue
            if dst.exists() or dst.is_symlink():
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir() and os.name == "nt":
                subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src)], check=True, capture_output=True)
            elif src.is_dir():
                dst.symlink_to(src, target_is_directory=True)
            else:
                shutil.copy2(src, dst)  # file symlinks need admin on Windows; roles are small
            out.append(f"linked {dst}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clients", help="comma list; default: every detected client")
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--with-skills", action="store_true", help="also link skills/roles into ~/.claude")
    ap.add_argument("--workspace", default=str(ROOT), help="workspace folder (default: this one)")
    a = ap.parse_args()
    global NAME
    root = Path(a.workspace).resolve()
    SERVERS.update(own_servers(root))
    CLIENTS["opencode"] = (root / "opencode.json", "opencode")
    CLIENTS["deepseek"] = (root / ".dsh" / "mcp.cordis.yml", "deepseek")
    names = ["claude-code", *CLIENTS]
    if a.list:
        for n in names:
            print(f"{n:15} {'detected' if detected(n) else '-':9} {CLIENTS[n][0] if n in CLIENTS else 'claude mcp --scope user'}")
        return 0
    chosen = a.clients.split(",") if a.clients else [n for n in names if n not in ("opencode", "deepseek") and detected(n)]
    unknown = [n for n in chosen if n not in names]
    if unknown:
        ap.error("unknown clients: " + ", ".join(unknown))
    for NAME in SERVERS:
        print(f"== {NAME}")
        install_all(chosen, a)
    if a.with_skills and not a.dry_run:
        for line in link_claude_skills(a.remove, root):
            print(line)
    print("Restart each client so it picks up the new servers.")
    return 0


def install_all(chosen: list[str], a) -> None:
    for n in chosen:
        if n == "claude-code":
            result = claude_code(a.remove, a.dry_run)
        elif n not in CLIENTS:
            result = f"unknown client (use {', '.join(['claude-code', *CLIENTS])})"
        else:
            path, style = CLIENTS[n]
            if a.dry_run:
                result = f"would {'remove from' if a.remove else 'write'} {path}"
            elif style in ("opencode", "deepseek"):
                result = edit_agent(path, NAME, server(), style, a.remove)
                if style == "deepseek" and not a.remove:
                    result += f'; start with dsh web --patch "{path}"'
            elif style == "toml":
                result = edit_toml(path, a.remove)
            elif style == "vscode":
                result = edit_json(path, "servers", a.remove, {"type": "stdio"})
            else:
                result = edit_json(path, "mcpServers", a.remove)
        print(f"{n:15} {result}")


if __name__ == "__main__":
    sys.exit(main())
