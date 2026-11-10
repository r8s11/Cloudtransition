"""Scout runs through the existing allowlisted run path, on a free OpenCode
model, with no bypass flag and no second in-flight scan."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient  # noqa: E402
import app as module  # noqa: E402

CSRF = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _clear_runs():
    with module._RUNS_LOCK:
        module._RUNS.clear()
    yield
    with module._RUNS_LOCK:
        module._RUNS.clear()


def test_scout_scan_catalog_entry_is_opencode_only():
    cfg = module.SKILL_RUNNERS["scout-scan"]
    assert cfg["kind"] == "opencode-agent"
    assert cfg["agent"] == "scout"
    assert cfg["providers"] == ["opencode"]
    assert cfg["options"] is True
    assert module._card_allows_provider(cfg, "claude") == (
        False,
        "Run Scout scan only supports opencode models.",
    )
    assert module._card_allows_provider(cfg, "opencode") == (True, None)


def test_scout_scan_resolves_agent_and_model(monkeypatch):
    monkeypatch.setattr(module, "_resolve_opencode_exe", lambda: "/fake/opencode")
    cfg = module.SKILL_RUNNERS["scout-scan"]
    req = module.RunRequest(
        skill="scout-scan", model="opencode:opencode/beam-free", effort="default"
    )

    spec, shown = module._resolve_run(cfg, req)

    assert spec["kind"] == "opencode"
    assert spec["argv"][:7] == [
        "/fake/opencode",
        "run",
        "--standalone",
        "--agent",
        "scout",
        "-m",
        "opencode/beam-free",
    ]
    assert "--auto" not in spec["argv"]
    assert "workspace/agents/scout/outputs/scan-" in spec["argv"][-1]
    assert "--agent scout" in shown


def test_scout_scan_missing_opencode_is_an_error_spec(monkeypatch):
    monkeypatch.setattr(module, "_resolve_opencode_exe", lambda: None)
    cfg = module.SKILL_RUNNERS["scout-scan"]
    req = module.RunRequest(
        skill="scout-scan", model="opencode:opencode/beam-free", effort="default"
    )

    spec, _ = module._resolve_run(cfg, req)

    assert spec["kind"] == "error"
    assert "opencode" in spec["error"]


def test_scout_scan_rejects_a_non_opencode_model_and_missing_csrf():
    with TestClient(module.app) as client:
        missing = client.post(
            "/api/skills/run",
            json={"skill": "scout-scan", "model": "opencode:opencode/beam-free"},
        )
        assert missing.status_code == 403

        wrong = client.post(
            "/api/skills/run",
            headers=CSRF,
            json={"skill": "scout-scan", "model": "claude:sonnet", "effort": "default"},
        )
        assert wrong.status_code == 400
        assert "opencode" in wrong.json()["error"].lower()

        no_model = client.post(
            "/api/skills/run",
            headers=CSRF,
            json={"skill": "scout-scan", "effort": "default"},
        )
        assert no_model.status_code == 400


def test_scout_scan_is_single_flight(monkeypatch):
    monkeypatch.setattr(module, "_resolve_opencode_exe", lambda: "/fake/opencode")
    monkeypatch.setattr(module, "_execute_run", lambda *args: None)
    monkeypatch.setattr(module, "_log_run", lambda entry: None)
    with TestClient(module.app) as client:
        body = {
            "skill": "scout-scan",
            "model": "opencode:opencode/beam-free",
            "effort": "default",
        }
        first = client.post("/api/skills/run", headers=CSRF, json=body)
        assert first.status_code == 200
        second = client.post("/api/skills/run", headers=CSRF, json=body)
        assert second.status_code == 409
        runs = client.get("/api/skills/runs", headers=CSRF).json()["runs"]
        running = [
            r
            for r in runs
            if r["skill"] == "scout-scan" and r["status"] == "running"
        ]
        assert len(running) == 1


def test_scout_scan_catalog_payload_carries_provider_limit(monkeypatch):
    monkeypatch.setattr(
        module,
        "_fetch_skill_catalog",
        lambda: {"provider_models": {}, "provider_available": {}, "effort": []},
    )
    payload = module._skill_catalog_payload()
    skill = next(s for s in payload["skills"] if s["id"] == "scout-scan")
    assert skill["providers"] == ["opencode"]


def test_opencode_agent_card_without_agent_is_an_error_spec(monkeypatch):
    monkeypatch.setattr(module, "_resolve_opencode_exe", lambda: "/fake/opencode")
    cfg = {
        "kind": "opencode-agent",
        "prompt": "scan",
        "providers": ["opencode"],
    }
    req = module.RunRequest(
        skill="malformed", model="opencode:opencode/beam-free", effort="default"
    )

    spec, _ = module._resolve_run(cfg, req)

    assert spec["kind"] == "error"
    assert "agent" in spec["error"].lower()
