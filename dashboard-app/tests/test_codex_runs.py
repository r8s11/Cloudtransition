"""Invalid run selections (F1) and provider failure/duplicate lifecycle (F3).

Uses isolated temporary executable fixtures on a private PATH so no real
model executable is invoked. No paid model calls are made.
"""

import os
import stat
import sys
import time
from pathlib import Path

import pytest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
import app as module  # noqa: E402

CSRF = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _isolated_run_registry():
    """Clear the module-global run registry so tests cannot see each other's runs.

    Runs execute on daemon threads and update `_RUNS` by id; clearing is safe
    because `_execute_run` ignores ids that are no longer present.
    """
    with module._RUNS_LOCK:
        module._RUNS.clear()
    yield
    with module._RUNS_LOCK:
        module._RUNS.clear()


def _put_on_path(tmp_path, name, run_body, models_output):
    """Write an executable script into a per-test bin dir on PATH.

    The script answers `opencode models` (catalogue listing) immediately and
    runs `run_body` for any other invocation (e.g. `opencode run ...` /
    `codex exec ...`), simulating a slow or failing provider.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    p = bindir / name
    p.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"models\" ]; then\n"
        "  for m in " + " ".join(models_output) + ";\n"
        "  do echo \"$m\"; done\n"
        "  exit 0;\n"
        "fi\n"
        + run_body
        + "\n"
    )
    p.chmod(p.stat().st_mode | stat.S_IXUSR)
    monkeypath = str(bindir) + os.pathsep + os.environ.get("PATH", "")
    return bindir, monkeypath


# ── F1 — Invalid selections cannot launch processes ─────────────────


def test_invalid_selection_rejected(tmp_path, monkeypatch):
    # Cases that are still rejected: missing CSRF, unknown skill, unknown model
    # ID, hostile shell-ish ID, OpenRouter without API key, non-default effort
    # for OpenCode/OpenRouter. Provider/model mismatches are now allowed (all
    # providers run on all cards per F4 revision).
    # The one allowed case launches a run, so put a fake opencode on PATH to
    # avoid invoking a real provider from the test suite.
    _, monkeypath = _put_on_path(
        tmp_path, "opencode", "exec sleep 5\n", ["opencode/beam-free"]
    )
    monkeypatch.setenv("PATH", monkeypath)
    with TestClient(module.app) as client:
        # missing CSRF header
        r = client.post("/api/skills/run", json={"skill": "ui-ux-review", "model": "claude:sonnet"})
        assert r.status_code == 403, r.text

        # unknown skill
        r = client.post(
            "/api/skills/run", headers=CSRF, json={"skill": "no-such-skill", "model": "claude:sonnet"}
        )
        assert r.status_code == 400, r.text

        # unknown model ID (not in any catalogue)
        r = client.post(
            "/api/skills/run",
            headers=CSRF,
            json={"skill": "ui-ux-review", "model": "codex:does-not-exist"},
        )
        assert r.status_code == 400, r.text

        # hostile shell-ish ID (never interpreted as shell code)
        r = client.post(
            "/api/skills/run",
            headers=CSRF,
            json={"skill": "ui-ux-review", "model": "codex:; rm -rf /; #"},
        )
        assert r.status_code == 400, r.text

        # OpenRouter without an API key -> rejected before launch
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        r = client.post(
            "/api/skills/run",
            headers=CSRF,
            json={
                "skill": "update-sheet",
                "model": "openrouter:nvidia/nemotron-3-super-120b-a12b:free",
                "effort": "default",
            },
        )
        assert r.status_code == 400, r.text
        assert "OpenRouter" in r.json()["error"]

        # OpenCode with non-default effort (opencode run has no effort flag)
        r = client.post(
            "/api/skills/run",
            headers=CSRF,
            json={
                "skill": "update-sheet",
                "model": "opencode:opencode/beam-free",
                "effort": "high",
            },
        )
        assert r.status_code == 400, r.text

        # OpenRouter with non-default effort
        r = client.post(
            "/api/skills/run",
            headers=CSRF,
            json={
                "skill": "update-sheet",
                "model": "openrouter:nvidia/nemotron-3-super-120b-a12b:free",
                "effort": "high",
            },
        )
        assert r.status_code == 400, r.text

        # Provider/model mismatches are now allowed (all providers on all cards)
        r = client.post(
            "/api/skills/run",
            headers=CSRF,
            json={"skill": "ui-ux-review", "model": "opencode:gpt-6.1-sol"},
        )
        assert r.status_code == 200, r.text
        allowed_run_id = r.json()["run"]["id"]

        # Rejected cases (400/403) did not start runs; the allowed case did.
        runs = client.get("/api/skills/runs", headers=CSRF).json()["runs"]
        running_ids = {x["id"] for x in runs if x["status"] == "running"}
        assert running_ids == {allowed_run_id}


# ── F3 — Provider failure, timeout and duplicate submit ─────────────


@pytest.mark.parametrize(
    "provider,skill,model,exe_name",
    [
        ("codex", "ui-ux-review", "codex:gpt-6.1-sol", "codex"),
        ("opencode", "update-sheet", "opencode:opencode/beam-free", "opencode"),
    ],
)
def test_failure_lifecycle_and_duplicate(tmp_path, monkeypatch, provider, skill, model, exe_name):
    # Fake executable that sleeps (simulates a slow/hung provider). `exec` so a
    # killed run leaves no child holding the inherited stdout pipe.
    if exe_name == "opencode":
        _, monkeypath = _put_on_path(
            tmp_path, exe_name, "exec sleep 10\n",
            ["opencode/beam-free"],
        )
    else:
        _, monkeypath = _put_on_path(
            tmp_path, exe_name, "exec sleep 10\n",
            [],
        )
    monkeypatch.setenv("PATH", monkeypath)
    monkeypatch.setattr(module, "RUN_TIMEOUT", 2)

    with TestClient(module.app) as client:
        # Start a run.
        r = client.post(
            "/api/skills/run",
            headers=CSRF,
            json={"skill": skill, "model": model, "effort": "default"},
        )
        assert r.status_code == 200, r.text
        run_id = r.json()["run"]["id"]

        # Same-skill duplicate while running -> 409, only one active execution.
        r2 = client.post(
            "/api/skills/run",
            headers=CSRF,
            json={"skill": skill, "model": model, "effort": "default"},
        )
        assert r2.status_code == 409, r2.text
        runs = client.get("/api/skills/runs", headers=CSRF).json()["runs"]
        running = [x for x in runs if x["skill"] == skill and x["status"] == "running"]
        assert len(running) == 1

        # Wait for the timeout to surface as failed with recorded output/duration.
        run = None
        for _ in range(100):
            runs = client.get("/api/skills/runs", headers=CSRF).json()["runs"]
            run = next((x for x in runs if x["id"] == run_id), None)
            if run and run["status"] != "running":
                break
            time.sleep(0.1)
        assert run is not None
        assert run["status"] == "failed", run
        assert run["exit_code"] != 0
        assert run["output"]
        assert run["duration"]

        # Controls permit another explicit attempt after failure (no auto-retry).
        r3 = client.post(
            "/api/skills/run",
            headers=CSRF,
            json={"skill": skill, "model": model, "effort": "default"},
        )
        assert r3.status_code == 200, r3.text


# ── F2 — A missing executable is reported, not crashed on ────────────


def test_missing_codex_executable_is_reported(monkeypatch):
    """No codex binary: the provider is unavailable and a run fails with a reason."""
    monkeypatch.setattr(module, "_resolve_codex_exe", lambda: None)

    models, available, reason = module._load_codex_models()
    assert models == []
    assert available is False
    assert reason == "codex executable not on PATH"

    cfg = module.SKILL_RUNNERS["ui-ux-review"]
    run_spec, shown = module._resolve_run(
        cfg,
        module.RunRequest(skill="ui-ux-review", model="codex:gpt-6.1-sol", effort="default"),
    )
    assert run_spec["kind"] == "error"
    assert run_spec["error"] == "codex executable not on PATH"
    assert shown == "codex exec -m <model> <prompt>"
