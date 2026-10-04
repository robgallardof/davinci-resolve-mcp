"""The portable agent layer (AGENTS.md, .agents/skills, .agents/agents, generated docs) stays consistent."""

import re
from pathlib import Path

import pytest

from resolve_forge.domain import formats

ROOT = Path(__file__).resolve().parents[4]
SKILLS = ROOT / ".agents" / "skills"
AGENTS = ROOT / ".agents" / "agents"


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, f"{path} has no frontmatter"
    fm = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip().strip('"')
    return fm


def test_every_skill_follows_the_open_standard():
    names = []
    for skill in sorted(SKILLS.iterdir()):
        fm = _frontmatter(skill / "SKILL.md")
        assert fm["name"] == skill.name, "name must match the folder (agentskills.io)"
        assert re.fullmatch(r"[a-z0-9-]{1,64}", fm["name"])
        assert 50 < len(fm["description"]) <= 1024
        names.append(skill.name)
    assert {"davinci-resolve-mcp", "vertical-video", "horizontal-video",
            "dynamic-zoom-talking-head", "resolve-delivery", "editorial-direction", "entertainment-pacing", "video-qa",
            "color-audio-finishing", "captions-and-titles"} <= set(names)


def test_agents_exist_and_only_reference_real_skills():
    skills = {p.name for p in SKILLS.iterdir()}
    agents = {p.stem: p.read_text(encoding="utf-8") for p in AGENTS.glob("*.md")}
    assert {"vertical-editor", "horizontal-editor", "video-director"} <= set(agents)
    for name, text in agents.items():
        assert _frontmatter(AGENTS / f"{name}.md")["name"] == name
        for ref in re.findall(r"`([a-z0-9-]+)`", text):
            if ref.endswith(("-video", "-mcp", "-delivery", "-head", "-direction", "-pacing", "-qa", "-finishing", "-titles")):
                assert ref in skills, f"{name} references missing skill {ref}"


def test_vertical_and_horizontal_agents_cover_every_format():
    vertical = (AGENTS / "vertical-editor.md").read_text(encoding="utf-8").lower()
    horizontal = (AGENTS / "horizontal-editor.md").read_text(encoding="utf-8").lower()
    for word in ("tiktok", "reels", "facebook", "shorts", "stories", "snapchat", "4:5"):
        assert word in vertical
    for word in ("youtube", "facebook", "linkedin", "x,", "web"):
        assert word in horizontal


def test_platform_reference_is_generated_from_code():
    doc = SKILLS / "resolve-delivery" / "references" / "platforms.md"
    if not doc.exists():
        pytest.skip("run python scripts/sync.py")
    assert formats.markdown_table() in doc.read_text(encoding="utf-8"), "run python scripts/sync.py"


def test_claude_code_sees_the_same_files():
    for kind in ("skills", "agents"):
        link = ROOT / ".claude" / kind
        if not link.exists():
            pytest.skip("run python scripts/sync.py")
        assert sorted(p.name for p in link.iterdir()) == sorted(p.name for p in (ROOT / ".agents" / kind).iterdir())


def test_entry_docs_exist():
    for doc in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md", "docs/FIRST-STEPS.md", "docs/mcp-reviews.md"):
        assert (ROOT / doc).is_file(), doc


def test_native_tools_have_no_external_runtime():
    import json
    repos = json.loads((ROOT / "config" / "mcp.servers.json").read_text(encoding="utf-8"))["servers"]
    assert set(repos) == {"resolve-forge"}
    package = ROOT / "mcp/resolve-forge/src/resolve_forge"
    assert not list((package / "api").rglob("*.py"))
    for source in package.rglob("*.py"):
        assert "resolve_forge.api" not in source.read_text(encoding="utf-8")
    assert not (ROOT / "scripts/references.py").exists()
    assert not (ROOT / "config/references.json").exists()
    assert "vendor/" not in (ROOT / "mcp/resolve-forge/src/resolve_forge/gateway.py").read_text(encoding="utf-8")


def test_docs_list_every_registered_tool_and_the_real_count():
    """README and the Resolve skill stay in sync with the server: no missing tools, no stale counts."""
    import asyncio

    from mcp.server.fastmcp import FastMCP
    from resolve_forge import tools
    from resolve_forge.gateway import Session
    mcp = FastMCP("docs")
    tools.register(mcp, Session([]))
    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert not {name for name in names if name not in readme}, "README tool table is missing tools"
    for doc in ("README.md", "docs/install.md", "docs/architecture.md", "docs/third-party-migration.md",
                ".agents/skills/davinci-resolve-mcp/SKILL.md"):
        counts = {int(n) for n in re.findall(r"(\d+) (?:tools|herramientas)\b", (ROOT / doc).read_text(encoding="utf-8"))}
        assert counts <= {len(names)}, f"{doc} mentions {counts}, server has {len(names)}"
