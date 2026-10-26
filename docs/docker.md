# Docker (optional)

resolve-forge runs natively with `uv` and that remains the recommended setup. Docker is for people who would rather
not install Python. **DaVinci Resolve always runs on the host**: the container is only the MCP server, and it talks to
Resolve through the in-app bridge exactly like the native server does.

```
 MCP client ──stdio or HTTP──▶ container: resolve-forge ──signed TCP──▶ host: Resolve + resolve_bridge (loopback)
                                   │ /media  ◀── bind mount ──▶  host media folder (e.g. C:/Users/me/Movies)
```

## Before you start (every Resolve session)

1. Open Resolve and a project, then run **Workspace → Scripts → resolve_bridge** (Free; Studio can use it too).
   Install the bridge once natively: `cd mcp/resolve-forge && uv run resolve-forge-install-bridge`.
2. The bridge writes its token and port to `~/.config/davinci-resolve-mcp/bridge.json`. The container mounts that
   file read-only; it never changes it.

## How the container reaches Resolve

| Variable | Meaning |
|---|---|
| `FORGE_BRIDGE_HOST` | Where the bridge is. Docker Desktop (Windows/macOS): `host.docker.internal`. Linux: run with `--network host` and keep `127.0.0.1` |
| `FORGE_PATH_MAP` | `CONTAINER=HOST` pairs separated by `;`, e.g. `/media=C:/Users/me/Movies`. Paths sent to Resolve are rewritten to host paths and paths coming back are rewritten to `/media/...` |
| `FORGE_BRIDGE_CONFIG` | Bridge config inside the container (default `/config/bridge.json`) |

The bridge keeps binding to the host's loopback only and still checks every path against its own media/output roots.
On Docker Desktop, connections to `host.docker.internal` arrive on the host's loopback, so nothing is opened to the
network. Mount the folder Resolve imports from and renders into (in Free, inside `~/Movies`) at `/media`, and refer to
media as `/media/...` when talking to the agent.

## Build

```bash
docker build -t resolve-forge:local .                              # with face anchors (vision, default)
docker build --build-arg EXTRAS= -t resolve-forge:local .          # smallest
docker build --build-arg EXTRAS=vision,speech -t resolve-forge:local .  # + local Whisper on CPU (large image)
```

## stdio: launched by your MCP client

```json
{
  "mcpServers": {
    "resolve-forge": {
      "command": "docker",
      "args": ["run", "--rm", "-i",
               "--add-host", "host.docker.internal:host-gateway",
               "-e", "FORGE_BRIDGE_HOST=host.docker.internal",
               "-e", "FORGE_PATH_MAP=/media=C:/Users/me/Movies",
               "-v", "C:/Users/me/Movies:/media",
               "-v", "C:/Users/me/.config/davinci-resolve-mcp/bridge.json:/config/bridge.json:ro",
               "-v", "C:/path/to/davinci-agents:/workspace:ro",
               "resolve-forge:local"]
    }
  }
}
```

Keep `-i`, never `-t`. The `/workspace` mount is optional: it exposes the skills (`skill://…`) and roles as MCP
resources and prompts. Linux: replace the `--add-host`/`FORGE_BRIDGE_HOST` lines with `--network host`.

## HTTP with a token

```powershell
$env:RESOLVE_FORGE_MCP_TOKEN = python -c "import secrets; print(secrets.token_hex(32))"
$env:FORGE_MEDIA = 'C:/Users/me/Movies'
$env:RESOLVE_FORGE_PORT = '8767'            # optional, default 8080
docker compose up -d --build --wait
```

Point a Streamable HTTP MCP client at `http://127.0.0.1:<port>/mcp` with `Authorization: Bearer <token>`.

| Variable | Default | Purpose |
|---|---|---|
| `RESOLVE_FORGE_MCP_TOKEN` | required | Bearer token, at least 32 characters |
| `FORGE_MEDIA` | required | Host media folder mounted at `/media` and used for `FORGE_PATH_MAP` |
| `FORGE_BRIDGE_CONFIG_FILE` | `~/.config/davinci-resolve-mcp/bridge.json` | Bridge config to mount |
| `RESOLVE_FORGE_PORT` | `8080` | Host port (container port is 8080) |
| `RESOLVE_FORGE_BIND_ADDRESS` | `127.0.0.1` | Interface Docker publishes on |
| `RESOLVE_FORGE_USER` | `10001:10001` | Runtime UID:GID; on Linux use `"$(id -u):$(id -g)"` |
| `RESOLVE_FORGE_EXTRAS` | `vision` | Build extras |

On Linux the bridge is only reachable from the host network. Use the supplied override
(a recent Docker Compose with [`!reset`](https://docs.docker.com/reference/compose-file/merge/#reset-value) support):

```bash
export RESOLVE_FORGE_MCP_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export FORGE_MEDIA="$HOME/Movies"
export RESOLVE_FORGE_USER="$(id -u):$(id -g)"
export RESOLVE_FORGE_PORT=8767
docker compose -f compose.yaml -f compose.linux.yaml up -d --build --wait
```

The override shares the host network, binds MCP to `127.0.0.1:<port>`, removes port
publication and reaches the signed bridge through host loopback. It does not expose
the bridge or MCP on the LAN. `scripts/test_docker.py` uses the same override on Linux.
Native equivalent: `uv run resolve-forge --http --listen 127.0.0.1:8767`.
`/healthz` answers without a token; browser `Origin` headers and unknown `Host` names are rejected.

## Limits

- Resolve, the bridge and its one-time install stay native; `resolve-forge-doctor` and `uv run pytest -m live` are
  host commands.
- Only paths under a `FORGE_PATH_MAP` prefix are translated. A host path typed by the user (`C:\...`) is not visible
  inside the container; use `/media/...`.
- GPU transcription is not set up in the image; `speech` runs on CPU.

## Verify

```bash
python scripts/test_docker.py
```

Resolve is not required: the script starts a real bridge listener (same protocol, signatures and path policy) on the
host with Forge's Resolve fake, then checks stdio `forge_status` through the bridge, `ingest_media` with a `/media`
path that the host bridge only accepts after translation, and Compose over HTTP with a token on a free port.
A live session against a running Resolve from the container has not been executed.

### Verification — 2026-10-26

Executed on Windows with Docker Desktop Linux containers: default `EXTRAS=vision`
image build, interactive stdio initialization and real bridge requests, media-path
translation accepted by the bridge's path policy, and authenticated Compose HTTP
on a custom port. All passed. The bridge listener was real; its Resolve backend was
the project's simulation, not the running editor. The smoke client now waits for
each response before closing stdin, so slower operations are actually observed.

`uv run pytest -q`: 693 passed, 13 live tests deselected. Root/drive-root path-map
regressions also pass. The shared Linux Compose override was parsed and checked
for host networking, no published ports and the chosen loopback MCP port.
Linux host-network end-to-end, live Resolve editing/rendering and the optional
`speech` image were NOT EXECUTED locally in this verification; CI runs the Linux
container/bridge test on push.
