# Agents Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Agents tab that shows the Forge team, their memory and recent events, the latest Scout scan, and a button that runs a free Scout scan on a chosen free OpenCode model.

**Architecture:** A new read-only `agents.py` loads `.opencode/agents/*.md`, `workspace/agents/*/memory/`, and the newest valid `workspace/agents/scout/outputs/scan-*.json`; `build_context()` exposes the result to a server-rendered `agents.html`. The scan button is a new `opencode-agent` runner kind that launches `opencode run --standalone --agent scout -m <model> <prompt>` through the existing `/api/skills/run` path, with the model picker limited to OpenCode's free catalogue.

**Tech Stack:** FastAPI, Jinja2, vanilla JS, pytest, OpenCode CLI.

**Spec:** `docs/superpowers/specs/2026-11-09-agents-dashboard-design.md`

## Global Constraints

- The workspace files are the database; the tab reads them on every page load.
- No new listener, database, build step, or JavaScript framework.
- Only the existing `/api/skills/run` write path starts a scan.
- Privacy rules in `workspace_content.privacy_violation()` still apply to every file link.
- Run path invariants: argv only, no shell, no interactive prompts, no bypass flags (`--auto`), 30-minute deadline.
- Missing files, malformed JSONL, and absent scans render explicit empty states. Never fabricate a job, score, salary, status, or timestamp.
- The scan card uses free OpenCode models only. No paid Job Reader or CV Adapter promotion in this slice.
- Never run a scan on page load, in the background, or more than once at a time.

## Review Focus

- A missing or empty `.opencode/agents/` directory: the tab renders an explicit "no agents" empty state, not a crash or invented roster.
- A `log.jsonl` with malformed or truncated lines: bad lines are skipped, valid events still show, and an all-invalid log reports an explicit error.
- A truncated `scan-*.json`, `jobs: null`, or jobs with missing score/title/URL: the loader never crashes, missing scores sort last, and the table leaves missing cells blank.
- No free OpenCode models or a foreign model selection: the card shows an explicit no-model state and the endpoint returns 400 instead of launching a Claude run.
- A scan already in flight or a missing CSRF header: the endpoint returns 409/403 and writes no start event or second process.

---

### Task 1: Read-only agent and scan loader

**Files:**
- Create: `dashboard-app/agents.py`
- Modify: `dashboard-app/app.py` (import near `workspace_content`, and the `build_context()` return)
- Test: `dashboard-app/tests/test_agents.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `load_roster() -> list[dict]` with keys `slug`, `name`, `mode`, `description`, `definition`
  - `load_memory(slug: str) -> dict` with keys `summary`, `summary_missing`, `events`, `events_error`
  - `load_latest_scan() -> dict` with keys `scan`, `files`, `error`
  - `build_agents_view() -> dict` with keys `agents`, `agent_events`, `agent_scan`, `agent_scan_files`, `agent_scan_error`
  - `agents` entries merge the roster keys with the memory keys and add `events`.

- [ ] **Step 1: Write the failing loader tests**

Create `dashboard-app/tests/test_agents.py`:

```python
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
    assert "no valid JSON" in view["events_error"].lower()


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd dashboard-app && venv/bin/python -m pytest tests/test_agents.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'agents'`.

- [ ] **Step 3: Implement `dashboard-app/agents.py`**

Use these module constants and exact signatures. The parsing, ordering and fallback rules are the part the tests do not infer.

```python
"""Read-only views of the Forge job-hunting agents.

The workspace files are the database. Every function tolerates missing or
malformed files and returns an explicit empty/error value instead of raising.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parent.parent
AGENT_DEFS = WORKSPACE / ".opencode" / "agents"
AGENT_STATE = WORKSPACE / "workspace" / "agents"
SCOUT_OUTPUTS = AGENT_STATE / "scout" / "outputs"

ROSTER_ORDER = ("forge", "scout", "job-reader", "cv-adapter")
AGENT_LABELS = {
    "forge": "Forge",
    "scout": "Scout",
    "job-reader": "Job Reader",
    "cv-adapter": "CV Adapter",
}
MAX_EVENTS = 5


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter dict, body). Bad or absent YAML is an empty dict."""


def _agent_name(slug: str, body: str) -> str:
    """Read `Your name is X.` from the body, else the known label or title."""


def load_roster() -> list[dict]:
    """Read .opencode/agents/*.md in roster order; unknown files appended."""


def _event_view(event: dict) -> dict:
    """Normalize one log object to {when, event, detail}."""


def load_memory(slug: str) -> dict:
    """Read index.md and the newest MAX_EVENTS valid JSONL objects."""


def load_latest_scan() -> dict:
    """Newest scan-*.json with a jobs list; sort jobs by score, missing last."""


def build_agents_view() -> dict:
    """Assemble agents, agent_events, agent_scan, agent_scan_files, agent_scan_error."""
```

Rules the tests pin:

- `_parse_frontmatter` only accepts a leading `---` block closed by a second `---`; `yaml.safe_load` failures become `{}`.
- `_agent_name` uses `re.search(r"Your name is\s+([^.\n]+)\.", body)`; fallback is `AGENT_LABELS` then `slug.replace("-", " ").title()`.
- `load_roster` sorts by `ROSTER_ORDER` index, then slug; `definition` is the path relative to `WORKSPACE`.
- `_event_view` reads `when` from `ts` or `timestamp`; `event` from `event` or `type` (default `"event"`); `detail` from `detail`, `summary`, `notes`, or `result`. Non-string values are JSON-encoded.
- `load_memory` returns events newest first, capped at `MAX_EVENTS`; a missing log is silent, a log with no valid object is an error.
- `load_latest_scan` sorts candidates by `(mtime, name)` descending and returns the first file whose JSON is a dict with a list `jobs`; non-dict jobs are skipped; score sorting uses `float(score)` for numbers and `-1.0` otherwise. `files` always has `json` and adds `markdown` only when the sibling `.md` exists.

- [ ] **Step 4: Wire the view into `build_context()`**

In `dashboard-app/app.py`, add `from agents import build_agents_view` beside `import workspace_content as wc`, and add `**build_agents_view(),` to the final `return { ... }` of `build_context()`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd dashboard-app && venv/bin/python -m pytest tests/test_agents.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add dashboard-app/agents.py dashboard-app/app.py dashboard-app/tests/test_agents.py
git commit -m "feat(dashboard): load Forge agent roster and Scout scan"
```

---

### Task 2: Agents tab roster and scan table

**Files:**
- Create: `dashboard-app/templates/pages/agents.html`
- Modify: `dashboard-app/templates/index.html` (nav `pages` list and includes)
- Modify: `dashboard-app/static/style.css` (agent card, memory, events, scan table)
- Test: `dashboard-app/tests/test_design_contracts.py`

**Interfaces:**
- Consumes from Task 1: `agents`, `agent_events`, `agent_scan`, `agent_scan_files`, `agent_scan_error`.
- Produces: `#page-agents`, `#tab-agents`, and the `.agents-scan-table` contract that Task 3's run card sits under.

- [ ] **Step 1: Write the failing design-contract test**

Add to `dashboard-app/tests/test_design_contracts.py`:

```python
def test_agents_tab_renders_roster_and_a_contained_scan_table():
    assert '("agents", "Agents")' in INDEX
    assert 'include "pages/agents.html"' in INDEX
    page = (ROOT / "templates" / "pages" / "agents.html").read_text()
    assert 'id="page-agents"' in page
    assert 'aria-labelledby="tab-agents"' in page
    assert "agent_events[agent.slug]" in page
    assert "agent_scan.jobs" in page
    assert "No memory recorded" in page
    assert "No Scout scan yet" in page
    assert 'class="ops-table-scroll"' in page
    assert 'class="ops-table agents-scan-table"' in page
    assert ".agents-scan-table" in STYLE
    block = re.search(r"\.agents-scan-table \{[^}]*\}", STYLE)
    assert block and "min-width" in block.group(0)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd dashboard-app && venv/bin/python -m pytest tests/test_design_contracts.py::test_agents_tab_renders_roster_and_a_contained_scan_table -q`

Expected: FAIL because the page and nav entry do not exist.

- [ ] **Step 3: Create `templates/pages/agents.html`**

Use this DOM contract:

- Wrapper: `<div class="page" id="page-agents" role="tabpanel" aria-labelledby="tab-agents">`.
- Header: `<h2>Agents</h2>` and a paragraph naming the Forge job-hunting team.
- Roster section: loop `agents` into `.card.agent-card` articles. Each shows `agent.name`, a `badge` with `agent.mode`, `agent.description`, the memory summary in `<pre class="agent-memory">`, and `agent_events[agent.slug]` as a `<ul class="agent-events">` of `when`, `event`, `detail`. If `agent.summary` is empty, render `<p class="muted">No memory recorded.</p>`. If `agent.events_error`, render it in `<p class="run-status is-failed">`. If no agents, render an `.empty-state` saying no definitions were found in `.opencode/agents/`.
- Scan section: if `agent_scan`, show `generated_at` (or `timestamp not recorded`), `job_count`, `primary_count`, `secondary_count`, `scan_id`, and `notes`. Put JSON/Markdown buttons in `.run-actions` using the existing output-dialog contract: `<button class="action-btn action-btn-ghost" data-output="{{ agent_scan_files.json }}" data-output-label="Scout scan JSON">JSON</button>` and the same for `markdown` only when present.
- Scan table: `.ops-table-scroll` wrapper with `tabindex="0" role="region" aria-label="Scout scan results"`, then `<table class="ops-table agents-scan-table">` with a visually hidden caption. Columns: Job, Score, Company, Location, Salary, Source, Posted, Track. Link the job title only when `job.url` is present (`target="_blank" rel="noopener noreferrer"`). Render missing values as blank cells; do not invent a dash value or a default score. Put `job.work_model` as a `<small>` under the location.
- If `agent_scan_error`, render it in `.empty-state.empty-state-pad`. If no scan and no error, render `No Scout scan yet. Run one below.` (the run card arrives in Task 3).

- [ ] **Step 4: Register the tab and include**

In `templates/index.html`:

- Add `("agents", "Agents")` immediately after `("interviews", "Interviews")` in the `pages` list.
- Add `{% include "pages/agents.html" %}` with the other page includes.

- [ ] **Step 5: Add the agent styles**

Add near the other card/table styles in `static/style.css`:

```css
.agent-card .card-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.agent-memory {
  margin: 8px 0 12px;
  padding: 10px;
  max-height: 220px;
  overflow: auto;
  white-space: pre-wrap;
  font-family: var(--mono);
  font-size: 11px;
  line-height: 1.5;
  background: var(--paper-deep);
  border: 1px solid var(--border-light);
  border-radius: var(--radius);
}
.agent-events {
  list-style: none;
  margin: 6px 0 0;
  padding: 0;
  display: grid;
  gap: 6px;
  font-size: 12px;
}
.agent-event-when {
  color: var(--text-muted);
  font-family: var(--mono);
  font-size: 10px;
}
.agents-scan-table {
  min-width: 900px;
}
.agents-scan-table td:first-child {
  min-width: 220px;
}
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd dashboard-app && venv/bin/python -m pytest tests/test_design_contracts.py::test_agents_tab_renders_roster_and_a_contained_scan_table -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add dashboard-app/templates/pages/agents.html dashboard-app/templates/index.html dashboard-app/static/style.css dashboard-app/tests/test_design_contracts.py
git commit -m "feat(dashboard): add the Agents tab"
```

---

### Task 3: Scout runner and free OpenCode model picker

**Files:**
- Modify: `dashboard-app/app.py` (`SKILL_RUNNERS`, `_resolve_run`, `_card_allows_provider`, `_skill_catalog_payload`)
- Modify: `dashboard-app/static/app.js` (model picker provider filter)
- Modify: `dashboard-app/templates/pages/agents.html` (run card)
- Modify: `dashboard-app/templates/pages/run.html` (Other workspace tools grid)
- Test: `dashboard-app/tests/test_agents_runner.py`
- Test: `dashboard-app/tests/test_design_contracts.py`

**Interfaces:**
- Consumes from Task 1: `agent_scan*` context is already on the page.
- Produces: `SKILL_RUNNERS["scout-scan"]` with `kind: "opencode-agent"`, `agent: "scout"`, `options: True`, `providers: ["opencode"]`; catalogue entries carry `providers`; `app.js` hides non-allowed providers and selects the first allowed model.

- [ ] **Step 1: Write the failing runner tests**

Create `dashboard-app/tests/test_agents_runner.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd dashboard-app && venv/bin/python -m pytest tests/test_agents_runner.py -q`

Expected: FAIL with `KeyError: 'scout-scan'`.

- [ ] **Step 3: Add the `scout-scan` runner**

Add this entry to `SKILL_RUNNERS` (near the other job tools):

```python
"scout-scan": {
    "label": "Run Scout scan",
    "blurb": "Free search-and-rank pass over the configured job sources. Writes a scan to workspace/agents/scout/outputs/.",
    "icon": "◎",
    "kind": "opencode-agent",
    "agent": "scout",
    "prompt": (
        "Today is {today}. You are Scout. Read workspace/agents/scout/memory/index.md "
        "and the search history in workspace/agents/scout/memory/log.jsonl first. "
        "Run a free search-and-rank pass using the job sources configured for the "
        "system; if none are configured, use the sources recorded in your memory. "
        "Merge and de-duplicate listings, score every listing 0-100 against "
        "Roosevelt's profile, and read no full job descriptions. Write the complete "
        "result to workspace/agents/scout/outputs/scan-{today}.json and a readable "
        "summary to workspace/agents/scout/outputs/scan-{today}.md. Update "
        "workspace/agents/scout/memory/index.md and append your events to "
        "workspace/agents/scout/memory/log.jsonl. Do not run Job Reader, do not "
        "tailor a CV, and do not use any paid step. Finish by reporting source "
        "failures, the number of listings found and scored, and the top matches."
    ),
    "options": True,
    "providers": ["opencode"],
    "read_only": False,
},
```

- [ ] **Step 4: Resolve the agent in `_resolve_run`**

In the `if provider == "opencode":` branch, build the argv in this order:

```python
argv = [exe, "run", "--standalone"]
if cfg.get("kind") == "opencode-agent":
    argv += ["--agent", cfg["agent"]]
argv += ["-m", model_id, prompt]
```

Keep the existing `--standalone` comment. Do not add `--auto` or a shell.

- [ ] **Step 5: Enforce the provider limit in `_card_allows_provider`**

Replace the always-true body with:

```python
allowed = cfg.get("providers")
if allowed and provider not in allowed:
    return False, f"{cfg['label']} only supports {', '.join(allowed)} models."
return True, None
```

Update the docstring: cards that declare `providers` are restricted; every other card keeps the existing permissive behavior.

- [ ] **Step 6: Publish `providers` in the catalogue**

In `_skill_catalog_payload()`, add `"providers": cfg.get("providers"),` to each skill dict.

- [ ] **Step 7: Filter the model picker in `static/app.js`**

Inside `renderItem`, before the model loop:

```javascript
const allowedProviders = Array.isArray(s.providers) && s.providers.length ? s.providers : null;
const providerName = (p) =>
    p === "claude" ? "Claude" : p === "opencode" ? "OpenCode" : p.charAt(0).toUpperCase() + p.slice(1);
const providerLabel = (p) =>
    p === "opencode" ? "OpenCode — free models" : `${providerName(p)} — local catalogue`;
```

In the provider loop, skip disallowed providers before the empty check:

```javascript
if (allowedProviders && !allowedProviders.includes(provider)) continue;
if (!models || !models.length) continue;
```

After the existing `let defaultValue = \`claude:${s.model || "sonnet"}\`;`, add:

```javascript
if (allowedProviders) {
    const provider = allowedProviders.find((p) => providerModels[p]?.length);
    defaultValue = provider
        ? `${provider}:${providerModels[provider][0].id}`
        : `${allowedProviders[0]}:`;
}
```

After the provider loop, when a restricted card has no models at all, append a disabled option:

```javascript
if (allowedProviders && !allowedProviders.some((p) => providerModels[p]?.length)) {
    const option = el("option", null, `No free ${providerName(allowedProviders[0])} models`);
    option.value = "";
    option.disabled = true;
    option.selected = true;
    modelPicker.appendChild(option);
}
```

- [ ] **Step 8: Add the run card to the Agents page**

Append this card to `templates/pages/agents.html` after the scan section:

```html
<div class="card">
  <div class="card-title">Run a scan</div>
  <p>Starts Scout's free search-and-rank pass. It reads no full job descriptions and never runs Job Reader or CV Adapter.</p>
  <div class="run-grid" data-run-grid data-skills="scout-scan" aria-busy="true">
    <p class="run-empty">Loading the scan runner&hellip;</p>
  </div>
</div>
```

- [ ] **Step 9: Show the runner on the Run tab too**

Add `scout-scan` to the “Other workspace tools” grid's `data-skills` list in `templates/pages/run.html`.

- [ ] **Step 10: Add the failing UI contract tests**

Add to `dashboard-app/tests/test_design_contracts.py`:

```python
def test_run_picker_can_be_limited_to_allowed_providers():
    js = (ROOT / "static" / "app.js").read_text()
    assert "const allowedProviders = Array.isArray(s.providers)" in js
    assert "if (allowedProviders && !allowedProviders.includes(provider)) continue;" in js
    assert "allowedProviders.find((p) => providerModels[p]?.length)" in js
    assert "No free ${providerName(allowedProviders[0])} models" in js


def test_scout_scan_is_available_on_the_agents_and_run_tabs():
    agents_page = (ROOT / "templates" / "pages" / "agents.html").read_text()
    run_page = (ROOT / "templates" / "pages" / "run.html").read_text()
    assert 'data-skills="scout-scan"' in agents_page
    assert "scout-scan" in run_page
```

- [ ] **Step 11: Run the runner and design tests**

Run: `cd dashboard-app && venv/bin/python -m pytest tests/test_agents_runner.py tests/test_design_contracts.py -q`

Expected: PASS.

- [ ] **Step 12: Commit**

```bash
git add dashboard-app/app.py dashboard-app/static/app.js dashboard-app/templates/pages/agents.html dashboard-app/templates/pages/run.html dashboard-app/tests/test_agents_runner.py dashboard-app/tests/test_design_contracts.py
git commit -m "feat(dashboard): run Scout from the dashboard on a free OpenCode model"
```

---

### Task 4: Documentation and end-to-end verification

**Files:**
- Modify: `dashboard-app/CLAUDE.md`
- Modify: `CODE.md`
- Modify: `docs/superpowers/specs/2026-11-09-agents-dashboard-design.md` (status only)

**Interfaces:**
- Consumes: the module, tab and runner from Tasks 1–3.
- Produces: the file map and data-source documentation the next agent reads.

- [ ] **Step 1: Update `dashboard-app/CLAUDE.md`**

- Add `agents.py` to the file map: read-only loader for the roster, memory/events and newest valid Scout scan; change it when the Agents tab data changes.
- Add `agents` to the `templates/pages/<tab>.html` list.
- Add an **Agents tab** bullet under “Data sources → tabs”: `.opencode/agents/*.md`, `workspace/agents/<slug>/memory/index.md` plus the newest five valid `log.jsonl` events, and the newest `workspace/agents/scout/outputs/scan-*.json` with a `jobs` list. Missing files, malformed JSONL and unreadable scans render explicit empty states; the table sorts by score with missing scores last; full JSON/Markdown open through the existing `/api/file` output dialog. The scan card is `scout-scan`, an `opencode-agent` runner restricted to free OpenCode models.
- Extend the “Add a Run-tab button” recipe: `kind: "opencode-agent"` runs `opencode run --standalone --agent <agent> -m <model> <prompt>`; set `agent` and `providers: ["opencode"]` to restrict the card to free OpenCode models.
- Extend the “Run records” recipe: a card with `providers` rejects a model from another provider before launch.

- [ ] **Step 2: Update `CODE.md`**

Add a Dashboard entry-point row:

```markdown
| `dashboard-app/agents.py` | Read-only Forge agent roster, memory/events and latest Scout scan loader for the Agents tab |
```

- [ ] **Step 3: Mark the design approved**

Change the design doc status line to:

```markdown
_Status: approved · 2026-11-09 · scope chosen by Roosevelt: “Agents tab + free scan”_
```

- [ ] **Step 4: Run the full suite**

Run: `cd dashboard-app && venv/bin/python -m pytest tests/ -q`

Expected: all tests pass.

- [ ] **Step 5: Verify the page and screenshots**

Run:

```bash
cd dashboard-app
venv/bin/python -c "import app; print('import OK')"
launchctl kickstart -k gui/$(id -u)/com.cloudtransition.dashboard
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/
sh screenshot.sh agents 390
sh screenshot.sh agents 1280
```

Expected: `import OK`, `200`, and two PNG paths. Open both images and confirm the roster, scan table, and run card are readable with no page-level horizontal overflow; the scan table scrolls inside its card.

- [ ] **Step 6: Refresh the repo graph**

Run: `trail build`

Expected: the graph refreshes with the new module, template and runner.

- [ ] **Step 7: Commit**

```bash
git add dashboard-app/CLAUDE.md CODE.md docs/superpowers/specs/2026-11-09-agents-dashboard-design.md
git commit -m "docs(dashboard): document the Agents tab and Scout runner"
```

---

## Self-review notes

- Spec coverage: roster/memory/events → Task 1; scan table and empty states → Tasks 1–2; run card, model picker, provider restriction and run invariants → Task 3; docs and manual proof → Task 4.
- Type consistency: `agent_events` is a slug-keyed map in both the loader and the template; `agent_scan_files` uses `json`/`markdown`; `scout-scan` is the single runner id everywhere.
- The scan card is the only card with `providers`; every other card keeps the existing permissive provider behavior, so the existing “all providers on all cards” test stays valid.
