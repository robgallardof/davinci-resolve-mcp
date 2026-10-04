"""Standard-library wire protocol and listener; no editing policy lives here.

Protocol 1.0 remains compatible with already installed bridges during migration.
"""
import hashlib
import hmac
import json
import math
import os
import queue
import secrets
import socketserver
import sys
import threading
import time
from pathlib import Path

PROTOCOL_VERSION = "1.0"
MAX_BYTES = 8 * 1024 * 1024


class BridgeConfigError(ValueError):
    pass


def sign_request(token, message):
    body = {key: value for key, value in message.items() if key != "signature"}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hmac.new(token.encode(), encoded, hashlib.sha256).hexdigest()


def load_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if config.get("host", "127.0.0.1") != "127.0.0.1":
        raise BridgeConfigError("The bridge must bind to loopback.")
    if not isinstance(config.get("token"), str) or len(config["token"]) < 32:
        raise BridgeConfigError("A token of at least 32 characters is required.")
    if type(config.get("port")) is not int or not 0 <= config["port"] <= 65535:
        raise BridgeConfigError("Invalid bridge port.")
    skew = config.get("auth_clock_skew_seconds", 60)
    if not isinstance(skew, (int, float)) or not math.isfinite(skew) or not 0 < skew <= 300:
        raise BridgeConfigError("Invalid authentication clock window.")
    return config


class Authenticator:
    """Authenticate before dispatch, retaining nonces across the full replay window."""
    def __init__(self, token, skew=60, clock=time.time):
        self.token, self.skew, self.clock = token, skew, clock
        self.nonces = {}
        self.lock = threading.Lock()

    def verify(self, message):
        if not isinstance(message, dict) or message.get("protocol") != PROTOCOL_VERSION:
            raise ValueError("Invalid protocol.")
        timestamp, nonce = message.get("timestamp"), message.get("nonce")
        now = self.clock()
        if type(timestamp) not in (int, float) or not math.isfinite(timestamp) or abs(now - timestamp) > self.skew:
            raise ValueError("Expired request.")
        if not isinstance(nonce, str) or not 16 <= len(nonce) <= 128:
            raise ValueError("Invalid nonce.")
        signature = message.get("signature")
        if not isinstance(signature, str) or not hmac.compare_digest(signature, sign_request(self.token, message)):
            raise ValueError("Invalid signature.")
        with self.lock:
            self.nonces = {key: expiry for key, expiry in self.nonces.items() if expiry >= now}
            if nonce in self.nonces or len(self.nonces) >= 10000:
                raise ValueError("Replay or authentication capacity exceeded.")
            self.nonces[nonce] = timestamp + self.skew


class _Server(socketserver.TCPServer):
    allow_reuse_address = os.name != "nt"
    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return connection, address


class Bridge:
    """One listener, one native call at a time; project operations are injected."""
    def __init__(self, resolve, config, dispatch, alive=None, alive_every_s=5.0):
        self.config, self.dispatch = config, dispatch
        # A bridge whose Resolve has closed must release the port, or the next session cannot start.
        self.alive, self.alive_every_s = alive, alive_every_s
        self.auth = Authenticator(config["token"], config.get("auth_clock_skew_seconds", 60))
        self.session = secrets.token_hex(16)
        self._server = self._thread = None
        self.stop_mode = None
        # Resolve's objects only answer on the script's own thread (fuscript.exe): when serve() blocks,
        # the listener hands each call to that thread through this queue instead of calling Resolve itself.
        self._jobs = queue.Queue()
        self._pumping = False

    def execute(self, operation, arguments, timeout=300):
        if not self._pumping:
            return self.dispatch(operation, arguments)
        box, done = {}, threading.Event()
        self._jobs.put((operation, arguments, box, done))
        if not done.wait(timeout):
            raise TimeoutError("Resolve did not answer in time; the call may still complete.")
        if "error" in box:
            raise box["error"]
        return box["value"]

    def _drain(self, wait_s=.05):
        try:
            operation, arguments, box, done = self._jobs.get(timeout=wait_s)
        except queue.Empty:
            return
        try:
            box["value"] = self.dispatch(operation, arguments)
        except Exception as exc:
            box["error"] = exc
        finally:
            done.set()

    @property
    def port(self):
        return self._server.server_address[1] if self._server else self.config["port"]

    def start(self):
        owner = self
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                message = {}
                try:
                    raw = self.rfile.readline(MAX_BYTES + 1)
                    if len(raw) > MAX_BYTES or not raw.endswith(b"\n"):
                        raise ValueError("Request too large or incomplete.")
                    message = json.loads(raw)
                    owner.auth.verify(message)
                    value = owner.execute(message["operation"], message.get("arguments", {}))
                    if message["operation"] == "health":
                        value = {**value, "session": owner.session}
                    response = {"id": message.get("id"), "ok": True, "result": value}
                except Exception as exc:
                    response = {"id": message.get("id") if isinstance(message, dict) else None,
                                "ok": False, "error": {"code": getattr(exc, "code", "BRIDGE_REFUSED"),
                                                        "message": str(exc)}}
                encoded = (json.dumps(response, allow_nan=False) + "\n").encode()
                if len(encoded) > MAX_BYTES:
                    encoded = (json.dumps({"id": message.get("id"), "ok": False,
                        "error": {"code": "REPLY_TOO_LARGE", "message": "Reply exceeded transport capacity; use a smaller query."}}) + "\n").encode()
                self.wfile.write(encoded)
        self._server = _Server(("127.0.0.1", self.config["port"]), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": .1}, daemon=True)
        self._thread.start()
        return self

    def request_stop(self, mode):
        if mode not in ("reload", "exit"):
            raise ValueError("Invalid lifecycle mode.")
        self.stop_mode = mode

    def serve(self, host_model=None):
        self.start()
        if not (host_model or _host_model())["blocking_required"]:
            threading.Thread(target=self._wait, daemon=True).start()
            return {"stop_reason": "background"}
        return self._wait()

    def _wait(self):
        self._pumping = True
        checked = time.monotonic()
        try:
            while self.stop_mode is None and self._thread.is_alive():
                self._drain()
                if self.alive is not None and time.monotonic() - checked >= self.alive_every_s:
                    checked = time.monotonic()
                    if not self.alive():
                        self.stop_mode = "resolve_gone"
        finally:
            self._pumping = False
            while not self._jobs.empty():  # never leave a caller hanging on shutdown
                self._drain(0)
        self.stop()
        return {"stop_reason": self.stop_mode or "listener_closed"}

    def stop(self):
        if self._server is not None:
            if self._thread and self._thread.is_alive():
                self._server.shutdown()
                self._thread.join(5)
            self._server.server_close()
            self._server = None


def _host_model():
    embedded = "resolve" in Path(sys.executable).stem.lower()
    return {"model": "embedded" if embedded else "child", "blocking_required": not embedded}


def validate_runtime_sources(directory):
    problems = []
    for name in ("resolve_bridge.py", "resolve_bridge_ops.py"):
        try:
            path = Path(directory) / name
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except (OSError, SyntaxError) as exc:
            problems.append(str(exc))
    return problems
