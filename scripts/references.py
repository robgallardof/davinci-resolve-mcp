"""Fetch, patch and test the third-party DaVinci Resolve MCPs listed in config/references.json.

Each repo is fetched at its pinned `base` commit into vendor/<dir>; our improvements live as
`git format-patch` files in patches/<dir>/ and are applied on top with `git am` (authorship
kept), so they stay reviewable, reproducible and ready to send upstream as pull requests.

    python scripts/references.py status            # what is present / patched
    python scripts/references.py fetch [dir ...]   # clone at base + apply patches (idempotent)
    python scripts/references.py test  [dir ...]   # run each repo's tests (incl. ours)
    python scripts/references.py export [dir ...]  # vendor/<dir> commits after base -> patches/<dir>/
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = Path(os.environ.get("REFERENCES_VENDOR_DIR", ROOT / "vendor"))  # override: dry runs in a temp dir
PATCHES = ROOT / "patches"
# git am records the patch author; the committer of the local copy is just this tool.
COMMITTER = {"GIT_COMMITTER_NAME": "references.py", "GIT_COMMITTER_EMAIL": "references@localhost"}


def load(selected: list[str]) -> list[dict]:
    repos = json.loads((ROOT / "config" / "references.json").read_text(encoding="utf-8"))["repos"]
    unknown = set(selected) - {r["dir"] for r in repos}
    if unknown:
        sys.exit(f"unknown repo(s): {', '.join(sorted(unknown))}")
    return [r for r in repos if not selected or r["dir"] in selected]


def git(path: Path, *args: str, check: bool = True, env: dict | None = None) -> str:
    out = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, encoding="utf-8",
                         env={**os.environ, **(env or {})})
    if check and out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {path.name}: {out.stderr.strip()}")
    return out.stdout.strip()


def patch_files(repo: dict) -> list[Path]:
    return sorted((PATCHES / repo["dir"]).glob("*.patch"))


def patch_subject(path: Path) -> str:
    """The commit subject, unfolding RFC 2822 continuation lines (long subjects wrap)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("Subject: "):
            parts = [line.removeprefix("Subject: ")]
            for cont in lines[i + 1:]:
                if not cont.startswith((" ", "\t")):
                    break
                parts.append(cont.strip())
            return " ".join(parts).removeprefix("[PATCH] ").strip()
    return path.stem


def applied_subjects(path: Path, base: str) -> set[str]:
    try:
        return set(git(path, "log", "--format=%s", f"{base}..HEAD").splitlines())
    except RuntimeError:
        return set()


def fetch(repo: dict) -> str:
    path = VENDOR / repo["dir"]
    if not (path / ".git").exists():
        path.mkdir(parents=True, exist_ok=True)
        git(path, "init", "-q")
        git(path, "remote", "add", "origin", repo["url"])
        git(path, "fetch", "-q", "--depth", "1", "origin", repo["base"])
        git(path, "checkout", "-q", "-B", "forge", "FETCH_HEAD")
    if not git(path, "cat-file", "-t", repo["base"], check=False):
        return f"{repo['dir']}: base {repo['base'][:8]} is not in this clone; left untouched"
    done = applied_subjects(path, repo["base"])
    pending = [p for p in patch_files(repo) if patch_subject(p) not in done]
    for p in pending:
        try:
            git(path, "am", "-q", "--3way", "--keep-cr", str(p), env=COMMITTER)
        except RuntimeError as exc:
            git(path, "am", "--abort", check=False)
            return f"{repo['dir']}: could not apply {p.name}: {exc}"
    return f"{repo['dir']}: ok ({len(pending)} applied, {len(patch_files(repo)) - len(pending)} already present)"


def export(repo: dict) -> str:
    path = VENDOR / repo["dir"]
    count = int(git(path, "rev-list", "--count", f"{repo['base']}..HEAD") or 0)
    out = PATCHES / repo["dir"]
    shutil.rmtree(out, ignore_errors=True)
    if count == 0:
        return f"{repo['dir']}: no commits after base"
    out.mkdir(parents=True)
    git(path, "format-patch", "-q", "--zero-commit", "--no-signature", "-o", str(out), f"{repo['base']}..HEAD")
    return f"{repo['dir']}: exported {count} patch(es)"


def test(repo: dict) -> tuple[str, bool]:
    if not repo.get("test"):
        return f"{repo['dir']}: no test command (review only)", True
    path = VENDOR / repo["dir"]
    if not path.exists():
        return f"{repo['dir']}: not fetched", False
    proc = subprocess.run(repo["test"], cwd=path, capture_output=True, text=True, encoding="utf-8", errors="replace")
    last = (proc.stdout.strip().splitlines() or proc.stderr.strip().splitlines() or ["?"])[-1]
    return f"{repo['dir']}: {'PASS' if proc.returncode == 0 else 'FAIL'} - {last}", proc.returncode == 0


def status(repo: dict) -> str:
    path = VENDOR / repo["dir"]
    if not (path / ".git").exists():
        return f"{repo['dir']}: missing (run fetch)"
    done = applied_subjects(path, repo["base"])
    patches = patch_files(repo)
    applied = sum(patch_subject(p) in done for p in patches)
    return f"{repo['dir']}: {applied}/{len(patches)} patches applied, HEAD {git(path, 'rev-parse', '--short', 'HEAD')}"


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("status", "fetch", "test", "export"):
        print(__doc__)
        return 2
    command, repos = argv[0], load(argv[1:])
    ok = True
    for repo in repos:
        if command == "test":
            line, passed = test(repo)
            ok &= passed
        else:
            line = {"status": status, "fetch": fetch, "export": export}[command](repo)
            ok &= "could not" not in line
        print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
