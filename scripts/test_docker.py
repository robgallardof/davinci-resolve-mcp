"""Real test of the optional Docker image against a real bridge listener (standard library only).

DaVinci Resolve is not needed: a real `Bridge` (the same wire protocol, authentication and
path policy as the in-app bridge) runs on the host with Forge's Resolve fake. The
container then reaches it like it would reach Resolve:

- Docker Desktop (Windows/macOS): FORGE_BRIDGE_HOST=host.docker.internal;
- Linux: --network host and FORGE_BRIDGE_HOST=127.0.0.1.

Checks: stdio handshake and forge_status through the bridge; ingest_media with a /media
path that the bridge's path policy only accepts after FORGE_PATH_MAP translation; Compose
over HTTP with a token on a free port. Temporary files and containers are removed on exit.

    python scripts/test_docker.py [--extras vision]
"""

import argparse
import json
import os
import platform
import queue
import secrets
import socket
import subprocess
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORGE = ROOT / "mcp" / "resolve-forge"
IMAGE = "resolve-forge:local"
LINUX = platform.system() == "Linux"
FAKE_BRIDGE = """
import json, sys, time
sys.path.insert(0, "tests")
from fakes import demo_resolve
from resolve_forge.bridge.resolve_bridge import Bridge
from resolve_forge.bridge.resolve_bridge_ops import ResolveOperations, make_dispatch
media, token = sys.argv[1], sys.argv[2]
resolve = demo_resolve(studio=False)
config = {"host": "127.0.0.1", "port": 0, "token": token}
bridge = Bridge(resolve, config, make_dispatch(ResolveOperations(resolve, [media], [media]))).start()
print(json.dumps({**config, "port": bridge.port}), flush=True)
while True:
    time.sleep(1)
"""


def run(*args, env=None, input=None, timeout=1800):
    out = subprocess.run(args, env=env, input=input, text=True, capture_output=True, timeout=timeout, encoding="utf-8")
    if out.returncode:
        raise RuntimeError(f"failed {' '.join(map(str, args))}:\n{out.stdout}\n{out.stderr}")
    return out.stdout


def rpc(url, token, message, session=None):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
               "Authorization": f"Bearer {token}"}
    if session:
        headers.update({"Mcp-Session-Id": session, "MCP-Protocol-Version": "2025-11-25"})
    req = urllib.request.Request(url, json.dumps(message).encode(), headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read().decode()
        if "text/event-stream" in resp.headers.get("Content-Type", ""):
            data = next((line[5:].strip() for line in data.splitlines()
                         if line.startswith("data:") and line[5:].strip()), "")
        return (json.loads(data) if data else None), resp.headers.get("Mcp-Session-Id")


def call(name, arguments, ident):
    return {"jsonrpc": "2.0", "id": ident, "method": "tools/call", "params": {"name": name, "arguments": arguments}}


def stdio_exchange(command, messages):
    """Keep the real client connection open until each request has answered.

    Sending all requests with communicate() closes stdin immediately and can
    cancel slower bridge operations before their responses reach stdout.
    """
    replies = {}
    container = "forge-stdio-" + secrets.token_hex(4)
    command = [*command[:3], "--name", container, *command[3:]]
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errors:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=errors, text=True, encoding="utf-8")
        lines = queue.Queue()

        def read_lines():
            for line in process.stdout:
                lines.put(line)
            lines.put(None)

        reader = threading.Thread(target=read_lines, daemon=True)
        reader.start()
        try:
            for message in messages:
                process.stdin.write(json.dumps(message) + "\n")
                process.stdin.flush()
                if "id" not in message:
                    continue
                while True:
                    line = lines.get(timeout=90)
                    if line is None:
                        errors.seek(0)
                        raise AssertionError("MCP closed before answering: " + errors.read())
                    reply = json.loads(line)
                    if reply.get("id") == message["id"]:
                        replies[message["id"]] = reply
                        break
            process.stdin.close()
            assert process.wait(timeout=30) == 0
            return replies
        finally:
            subprocess.run(["docker", "rm", "-f", container], capture_output=True, timeout=30)
            if process.poll() is None:
                process.kill()
            process.wait(timeout=30)
            reader.join(timeout=5)


INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "docker-smoke", "version": "1"}}}
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}


def payload(reply):
    result = reply["result"]
    assert not result.get("isError"), reply
    return json.loads(result["content"][0]["text"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--extras", default="vision")
    extras = parser.parse_args().extras
    run("docker", "build", "--build-arg", f"EXTRAS={extras}", "-t", IMAGE, str(ROOT))
    print(f"ok  build (EXTRAS={extras})")

    with tempfile.TemporaryDirectory(prefix="forge-docker-") as tmp:
        media = Path(tmp) / "Movies"
        media.mkdir()
        (media / "clip.mp4").write_bytes(b"\0" * 64)
        os.chmod(media, 0o777)
        token = secrets.token_hex(32)
        bridge = subprocess.Popen(["uv", "run", "--quiet", "python", "-c", FAKE_BRIDGE, str(media), token],
                                  cwd=FORGE, stdout=subprocess.PIPE, text=True)
        try:
            config = json.loads(bridge.stdout.readline())
            config_file = Path(tmp) / "bridge.json"
            config_file.write_text(json.dumps(config), encoding="utf-8")
            os.chmod(config_file, 0o644)
            host_media = media.as_posix()
            user = f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else "10001:10001"
            network = (["--network", "host", "-e", "FORGE_BRIDGE_HOST=127.0.0.1"] if LINUX else
                       ["--add-host", "host.docker.internal:host-gateway",
                        "-e", "FORGE_BRIDGE_HOST=host.docker.internal"])
            docker_run = ["docker", "run", "--rm", "-i", "--user", user, *network,
                          "-e", f"FORGE_PATH_MAP=/media={host_media}",
                          "-v", f"{media}:/media", "-v", f"{config_file}:/config/bridge.json:ro",
                          "-v", f"{ROOT}:/workspace:ro", IMAGE]
            messages = (
                INIT, INITIALIZED, call("forge_status", {}, 2),
                call("ingest_media", {"paths": ["/media/clip.mp4"], "dry_run": False}, 3))
            replies = stdio_exchange(docker_run, messages)
            assert replies[1]["result"]["serverInfo"]["name"] == "resolve-forge", replies
            status = payload(replies[2])
            assert status["transport"] == "bridge" and status["version"].startswith("21."), status
            print(f"ok  stdio: forge_status through the bridge ({status['version']})")
            ingest = payload(replies[3])
            assert ingest["applied"] and ingest["complete"], ingest
            assert ingest["imported"][0]["path"] == "/media/clip.mp4", ingest
            print("ok  ingest_media: /media path accepted by the host bridge and reported back as /media")

            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
            http_token = secrets.token_hex(32)
            env = dict(os.environ, RESOLVE_FORGE_MCP_TOKEN=http_token, RESOLVE_FORGE_PORT=str(port),
                       FORGE_MEDIA=str(media), FORGE_BRIDGE_CONFIG_FILE=str(config_file),
                       RESOLVE_FORGE_WORKSPACE=str(ROOT), RESOLVE_FORGE_USER=user, RESOLVE_FORGE_EXTRAS=extras)
            files = ["-f", str(ROOT / "compose.yaml")]
            if LINUX:  # the bridge listens on host loopback: share the host network instead of publishing a port
                files += ["-f", str(ROOT / "compose.linux.yaml")]
            compose = ["docker", "compose", "-p", f"forge{secrets.token_hex(3)}", *files]
            try:
                run(*compose, "up", "-d", "--wait", env=env, timeout=600)
                url = f"http://127.0.0.1:{port}/mcp"
                try:
                    rpc(url, "x" * 64, INIT)
                    raise AssertionError("accepted a wrong token")
                except urllib.error.HTTPError as e:
                    assert e.code == 401, e.code
                init, session = rpc(url, http_token, INIT)
                assert init["result"]["serverInfo"]["name"] == "resolve-forge"
                rpc(url, http_token, INITIALIZED, session)
                status, _ = rpc(url, http_token, call("forge_status", {}, 2), session)
                assert payload(status)["transport"] == "bridge"
                print(f"ok  compose HTTP on port {port}: token, forge_status through the bridge")
            finally:
                subprocess.run([*compose, "down", "--remove-orphans"], env=env, capture_output=True, timeout=180)
        finally:
            bridge.kill()
            bridge.wait()
    print("all ok")


if __name__ == "__main__":
    main()
