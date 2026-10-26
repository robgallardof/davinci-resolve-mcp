# syntax=docker/dockerfile:1
# Optional image for the resolve-forge MCP. DaVinci Resolve itself always runs on the host:
# the container talks to the in-app bridge (Workspace > Scripts > resolve_bridge) through
# FORGE_BRIDGE_HOST, and FORGE_PATH_MAP translates /media paths to the host paths Resolve
# uses. See docs/docker.md.
#
# Optional extras at build time: --build-arg EXTRAS=vision (default) | "" | vision,speech
#   vision -> face anchors and highlight detection (opencv-headless)
#   speech -> local faster-whisper transcription on CPU (much bigger image)
FROM python:3.12-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
ARG EXTRAS=vision
WORKDIR /app
COPY mcp/resolve-forge/pyproject.toml mcp/resolve-forge/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    set -e; flags=""; for e in $(echo "$EXTRAS" | tr ',' ' '); do flags="$flags --extra $e"; done; \
    uv sync --locked --no-dev --no-install-project $flags
COPY mcp/resolve-forge/src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    set -e; flags=""; for e in $(echo "$EXTRAS" | tr ',' ' '); do flags="$flags --extra $e"; done; \
    uv sync --locked --no-dev --no-editable $flags

FROM python:3.12-slim-bookworm
# DejaVu fonts: title cards and captions fall back to them when Windows/macOS fonts are absent.
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 forge && useradd --uid 10001 --gid forge --create-home forge \
    && mkdir -p /workspace /media /config && chown forge:forge /workspace /media
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH DAVINCI_AGENTS_ROOT=/workspace PYTHONUNBUFFERED=1 PYTHONUTF8=1 \
    FORGE_BRIDGE_CONFIG=/config/bridge.json HF_HOME=/media/.cache/huggingface
USER forge
WORKDIR /media
EXPOSE 8080
ENTRYPOINT ["resolve-forge"]
CMD ["--stdio"]
