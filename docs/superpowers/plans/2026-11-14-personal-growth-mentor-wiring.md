# Personal Growth Mentor Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `personal-growth-mentor` durable workspace memory and a dashboard roster entry plus an OpenCode-only Mentor check-in runner.

**Architecture:** Reuse the existing file-backed agent state, Agents-tab roster, and `SKILL_RUNNERS` / `/api/skills/run` path. Add no endpoint, database, frontend framework, or paid provider.

**Tech Stack:** Markdown/YAML frontmatter, Python 3.14, FastAPI, Jinja2, pytest, existing dashboard JavaScript runner grid.

**Spec:** `docs/superpowers/specs/2026-11-14-personal-growth-mentor-wiring-design.md`

## Global Constraints

- Workspace files are the database; dashboard loaders stay read-only.
- Mentor runner uses `kind: "opencode-agent"`, `agent: "personal-growth-mentor"`, and `providers: ["opencode"]` only.
- Preserve argv execution, CSRF checks, model validation, single-flight runs, and the 30-minute deadline.
- Mentor writes only `workspace/agents/personal-growth-mentor/memory/`; no live model call is needed for verification.
- Use `dashboard-app/venv/bin/python`, never system Python.
- Do not run git mutations unless Roosevelt explicitly asks.

## Review Focus

- An empty new `log.jsonl` must mean “no events,” not a dashboard error; pinned by Task 2's empty-log test.
- A mentor definition without `Your name is …` must still sort immediately after the job-hunting team; pinned by Task 2's roster test.
- Missing, too-short, or over-1000-character goal input must be rejected before launch; pinned by Task 3's endpoint test.
- A non-OpenCode model must not launch the mentor; pinned by Task 3's provider test.
- Adding the mentor card must not remove the Scout scan runner; pinned by Task 4's template test.

---

### Task 1: Mentor state and workspace routers

**Files:**
- Create: `workspace/agents/personal-growth-mentor/memory/index.md`
- Create: `workspace/agents/personal-growth-mentor/memory/log.jsonl`
- Modify: `workspace/agents/README.md`
- Modify: `AGENTS.md:33-52`
- Modify: `docs/superpowers/specs/2026-11-14-personal-growth-mentor-wiring-design.md:3`

**Interfaces:**
- Consumes: existing agent memory convention (`index.md` summary plus append-only JSON objects in `log.jsonl`).
- Produces: `workspace/agents/personal-growth-mentor/memory/` for Tasks 2–4 and future mentor runs.

- [ ] **Step 1: Create the initial memory files**

`index.md` has title `# Personal Growth Mentor — memory index`, `_Last updated: 2026-11-14_`, a pointer to `log.jsonl`, and empty starting sections for current focus, commitments, and run history. State explicitly that no mentor runs, goals, or commitments have been recorded yet; invent none. `log.jsonl` is zero bytes.

- [ ] **Step 2: Document the new state directory**

Add a `personal-growth-mentor` row to `workspace/agents/README.md` with memory path `workspace/agents/personal-growth-mentor/memory/` and outputs `—`; explain that it is independent of the Forge job-hunting pipeline. In `AGENTS.md`, replace the mentor's state `—` with a link to `workspace/agents/personal-growth-mentor/` and include it in the state-directory prose. Change the design-doc status from `draft` to `approved`.

- [ ] **Step 3: Verify files and links**

Run:

```bash
test -f workspace/agents/personal-growth-mentor/memory/index.md
test -f workspace/agents/personal-growth-mentor/memory/log.jsonl
test ! -s workspace/agents/personal-growth-mentor/memory/log.jsonl
rg -n "personal-growth-mentor" AGENTS.md workspace/agents/README.md
```

Expected: all commands exit 0; `rg` shows the state path in both routers.

### Task 2: Roster ordering and empty-memory behavior

**Files:**
- Modify: `dashboard-app/tests/test_agents.py`
- Modify: `dashboard-app/agents.py:20-26,155-178`

**Interfaces:**
- Consumes: Task 1's memory layout and existing `load_roster()` / `load_memory(slug: str)`.
- Produces: roster slug order `forge`, `scout`, `job-reader`, `cv-adapter`, `personal-growth-mentor`, then unknown slugs alphabetically; `load_memory()` returns `events_error is None` for an empty log.

- [ ] **Step 1: Write failing roster and empty-log tests**

Add to `dashboard-app/tests/test_agents.py`:

```python
def test_load_roster_orders_personal_growth_mentor_before_unknown_agents(workspace):
    defs = workspace / ".opencode" / "agents"
    _agent(defs, "cv-adapter", name="CV Adapter")
    _agent(defs, "helper", name="Helper")
    (defs / "personal-growth-mentor.md").write_text(
        "---\ndescription: Growth mentor\nmode: subagent\n---\n# Mentor\n"
    )

    roster = agents.load_roster()

    assert [a["slug"] for a in roster] == [
        "cv-adapter", "personal-growth-mentor", "helper"
    ]
    assert roster[1]["name"] == "Personal Growth Mentor"


def test_load_memory_empty_log_has_no_error(workspace):
    memory = (
        workspace / "workspace" / "agents" / "personal-growth-mentor" / "memory"
    )
    memory.mkdir(parents=True)
    (memory / "index.md").write_text("# Personal Growth Mentor\n")
    (memory / "log.jsonl").write_text("")

    view = agents.load_memory("personal-growth-mentor")

    assert view["summary"] == "# Personal Growth Mentor"
    assert view["events"] == []
    assert view["events_error"] is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd dashboard-app && venv/bin/python -m pytest tests/test_agents.py -k 'personal_growth_mentor or empty_log' -q`
Expected: roster order assertion fails and empty log reports `log.jsonl contains no valid JSON objects.`

- [ ] **Step 3: Implement roster metadata and empty-log handling**

In `agents.py`, append `"personal-growth-mentor"` to `ROSTER_ORDER` after `"cv-adapter"` and add its `AGENT_LABELS` value `"Personal Growth Mentor"`. In `load_memory()`, preserve the malformed-nonempty-log error, but return no error when `log.jsonl` is empty or whitespace-only.

- [ ] **Step 4: Run the focused and full loader tests**

Run: `cd dashboard-app && venv/bin/python -m pytest tests/test_agents.py -q`
Expected: all pass, including the existing malformed-log test.

### Task 3: Mentor check-in runner

**Files:**
- Modify: `dashboard-app/tests/test_agents_runner.py`
- Modify: `dashboard-app/app.py` (`SKILL_RUNNERS`, beside the other agent cards)

**Interfaces:**
- Consumes: existing `RunRequest`, `_resolve_run()`, `_card_allows_provider()`, and `/api/skills/run`.
- Produces: `SKILL_RUNNERS["mentor-checkin"]`, accepting `RunRequest.input` as a required 3–1000 character goal/situation and launching agent `personal-growth-mentor`.

- [ ] **Step 1: Write failing runner configuration and resolution tests**

Add tests asserting:

```python
cfg = module.SKILL_RUNNERS["mentor-checkin"]
assert cfg["kind"] == "opencode-agent"
assert cfg["agent"] == "personal-growth-mentor"
assert cfg["providers"] == ["opencode"]
assert cfg["input_label"] == "Goal or situation"
assert cfg["input_type"] == "text"
assert cfg["read_only"] is False
```

With `_resolve_opencode_exe` monkeypatched to `/fake/opencode`, resolve a request using model `opencode:opencode/beam-free`, effort `default`, and input `Build a consistent sleep routine`. Assert argv begins:

```python
[
    "/fake/opencode", "run", "--standalone", "--agent",
    "personal-growth-mentor", "-m", "opencode/beam-free",
]
```

Assert the prompt contains the exact input, `{today}` was rendered, both mentor memory paths are present, and it forbids writes outside that memory directory. Assert `"--auto" not in spec["argv"]`.

- [ ] **Step 2: Write failing input and provider endpoint tests**

Monkeypatch `_load_opencode_models` to return `([{"id": "opencode/beam-free", "efforts": ["default"]}], True, None)`. With `TestClient` and `CSRF`:

- POST `mentor-checkin` without `input` → 400 containing `Goal or situation is required`.
- POST with `input: "x"` → 400 containing `Not a valid Goal or situation`.
- POST with 1001 characters → 400 containing `Not a valid Goal or situation`.
- POST with `model: "claude:sonnet"` and valid input → 400 containing `opencode`.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd dashboard-app && venv/bin/python -m pytest tests/test_agents_runner.py -k mentor -q`
Expected: failures because `mentor-checkin` is absent.

- [ ] **Step 4: Add the `mentor-checkin` card**

Add to `SKILL_RUNNERS`:

- `label: "Mentor check-in"`, `icon: "🌱"`.
- `kind: "opencode-agent"`, `agent: "personal-growth-mentor"`.
- `input_label: "Goal or situation"`, `input_type: "text"`, `input_pattern: r"^.{3,1000}$"`.
- `options: True`, `providers: ["opencode"]`, `read_only: False`.
- `blurb`: concise explanation that the mentor reads its memory, diagnoses one goal/situation, gives a next action, and updates its memory.

The prompt must include `{today}` and `{input}`; instruct the agent to read `workspace/agents/personal-growth-mentor/memory/index.md` and `log.jsonl` first, read only relevant workspace context, diagnose the real goal and primary bottleneck, give one concrete next action and accountability checkpoint, avoid invented facts/commitments and professional advice boundaries, update `index.md`, append one JSON event to `log.jsonl`, and write no files outside its own memory directory.

- [ ] **Step 5: Run runner tests**

Run: `cd dashboard-app && venv/bin/python -m pytest tests/test_agents_runner.py -q`
Expected: all existing Scout and new mentor tests pass.

### Task 4: Agents-tab card, docs, and full verification

**Files:**
- Modify: `dashboard-app/tests/test_design_contracts.py` (Agents-tab tests)
- Modify: `dashboard-app/templates/pages/agents.html`
- Modify: `dashboard-app/CLAUDE.md` (Agents tab/source notes)

**Interfaces:**
- Consumes: Task 3's runner id `mentor-checkin` and existing `data-run-grid` rendering.
- Produces: a visible Mentor check-in card on the Agents tab while preserving `data-skills="scout-scan"`.

- [ ] **Step 1: Write the failing template contract test**

Add:

```python
def test_agents_page_offers_mentor_checkin_without_replacing_scout():
    page = (ROOT / "templates" / "pages" / "agents.html").read_text()
    assert 'data-skills="mentor-checkin"' in page
    assert 'data-skills="scout-scan"' in page
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd dashboard-app && venv/bin/python -m pytest tests/test_design_contracts.py -k mentor_checkin -q`
Expected: fail on the missing mentor grid.

- [ ] **Step 3: Add the card and update dashboard documentation**

Add a separate `Mentor check-in` card to `agents.html` with a short blurb and:

```html
<div class="run-grid" data-run-grid data-skills="mentor-checkin" aria-busy="true">
  <p class="run-empty">Loading the mentor runner&hellip;</p>
</div>
```

Leave the Scout scan table and `data-skills="scout-scan"` unchanged. Update `dashboard-app/CLAUDE.md` to record the mentor memory path, roster placement, runner id, required input, and OpenCode-only provider restriction.

- [ ] **Step 4: Run all automated verification**

Run:

```bash
cd dashboard-app
venv/bin/python -c "import app; print('import OK')"
venv/bin/python -m pytest tests/ -q
```

Expected: `import OK` and all tests pass.

- [ ] **Step 5: Restart and smoke-check the dashboard**

Run:

```bash
launchctl kickstart -k gui/$(id -u)/com.cloudtransition.dashboard
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/
```

Expected: HTTP `200`. Do not start a live mentor model run as part of verification.
