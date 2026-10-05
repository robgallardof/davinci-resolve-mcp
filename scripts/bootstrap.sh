#!/usr/bin/env sh
# Install the single Forge MCP, its packaged Free bridge and agent configs (macOS and Linux).
set -eu
task_root=$(cd "$(dirname "$0")/.." && pwd)
command -v uv >/dev/null 2>&1 || { echo "uv not found: https://docs.astral.sh/uv/getting-started/installation/" >&2; exit 1; }
uv python install 3.12
cd "$task_root/mcp/resolve-forge"
uv sync --python 3.12 --extra vision --extra speech
uv run python -m resolve_forge.bridge_install.install_resolve_bridge
uv run pytest -q
uv run python "$task_root/scripts/sync.py"
echo "Done. Free: Workspace > Scripts > resolve_bridge. Then ask your agent for forge_status."
