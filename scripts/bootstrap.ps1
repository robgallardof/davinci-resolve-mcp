# Install the single Forge MCP, its packaged Free bridge and agent configs.
$ErrorActionPreference = "Stop"
$taskRoot = Split-Path -Parent $PSScriptRoot
uv python install 3.12
if ($LASTEXITCODE -ne 0) { throw "Python installation failed" }
Push-Location (Join-Path $taskRoot "mcp/resolve-forge")
try {
    uv sync --python 3.12 --extra vision --extra speech
    if ($LASTEXITCODE -ne 0) { throw "Forge installation failed" }
    uv run python -m resolve_forge.bridge_install.install_resolve_bridge
    if ($LASTEXITCODE -ne 0) { throw "Bridge installation failed" }
    uv run pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Forge tests failed" }
    uv run python (Join-Path $taskRoot "scripts/sync.py")
    if ($LASTEXITCODE -ne 0) { throw "Config sync failed" }
} finally { Pop-Location }
Write-Host "Done. Free: Workspace > Scripts > resolve_bridge. Then ask your agent for forge_status."
