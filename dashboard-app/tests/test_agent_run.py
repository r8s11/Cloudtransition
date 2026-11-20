"""The Orca entry point only calls the dashboard runner; it refuses without a job id."""

import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient  # noqa: E402
import app as module  # noqa: E402
from routes import runs as run_routes  # noqa: E402

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "agent_run.py"
spec = importlib.util.spec_from_file_location("agent_run", SCRIPT)
agent_run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_run)

CSRF = {"X-Requested-With": "XMLHttpRequest"}
FREE = [{"id": "opencode/some-model-free", "label": "x", "efforts": ["default"]}]


@pytest.fixture
def calls(monkeypatch):
    """Record dashboard calls instead of making HTTP requests."""
    seen = []

    def fake_call(method, path, body=None):
        seen.append((method, path, body))
        if path == "/api/skills/catalog":
            return {"provider_available": {"opencode": True}, "provider_models": {"opencode": FREE}}
        if method == "POST":
            return {"run": {"id": "r1", "label": "L", "status": "running", "model": "m", "output": None}}
        return {}

    monkeypatch.setattr(agent_run, "_call", fake_call)
    return seen


def _posted(calls):
    return next(body for method, path, body in calls if method == "POST")


def test_scout_posts_scout_scan_on_a_free_model(calls, capsys):
    assert agent_run.main(["scout"]) == 0
    assert _posted(calls) == {"skill": "scout-scan", "model": "opencode:opencode/some-model-free"}


def test_job_reader_sends_job_id_and_url(calls):
    agent_run.main(["job-reader", "acme-1", "https://example.com/job/1"])
    assert _posted(calls)["skill"] == "job-reader"
    assert _posted(calls)["input"] == "acme-1 https://example.com/job/1"


def test_cv_tailor_sends_job_id(calls):
    agent_run.main(["cv-adapter", "tailor", "acme-1"])
    assert _posted(calls)["skill"] == "cv-tailor"
    assert _posted(calls)["input"] == "acme-1"


def test_job_reader_refuses_without_job_id_or_url_before_any_call(calls):
    with pytest.raises(SystemExit) as exc:
        agent_run.main(["job-reader"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit):
        agent_run.main(["cv-adapter", "tailor"])
    assert calls == []


def test_forge_has_no_runner_and_calls_nothing(calls):
    with pytest.raises(SystemExit, match="no dashboard runner"):
        agent_run.main(["forge"])
    assert calls == []


def test_server_refuses_job_reader_without_input(monkeypatch):
    """The server-side gate holds even when a caller skips the wrapper."""
    monkeypatch.setattr(run_routes, "_load_opencode_models", lambda: (FREE, True, None))
    with run_routes._RUNS_LOCK:
        run_routes._RUNS.clear()
    with TestClient(module.app) as client:
        resp = client.post(
            "/api/skills/run",
            json={"skill": "job-reader", "model": "opencode:opencode/some-model-free"},
            headers=CSRF,
        )
    assert resp.status_code == 400
    assert "required" in resp.json()["error"]
    assert run_routes._RUNS == {}
