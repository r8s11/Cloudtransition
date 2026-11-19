"""HTTP boundaries and local-write regressions for the Calendar integration."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app
from core import config
from core.tasks import parse_tasks_from_file


@pytest.fixture
def calendar_workspace(tmp_path, monkeypatch):
    tasks = tmp_path / "TASKS.md"
    tasks.write_text("# Tasks\n\n## Inbox\n- [ ] Existing task\n")
    jobs = tmp_path / "interviews" / "job-applications.yml"
    jobs.parent.mkdir()
    jobs.write_text("active_applications: []\n")
    realms = [{"id": "tasks", "name": "Tasks", "file": "TASKS.md", "color": "#b3212e", "icon": ""}]
    monkeypatch.setattr(config, "WORKSPACE", tmp_path)
    monkeypatch.setattr(config, "TASKS_FILE", tasks)
    monkeypatch.setattr(config, "JOBS_FILE", jobs)
    monkeypatch.setattr(config, "REALMS", realms)
    return TestClient(app.app), tasks


HEADERS = {"X-Requested-With": "XMLHttpRequest"}


def test_schedule_sources_http(calendar_workspace):
    client, tasks = calendar_workspace
    reply = client.post("/api/capture", json={"text": "Prepare résumé", "schedule": {"date": "2026-11-16"}}, headers=HEADERS)
    assert reply.status_code == 200
    item = reply.json()
    assert item["text"] == "Prepare résumé"
    assert "<!-- calendar:" in tasks.read_text()
    parsed = app.parse_tasks_from_file(tasks, "tasks")
    added = next(row for row in parsed if row["text"] == "Prepare résumé")
    assert added["schedule"] == {"date": "2026-11-16"}
    tasks.write_text("\n" + tasks.read_text())
    toggled = client.post("/api/tasks/toggle", json={"realm": "tasks", "line": item["line"], "text": item["raw_text"], "done": True}, headers=HEADERS)
    assert toggled.status_code == 200
    assert "- [x] Prepare résumé <!-- calendar:" in tasks.read_text()
    saved = next(t for t in app.parse_tasks_from_file(tasks, "tasks") if t["raw_text"] == item["raw_text"])
    assert (saved["text"], saved["done"], saved["schedule"]) == ("Prepare résumé", True, {"date": "2026-11-16"})


def test_schedule_sources_local_capture(calendar_workspace):
    client, tasks = calendar_workspace
    reply = client.post("/api/capture", json={"text": "Undated stays local"}, headers=HEADERS)
    assert reply.status_code == 200
    assert "Undated stays local\n" in tasks.read_text()
    assert reply.json()["schedule"] == {}
    assert "<!-- calendar:" not in tasks.read_text()


def test_authorization_http(calendar_workspace, monkeypatch):
    client, tasks = calendar_workspace
    class Service:
        def snapshot(self):
            return {"enabled": False, "connection": {"calendar": "disconnected"}}
        def pause(self):
            raise AssertionError("Unauthorized call reached service")
    monkeypatch.setattr(app, "calendar_service", Service())
    before = tasks.read_bytes()
    assert client.get("/api/calendar").json()["enabled"] is False
    assert client.get("/api/calendar/pause").status_code == 405
    assert client.post("/api/calendar/pause", json={}).status_code == 403
    assert client.post("/api/calendar/pause", json={}, headers={**HEADERS, "Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/calendar/schedule", json={"source": "../../private", "line": 4, "text": "Existing task", "schedule": {"date": "2026-11-16"}}, headers=HEADERS).status_code == 400
    assert tasks.read_bytes() == before


def test_schedule_privacy_http(calendar_workspace):
    client, tasks = calendar_workspace
    before = tasks.read_bytes()
    invalid = [
        {"date": "2026-02-30"},
        {"start": "2026-11-16T10:00", "timezone": "America/New_York"},
        {"start": "2026-11-01T01:30", "end": "2026-11-01T02:30", "timezone": "America/New_York"},
    ]
    for schedule in invalid:
        reply = client.post("/api/capture", json={"text": "Must not save", "schedule": schedule}, headers=HEADERS)
        assert reply.status_code == 400
        assert tasks.read_bytes() == before


def test_schedule_sources_unrelated_ambiguous_application(calendar_workspace):
    from core import calendar_sources as sources
    _, tasks = calendar_workspace
    jobs = config.JOBS_FILE
    valid = 'active_applications:\n  - company: Valid\n    role: Engineer\n    next_steps:\n      - task: First action\n        date: 2026-11-16\n'
    ambiguous = '  - company: Ambiguous\n    role: Engineer\n    next_steps: []\n    next_steps:\n      - task: Must not send\n        date: 2026-11-17\n'
    jobs.write_text(valid + ambiguous)
    items = sources.collect(config.WORKSPACE, config.REALMS, jobs, ["interviews"])
    assert [item["title"] for item in items] == ["First action"]
    updated = sources.edit_first_action(valid + ambiguous, "Valid", "Engineer", "Changed first action", "2026-11-18")
    assert updated.endswith(ambiguous)
    assert 'task: \"Changed first action\"' in updated
