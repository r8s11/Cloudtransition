"""The Skill Registry mirrors OpenCode 2.3's documented skill discovery and
precedence, reports bad definitions, and derives agent access only from each
agent's resolved `skill` rules. It writes nothing and assigns nothing."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient  # noqa: E402

import app as module  # noqa: E402
from core import agents, skills  # noqa: E402


@pytest.fixture
def homes(tmp_path, monkeypatch):
    home, ws = tmp_path / "home", tmp_path / "ws"
    home.mkdir()
    ws.mkdir()
    monkeypatch.setattr(skills, "HOME", home)
    monkeypatch.setattr(agents, "WORKSPACE", ws)
    return home, ws


def _skill(root, rel, description="Use it.", body="Do the thing.", extra=""):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = f"description: {description}\n" if description is not None else ""
    path.write_text(f"---\n{fm}{extra}---\n{body}\n")
    return path


def _by_id(result):
    return {s["id"]: s for s in result["skills"]}


def test_discovery_follows_opencode_file_rules(homes):
    home, ws = homes
    src = ws / ".agents" / "skills"
    _skill(src, "flat.md")                                   # root-level Markdown -> id "flat"
    _skill(src, "grouped/team/release/SKILL.md")            # nested in grouping folders -> "release"
    _skill(src, "outer/SKILL.md")
    _skill(src, "outer/inner/SKILL.md")                      # inside another skill: ignored
    _skill(src, ".hidden/SKILL.md")
    _skill(src, "node_modules/pkg/SKILL.md")
    _skill(src, "a/b/c/d/e/f/deep/SKILL.md")                 # 7 levels down: past the search limit
    _skill(src, "a/b/c/d/e/six/SKILL.md")                    # 6 levels down: found
    (src / "notes.txt").write_text("not a skill")

    result = skills.discover_skills()
    found = _by_id(result)

    assert set(found) == {"flat", "release", "outer", "six"}
    assert found["release"]["loaded"]["path"] == ".agents/skills/grouped/team/release/SKILL.md"
    assert any("1 SKILL.md inside another skill are ignored" in w for w in result["warnings"])


def test_later_source_wins_and_conflicts_are_reported(homes):
    home, ws = homes
    _skill(ws, ".claude/skills/review/SKILL.md", body="Old review steps.")
    _skill(home, ".config/opencode/skills/review/SKILL.md", body="New review steps.")
    _skill(ws, ".agents/skills/same/SKILL.md")
    _skill(ws, ".opencode/skills/same/SKILL.md")

    found = _by_id(skills.discover_skills())

    review = found["review"]
    assert review["loaded"]["path"] == "~/.config/opencode/skills/review/SKILL.md"
    assert review["versions"] == 2
    assert any("different instructions" in w for w in review["warnings"])
    same = found["same"]
    assert same["loaded"]["path"] == ".opencode/skills/same/SKILL.md"
    assert any("same instructions" in w for w in same["warnings"])


def test_invalid_and_unadvertised_metadata_is_reported(homes):
    home, ws = homes
    src = ws / ".opencode" / "skills"
    (src / "broken").mkdir(parents=True)
    (src / "broken" / "SKILL.md").write_text("---\ndescription: [unclosed\n---\nBody\n")
    _skill(src, "silent/SKILL.md", description=None)
    _skill(src, "manual/SKILL.md", extra="disable-model-invocation: true\n")
    _skill(src, "override/SKILL.md", extra="disable-model-invocation: true\nmetadata:\n  opencode/autoinvoke: true\n")
    _skill(src, "Bad_Name/SKILL.md")
    _skill(src, "README.md")

    found = _by_id(skills.discover_skills())

    assert any("not valid YAML" in w for w in found["broken"]["warnings"])
    assert not found["silent"]["advertised"] and any("No description" in w for w in found["silent"]["warnings"])
    assert not found["manual"]["advertised"] and found["manual"]["warnings"] == []
    assert found["override"]["advertised"], "opencode/autoinvoke wins over disable-model-invocation"
    assert any("kebab-case" in w for w in found["Bad_Name"]["warnings"])
    assert any("looks like documentation" in w for w in found["README"]["warnings"])


def test_dashboard_app_sources_are_listed_but_not_registered(homes):
    home, ws = homes
    _skill(ws, "dashboard-app/.agents/skills/local-only/SKILL.md")
    found = _by_id(skills.discover_skills())
    assert found["local-only"]["registered"] is False
    assert any("Only in dashboard-app/" in w for w in found["local-only"]["warnings"])


def test_v1_skills_config_is_flagged(homes):
    home, ws = homes
    (ws / "opencode.json").write_text('{"skills": {"paths": [".claude/skills"]}}')
    assert any("V1 form" in w for w in skills.discover_skills()["warnings"])


def test_missing_workspace_is_reported(homes, monkeypatch):
    home, ws = homes
    monkeypatch.setattr(agents, "WORKSPACE", ws / "unmounted")
    result = skills.discover_skills()
    assert result["skills"] == [] and "not available" in result["warnings"][0]
    assert not (ws / "unmounted").exists()


# ── Agent access comes only from the agent's resolved `skill` rules ──

BASE = [{"action": "*", "resource": "*", "effect": "allow"}]


def _registry(homes):
    home, ws = homes
    src = ws / ".opencode" / "skills"
    _skill(src, "pdf/SKILL.md")
    _skill(src, "internal-notes/SKILL.md")
    _skill(src, "manual/SKILL.md", extra="disable-model-invocation: true\n")
    _skill(ws, ".claude/skills/clash/SKILL.md", body="A")
    _skill(src, "clash/SKILL.md", body="B")
    return skills.discover_skills()["skills"]


def test_matrix_uses_last_matching_skill_rule(homes):
    registry = _registry(homes)
    resolved = [
        {"id": "open", "permissions": BASE},
        {"id": "locked", "permissions": BASE + [{"action": "*", "resource": "*", "effect": "deny"}]},
        {"id": "mixed", "permissions": BASE + [
            {"action": "skill", "resource": "internal-*", "effect": "deny"},
            {"action": "skill", "resource": "pdf", "effect": "ask"},
        ]},
    ]

    rows = {r["agent"]: r for r in skills.agent_matrix(resolved, registry, ["open", "locked", "mixed", "claude-only"])}

    assert rows["open"]["access"] == {"pdf": "loadable", "internal-notes": "loadable", "manual": "hidden", "clash": "loadable"}
    assert set(rows["locked"]["access"].values()) == {"denied"}
    assert rows["mixed"]["access"]["internal-notes"] == "denied"
    assert rows["mixed"]["access"]["pdf"] == "ask"
    assert rows["claude-only"]["evaluated"] is False
    assert skills.approved_skills(rows["open"], registry) == ["internal-notes", "pdf"], "conflicting 'clash' is not approved"
    assert skills.approved_skills(rows["locked"], registry) == []


def test_no_opencode_answer_means_nothing_is_evaluated(homes):
    rows = skills.agent_matrix(None, _registry(homes), ["job-reader"])
    assert rows == [{"agent": "job-reader", "evaluated": False, "reason": "OpenCode did not answer."}]


def test_job_reader_definition_denies_every_skill():
    import yaml

    text = (module.WORKSPACE / ".opencode" / "agents" / "job-reader.md").read_text()
    rules = BASE + yaml.safe_load(text.split("---", 2)[1])["permissions"]
    for skill_id in ("pdf", "impeccable", "using-superpowers", "anything"):
        assert agents.permission_effect(rules, "skill", skill_id) == "deny"


def test_registry_page_renders_read_only(homes, monkeypatch):
    _registry(homes)
    monkeypatch.setattr(module, "_opencode_resolved_agents", lambda: [{"id": "forge", "permissions": BASE}])
    monkeypatch.setattr(module.forge_agents, "discover_agents",
                        lambda: {"agents": [{"slug": "forge", "discovered": True}]})
    with TestClient(module.app) as client:
        page = client.get("/agents/skills")
    assert page.status_code == 200
    assert "A skill grants nothing" in page.text
    assert 'id="skill-pdf"' in page.text
    assert "<form" not in page.text and "method=\"post\"" not in page.text.lower()
