# Rebuild everything that is not versioned: upstream MCP + venv, Resolve bridge, forge env, client configs.
# Usage:  pwsh scripts/bootstrap.ps1 [-WithReferences]
param([switch]$WithReferences)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$vendor = Join-Path $root "vendor"
$upstream = Join-Path $vendor "davinci-resolve-mcp"
New-Item -ItemType Directory -Force $vendor | Out-Null

if (-not (Test-Path $upstream)) {
    git clone --depth 1 https://github.com/samuelgursky/davinci-resolve-mcp.git $upstream
}

uv python install 3.12 | Out-Null
$py = (uv python find 3.12 --managed-python).Trim()
Push-Location $upstream
& $py install.py --clients manual --update-policy notify
$env:PYTHONIOENCODING = "utf-8"
& .\venv\Scripts\python.exe scripts\install_resolve_bridge.py
Pop-Location

Push-Location (Join-Path $root "mcp\resolve-forge")
uv sync --python 3.12 --extra vision
uv run pytest -q
Pop-Location

if ($WithReferences) {
    $refs = @{ lordhoell = "lordhoell/davinci-resolve-mcp"; hiteshk03 = "hiteshK03/davinci-resolve-mcp";
               dwc = "DigitalWorkflowCompany/resolve-mcp"; kerwilgil = "kerwilgil/davinci-resolve-mcp";
               apvlv = "apvlv/davinci-resolve-mcp"; tooflex = "Tooflex/davinci-resolve-mcp" }
    foreach ($k in $refs.Keys) {
        $dst = Join-Path $vendor "ref-$k"
        if (-not (Test-Path $dst)) { git clone --depth 1 "https://github.com/$($refs[$k]).git" $dst }
    }
}

& $py (Join-Path $root "scripts\sync.py")   # uv's Python: plain `python` may not be on PATH
Write-Host "`nListo. Abre Resolve (Free: Workspace > Scripts > resolve_bridge) y pide al agente: forge_status"
