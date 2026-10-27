"""Opt-in project configuration for OpenCode 1.x and DeepSeek Harness.

JSON is also valid YAML: owned Cordis overlays need no YAML dependency.
"""
from __future__ import annotations
import json
from pathlib import Path


def edit_agent(path: Path, name: str, spec: dict, client: str, remove: bool) -> str:
    """Preserve unrelated entries; refuse malformed or symbolic-link configs."""
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("refusing symbolic-link configuration")
    if client == "opencode" and path.with_suffix(".jsonc").exists():
        raise ValueError("opencode.jsonc exists; merge manually to preserve comments")
    before = path.read_text(encoding="utf-8") if path.exists() else None
    data = json.loads(before) if before is not None else ({} if client == "opencode" else [])
    if client == "opencode":
        if not isinstance(data, dict) or not isinstance(data.get("mcp", {}), dict):
            raise ValueError("OpenCode configuration must contain an MCP object (1.x schema)")
        entries = data.setdefault("mcp", {})
        if "servers" in entries:
            raise ValueError("OpenCode 2.x schema requires a separate adapter")
        if remove:
            if name not in entries:
                return "not installed"
            del entries[name]
        else:
            entries[name] = {"type": "local", "command": [spec["command"], *spec.get("args", [])],
                             "environment": spec.get("env", {}), "enabled": True}
    else:
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise ValueError("owned DeepSeek overlay must be a JSON array")
        identity = "mcp-" + name
        found = any(row.get("id") == identity for row in data)
        if remove and not found:
            return "not installed"
        data = [row for row in data if row.get("id") != identity]
        if not remove:
            data.append({"id": identity, "name": "@deepseek-ai/dsh-mcp-client", "config": {
                "serverName": name, "transport": "stdio", **spec}})
    after = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if before is not None and json.loads(before) == data:
        return "unchanged"
    path.parent.mkdir(parents=True, exist_ok=True)
    if before is not None:
        backup = path.with_name(path.name + ".bak")
        if not backup.exists():
            backup.write_text(before, encoding="utf-8")
    path.write_text(after, encoding="utf-8")
    return "removed" if remove else "installed"
