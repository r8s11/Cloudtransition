"""Today's links to TASKS.md projects, agentic-os and the second brain."""

import io
import json
import urllib.request
from datetime import date

from core import config
from core.today import brain_summary, live_projects, mission_control_summary


def task(cat, done=False, text="t", realm="tasks"):
    return {"cat": cat, "done": done, "text": text, "realm": realm}


def test_live_projects_are_the_project_lane_sections_of_tasks_md():
    tasks = {
        "all": [
            task("IT Mgmt Playbook (project block — Week A)", done=True),
            task("IT Mgmt Playbook (project block — Week A)", text="commit"),
            task("Monetization — playbook → income"),  # income lane, not a project
            task("Week B slot — Bogatyr (project absent)", text="phase 2"),
            task("DevOps block — automation builds (weekly)"),
            task("DevOps phase 1", realm="devops"),  # another file's realm
            task("Debt plan"),
        ]
    }
    rows = app.live_projects(tasks, date(2026, 11, 12))  # ISO week 46: Week B

    assert [(r["name"].split(" ")[0], r["when"]) for r in rows] == [
        ("IT", "Next week"),
        ("Week", "This week"),
        ("DevOps", "Every week"),
    ]
    playbook = rows[0]
    assert (playbook["done"], playbook["total"], playbook["pct"]) == (1, 2, 50)
    assert playbook["next"] == "commit"


def test_mission_control_counts_only_what_needs_attention(monkeypatch):
    replies = {
        "missions": [{"status": "running"}, {"status": "completed"}, "junk"],
        "approvals": [{"status": "pending"}, {"status": "approved"}],
        "runs?active=true": [{"id": "r1"}],
    }

    def fake_urlopen(url, timeout):
        return io.BytesIO(json.dumps(replies[url.split("/api/")[1]]).encode())

    monkeypatch.setattr(app.urllib.request, "urlopen", fake_urlopen)
    assert app.mission_control_summary() == {
        "ok": True,
        "missions": 1,
        "approvals": 1,
        "runs": 1,
    }


def test_mission_control_offline_or_garbled_is_a_state_not_a_crash(monkeypatch):
    def refused(url, timeout):
        raise ConnectionRefusedError

    monkeypatch.setattr(app.urllib.request, "urlopen", refused)
    assert app.mission_control_summary() == {"ok": False}

    monkeypatch.setattr(
        app.urllib.request, "urlopen", lambda url, timeout: io.BytesIO(b"<html>")
    )
    assert app.mission_control_summary() == {"ok": False}


def test_brain_summary_reads_the_catalogue_header(monkeypatch, tmp_path):
    catalogue = tmp_path / "catalogue.md"
    catalogue.write_text("# Catalogue\n\nSources: 200 · Memories: 63\n", "utf-8")
    monkeypatch.setattr(config, "BRAIN_CATALOGUE", catalogue)
    summary = app.brain_summary()
    assert (summary["ok"], summary["sources"], summary["memories"]) == (True, 200, 63)

    monkeypatch.setattr(config, "BRAIN_CATALOGUE", tmp_path / "missing.md")
    assert app.brain_summary() == {"ok": False}
