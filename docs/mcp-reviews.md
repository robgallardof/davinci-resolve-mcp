> Revisión histórica. Las capacidades elegidas se implementaron de forma independiente en Forge. Los patches y 152 archivos de referencia se retiraron; los clones restantes quedan ignorados por Git. Estado actual: [third-party-migration.md](third-party-migration.md).

# Code review and improvements of the public DaVinci Resolve MCPs

> **Resumen (ES):** descargamos los 7 MCPs públicos de DaVinci Resolve, los revisamos a fondo y les arreglamos
> bugs reales, cada uno reproducido antes y verificado después en Windows 11 con Resolve 21.0.4:
> - **3 servidores hacían segfault en Windows** dentro de un venv: apvlv, lordhoell y DWC.
> - DWC **solo funcionaba en macOS**.
> - hiteshK03 transcribía con **tiempos equivocados**.
> - apvlv **ejecutaba código arbitrario** sin protección.
> - kerwilgil **no se podía instalar con uv**.
> - Cuatro proyectos se rompen con **mcp 2.x**: hiteshK03, DWC, lordhoell y apvlv.
> - El instalador del bridge de samuelgursky **crasheaba en consolas cp1252**.
>
> Cada mejora fue un patch con tests nuevos (6/6 aplicaban y pasaban 97 tests). Los patches y `scripts/references.py`
> ya se retiraron; los commits consultados quedan en `config/provenance.json`.

Everything below was found by reading the code, a `ruff` pass for real errors (F821/F841/B9xx) and running each
project on **Windows 11 + DaVinci Resolve 21.0.4 (Free)**. Every fix was reproduced first, verified after, and
covered by a test. The patches are standard `git format-patch` files: reviewable and ready to open as pull requests.

| Repo | License | Findings fixed | Evidence | Tests |
|---|---|---|---|---|
| [samuelgursky/davinci-resolve-mcp](https://github.com/samuelgursky/davinci-resolve-mcp) | MIT | Bridge installer crashed on cp1252 consoles | `--help` exit 1 → 0 | +1 (fails before, passes after) |
| [hiteshK03/davinci-resolve-mcp](https://github.com/hiteshK03/davinci-resolve-mcp) | MIT | Wrong transcription times; PyAV crash; mcp 2.x | 190 s of real audio decoded | +4 (had none) |
| [DigitalWorkflowCompany/resolve-mcp](https://github.com/DigitalWorkflowCompany/resolve-mcp) | MIT | macOS-only paths; venv segfault; misleading errors; mcp 2.x | module "not found at /Library/…" → imports | +4 (had none) |
| [apvlv/davinci-resolve-mcp](https://github.com/apvlv/davinci-resolve-mcp) | MIT | Segfault on start (Windows venv); unrestricted code execution; mcp 2.x | exit 139 → 0 | 1 → 6 |
| [kerwilgil/davinci-resolve-mcp](https://github.com/kerwilgil/davinci-resolve-mcp) | MIT | Not installable with uv; plain `pytest` broken; undefined name | lock fails → 78/78 pass | 78 (theirs) |
| [lordhoell/davinci-resolve-mcp](https://github.com/lordhoell/davinci-resolve-mcp) | MIT | Segfault on connect (Windows venv); comp_lock trap; mcp 2.x | exit 139 → clear error | +4 (had none) |
| [Tooflex/davinci-resolve-mcp](https://github.com/Tooflex/davinci-resolve-mcp) | none | Review only (no license → no redistributed changes) | – | – |

## The Windows virtualenv segfault (apvlv, lordhoell, DWC)

`fusionscript.dll` embeds a Python interpreter. Loaded from inside a virtualenv (uv or pip venvs, which these
READMEs recommend), it **crashes the whole process** (segfault, exit code 139) unless `PYTHONHOME` names the base
interpreter. apvlv connects at import time, so its server never started. Fix, applied before the import and only
inside a venv on Windows:

```python
if sys.platform.startswith("win") and sys.prefix != sys.base_prefix:
    os.environ.setdefault("PYTHONHOME", sys.base_prefix)
```

The Free edition then answers "external scripting refused" (`scriptapp` → `None`) instead of crashing, and the
error messages now say so.

## mcp 2.x breaks four servers

`mcp` 2.0 renamed `mcp.server.fastmcp.FastMCP` (→ `MCPServer`). hiteshK03 (`mcp>=1.0.0`), DWC (`mcp>=1.0.0`),
lordhoell (`mcp[cli]>=1.0`) and apvlv (`mcp>=0.3.0`) all import FastMCP, so a fresh `pip install` today installs
2.x and the server fails with `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`. Each patch pins `<2`.
kerwilgil pins `==1.28.1` and Tooflex ships a lockfile, so neither was affected.

## samuelgursky/davinci-resolve-mcp

The best-maintained project, and the one we run. One issue found:

- `scripts/install_resolve_bridge.py` prints `▸`/`•`. On a cp1252 console (cmd / Windows PowerShell 5.1 default),
  `--help` and the install summary raised `UnicodeEncodeError`. That is exactly the step the README gives Free
  users. `install.py` already had the guard (#150); the patch applies the same `_ensure_glyph_capable_stdio()`.
  The new test runs `--help` with `PYTHONIOENCODING=cp1252`.

## hiteshK03/davinci-resolve-mcp

- **`transcribe_timeline` returned the first clip's source times only.** It transcribed `clips[0]`'s whole file,
  so on any edited timeline the timestamps pointed to the wrong place and every other clip was missing. Now the
  bridge reports `leftOffset`. A new pure module, `transcript_mapping.py`, re-times each clip's words to where the
  clip sits on the timeline: it clamps words cut by the edit and handles mixed frame rates. Each source is
  transcribed once.
- **Every transcription failed with recent PyAV.** faster-whisper's loader calls `av.open(..., metadata_errors=…)`,
  which PyAV removed. The fix decodes audio with PyAV directly (verified on 190 s of real phone audio) and falls
  back to the path.
- mcp pinned `<2`.
- Not changed on purpose: ruff flags 7 mutable defaults (`= {}` / `= []`), but they are only passed to JSON and
  never mutated, so they are not bugs.

## DigitalWorkflowCompany/resolve-mcp

- **macOS only.** The scripting module path and LUT folders were hard-coded to `/Library/...`, so on Windows and
  Linux the server could not import `DaVinciResolveScript` and LUT tools never found anything. New `paths.py`
  covers all three OSes per Blackmagic's README, with env overrides.
- Windows venv segfault guard (see above).
- "DaVinci Resolve is not running" was printed even with Resolve open. The message now lists the real causes
  (not running, scripting disabled, Free edition).
- `_find_lut` tolerated `PermissionError` only; a LUT root that does not exist on this machine now counts as
  "not here".
- mcp pinned `<2`.

## apvlv/davinci-resolve-mcp

- **Segfault on start on Windows.** Reproduced: `import davinci_resolve_mcp.server` → exit 139. After the patch
  the server starts and reports the connection state.
- **`execute_python` / `execute_lua` ran arbitrary code from any prompt** with full access to the machine (files,
  network, other apps). This is a prompt-injection path. They now refuse unless
  `DAVINCI_MCP_ALLOW_CODE_EXECUTION=1` is set, and say why.
- `execute_python` ran the snippet against the server module's own globals, so a snippet could overwrite the
  server itself (`mcp = None`). It now gets an isolated namespace. Tested.
- mcp pinned `<2`.

## kerwilgil/davinci-resolve-mcp

- **Not installable with uv.** The `audio` extra (demucs 4.1.0, numpy<2 on Intel macOS) and the
  `background-removal` extra (rembg 2.0.76, numpy≥2.3) can never share an environment. uv refused to lock, so
  every `uv sync` / `uv run` failed. Declared as `[tool.uv] conflicts`.
- Tests import `src.davinci_mcp`, so only `python -m pytest` worked. Added `pythonpath = ["."]`.
- `ToolSchema` was used in an annotation without being imported (F821).
- Their 78 tests pass with `uv run pytest`.

## lordhoell/davinci-resolve-mcp

- **Segfault on connect on Windows venvs.** Reproduced: exit 139 → now a normal `ConnectionError`. The message
  names the Free edition and the Preferences setting.
- `comp_lock` now documents the trap measured by the samuelgursky project: input values and keyframes written
  while the comp is locked read back correctly but are **ignored at render**, so lock only around structural edits.
- mcp pinned `<2`.

## Tooflex/davinci-resolve-mcp (review only)

No license file, so its code cannot be redistributed modified. Observations for the author: `pyproject` allows
`mcp[cli]>=1.4.1` (the lockfile pins 1.4.1, but `pip install` would pull 2.x and break FastMCP). It has the
nicest idea of the small servers: probing the native module before trusting it.
