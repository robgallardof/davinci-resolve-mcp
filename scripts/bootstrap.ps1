# Rebuild everything that is not versioned: upstream MCP (pinned + our patches) + venv, Resolve bridge,
# forge env, client configs. With -WithReferences also the other studied MCPs, patched and tested.
# Usage:  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\bootstrap.ps1 [-WithReferences]
param([switch]$WithReferences)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$upstream = Join-Path $root "vendor\davinci-resolve-mcp"
$references = Join-Path $root "scripts\references.py"

uv python install 3.12 | Out-Null
$py = (uv python find 3.12 --managed-python).Trim()   # uv's Python: plain `python` may not be on PATH

# Upstream MCP at the pinned commit in config/references.json, with patches/davinci-resolve-mcp applied.
& $py $references fetch davinci-resolve-mcp
if ($LASTEXITCODE -ne 0) { throw "could not fetch or patch the upstream MCP (see message above)" }

Push-Location $upstream
& $py install.py --clients manual --update-policy notify
$env:PYTHONIOENCODING = "utf-8"
& .\venv\Scripts\python.exe scripts\install_resolve_bridge.py
Pop-Location

Push-Location (Join-Path $root "mcp\resolve-forge")
uv sync --python 3.12 --extra vision --extra speech   # speech: local Whisper (captions/transcription on Free)
uv run pytest -q
Pop-Location

if ($WithReferences) {
    & $py $references fetch    # every studied MCP at its pinned commit + our improvements
    & $py $references test     # their tests + the ones we added
}

& $py (Join-Path $root "scripts\sync.py")
Write-Host "`nListo. Abre Resolve (Free: Workspace > Scripts > resolve_bridge) y pide al agente: forge_status"
