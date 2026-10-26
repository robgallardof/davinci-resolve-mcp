"""Optional Streamable HTTP transport for the MCP server, guarded by a shared token.

stdio stays the normal mode (the MCP client launches the server). HTTP exists for
Docker or for deliberately serving the MCP on a network, and only starts with ``--http``:

- every request to ``/mcp`` needs ``Authorization: Bearer <token>``; the token comes
  from an environment variable and must be at least 32 printable ASCII characters;
- ``/healthz`` answers without a token and only reports that the process is alive;
- requests carrying an ``Origin`` header (browsers) are rejected: native MCP clients
  do not send one, and this stops a web page from talking to the server;
- the MCP SDK checks ``Host`` against an allowlist (DNS-rebinding protection) and
  bounds request bodies.

Same contract as Rekora's HTTP server, so clients are configured the same way.
"""

from __future__ import annotations

import hmac
import ipaddress
import os
import string

MIN_TOKEN_CHARS = 32
DEFAULT_LISTEN = "127.0.0.1:8080"
_PRINTABLE = set(string.printable) - set(string.whitespace)


class HttpConfigError(ValueError):
    """Invalid HTTP configuration; the message is shown to the user as is."""


def read_token(env_var: str) -> str:
    """Read and validate the token from the environment. There is never a default."""
    token = os.environ.get(env_var, "")
    if len(token) < MIN_TOKEN_CHARS or any(c not in _PRINTABLE for c in token):
        raise HttpConfigError(
            f"{env_var} must be at least {MIN_TOKEN_CHARS} printable ASCII characters "
            "(e.g. python -c \"import secrets; print(secrets.token_hex(32))\")"
        )
    return token


def parse_listen(value: str) -> tuple[str, int]:
    """``HOST:PORT`` (IPv4, or IPv6 in brackets) to ``(host, port)``."""
    host, sep, port_text = value.rpartition(":")
    if not sep or not port_text.isdigit() or not 0 < int(port_text) < 65536:
        raise HttpConfigError(f"--listen expects HOST:PORT, got {value!r}")
    host = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    try:
        ipaddress.ip_address(host)
    except ValueError as error:
        raise HttpConfigError(f"--listen needs an IP address, got {host!r}") from error
    return host, int(port_text)


def allowed_hosts(extra: list[str]) -> list[str]:
    """Accepted ``Host`` values: loopback always, plus explicitly allowed names."""
    hosts = ["127.0.0.1", "localhost", "[::1]"] + [h for h in extra if h]
    return [pattern for h in hosts for pattern in (h, f"{h}:*")]


class BearerGuard:
    """ASGI middleware: unauthenticated health, no browsers, mandatory token."""

    def __init__(self, app, token: str):
        self.app = app
        self.token = token.encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":  # session-manager lifespan passes through untouched
            await self.app(scope, receive, send)
            return
        if scope.get("path") == "/healthz":
            await _respond(send, 200, b"ok")
            return
        headers = dict(scope.get("headers") or [])
        if b"origin" in headers:
            await _respond(send, 403, b"browser origins are not allowed")
            return
        auth = headers.get(b"authorization", b"")
        scheme, _, presented = auth.partition(b" ")
        if scheme.lower() != b"bearer" or not hmac.compare_digest(presented.strip(), self.token):
            await _respond(send, 401, b"missing or invalid bearer token",
                           [(b"www-authenticate", b'Bearer realm="mcp"')])
            return
        await self.app(scope, receive, send)


async def _respond(send, status: int, body: bytes, extra: list | None = None) -> None:
    headers = [(b"content-type", b"text/plain; charset=utf-8"), (b"content-length", str(len(body)).encode())]
    await send({"type": "http.response.start", "status": status, "headers": headers + (extra or [])})
    await send({"type": "http.response.body", "body": body})


def serve(mcp, listen: str, extra_hosts: list[str], token_env: str) -> None:
    """Serve ``mcp`` (a FastMCP) over HTTP until SIGINT/SIGTERM."""
    import uvicorn
    from mcp.server.transport_security import TransportSecuritySettings

    token = read_token(token_env)
    host, port = parse_listen(listen)
    mcp.settings.host, mcp.settings.port = host, port
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True, allowed_hosts=allowed_hosts(extra_hosts), allowed_origins=[]
    )
    app = BearerGuard(mcp.streamable_http_app(), token)
    uvicorn.run(app, host=host, port=port, log_level="warning")


def add_arguments(parser) -> None:
    """Transport options shared by the MCP servers in this repository."""
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--stdio", action="store_true", help="stdio (default)")
    mode.add_argument("--http", action="store_true", help="Streamable HTTP with a bearer token")
    parser.add_argument("--listen", default=DEFAULT_LISTEN, help=f"HOST:PORT for --http (default {DEFAULT_LISTEN})")
    parser.add_argument("--allow-host", action="append", default=[], metavar="NAME",
                        help="public host name accepted in addition to loopback (repeatable)")
