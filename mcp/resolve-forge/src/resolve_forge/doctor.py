"""`resolve-forge-doctor`: check every link of the chain and say exactly what to do next.

Works the same for Free and Studio; it only reads (never edits a project).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from .analysis import faces
from .gateway import WIN_API, ResolveUnavailable, Session, call, resolve_process_running

APPDATA_SCRIPTS = Path(os.environ.get("APPDATA", "")) / "Blackmagic Design/DaVinci Resolve/Support/Fusion/Scripts/Utility"
PROGRAMDATA_SCRIPTS = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    fix: str = ""


def edition(resolve) -> str:
    name = str(call(resolve, "GetProductName", default="") or "")
    return "Studio" if "studio" in name.lower() else "Free"


def run() -> list[Check]:
    checks = [
        Check("Python", sys.version_info[:2] <= (3, 13), sys.version.split()[0],
              "Use Python 3.10–3.13 (uv sync --python 3.12)."),
        Check("Resolve scripting API", Path(WIN_API).is_dir() or sys.platform != "win32", WIN_API,
              "Install DaVinci Resolve 20+ (Free or Studio)."),
        Check("Bridge installed in Resolve (Free)",
              any((d / "resolve_bridge.py").exists() for d in (APPDATA_SCRIPTS, PROGRAMDATA_SCRIPTS)),
              "Workspace > Scripts > resolve_bridge",
              "uv run resolve-forge-install-bridge, then restart Resolve."),
        Check("Face detection (optional)", faces.available(), "opencv" if faces.available() else "no opencv",
              "uv sync --extra vision"),
    ]
    running = resolve_process_running()
    checks.append(Check("Resolve running", running, "Resolve.exe" if running else "not running",
                        "Open DaVinci Resolve and a project."))
    if running:
        session = Session()
        try:
            r = session.resolve()
            project = r.GetProjectManager().GetCurrentProject()
            timeline = project.GetCurrentTimeline() if project else None
            checks.append(Check("Connection", True,
                                f"{edition(r)} {r.GetVersionString()} via {session.transport_name}"))
            checks.append(Check("Project/timeline", timeline is not None,
                                f"{project.GetName() if project else '-'} / {timeline.GetName() if timeline else '-'}",
                                "Open or create a timeline with clips."))
        except ResolveUnavailable:
            checks.append(Check("Connection", False, "Resolve does not respond",
                                "Free: Workspace > Scripts > resolve_bridge (no window opens; it listens until Resolve closes). "
                                "Studio: Preferences > System > General > External scripting using = Local."))
    return checks


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    checks = run()
    for c in checks:
        print(f"[{'OK' if c.ok else '!!'}] {c.name}: {c.detail}")
        if not c.ok and c.fix:
            print(f"      -> {c.fix}")
    required = [c for c in checks if not c.ok and "optional" not in c.name]
    print("\nAll good." if not required else f"\nNext step: {required[0].fix}")
    return 0 if not required else 1


if __name__ == "__main__":
    sys.exit(main())
