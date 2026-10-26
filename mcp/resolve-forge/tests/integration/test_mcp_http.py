"""HTTP transport: unit tests of the guard and integration against a real server.

The integration starts `resolve-forge --http` in a subprocess on a free port and talks to it with the official MCP Streamable HTTP client.
"""

import asyncio
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from resolve_forge import http_transport as ht

PKG = Path(__file__).resolve().parents[2]
TOKEN = "t" * 40


# ---------- units ----------
def test_parse_listen():
    assert ht.parse_listen("127.0.0.1:8080") == ("127.0.0.1", 8080)
    assert ht.parse_listen("0.0.0.0:1") == ("0.0.0.0", 1)
    assert ht.parse_listen("[::1]:9000") == ("::1", 9000)
    for malo in ("8080", "localhost:8080", "127.0.0.1:0", "127.0.0.1:70000", "127.0.0.1:x", ":80"):
        with pytest.raises(ht.HttpConfigError):
            ht.parse_listen(malo)


def test_token_required_and_long(monkeypatch):
    monkeypatch.delenv("X_TOKEN", raising=False)
    with pytest.raises(ht.HttpConfigError):
        ht.read_token("X_TOKEN")
    for malo in ("corto", "a" * 31, "a" * 31 + " ", "ñ" * 40):
        monkeypatch.setenv("X_TOKEN", malo)
        with pytest.raises(ht.HttpConfigError):
            ht.read_token("X_TOKEN")
    monkeypatch.setenv("X_TOKEN", TOKEN)
    assert ht.read_token("X_TOKEN") == TOKEN


def test_allowed_hosts():
    hosts = ht.allowed_hosts(["mem.example.com"])
    assert {"127.0.0.1:*", "localhost:*", "[::1]:*", "mem.example.com", "mem.example.com:*"} <= set(hosts)


def _llamar(guard, path, headers):
    enviados = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        enviados.append(msg)

    scope = {"type": "http", "path": path, "headers": [(k.encode(), v.encode()) for k, v in headers.items()]}
    asyncio.run(guard(scope, receive, send))
    return enviados[0]["status"] if enviados else None


def test_bearer_guard():
    llamado = []

    async def app(scope, receive, send):
        llamado.append(scope["path"])
        await send({"type": "http.response.start", "status": 299, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    guard = ht.BearerGuard(app, TOKEN)
    assert _llamar(guard, "/healthz", {}) == 200
    assert _llamar(guard, "/mcp", {}) == 401
    assert _llamar(guard, "/mcp", {"authorization": "Bearer " + "x" * 40}) == 401
    assert _llamar(guard, "/mcp", {"authorization": "Basic " + TOKEN}) == 401
    assert _llamar(guard, "/mcp", {"authorization": "Bearer " + TOKEN, "origin": "https://evil.example"}) == 403
    assert _llamar(guard, "/mcp", {"authorization": "Bearer " + TOKEN}) == 299
    assert llamado == ["/mcp"]


# ---------- integration: real server ----------
def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def servidor(tmp_path):
    port = _puerto_libre()
    # No bridge config: forge_status must answer "not connected" instead of hanging.
    env = dict(os.environ, RESOLVE_FORGE_MCP_TOKEN=TOKEN, FORGE_BRIDGE_CONFIG=str(tmp_path / "none.json"))
    proc = subprocess.Popen(
        [sys.executable, "-m", "resolve_forge.server", "--http", "--listen", f"127.0.0.1:{port}"],
        env=env, cwd=PKG, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    base = f"http://127.0.0.1:{port}"
    limite = time.time() + 60
    while time.time() < limite:
        try:
            with urllib.request.urlopen(base + "/healthz", timeout=1) as r:
                if r.status == 200:
                    break
        except OSError:
            if proc.poll() is not None:
                pytest.fail(proc.stderr.read().decode())
            time.sleep(0.2)
    else:
        proc.kill()
        pytest.fail("HTTP server did not answer /healthz within 60 s")
    yield base
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def _status(url, headers=None, body=b"{}"):
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def test_real_http_rejects_missing_token_and_browsers(servidor):
    assert _status(servidor + "/mcp") == 401
    assert _status(servidor + "/mcp", {"Authorization": "Bearer " + "z" * 40}) == 401
    assert _status(servidor + "/mcp", {"Authorization": "Bearer " + TOKEN, "Origin": "https://evil.example"}) == 403
    # Host outside the allowlist: blocked by the SDK DNS-rebinding protection.
    assert _status(servidor + "/mcp", {"Authorization": "Bearer " + TOKEN, "Host": "attacker.example",
                                       "Accept": "application/json, text/event-stream"}) in (400, 421)


def test_real_http_official_mcp_client(servidor):
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async def flujo():
        cliente = httpx.AsyncClient(headers={"Authorization": f"Bearer {TOKEN}"}, timeout=30)
        async with cliente, streamable_http_client(servidor + "/mcp", http_client=cliente) as (r, w, _):
            async with ClientSession(r, w) as sesion:
                info = await sesion.initialize()
                herramientas = {t.name for t in (await sesion.list_tools()).tools}
                resultado = await sesion.call_tool("preview_motion", {"style": "youtube_dynamic", "seconds": 20})
                return info, herramientas, resultado

    info, herramientas, resultado = asyncio.run(flujo())
    assert info.serverInfo.name == "resolve-forge"
    assert {"forge_status", "apply_motion", "render_for", "list_styles"} <= herramientas
    assert len(herramientas) == 65
    assert not resultado.isError


def test_http_without_token_refuses_to_start():
    env = {k: v for k, v in os.environ.items() if k != "RESOLVE_FORGE_MCP_TOKEN"}
    out = subprocess.run([sys.executable, "-m", "resolve_forge.server", "--http", "--listen", "127.0.0.1:1"],
                         env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode != 0 and "RESOLVE_FORGE_MCP_TOKEN" in out.stderr
