"""Run validation and lifecycle against isolated local providers, never paid APIs."""

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app as module

CSRF = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = "#!/bin/sh\nif [ \"$1\" = models ]; then echo vendor/fixture-free; exit; fi\nexec /bin/sleep 0.1\n"
    for name in ("codex", "opencode", "claude"):
        exe = bin_dir / name
        exe.write_text(script)
        exe.chmod(0o700)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    monkeypatch.setattr(module, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(module, "RUNS_LOG", tmp_path / "runs.log")
    monkeypatch.setattr(module, "_resolve_codex_exe", lambda: str(bin_dir / "codex"))
    monkeypatch.setattr(module, "_resolve_opencode_exe", lambda: str(bin_dir / "opencode"))
    for attr, data in {
        "CODEX_CACHE": {"models": [{"slug": "fixture-codex", "visibility": "list", "supported_in_api": True, "supported_reasoning_levels": [{"effort": "high"}]}]},
        "OPENROUTER_CATALOG": {"curated": [["vendor/fixture:free", "free"]]},
        "OPENROUTER_METADATA": {},
    }.items():
        path = tmp_path / (attr + ".json")
        path.write_text(json.dumps(data))
        monkeypatch.setattr(module, attr, path)
    with module._RUNS_LOCK:
        module._RUNS.clear()
    yield bin_dir
    deadline = time.monotonic() + 5
    while any(r["status"] == "running" for r in module._RUNS.values()) and time.monotonic() < deadline:
        time.sleep(0.02)
    with module._RUNS_LOCK:
        module._RUNS.clear()


def finish(client, run_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        run = next(r for r in client.get("/api/skills/runs").json()["runs"] if r["id"] == run_id)
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    pytest.fail("Run did not leave running state")


def test_invalid_selection_rejected(isolated):
    with TestClient(module.app) as client:
        assert client.post("/api/skills/run", json={"skill": "plan-today"}).status_code == 403
        for model, effort in [
            ("claude:unknown", "default"),
            ("codex:unknown", "default"),
            ("codex:;touch /tmp/forbidden", "default"),
            ("opencode:fixture-codex", "default"),
            ("opencode:vendor/paid", "default"),
            ("openrouter:vendor/fixture-free", "default"),
            ("openrouter:vendor/paid", "default"),
            ("opencode:vendor/fixture-free", "high"),
            ("openrouter:vendor/fixture:free", "high"),
            ("codex:fixture-codex", "ultra"),
        ]:
            response = client.post("/api/skills/run", headers=CSRF, json={"skill": "plan-today", "model": model, "effort": effort})
            assert response.status_code == 400, (model, response.text)
        no_key = client.post("/api/skills/run", headers=CSRF, json={"skill": "plan-today", "model": "openrouter:vendor/fixture:free"})
        assert no_key.status_code == 400 and "OPENROUTER_API_KEY" in no_key.json()["error"]
        assert client.get("/api/skills/runs").json()["runs"] == []
        assert not module.RUNS_LOG.exists()


@pytest.mark.parametrize("provider,model", [("codex", "fixture-codex"), ("opencode", "vendor/fixture-free"), ("openrouter", "vendor/fixture:free")])
@pytest.mark.parametrize("failure", ["nonzero", "timeout"])
def test_failure_lifecycle_and_duplicate(isolated, monkeypatch, provider, model, failure):
    server = None
    if provider == "openrouter":
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                time.sleep(0.3 if failure == "nonzero" else 1)
                try:
                    self.send_response(503)
                    self.end_headers()
                    self.wfile.write(b"fixture provider unavailable")
                except BrokenPipeError:
                    pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        monkeypatch.setattr(module, "OPENROUTER_API_URL", f"http://127.0.0.1:{server.server_port}/chat")
        monkeypatch.setenv("OPENROUTER_API_KEY", "local-fixture-only")
    else:
        (isolated / provider).write_text("#!/bin/sh\nif [ \"$1\" = models ]; then echo vendor/fixture-free; exit; fi\n/bin/sleep " + ("0.3" if failure == "nonzero" else "1") + "\nexit 7\n")
    monkeypatch.setattr(module, "RUN_TIMEOUT", 0.15 if failure == "timeout" else 2)
    try:
        with TestClient(module.app) as client:
            body = {"skill": "plan-today", "model": f"{provider}:{model}"}
            start = client.post("/api/skills/run", headers=CSRF, json=body)
            assert start.status_code == 200, start.text
            assert client.post("/api/skills/run", headers=CSRF, json=body).status_code == 409
            run = finish(client, start.json()["run"]["id"])
            assert run["status"] == "failed" and run["exit_code"] != 0
            assert run["duration"] and run["output"]
            events = [json.loads(line) for line in module.RUNS_LOG.read_text().splitlines()]
            assert [event["status"] for event in events] == ["running", "failed"]
            assert all(event["provider"] == provider and event["model"] == model for event in events)
            retry = client.post("/api/skills/run", headers=CSRF, json=body)
            assert retry.status_code == 200
            assert finish(client, retry.json()["run"]["id"])["status"] == "failed"
    finally:
        if server:
            server.shutdown()
            server.server_close()


def test_missing_codex_executable_is_reported(monkeypatch):
    monkeypatch.setattr(module, "_resolve_codex_exe", lambda: None)
    models, available, reason = module._load_codex_models()
    assert models == [] and not available and "codex executable" in reason
    response = TestClient(module.app).post("/api/skills/run", headers=CSRF, json={"skill": "plan-today", "model": "codex:fixture-codex"})
    assert response.status_code == 400 and "codex executable" in response.json()["error"]


@pytest.mark.parametrize("provider,model", [("codex", "fixture-codex"), ("opencode", "vendor/fixture-free"), ("openrouter", "vendor/fixture:free")])
def test_non_claude_skill_prompt_is_resolved(isolated, provider, model):
    directory = module.WORKSPACE / ".claude" / "skills" / "youtube-summarizer"
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text("# Summarize\nExtract the transcript before summarizing. Never invent video content.\n")
    request = module.RunRequest(skill="youtube-summary", model=f"{provider}:{model}", input="https://youtu.be/example")
    spec, _ = module._resolve_run(module.SKILL_RUNNERS["youtube-summary"], request)
    prompt = spec["prompt"] if provider == "openrouter" else spec["argv"][-1]
    assert "Extract the transcript before summarizing." in prompt
    assert "https://youtu.be/example" in prompt
    assert not prompt.startswith("/youtube-summarizer")


def test_shell_run_has_no_model(isolated):
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(module.SKILL_RUNNERS, "brain-index", {**module.SKILL_RUNNERS["brain-index"], "argv": ["/bin/echo", "local output"]})
        with TestClient(module.app) as client:
            response = client.post("/api/skills/run", headers=CSRF, json={"skill": "brain-index"})
            assert response.status_code == 200
            run = finish(client, response.json()["run"]["id"])
            assert run["status"] == "done" and run["model"] is None and run["provider"] is None
            assert client.post("/api/skills/run", headers=CSRF, json={"skill": "brain-index", "model": "claude:sonnet"}).status_code == 400


def test_openrouter_catalogue_requires_explicit_free_pricing(isolated):
    module.OPENROUTER_CATALOG.write_text(json.dumps({"curated": [
        ["vendor/free:free", "free"], ["vendor/zero", ""], ["vendor/missing", ""],
        ["vendor/invalid", ""], ["vendor/paid", "free"], [None, "free"],
    ]}))
    module.OPENROUTER_METADATA.write_text(json.dumps({
        "vendor/zero": {"pricing": {"prompt": "0", "completion": "0"}},
        "vendor/missing": {"pricing": {}},
        "vendor/invalid": {"pricing": {"prompt": "bad", "completion": "bad"}},
        "vendor/paid": {"pricing": {"prompt": "1", "completion": "1"}},
    }))
    models, available, _ = module._load_openrouter_models()
    assert available
    assert {model["id"] for model in models} == {"vendor/free:free", "vendor/zero"}
