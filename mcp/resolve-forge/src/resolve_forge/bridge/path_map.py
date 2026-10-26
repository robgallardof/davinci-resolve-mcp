"""Path translation between a container and the host where Resolve runs. Pure; no I/O.

When resolve-forge runs in Docker, media is mounted at container paths (``/media/...``)
but Resolve, on the host, imports and renders host paths (``C:/Users/me/Movies/...``).
``FORGE_PATH_MAP`` lists ``CONTAINER=HOST`` pairs separated by ``;``. Every string in a
bridge request that starts with a container prefix is rewritten to the host prefix, and
every string in a reply that starts with a host prefix is rewritten back, so tools and
agents only ever see container paths. Without the variable nothing is rewritten.
"""
from __future__ import annotations

import os
import re

_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")


def _norm(path: str) -> str:
    path = path.replace("\\", "/")
    if re.fullmatch(r"[A-Za-z]:/+", path):
        return path[:2] + "/"
    return path.rstrip("/") or "/"


def _join(prefix: str, remainder: str) -> str:
    """Root mappings need exactly one separator, including Windows drive roots."""
    return prefix.rstrip("/") + "/" + remainder.lstrip("/") if remainder else prefix


class PathMap:
    def __init__(self, pairs: list[tuple[str, str]] | None = None):
        self.pairs = [(_norm(c), _norm(h)) for c, h in (pairs or [])]
        # Longest prefix wins in each direction (/media/raw over /media; .../Movies/renders over .../Movies).
        self.outbound = sorted(self.pairs, key=lambda pair: len(pair[0]), reverse=True)
        self.inbound = sorted(self.pairs, key=lambda pair: len(pair[1]), reverse=True)

    @classmethod
    def parse(cls, spec: str | None) -> "PathMap":
        pairs = []
        for chunk in (spec or "").split(";"):
            if not chunk.strip():
                continue
            container, sep, host = chunk.partition("=")
            if not sep or not container.strip().startswith("/") or not host.strip():
                raise ValueError(f"FORGE_PATH_MAP entries must look like /container=HOST_PATH, got {chunk!r}")
            pairs.append((container.strip(), host.strip()))
        return cls(pairs)

    @classmethod
    def from_env(cls) -> "PathMap":
        return cls.parse(os.environ.get("FORGE_PATH_MAP"))

    def __bool__(self) -> bool:
        return bool(self.pairs)

    def to_host(self, value):
        return self._walk(value, self._one_to_host)

    def to_container(self, value):
        return self._walk(value, self._one_to_container)

    def _walk(self, value, convert):
        if not self.pairs:
            return value
        if isinstance(value, str):
            return convert(value)
        if isinstance(value, dict):
            return {key: self._walk(item, convert) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._walk(item, convert) for item in value]
        return value

    def _one_to_host(self, text: str) -> str:
        for container, host in self.outbound:
            rest = _strip_prefix(text, container, case_insensitive=False)
            if rest is not None:
                return _join(host, rest)
        return text

    def _one_to_container(self, text: str) -> str:
        normalized = text.replace("\\", "/")
        for container, host in self.inbound:
            # Windows paths compare case-insensitively, as the file system does.
            rest = _strip_prefix(normalized, host, case_insensitive=bool(_WINDOWS_DRIVE.match(host)))
            if rest is not None:
                return _join(container, rest)
        return text


def _strip_prefix(text: str, prefix: str, case_insensitive: bool) -> str | None:
    """The remainder after ``prefix`` (``""`` or ``/...``) when ``text`` is under it, else None."""
    head, tail = text[: len(prefix)], text[len(prefix):]
    same = head.lower() == prefix.lower() if case_insensitive else head == prefix
    if same and (tail == "" or tail.startswith("/") or prefix.endswith("/")):
        return tail
    return None
