"""Scout runs through the existing allowlisted run path, on a free OpenCode
model, with no bypass flag and no second in-flight scan."""

import json
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
    monkeypatch.setattr(module, "_load_opencode_models", lambda: ([{"id": "opencode/beam-free", "efforts": ["default"]}], True, None))
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


# ── Job Reader from its Agents-tab card: definition traced to each run ──

JOB_INPUT = "acme-it-support https://example.com/jobs/1"
DEFINITION = "---\ndescription: d\nmode: subagent\n---\nYour name is Job Reader.\nExtract only.\n"


@pytest.fixture
def agent_home(tmp_path, monkeypatch):
    """A workspace holding one job-reader definition and no global OpenCode copy."""
    from core import agents

    path = tmp_path / ".opencode" / "agents" / "job-reader.md"
    path.parent.mkdir(parents=True)
    path.write_text(DEFINITION)
    monkeypatch.setattr(agents, "WORKSPACE", tmp_path)
    monkeypatch.setattr(agents, "OPENCODE_GLOBAL_AGENTS", tmp_path / "no-global")
    return path


def _start_job_reader(monkeypatch, client, skill="job-reader"):
    monkeypatch.setattr(module, "_resolve_opencode_exe", lambda: "/fake/opencode")
    monkeypatch.setattr(module, "_load_opencode_models", lambda: ([{"id": "opencode/beam-free", "efforts": ["default"]}], True, None))
    monkeypatch.setattr(module, "_log_run", lambda entry: None)
    body = {"skill": skill, "model": "opencode:opencode/beam-free", "effort": "default", "input": JOB_INPUT}
    return client.post("/api/skills/run", headers=CSRF, json=body)


def _resolved(system, permissions=()):
    return [{"id": "job-reader", "system": system, "permissions": list(permissions)}]


def _fake_debug(monkeypatch, stdout, returncode=0):
    class Proc:
        pass

    proc = Proc()
    proc.stdout, proc.returncode = stdout, returncode
    calls = []
    monkeypatch.setattr(module, "_resolve_opencode_exe", lambda: "/fake/opencode")
    # Only OpenCode calls count: other app threads (calendar) may call subprocess too.
    monkeypatch.setattr(
        module.subprocess, "run",
        lambda argv, **kw: (calls.append(argv) if argv and argv[0] == "/fake/opencode" else None) or proc,
    )
    return calls


def test_job_reader_run_records_its_definition_and_launch_facts(monkeypatch, agent_home):
    import hashlib

    started = []
    monkeypatch.setattr(module, "_execute_run", lambda run_id, spec: started.append(spec))
    with TestClient(module.app) as client:
        response = _start_job_reader(monkeypatch, client)

    assert response.status_code == 200
    run = response.json()["run"]
    assert run["agent"] == "job-reader"
    assert run["runner"] == "opencode-agent"
    assert run["provider"] == "opencode" and run["model"] == "opencode/beam-free"
    assert run["cwd"] == str(module.WORKSPACE)
    assert run["log"] == "runs.log"
    assert run["definition"]["path"] == ".opencode/agents/job-reader.md"
    assert run["definition"]["sha256"] == hashlib.sha256(DEFINITION.encode()).hexdigest()
    assert run["definition"]["check"] == "pending"
    assert started[0]["argv"][:5] == ["/fake/opencode", "run", "--standalone", "--agent", "job-reader"]
    assert started[0]["verify_agent"]["expected"] == {k: run["definition"][k] for k in ("path", "sha256", "version")}


def test_job_reader_refuses_when_its_definition_is_missing(monkeypatch, agent_home):
    agent_home.unlink()
    monkeypatch.setattr(module, "_execute_run", lambda *a: pytest.fail("must not start"))
    with TestClient(module.app) as client:
        response = _start_job_reader(monkeypatch, client)
    assert response.status_code == 400
    assert "job-reader.md is missing" in response.json()["error"]


def test_one_agent_runs_one_task_at_a_time(monkeypatch, agent_home):
    second_card = {**module.SKILL_RUNNERS["job-reader"], "label": "Second job-reader card"}
    monkeypatch.setitem(module.SKILL_RUNNERS, "job-reader-again", second_card)
    monkeypatch.setattr(module, "_execute_run", lambda *a: None)
    with TestClient(module.app) as client:
        assert _start_job_reader(monkeypatch, client).status_code == 200
        other = _start_job_reader(monkeypatch, client, skill="job-reader-again")
    assert other.status_code == 409
    assert "job-reader is already running" in other.json()["error"]


def _pending_run(agent_home):
    from core import agents

    expected = agents.launch_definition("job-reader")
    module._RUNS["r1"] = {"id": "r1", "status": "running", "definition": {**expected, "check": "pending"}}
    return {"agent": "job-reader", "expected": expected}


def test_verification_matches_opencode_resolved_instructions(monkeypatch, agent_home):
    verify = _pending_run(agent_home)
    calls = _fake_debug(
        monkeypatch,
        json.dumps(_resolved("Your name is Job Reader.\n  Extract only.", [{"effect": "deny", "action": "edit", "resource": "*"}])),
    )

    assert module._verify_opencode_agent("r1", verify) is None
    definition = module._RUNS["r1"]["definition"]
    assert definition["check"] == "matched"
    assert definition["permissions"] == ["deny edit *"]
    assert calls[0][1:] == ["debug", "agents", "--standalone"]


def test_verification_refuses_other_instructions_or_a_changed_file(monkeypatch, agent_home):
    verify = _pending_run(agent_home)
    _fake_debug(monkeypatch, json.dumps(_resolved("Something else entirely.")))
    refused = module._verify_opencode_agent("r1", verify)
    assert refused["status"] == "failed" and refused["body"].startswith("Not started:")
    assert module._RUNS["r1"]["definition"]["check"] == "mismatch"

    verify = _pending_run(agent_home)
    agent_home.write_text(DEFINITION + "Edited after the request.\n")
    refused = module._verify_opencode_agent("r1", verify)
    assert refused["status"] == "failed"
    assert "changed or vanished" in module._RUNS["r1"]["definition"]["detail"]


def test_verification_fails_closed_when_opencode_gives_no_answer(monkeypatch, agent_home):
    verify = _pending_run(agent_home)
    _fake_debug(monkeypatch, "not json", returncode=0)
    refused = module._verify_opencode_agent("r1", verify)
    assert refused["status"] == "failed" and refused["body"].startswith("Not started:")
    assert module._RUNS["r1"]["definition"]["check"] == "unverified"


def test_verification_refuses_a_loosened_permission_policy(monkeypatch, agent_home):
    verify = {**_pending_run(agent_home), "policy": module.SKILL_RUNNERS["job-reader"]["policy"]}
    # The old definition: edit rules only, shell still allowed by the default.
    loose = [
        {"action": "*", "resource": "*", "effect": "allow"},
        {"action": "edit", "resource": "*", "effect": "deny"},
        {"action": "edit", "resource": "workspace/agents/job-reader/**", "effect": "allow"},
    ]
    _fake_debug(monkeypatch, json.dumps(_resolved("Your name is Job Reader.\nExtract only.", loose)))

    refused = module._verify_opencode_agent("r1", verify)

    assert refused["status"] == "failed"
    definition = module._RUNS["r1"]["definition"]
    assert definition["check"] == "policy"
    assert "shell true resolves to allow, not deny" in definition["detail"]
    assert "edit workspace/agents/job-reader/memory/log.jsonl resolves to allow" in definition["detail"]


def test_refused_run_is_a_visible_failure_and_never_launches(monkeypatch, agent_home, tmp_path):
    verify = _pending_run(agent_home)
    monkeypatch.setattr(module, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    monkeypatch.setattr(module, "_log_run", lambda entry: None)
    calls = _fake_debug(monkeypatch, json.dumps([]))

    module._execute_run("r1", {"kind": "opencode", "argv": ["/fake/opencode", "run"], "verify_agent": verify})

    run = module._RUNS["r1"]
    assert run["status"] == "failed"
    assert run["definition"]["check"] == "missing"
    assert run["finished"]
    assert "Not started" in (tmp_path / "runs" / "r1.txt").read_text()
    assert [c[1] for c in calls] == ["debug"], "the agent itself never ran"


def test_last_finished_run_reads_runs_log_and_skips_running(monkeypatch, tmp_path):
    log = tmp_path / "runs.log"
    log.write_text(
        json.dumps({"skill": "job-reader", "status": "done", "id": "old"}) + "\n"
        + "not json\n"
        + json.dumps({"skill": "job-reader", "status": "failed", "id": "new"}) + "\n"
        + json.dumps({"skill": "job-reader", "status": "running", "id": "live"}) + "\n"
        + json.dumps({"skill": "scout-scan", "status": "done", "id": "other"}) + "\n"
    )
    monkeypatch.setattr(module, "RUNS_LOG", log)
    assert module._last_finished_run("job-reader")["id"] == "new"
    assert module._last_finished_run("cv-base") is None


# ── Staging, publishing and the runner-owned memory write ──

from datetime import datetime, timedelta, timezone  # noqa: E402

LAUNCHED = datetime(2026, 11, 17, 20, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
EXITED = LAUNCHED + timedelta(seconds=30)
JOB = {"job_id": "acme-it", "url": "https://example.com/jobs/1", "run_id": "r2"}


@pytest.fixture
def reader_state(tmp_path, monkeypatch):
    from core import agents

    state = tmp_path / "workspace" / "agents"
    (state / "job-reader" / "memory").mkdir(parents=True)
    (state / "job-reader" / "outputs").mkdir(parents=True)
    monkeypatch.setattr(agents, "WORKSPACE", tmp_path)
    monkeypatch.setattr(agents, "AGENT_STATE", state)
    module._RUNS["r2"] = {
        "id": "r2", "status": "running", "provider": "opencode", "model": "opencode/beam-free",
        "definition": {"version": "abcd1234"},
    }
    assert module._stage_job_reading(JOB) is None
    return state / "job-reader"


def _reading(job="acme-it", **changes):
    data = {
        "job_id": job, "title": "IT Support", "company": "Acme", "source_url": "https://example.com/jobs/1",
        "responsibilities": ["Fix laptops"], "required_skills": ["Windows"],
        "preferred_skills": [], "language_requirements": [],
    }
    data.update(changes)
    return data


def _stage(reader, text, name="acme-it.json"):
    (reader / "staging" / "r2" / name).write_text(text)


def _finish(done=None):
    done = done or {"status": "done", "exit_code": 0, "body": "agent said ok"}
    return module._finish_job_reading("r2", JOB, done, LAUNCHED, EXITED)


def _events(reader):
    return [json.loads(line) for line in (reader / "memory" / "log.jsonl").read_text().splitlines() if line.strip()]


def test_staged_reading_is_published_with_runner_timestamps(reader_state):
    (reader_state / "memory" / "log.jsonl").write_text('{"event": "old"}')  # no trailing newline
    # The model's own timestamp and provenance must not survive.
    _stage(reader_state, json.dumps(_reading(fetched_at="1999-01-01T00:00:00Z", provenance={"run_id": "fake"})))

    result = _finish()

    assert result["status"] == "done"
    assert "Output published" in result["body"] and "Memory event recorded: jd_read" in result["body"]
    published = json.loads((reader_state / "outputs" / "acme-it.json").read_text())
    assert published["fetched_at"] == "2026-11-17T20:00:30-05:00"
    assert published["provenance"]["run_id"] == "r2"
    assert published["provenance"]["launched_at"] == "2026-11-17T20:00:00-05:00"
    assert published["provenance"]["definition_version"] == "abcd1234"
    assert published["required_skills"] == ["Windows"]
    assert not (reader_state / "staging" / "r2").exists(), "staging is cleaned up"
    old, new = _events(reader_state)
    assert old == {"event": "old"}
    assert new["event"] == "jd_read" and new["company"] == "Acme"
    assert new["fetched_at"] == "2026-11-17T20:00:30-05:00"
    assert new["recorded_by"] == "dashboard" and new["definition_version"] == "abcd1234"
    assert (new["provider"], new["model"]) == ("opencode", "opencode/beam-free")


def test_published_reading_still_feeds_the_interviews_tab(reader_state):
    from core import agents

    _stage(reader_state, json.dumps(_reading()))
    _finish()
    reading = agents.load_job_reading("acme-it")
    assert [s["label"] for s in reading["sections"]] == ["Responsibilities", "Required skills"]


def test_extra_staged_files_are_ignored_and_removed(reader_state):
    _stage(reader_state, json.dumps(_reading()))
    _stage(reader_state, json.dumps(_reading(job="other-job")), name="other-job.json")

    result = _finish()

    assert "ignored other staged files: other-job.json" in result["body"]
    assert not (reader_state / "outputs" / "other-job.json").exists()
    assert not (reader_state / "staging" / "r2").exists()


@pytest.mark.parametrize(
    "write, reason",
    [
        (None, "No output written"),
        ("not json", "not readable JSON"),
        (json.dumps(_reading(job="other-job")), "names job_id 'other-job'"),
        (json.dumps(_reading(required_skills="Windows")), "mistypes: required_skills"),
        (json.dumps({k: v for k, v in _reading().items() if k != "title"}), "mistypes: title"),
        ("x" * 1_000_001, "larger than"),
    ],
)
def test_missing_or_invalid_staged_output_fails_and_publishes_nothing(reader_state, write, reason):
    existing = reader_state / "outputs" / "acme-it.json"
    existing.write_text('{"kept": true}')
    if write is not None:
        _stage(reader_state, write)

    result = _finish()

    assert result["status"] == "failed"
    assert reason in result["body"]
    assert existing.read_text() == '{"kept": true}', "a rejected run never touches the published output"
    (event,) = _events(reader_state)
    assert event["event"] == "jd_read_failed" and reason in event["detail"]


def test_missing_memory_folder_is_reported_and_never_created(reader_state):
    import shutil

    shutil.rmtree(reader_state / "memory")
    _stage(reader_state, json.dumps(_reading()))
    result = _finish()
    assert result["status"] == "failed"
    assert "memory event not recorded and nothing was created" in result["body"]
    assert not (reader_state / "memory").exists()


def test_staging_is_per_run_and_never_created_without_the_agent_folder(reader_state, tmp_path, monkeypatch):
    from core import agents

    assert module._stage_job_reading(JOB) is not None, "a reused run id must not share a folder"
    other = {**JOB, "run_id": "r3"}
    assert module._stage_job_reading(other) is None
    module._discard_staging(other)
    assert (reader_state / "staging" / "r2").is_dir(), "discarding one run leaves others alone"

    monkeypatch.setattr(agents, "AGENT_STATE", tmp_path / "unmounted")
    assert "nothing was created" in module._stage_job_reading({**JOB, "run_id": "r4"})
    assert not (tmp_path / "unmounted").exists()


def test_job_reader_run_spec_carries_the_job_staging_and_policy(monkeypatch, agent_home):
    started = []
    monkeypatch.setattr(module, "_execute_run", lambda run_id, spec: started.append((run_id, spec)))
    with TestClient(module.app) as client:
        assert _start_job_reader(monkeypatch, client).status_code == 200
    run_id, spec = started[0]
    assert spec["job_reading"] == {"job_id": "acme-it-support", "url": "https://example.com/jobs/1", "run_id": run_id}
    assert f"workspace/agents/job-reader/staging/{run_id}/<job id>.json" in spec["argv"][-1]
    assert spec["verify_agent"]["policy"] is module.SKILL_RUNNERS["job-reader"]["policy"]


def test_launch_fails_cleanly_when_staging_cannot_be_created(monkeypatch, agent_home, tmp_path):
    from core import agents

    monkeypatch.setattr(agents, "AGENT_STATE", tmp_path / "gone")
    monkeypatch.setattr(module, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    monkeypatch.setattr(module, "_log_run", lambda entry: None)
    monkeypatch.setattr(module, "_verify_opencode_agent", lambda *a: None)
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: pytest.fail("must not launch"))
    module._RUNS["r5"] = {"id": "r5", "status": "running"}

    module._execute_run("r5", {"kind": "opencode", "argv": ["x"], "verify_agent": {}, "job_reading": {**JOB, "run_id": "r5"}})

    assert module._RUNS["r5"]["status"] == "failed"
    assert "Not started" in (tmp_path / "runs" / "r5.txt").read_text()
