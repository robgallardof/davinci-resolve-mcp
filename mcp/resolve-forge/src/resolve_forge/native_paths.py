"""Where DaVinci Resolve lives on Windows, macOS and Linux; environment overrides win on every OS."""
import os
import sys
from pathlib import Path

_BMD = "Blackmagic Design/DaVinci Resolve"


def get_resolve_paths():
    if sys.platform == "win32":
        api = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / _BMD / "Support/Developer/Scripting"
        library = Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / _BMD / "fusionscript.dll"
    elif sys.platform == "darwin":
        api = Path("/Library/Application Support") / _BMD / "Developer/Scripting"
        library = Path("/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so")
    else:
        api = Path("/opt/resolve/Developer/Scripting")
        library = Path("/opt/resolve/libs/Fusion/fusionscript.so")
    return {"api_path": os.environ.get("RESOLVE_SCRIPT_API", str(api)),
            "lib_path": os.environ.get("RESOLVE_SCRIPT_LIB", str(library))}


def script_dirs():
    """Resolve's Workspace > Scripts > Utility folders: (per-user, shared for all users)."""
    if sys.platform == "win32":
        user = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / _BMD / "Support/Fusion/Scripts/Utility"
        shared = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / _BMD / "Fusion/Scripts/Utility"
    elif sys.platform == "darwin":
        user = Path.home() / "Library/Application Support" / _BMD / "Fusion/Scripts/Utility"
        shared = Path("/Library/Application Support") / _BMD / "Fusion/Scripts/Utility"
    else:
        user = Path.home() / ".local/share/DaVinciResolve/Fusion/Scripts/Utility"
        shared = Path("/opt/resolve/Fusion/Scripts/Utility")
    return user, shared


def process_name():
    """Executable name of the Resolve process (Resolve.exe; Resolve inside the .app; /opt/resolve/bin/resolve)."""
    return {"win32": "Resolve.exe", "darwin": "Resolve"}.get(sys.platform, "resolve")
