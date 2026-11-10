"""The Agents tab reads the workspace files; every missing or bad file is an
explicit empty state, never an invented agent, event or job."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agents


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    defs = tmp_path / ".opencode" / "agents"
    state = tmp_path / "workspace" / "agents"
    outputs = state / "scout" / "outputs"
    defs.mkdir(parents=True)
    outputs.mkdir(parents=True)
    monkeypatch.setattr(agents, "WORKSPACE", tmp_path)
    monkeypatch.setattr(agents, "AGENT_DEFS", defs)
    monkeypatch.setattr(agents, "AGENT_STATE", state)
    monkeypatch.setattr(agents, "SCOUT_OUTPUTS", outputs)
    return tmp_path


def _agent(defs, slug, description="d", mode="subagent", name=None):
    body = f"Your name is {name or slug.title()}."
    (defs / f"{slug}.md").write_text(
        f"---\ndescription: {description}\nmode: {mode}\n---\n{body}\n"
    )


def test_load_roster_orders_known_agents_and_appends_unknown(workspace):
    defs = workspace / ".opencode" / "agents"
    _agent(defs, "cv-adapter", name="CV Adapter")
    _agent(defs, "scout", name="Scout")
    _agent(defs, "helper", mode="all", name="Helper")
    _agent(defs, "forge", mode="all", name="Forge")
    _agent(defs, "job-reader", name="Job Reader")

    roster = agents.load_roster()

    assert [a["slug"] for a in roster] == [
        "forge",
        "scout",
        "job-reader",
        "cv-adapter",
        "helper",
    ]
    assert roster[0] == {
        "slug": "forge",
        "name": "Forge",
        "mode": "all",
        "description": "d",
        "definition": ".opencode/agents/forge.md",
    }


def test_load_roster_missing_directory_is_empty(workspace, monkeypatch):
    monkeypatch.setattr(agents, "AGENT_DEFS", workspace / "missing")
    assert agents.load_roster() == []


def test_load_roster_tolerates_bad_frontmatter(workspace):
    defs = workspace / ".opencode" / "agents"
    (defs / "broken.md").write_text(
        "---\ndescription: [unclosed\n---\nYour name is Broken.\n"
    )
    roster = agents.load_roster()
    assert roster[0]["slug"] == "broken"
    assert roster[0]["name"] == "Broken"
    assert roster[0]["description"] == ""
    assert roster[0]["mode"] == ""


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
        "agent_scan",
        "agent_scan_files",
        "agent_scan_error",
    }
    assert view["agents"] == []
    assert view["agent_events"] == {}
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
