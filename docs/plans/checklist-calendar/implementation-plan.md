# Checklist items in Google Calendar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Worker tasks do not run build, lint, tests or formatters mid-flight; the integration owner runs acceptance once after integration.

**Goal:** Select unchecked TASKS.md entries, preview exact dated Google Tasks, and publish only an explicitly approved batch without duplicates or unrelated mutations.

**Architecture:** Two focused standard-library modules own the immutable source/preview contract and permission-gated Google Tasks publication. A small CLI composes them. Runtime state is nested under the existing private personal-KB directory, but uses its own calendar lock/token/state and never changes Gmail or the KB database.

**Tech Stack:** Python standard library; existing private `.kb-venv` Google API and OAuth libraries loaded lazily for login/read-lists/publication only. No frontend or new service.

**Spec:** [approved requirements](rd.md) and [approved acceptance eval](eval.md), explicitly approved by the owner on 2026-11-06.

## Global Constraints

- Source defaults to absolute workspace TASKS.md; no implicit fallback to another file.
- One-way create only: no events API, completion sync, edit/delete, attendees, time blocks, notifications or background publishing.
- Explicit YYYY-MM-DD dates; due encoding preserves the selected day, not a time of day.
- Preview is local, standard-library-only and stdout-only: no login, network request, source mutation or runtime file write. The user can explicitly redirect it into an owner-only local file.
- Every outgoing title/date/list/notes marker is bound into an approval fingerprint. Publication revalidates current source contents before any remote write.
- Existing root `kb_privacy.redact`, `kb_runtime.private_directory`, and `kb_runtime.ingest_lock` are reused without changing their APIs. Calendar publication uses its own nested runtime, not the live Gmail ingestion lock.
- Default calendar runtime: `~/.local-routines/personal-kb/calendar/`. Separate `credentials.json`, `token.json`, `state.json`, and `ingest.lock` live there. Never read or overwrite Gmail token as Tasks credentials.
- OAuth requests exactly `https://www.googleapis.com/auth/tasks`; explain that Google's grant can manage all Tasks although this program only lists/reconciles and creates selected items. No Calendar scopes.
- Building approval does not authorize OAuth or live writes. No interactive Google login until separately authorized, and no real insert before exact title/day/list/payload approval.
- Remote insert is non-idempotent. Persist intent before sending; retain successes on partial failure. Timeouts/5xx/interruption are uncertain, never blindly retried. Reconcile by the exact opaque marker, or stop uncertain.
- Source, token, approvals and state never appear in shared docs/evidence/logs/HTTP readers. Use synthetic fixtures for automated checks and sanitize live evidence.
- No commits, deployments or global settings changes are part of this build. Preserve the running Gmail backfill and its no-spend gate.

## Files and shared contracts

Create:
- `calendar_model.py`: source parsing, identities, strict date/payload validation, preview/fingerprint/revalidation; stdlib plus existing secret masking only.
- `calendar_google.py`: lazy Tasks OAuth/service, task-list discovery, atomic private publication state, lock, reconciliation and safe results.
- `calendar_cli.py`: list/preview/login/lists/publish commands, safe user-facing errors, JSON preview and summary output.
- `calendar_tests/fixtures.py`, `calendar_tests/test_model.py`, `calendar_tests/test_google.py`, `calendar_tests/test_integration.py`: isolated synthetic behavior cases with exact eval names.
- `CALENDAR-README.md`: executable command examples and permission/private-state/one-way boundaries.

Modify `CODE.md` to route to the finished implementation and README. Existing exclusion rules already protect the entire nested personal-kb runtime; change existing privacy code only if the real alias-boundary test finds a gap.

### Model API (owned by source/preview worker)

```python
class CalendarError(ValueError):
    pass

def list_items(source: Path) -> list[dict]: ...
def make_preview(source: Path, selections: list[tuple[str, str]], tasklist: str) -> dict: ...
def validate_preview(preview: dict) -> None: ...
```

`list_items` returns only unchecked actual boxes, each `{id: str(line_number), line: int, title: str, heading: str}`. Preserve the dashboard's `- [ ]`/x/X, indentation and nearest-heading/emoji stripping conventions, while excluding fenced examples. No Flask/FastAPI import.

Preview JSON schema:

```json
{
  "version": 1,
  "source": "/absolute/source/TASKS.md",
  "tasklist": "existing-provider-list-id",
  "items": [
    {
      "key": "stable-opaque-source-identity",
      "source": {"line": 4, "title": "Review plan", "heading": "Work", "occurrence": 0, "count": 1},
      "body": {"title": "Review plan", "due": "2026-11-10T00:00:00.000Z", "status": "needsAction", "notes": "cloudtransition-checklist:opaque-source-identity"}
    }
  ],
  "approval": "sha256-of-canonical-preview-without-approval"
}
```

Identity is derived from resolved source path, exact heading/title and duplicate occurrence. Distinct headings/duplicate entries must not conflate. Current-source revalidation follows unique content across unrelated line moves, but rejects changed/checked/deleted source, altered multiplicity or moved ambiguous duplicates. Keep count/occurrence metadata so ambiguity fails closed. Never silently approve an edited body, task list, selected set, notes marker or source binding. Publish only the exact canonical schema, rejecting added fields.

`make_preview` masks secret-looking title text before showing it and hashes the exact outgoing body; reject private-key/empty/over-limit payloads rather than sending unsafe content. Title limit 1024 characters, notes limit 8192, confirmed against current official docs before implementation. An empty selection, duplicate selection ID or missing/invalid date is an error. `validate_preview` recomputes the fingerprint and calls the same field/date/source rules so handmade or edited files cannot bypass validation.

### Google API (owned by publication worker)

```python
TASKS_SCOPES = ("https://www.googleapis.com/auth/tasks",)

def login(runtime: Path, credentials: Path | None = None) -> None: ...
def build_service(runtime: Path): ...
def list_tasklists(service) -> list[dict]: ...
def publish(preview: dict, approval: str, runtime: Path, service=None) -> dict: ...
```

`publish` consumes only `calendar_model.CalendarError` and `validate_preview`. Service injection is for deterministic synthetic fixtures; production builds the official Tasks v1 service from the distinct token. No auth/login fallback. Validate exact scope and token freshness; explicit login only in `login`. List choices return `id`/`title` and paginate correctly.

Result schema:

```json
{"results": [{"key": "opaque", "status": "published", "task_id": "real-returned-id"}], "failed": 0, "uncertain": 0}
```

Other result statuses are `already_published`, `failed`, `uncertain`; never print task bodies or provider exception strings. Errors may carry whitelisted numeric HTTP status and exception class only. No automatic retries of inserts, including client's `num_retries`; reconciliation GET/list calls paginate and compare exact marker and approved payload. A unique exact match is recorded as the actual remote ID; zero/ambiguous/conflicting matches remain uncertain. Stop the batch after failure rather than transmitting further items without a clear outcome.

State JSON holds per-list/source-key intent, approved body and remote outcome. Use owner-only directory, symlink-safe paths, a separate lock and write-temp/fsync/atomic-replace so interruption cannot corrupt or forget successful/uncertain state. Retain group multiplicity to prevent a changed duplicate group from being remapped silently. Already-published conflicting payloads are reported as a conflict requiring explicit user resolution, not another insert or remote edit.

### CLI contract (integration owner)

```text
python3 calendar_cli.py list [--source PATH]
python3 calendar_cli.py preview --task-list ID --item LINE=YYYY-MM-DD [--item LINE=YYYY-MM-DD ...] [--source PATH]
.kb-venv/bin/python3 calendar_cli.py login [--runtime PATH] [--credentials PATH]
.kb-venv/bin/python3 calendar_cli.py lists [--runtime PATH]
.kb-venv/bin/python3 calendar_cli.py publish --preview-file PATH --approve EXACT_HASH [--runtime PATH]
```

Every subcommand supports the applicable options after its name. Default source is independent of cwd. List returns stable selection fields as JSON; empty list is explicit. Preview returns the complete schema as JSON and does not create a file. Publication requires a nonsymlink owner-only preview file, matching fingerprint and current source. Return nonzero for errors/partial/uncertain outcomes. Catch only known validation/filesystem/provider categories and never echo unsafe provider strings. Runtime overrides are for explicit local use/tests, still owner-only and never symlink paths.

## Task 1 — Source selection and immutable preview

- [x] Read dashboard parser conventions at app.py:169-207 and approved U1/U2/F1/F2/F3/F4/U4 constraints.
- [x] Create synthetic Markdown fixtures with code fences, headings/emoji, nested/checked boxes, duplicate titles, source movement, invalid dates and secret/instruction text.
- [x] Implement model API/schema and tests `test_list_checklist_items`, `test_preview_selected_batch`, `test_missing_and_ambiguous_source`, `test_stale_preview_rejected`, `test_date_and_payload_boundaries`.

Concrete assertions include:

```python
preview = make_preview(source, [("4", "2026-11-10")], "list-one")
assert preview["items"][0]["body"]["due"] == "2026-11-10T00:00:00.000Z"
assert preview["items"][0]["body"]["title"] == "Review plan"
assert source.read_bytes() == original
validate_preview(preview)
preview["items"][0]["body"]["due"] = "2026-11-11T00:00:00.000Z"
with self.assertRaises(CalendarError):
    validate_preview(preview)
```

Integration owner later runs `python3 -m unittest discover -s calendar_tests -p test_model.py`. No worker test commands while other work is in flight.

## Task 2 — Permission-isolated Tasks publication

- [x] Consult current Google Tasks resource/auth docs for limits, due encoding and scopes; use only the existing installed SDK.
- [x] Implement the Google API contract and isolated fake official-service fixtures in test_google.py, without live Google calls.
- [x] Cover `test_publish_approved_batch`, `test_repeat_publish_idempotent`, `test_auth_approval_and_untrusted_text`, `test_partial_publish_recovery`, `test_uncertain_insert_and_concurrency`.
- [x] Exercise actual persisted state across service reconstruction, failure after successful create, two overlapping publishers and interruption of atomic state replacement. Assert actual selected request bodies and unrelated mutation absence, not mock-forwarding echoes.

Concrete failure invariant:

```python
# Fake service records the remote task, then raises a timeout.
first = publish(preview, preview["approval"], runtime, service)
assert first["uncertain"] == 1
second = publish(preview, preview["approval"], runtime, service)
assert second["results"][0]["task_id"] == recorded_remote_id
assert service.created_count == 1
```

Integration owner later runs `python3 -m unittest discover -s calendar_tests -p test_google.py`.

## Task 3 — CLI and real privacy neighbors

- [x] Implement commands exactly as above; keep list/preview importable without Google libraries.
- [x] Add `test_cli_build_and_stdlib_preview` using a fresh subprocess from another cwd with SDK imports blocked, real CLI output and syntax compilation.
- [x] Add `test_existing_kb_and_google_boundaries`, `test_private_task_state_boundaries`, `test_source_and_dashboard_preserved`. Exercise existing KB fixture ingestion/search, actual index eligibility and real dashboard read routes with private-token/approval/source canaries and symlink aliases. Do not rely on source-text assertions.
- [x] Publish against the synthetic official-service fake from the CLI integration seam; verify exact selected set/day, unchanged Markdown bytes, persisted IDs, repeat idempotence and safe error status. Inspect actual existing task toggle behavior without changing its parser.

## Task 4 — Verification, docs and separate live permission

- [x] Run the approved automated eval and nearest suites once after integration. Fix actual failures without narrowing evals or weakening neighboring tests.
- [x] Smoke the real `calendar_cli.py list/preview` from `/tmp` with a temporary synthetic Markdown file; verify outputs and byte-identical source. No real task writes in this smoke.
- [x] Write CALENDAR-README.md with all commands, local-only preview/private redirection, separate OAuth scope breadth and selected-batch approval, uncertainty reconciliation, no auto-sync/events, runtime files and safe errors. Update CODE.md route in the same change.
- [x] Re-index/check curated docs; verify raw runtime/evidence remain excluded.
- [x] Ask permission only when ready for Tasks login. Before any real insert, display the exact nonsensitive item/date/list/payload locally and obtain exact-batch approval. Verify real Calendar visibility and repeat without duplicate; do not delete the task without consent.
- [x] Record U6/U5 only after actual OAuth and Calendar observation. Keep feature explicitly blocked if the required permission is not granted. Run `evals check docs/plans/checklist-calendar` and mark the final feature task done only when every case passes.

## Coverage self-review

U1/U2/F1/F2/F3 → model. U3/U4/F4/F5/F6 → publication and state. R1/R2/R3/R4/R5 → CLI/integration/neighbor checks. U5/U6 → separately authorized real Google login/publication and Calendar observation. No requirement is dropped; no automatic auth, writes, paid summaries or dashboard work is authorized by this plan.
