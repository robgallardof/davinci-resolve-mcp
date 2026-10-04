"""Resolve SDK locations; environment overrides take precedence on every OS."""
import os
import sys
from pathlib import Path


def get_resolve_paths():
    if sys.platform == "win32":
        api = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting"
        library = Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Blackmagic Design/DaVinci Resolve/fusionscript.dll"
    elif sys.platform == "darwin":
        api = Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting")
        library = Path("/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so")
    else:
        api = Path("/opt/resolve/Developer/Scripting")
        library = Path("/opt/resolve/libs/Fusion/fusionscript.so")
    return {"api_path": os.environ.get("RESOLVE_SCRIPT_API", str(api)),
            "lib_path": os.environ.get("RESOLVE_SCRIPT_LIB", str(library))}
