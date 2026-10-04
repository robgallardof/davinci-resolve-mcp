"""Wire I/O and object proxies. No native imports and no project side effects."""
import json
import os
import secrets
import socket
import threading
import time
from pathlib import Path

from ..errors import ForgeError
from .resolve_bridge import MAX_BYTES, PROTOCOL_VERSION, load_config, sign_request


def config_path():
    return Path(os.environ.get("FORGE_BRIDGE_CONFIG") or os.environ.get("DAVINCI_RESOLVE_BRIDGE_CONFIG") or
                Path.home() / ".config/davinci-resolve-mcp/bridge.json").expanduser()


class Client:
    def __init__(self, config, timeout=30):
        self.config, self.timeout = config, timeout
        self.lock = threading.RLock()
        self.methods = {}

    def request(self, operation, arguments):
        message = {"protocol": PROTOCOL_VERSION, "id": secrets.token_hex(16), "timestamp": int(time.time()),
                   "nonce": secrets.token_urlsafe(24), "operation": operation, "arguments": arguments}
        message["signature"] = sign_request(self.config["token"], message)
        raw = (json.dumps(message, allow_nan=False) + "\n").encode()
        if len(raw) > MAX_BYTES:
            raise ForgeError("Bridge request exceeds capacity.", code="REQUEST_TOO_LARGE")
        with self.lock, socket.create_connection(("127.0.0.1", self.config["port"]), self.timeout) as connection:
            connection.settimeout(self.timeout)
            connection.sendall(raw)
            response = connection.makefile("rb").readline(MAX_BYTES + 1)
        if len(response) > MAX_BYTES or not response.endswith(b"\n"):
            raise ForgeError("Invalid bridge response size.", code="BRIDGE_PROTOCOL_ERROR")
        try:
            reply = json.loads(response)
        except (ValueError, UnicodeError) as exc:
            raise ForgeError("Bridge returned invalid JSON.", code="BRIDGE_PROTOCOL_ERROR") from exc
        if not isinstance(reply, dict):
            raise ForgeError("Bridge returned a non-object reply.", code="BRIDGE_PROTOCOL_ERROR")
        if reply.get("id") != message["id"]:
            raise ForgeError("Bridge response did not match request.", code="BRIDGE_PROTOCOL_ERROR")
        if reply.get("ok") is not True:
            error = reply.get("error") or {}
            raise ForgeError(error.get("message", "Bridge refused request."), code=error.get("code", "BRIDGE_REFUSED"))
        return reply.get("result")

    def decode(self, value):
        if isinstance(value, dict):
            if "__handle__" in value:
                return Proxy(self, value["__handle__"])
            return {key: self.decode(item) for key, item in value.items()}
        return [self.decode(item) for item in value] if isinstance(value, list) else value


def encode(value):
    if isinstance(value, Proxy):
        return {"__handle__": value.handle}
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    return [encode(item) for item in value] if isinstance(value, (tuple, list)) else value


class Proxy:
    def __init__(self, client, handle):
        self.client, self.handle = client, handle

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if self.handle not in self.client.methods:
            self.client.methods[self.handle] = set(self.client.request("list_methods", {"target": self.handle})["methods"])
        methods = self.client.methods[self.handle]
        fusion = bool(methods & {"ConnectInput", "AddTool", "FindTool"})
        if name not in methods and not (fusion and name in {"GetAttrs", "SetAttrs"}):
            value = self.client.request("get_attribute", {"target": self.handle, "name": name})
            if value.get("kind") == "value":
                return self.client.decode(value.get("value"))
            raise AttributeError(name)
        def invoke(*args):
            result = self.client.request("call", {"target": self.handle, "method": name, "args": encode(args)})
            if result.get("truncated"):
                raise ForgeError("Bridge returned an incomplete result. Re-read in smaller groups; do not retry a write.",
                                 code="INCOMPLETE_RESULT")
            return self.client.decode(result.get("value"))
        return invoke


def connect():
    client = Client(load_config(config_path()))
    health = client.request("health", {})
    if not {"call", "list_methods", "get_attribute"} <= set(health.get("operations", [])):
        raise ForgeError("Bridge does not support object capabilities.", code="BRIDGE_UNSUPPORTED")
    return Proxy(client, "resolve")
