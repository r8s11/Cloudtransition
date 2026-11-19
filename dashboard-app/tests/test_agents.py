"""The Agents tab reads the workspace files; every missing or bad file is an
explicit empty state, never an invented agent, event or job."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import agents


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    defs = tmp_path / ".opencode" / "agents"
    state = tmp_path / "workspace" / "agents"
    outputs = state / "scout" / "outputs"
    defs.mkdir(parents=True)
    outputs.mkdir(parents=True)
    monkeypatch.setattr(agents, "WORKSPACE", tmp_path)
    monkeypatch.setattr(agents, "AGENT_STATE", state)
    monkeypatch.setattr(agents, "SCOUT_OUTPUTS", outputs)
    monkeypatch.setattr(agents, "HUB_CONFIG", tmp_path / "agentic-os" / "config" / "agentic-os.yaml")
    return tmp_path


def _agent(defs, slug, description="d", mode="subagent", name=None):
    body = f"Your name is {name or slug.title()}."
    (defs / f"{slug}.md").write_text(
        f"---\ndescription: {description}\nmode: {mode}\n---\n{body}\n"
    )


def _write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _by_slug(result):
    return {a["slug"]: a for a in result["agents"]}


def test_discovery_orders_known_agents_first_and_keeps_every_other(workspace):
    defs = workspace / ".opencode" / "agents"
    for slug in ("cv-adapter", "scout", "helper", "forge", "job-reader"):
        _agent(defs, slug)

    slugs = [a["slug"] for a in agents.discover_agents()["agents"]]

    assert slugs == ["forge", "scout", "job-reader", "cv-adapter", "helper"]


def test_discovery_spans_every_folder_with_stem_ids(workspace):
    _agent(workspace / ".opencode" / "agents", "mentor", name="Mentor")
    _write(workspace, ".claude/agents/mentor.md", "---\nname: Mentor\n---\nYour name is Mentor.\n")
    _write(
        workspace,
        ".codex/agents/mentor.toml",
        'name = "Mentor"\ndescription = "d"\ndeveloper_instructions = "Your name is Mentor."\n',
    )
    _write(workspace, "dashboard-app/.claude/agents/only-here.md", "---\nname: Only Here\n---\nBody.\n")
    _write(workspace, "dashboard-app/.github/agents/copilot.agent.md", "Body.\n")

    found = _by_slug(agents.discover_agents())

    assert set(found) >= {"mentor", "only-here", "copilot"}
    mentor = found["mentor"]
    assert [c["folder"] for c in mentor["copies"]] == [".opencode/agents", ".claude/agents", ".codex/agents"]
    assert mentor["displayed"]["path"] == ".opencode/agents/mentor.md"
    assert len(mentor["versions"]) == 1, "same text in .md and .toml is one version"
    assert mentor["loadable"] == "active"
    assert found["only-here"]["name"] == "Only Here"
    assert found["only-here"]["loadable"] == "scoped"
    assert found["copilot"]["loadable"] == "unverified"


def test_precedence_is_fixed_even_when_a_lower_copy_is_newer(workspace):
    import os

    old = _write(workspace, ".opencode/agents/m.md", "# M\nOld line.\n")
    new = _write(workspace, ".claude/agents/m.md", "# M\nOld line.\n## Memory\nNew line.\n")
    os.utime(old, (1_000_000, 1_000_000))
    os.utime(new, (2_000_000_000, 2_000_000_000))

    for _ in range(2):
        agent = _by_slug(agents.discover_agents())["m"]
        assert agent["displayed"]["path"] == ".opencode/agents/m.md"
    assert len(agent["versions"]) == 2
    newer = next(v for v in agent["versions"] if not v["displayed"])
    assert newer["paths"] == [".claude/agents/m.md"]
    assert newer["extra_lines"] == 2
    assert newer["extra_headings"] == ["Memory"]
    assert any("Newer copy .claude/agents/m.md" in w and "Memory" in w for w in agent["warnings"])


def test_invalid_metadata_is_reported_not_dropped(workspace):
    _write(workspace, ".opencode/agents/broken.md", "---\ndescription: [unclosed\n---\nYour name is Broken.\n")
    _write(workspace, ".codex/agents/bad.toml", "name = \n")
    _write(workspace, ".codex/agents/thin.toml", 'name = "Thin"\n')
    _write(workspace, "dashboard-app/.github/agents/plain.md", "Body.\n")

    found = _by_slug(agents.discover_agents())

    assert found["broken"]["name"] == "Broken"
    assert any("not valid YAML" in w for w in found["broken"]["warnings"])
    assert any("not valid TOML" in w for w in found["bad"]["warnings"])
    assert found["bad"]["loadable"] == "unverified"
    assert any("lacks description, developer_instructions" in w for w in found["thin"]["warnings"])
    assert found["thin"]["loadable"] == "unverified"
    assert any(".agent.md suffix" in w for w in found["plain"]["warnings"])


def test_codex_capitalisation_is_flagged(workspace):
    _write(
        workspace,
        ".codex/agents/a.toml",
        'name = "a"\ndescription = "d"\ndeveloper_instructions = "Read .Codex/skills/x."\n',
    )
    agent = _by_slug(agents.discover_agents())["a"]
    assert any(".Codex/ (capital C)" in w for w in agent["warnings"])


def test_missing_folders_warn_and_create_nothing(workspace):
    before = sorted(p.relative_to(workspace) for p in workspace.rglob("*"))

    result = agents.discover_agents()

    assert any(".claude/agents/ is missing" in w for w in result["warnings"])
    assert any("agentic-os.yaml not found" in w for w in result["warnings"])
    assert sorted(p.relative_to(workspace) for p in workspace.rglob("*")) == before


def test_unavailable_workspace_is_one_clear_warning(workspace, monkeypatch):
    gone = workspace / "unmounted"
    monkeypatch.setattr(agents, "WORKSPACE", gone)

    result = agents.discover_agents()

    assert result["agents"] == []
    assert "is not available" in result["warnings"][0]
    assert not gone.exists()


def test_memory_and_outputs_are_associated_by_id(workspace):
    import os

    _agent(workspace / ".opencode" / "agents", "scout")
    _agent(workspace / ".opencode" / "agents", "mentor")
    state = workspace / "workspace" / "agents"
    _write(state, "scout/memory/index.md", "# Scout\n")
    _write(state, "scout/memory/log.jsonl", '{"event": "a"}\n\n{"event": "b"}\n')
    old = _write(state, "scout/outputs/old.json", "{}")
    _write(state, "scout/outputs/new.md", "x")
    os.utime(old, (1_000_000, 1_000_000))
    _write(state, "mentor/memory/index.md", "private\n")

    view = agents.build_agents_view()
    found = {a["slug"]: a for a in view["agents"]}

    scout = found["scout"]["state"]
    assert scout["memory_index"]["path"] == "workspace/agents/scout/memory/index.md"
    assert scout["memory_log"]["entries"] == 2
    assert [f["name"] for f in scout["outputs"]] == ["new.md", "old.json"]
    assert found["scout"]["summary"] == "# Scout"
    assert found["mentor"]["state"]["memory_index"] is not None
    assert "summary" not in found["mentor"], "non-team memory stays metadata-only"


def test_agent_without_state_is_uninitialized_not_invented(workspace):
    _agent(workspace / ".opencode" / "agents", "helper")
    agent = _by_slug(agents.discover_agents())["helper"]
    assert agent["state"]["exists"] is False
    assert agent["state"]["memory_index"] is None
    assert agent["state"]["outputs"] == []
    assert not (workspace / "workspace" / "agents" / "helper").exists()


def test_hub_discrepancies_are_reported(workspace):
    _agent(workspace / ".opencode" / "agents", "chief")
    _agent(workspace / ".opencode" / "agents", "loose")
    (workspace / "workspace" / "agents" / "ghost-hub").mkdir(parents=True)
    _write(
        workspace,
        "agentic-os/config/agentic-os.yaml",
        "hub:\n  agents:\n"
        "    chief:\n      installed: true\n      memoryDir: workspace/agents/chief-of-staff/memory\n"
        "    ghost:\n      installed: false\n      memoryDir: workspace/agents/ghost/memory\n",
    )

    found = _by_slug(agents.discover_agents())

    chief = found["chief"]
    assert chief["registered"] and chief["hub"]["installed"] is True
    assert any("memoryDir is workspace/agents/chief-of-staff/memory, not workspace/agents/chief/memory" in w for w in chief["warnings"])
    assert any("does not exist" in w for w in chief["warnings"])
    assert found["loose"]["registered"] is False
    assert found["ghost"]["discovered"] is False
    assert any("no definition file was found" in w for w in found["ghost"]["warnings"])
    assert any("no definition and no hub entry" in w for w in found["ghost-hub"]["warnings"])


def test_load_memory_missing_is_empty(workspace):
    assert agents.load_memory("scout") == {
        "summary": "",
        "summary_missing": True,
        "events": [],
        "events_error": None,
    }


def test_load_memory_returns_newest_events_and_skips_bad_lines(workspace):
    memory = workspace / "workspace" / "agents" / "scout" / "memory"
    memory.mkdir(parents=True)
    (memory / "index.md").write_text("# Scout\n\nKnown.\n")
    (memory / "log.jsonl").write_text(
        '{"ts":"1","event":"one","detail":"a"}\n'
        "not json\n"
        '{"ts":"2","event":"two","summary":"b"}\n'
        '{"ts":"3","type":"three","notes":"c"}\n'
    )

    view = agents.load_memory("scout")

    assert view["summary"] == "# Scout\n\nKnown."
    assert view["summary_missing"] is False
    assert [e["event"] for e in view["events"]] == ["three", "two", "one"]
    assert view["events"][0] == {"when": "3", "event": "three", "detail": "c"}
    assert view["events_error"] is None


def test_load_memory_reports_a_log_with_no_valid_events(workspace):
    memory = workspace / "workspace" / "agents" / "scout" / "memory"
    memory.mkdir(parents=True)
    (memory / "log.jsonl").write_text("not json\n[]\n")

    view = agents.load_memory("scout")

    assert view["events"] == []
    assert "no valid json" in view["events_error"].lower()


def test_load_memory_caps_events(workspace):
    memory = workspace / "workspace" / "agents" / "scout" / "memory"
    memory.mkdir(parents=True)
    (memory / "log.jsonl").write_text(
        "\n".join(
            json.dumps({"ts": str(i), "event": f"e{i}"}) for i in range(7)
        )
        + "\n"
    )

    view = agents.load_memory("scout")

    assert [e["event"] for e in view["events"]] == ["e6", "e5", "e4", "e3", "e2"]


def _scan(path, jobs, scan_id="scan-1"):
    path.write_text(
        json.dumps(
            {
                "scan_id": scan_id,
                "generated_at": "2026-11-09T18:00:00Z",
                "jobs": jobs,
            }
        )
    )


def test_load_latest_scan_sorts_by_score_and_counts_tracks(workspace):
    outputs = workspace / "workspace" / "agents" / "scout" / "outputs"
    _scan(
        outputs / "scan-2026-11-09.json",
        [
            {"job_id": "low", "title": "Low", "score": 10, "track": "secondary"},
            {"job_id": "none", "title": "None", "track": "primary"},
            {"job_id": "high", "title": "High", "score": 90, "track": "primary"},
        ],
    )
    (outputs / "scan-2026-11-09.md").write_text("# scan")

    view = agents.load_latest_scan()

    assert view["error"] is None
    assert view["scan"]["scan_id"] == "scan-1"
    assert [j["job_id"] for j in view["scan"]["jobs"]] == ["high", "low", "none"]
    assert view["scan"]["job_count"] == 3
    assert view["scan"]["primary_count"] == 2
    assert view["scan"]["secondary_count"] == 1
    assert view["files"] == {
        "json": "workspace/agents/scout/outputs/scan-2026-11-09.json",
        "markdown": "workspace/agents/scout/outputs/scan-2026-11-09.md",
    }


def test_load_latest_scan_falls_back_to_an_older_valid_file(workspace):
    outputs = workspace / "workspace" / "agents" / "scout" / "outputs"
    _scan(outputs / "scan-2026-11-08.json", [{"job_id": "old", "score": 1}])
    (outputs / "scan-2026-11-09.json").write_text("{bad")

    view = agents.load_latest_scan()

    assert view["error"] is None
    assert view["scan"]["jobs"][0]["job_id"] == "old"


def test_load_latest_scan_missing_is_explicit(workspace):
    view = agents.load_latest_scan()
    assert view["scan"] is None
    assert view["files"] == {}
    assert "No Scout scan yet" in view["error"]


def test_load_latest_scan_unreadable_is_explicit(workspace):
    outputs = workspace / "workspace" / "agents" / "scout" / "outputs"
    (outputs / "scan-2026-11-09.json").write_text('{"jobs": null}')

    view = agents.load_latest_scan()

    assert view["scan"] is None
    assert "unreadable" in view["error"].lower()


def test_build_agents_view_contract(workspace):
    view = agents.build_agents_view()
    assert set(view) == {
        "agents",
        "agent_events",
        "agent_registry",
        "agent_scan",
        "agent_scan_files",
        "agent_scan_error",
    }
    # The fixture holds only a scout state folder: shown, flagged, never invented.
    assert [a["slug"] for a in view["agents"]] == ["scout"]
    assert view["agents"][0]["discovered"] is False
    assert view["agent_events"] == {"scout": []}
    assert view["agent_registry"]["counts"]["discovered"] == 0
    assert view["agent_scan"] is None
    assert view["agent_scan_files"] == {}
    assert "No Scout scan yet" in view["agent_scan_error"]


def test_build_context_includes_agents_view(monkeypatch):
    import app as dashboard

    marker = {
        "agents": [{"slug": "forge"}],
        "agent_events": {"forge": []},
        "agent_scan": None,
        "agent_scan_files": {},
        "agent_scan_error": "No Scout scan yet.",
    }
    monkeypatch.setattr(dashboard, "build_agents_view", lambda: marker)

    ctx = dashboard.build_context()

    for key, value in marker.items():
        assert ctx[key] == value

def test_load_memory_derives_detail_from_a_score_outcome_event(workspace):
    """Real Scout logs record title/company/score, not detail/summary/notes/result."""
    memory = workspace / "workspace" / "agents" / "scout" / "memory"
    memory.mkdir(parents=True)
    event = {
        "ts": "2026-11-09T18:00:00Z",
        "type": "score_outcome",
        "agent": "scout",
        "job_id": "desktop-support-technician-lincolnit",
        "title": "Desktop Support Technician",
        "company": "LincolnIT",
        "score": 85,
        "surfaced": True,
    }
    (memory / "log.jsonl").write_text(json.dumps(event) + "\n")

    view = agents.load_memory("scout")

    detail = view["events"][0]["detail"]
    assert detail is not None
    assert "Desktop Support Technician" in detail
    assert "LincolnIT" in detail
    assert "85" in detail


def test_load_latest_scan_survives_a_stat_error(workspace, monkeypatch):
    """A dangling symlink or vanished file must not 500 every dashboard tab."""
    outputs = workspace / "workspace" / "agents" / "scout" / "outputs"
    _scan(outputs / "scan-2026-11-09.json", [{"job_id": "kept", "score": 5}])

    real_stat = Path.stat

    def flaky_stat(self, *args, **kwargs):
        if self.name.startswith("scan-") and self.suffix == ".json":
            raise OSError("stat failed")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", flaky_stat)

    view = agents.load_latest_scan()

    assert view["error"] is None
    assert view["scan"]["jobs"][0]["job_id"] == "kept"
