# OpenCode and DeepSeek Harness

Run these commands from the repository root. This page preserves the detailed setup and verification notes.

Project-scoped, opt-in setup (run from this checkout):

```sh
python scripts/install-mcp.py --clients opencode,deepseek --dry-run
python scripts/install-mcp.py --clients opencode,deepseek
opencode mcp list
dsh web --patch .dsh/mcp.cordis.yml
# Remove only this workspace's servers:
python scripts/install-mcp.py --clients opencode,deepseek --remove
```

OpenCode uses its **1.x** `opencode.json` MCP schema; 2.x configuration is rejected instead of rewritten.
DeepSeek uses the official **Harness** (`@deepseek-ai/dsh`) MCP plugin through an explicit Cordis overlay;
JSON output is valid YAML. Other entries survive installation and removal; the first original is retained in `.bak`.
Malformed configuration is refused. No provider credentials are written. The DeepSeek API alone is not an MCP host;
using a DeepSeek model in OpenCode uses the same OpenCode connection. Set credentials through the host's own login.
Harness exposes MCP tools/resources but does not support MCP prompt templates: read role files from `.agents/agents/`.

Installer integration tests run real subprocesses with temporary files (`tests/test_agent_clients.py`).
Model inference requires separate credentials and is **NOT EXECUTED** by these tests.
Contracts: [OpenCode MCP](https://opencode.ai/docs/en/mcp-servers),
[DeepSeek Harness MCP](https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/mcp/mcp-client).

Reproduce the real host probe (Node 24.9+; sync/build this server first):

```sh
npm install --prefix /tmp/agent-hosts --ignore-scripts --no-audit --no-fund opencode-ai@1.19.4 @deepseek-ai/dsh@0.2.1-rc.2
export AGENT_HOST_MODULES=/tmp/agent-hosts/node_modules
export OPENCODE_BIN=$AGENT_HOST_MODULES/opencode-linux-x64-baseline/bin/opencode
python scripts/test_agent_hosts.py
```

On Windows, use the absolute `opencode-windows-x64/bin/opencode.exe` path and PowerShell environment variables;
on macOS use `opencode-darwin-arm64/bin/opencode` (or the package matching your CPU).
The CI job **Agent host integrations** runs the same probe on Linux, with pinned host versions and no API key.
Local Windows execution: OpenCode **1.19.4**, DeepSeek Harness runtime **0.2.1-rc.2**; discovery and
read-only MCP execution passed. Paid/live model inference is **NOT EXECUTED**.
