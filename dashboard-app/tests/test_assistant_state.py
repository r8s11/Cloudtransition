"""GET /api/assistant/state: read-only live state for the bot/ assistant."""

from __future__ import annotations

import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as module  # noqa: E402

SECRET = "sk-test-DO-NOT-LEAK-1234567890"
EMAIL = "recruiter@example.com"


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    for realm in module.REALMS:
        target = tmp_path / realm["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# Lane\n\n- [ ] open item\n- [x] done item\n", encoding="utf-8")
    (tmp_path / ".env").write_text(f"API_KEY={SECRET}\n", encoding="utf-8")
    (tmp_path / "token.json").write_text(json.dumps({"token": SECRET}), encoding="utf-8")
    (tmp_path / "runs.log").write_text(
        json.dumps(
            {
                "timestamp": "2026-11-16T12:00:00-05:00",
                "id": "r1",
                "skill": "scout-scan",
                "status": "done",
                "command": f"opencode run --key {SECRET}",
                "output": "/tmp/out",
                "preview": SECRET,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    tracker = tmp_path / "interviews" / "job-applications.yml"
    tracker.parent.mkdir(parents=True, exist_ok=True)
    tracker.write_text(
        'active_applications:\n'
        '  - company: "Acme"\n    role: "Engineer"\n    status: "applied"\n'
        '    contacts:\n      - name: "R"\n        email: "%s"\n'
        '  - company: "Parked"\n    role: "Admin"\n    status: "waiting"\n'
        '  - company: "Fresh"\n    role: "Help"\n    status: "new_lead"\n'
        '  - company: "Gone"\n    role: "Desk"\n    status: "rejected"\n' % EMAIL,
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    monkeypatch.setattr(module, "JOBS_FILE", tracker)
    monkeypatch.setattr(module, "RUNS_LOG", tmp_path / "runs.log")
    return tmp_path


def fake_upstream(monkeypatch, payload=None, error=None):
    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def urlopen(url, timeout=None):
        if error:
            raise error
        return Resp(json.dumps(payload).encode())

    monkeypatch.setattr(module.urllib.request, "urlopen", urlopen)


def test_state_sections(workspace, monkeypatch):
    fake_upstream(monkeypatch, payload=[{"id": "m1", "title": "T", "status": "queued", "priority": "high"}])
    with TestClient(module.app) as client:
        r = client.get("/api/assistant/state")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"generated_at", "tasks", "interviews", "runs", "missions"}
    tasks = body["tasks"]
    assert tasks["source"] and len(tasks["realms"]) == len(module.REALMS)
    assert all(row["open"] == 1 and row["done"] == 1 for row in tasks["realms"])
    interviews = body["interviews"]
    assert interviews["counts"]["tracked"] == 3
    assert interviews["counts"]["waiting"] == 1
    assert {row["company"] for row in interviews["rows"]} == {"Acme", "Parked", "Fresh", "Gone"}
    assert body["runs"]["recent"][0]["skill"] == "scout-scan"
    assert body["missions"]["rows"][0]["id"] == "m1"


def test_include_filter(workspace, monkeypatch):
    fake_upstream(monkeypatch, payload=[])
    with TestClient(module.app) as client:
        r = client.get("/api/assistant/state", params={"include": "interviews,runs"})
        assert set(r.json()) == {"generated_at", "interviews", "runs"}
        monkeypatch.setattr(
            module.calendar_service, "snapshot", lambda: {"events": []}
        )
        r = client.get("/api/assistant/state", params={"include": "calendar"})
        assert r.json()["calendar"]["events"] == []
        monkeypatch.setattr(
            module.calendar_service,
            "snapshot",
            lambda: (_ for _ in ()).throw(RuntimeError("no consent")),
        )
        r = client.get("/api/assistant/state", params={"include": "calendar"})
        assert "unavailable" in r.json()["calendar"]


def test_missions_section(workspace, monkeypatch):
    fake_upstream(monkeypatch, error=urllib.error.URLError("down"))
    with TestClient(module.app) as client:
        r = client.get("/api/assistant/state")
    assert r.status_code == 200
    body = r.json()
    assert "unavailable" in body["missions"]
    assert body["interviews"]["counts"]["tracked"] == 3


def test_runs_section(workspace, monkeypatch):
    fake_upstream(monkeypatch, payload=[])
    with module._RUNS_LOCK:
        module._RUNS["live1"] = {
            "id": "live1",
            "skill": "job-reader",
            "status": "running",
            "started": "2026-11-16T12:00:00-05:00",
            "model": None,
            "provider": "opencode",
            "command": SECRET,
        }
    try:
        with TestClient(module.app) as client:
            r = client.get("/api/assistant/state", params={"include": "runs"})
        live = r.json()["runs"]["live"]
        assert live[0]["id"] == "live1" and live[0]["status"] == "running"
        assert "command" not in live[0]
    finally:
        with module._RUNS_LOCK:
            module._RUNS.pop("live1", None)


def test_unknown_include(workspace, monkeypatch):
    fake_upstream(monkeypatch, payload=[])
    with TestClient(module.app) as client:
        r = client.get("/api/assistant/state", params={"include": "secrets"})
    assert r.status_code == 400
    assert "secrets" in r.json()["error"]


def test_state_has_no_secrets(workspace, monkeypatch):
    fake_upstream(monkeypatch, payload=[])
    monkeypatch.setattr(module.calendar_service, "snapshot", lambda: {"events": []})
    with TestClient(module.app) as client:
        r = client.get("/api/assistant/state", params={"include": "tasks,interviews,runs,missions,calendar"})
    text = r.text
    assert SECRET not in text
    assert EMAIL not in text
    assert '"command":' not in text and '"preview":' not in text and '"output":' not in text
