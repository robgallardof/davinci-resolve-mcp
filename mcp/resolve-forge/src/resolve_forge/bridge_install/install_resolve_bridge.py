"""Install Forge-owned bridge modules. Preserve configuration and authentication."""
import argparse
import json
import os
import secrets
import shutil
import sys
from pathlib import Path

from resolve_forge.bridge.client import config_path
from resolve_forge.bridge.resolve_bridge import load_config


def script_targets():
    if sys.platform == "win32":
        targets = [Path(os.environ["APPDATA"]) / "Blackmagic Design/DaVinci Resolve/Support/Fusion/Scripts/Utility"]
        shared = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
        if shared.exists():
            targets.append(shared)
        return targets
    if sys.platform == "darwin":
        return [Path.home() / "Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"]
    return [Path.home() / ".local/share/DaVinciResolve/Fusion/Scripts/Utility"]


def install(targets=None, path=None):
    path = Path(path or config_path())
    if path.exists():
        config = load_config(path)
    else:
        config = {"host": "127.0.0.1", "port": 49632, "token": secrets.token_urlsafe(48),
                  "allowed_media_roots": [str(Path.home())], "allowed_output_roots": [str(Path.home() / "Movies")],
                  "auth_clock_skew_seconds": 60}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        os.chmod(path, 0o600)
    source = Path(__file__).resolve().parent.parent / "bridge"
    template = (Path(__file__).parent / "launcher.py.tmpl").read_text(encoding="utf-8")
    installed, skipped = [], []
    for target in targets if targets is not None else script_targets():
        target = Path(target)
        try:
            target.mkdir(parents=True, exist_ok=True)
            runtime = target.parents[1] / ".davinci_mcp_runtime"
            runtime.mkdir(parents=True, exist_ok=True)
            for filename in ("resolve_bridge.py", "resolve_bridge_ops.py"):
                shutil.copy2(source / filename, runtime / filename)
            (runtime / "bridge.json").write_text(json.dumps(config), encoding="utf-8")
            os.chmod(runtime / "bridge.json", 0o600)
            launcher = template.replace("@@RUNTIME_LITERAL@@", repr(str(runtime)))
            (target / "resolve_bridge.py").write_text(launcher, encoding="utf-8")
            installed.append(str(target))
        except OSError as exc:
            skipped.append({"target": str(target), "error": str(exc)})
    if not installed:
        raise OSError("No writable Resolve Scripts directory: " + str(skipped))
    return {"implementation": "resolve-forge", "installed": installed, "skipped": skipped,
            "config_path": str(path), "token_preserved": True,
            "next": "Run Workspace > Scripts > resolve_bridge after restarting Resolve, or reload the existing bridge."}


def main():
    parser = argparse.ArgumentParser(description="Install Forge's own Free-edition bridge.")
    parser.add_argument("--target", action="append", help="Explicit Scripts/Utility directory (repeatable).")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(install(args.target), indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
