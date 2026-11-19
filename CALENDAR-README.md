# Google Calendar and scheduled checklist work

Local CLI for explicitly adding selected `TASKS.md` checkboxes as dated **Google Tasks**. They appear on the chosen day in Google Calendar when Tasks display is enabled. These are not meeting events: no attendees, duration, start/end times or automatic dates. The Tasks API stores a scheduled day and discards time-of-day.

## CLI boundaries

- `list` and `preview` use standard-library Python plus the existing local secret masker. No network, Google SDK, OAuth, runtime file creation or source edits.
- CLI publication requires a current, exact preview and its approval fingerprint. The CLI and scheduled KB ingestion never activate dashboard automation.
- Google authorization is **separate from Gmail**, with a distinct Tasks token. The scope is `https://www.googleapis.com/auth/tasks`. Google grants management of all Tasks; this implementation only lists/reconciles and inserts explicitly approved items. It never updates or deletes tasks, accesses Calendar events, or mutates mail.
- No bidirectional sync. Checking a Markdown box does not complete or delete its Google task. Changing a published date/title does not edit the remote task or create another automatically.
- Build approval is not OAuth consent or approval of a live batch. Obtain both separately before using a real account. No paid summarization is part of this feature.

[Approved requirements, acceptance cases and implementation plan](docs/plans/checklist-calendar/).

## Dashboard agenda and automatic creation

Today → **Upcoming calendar** shows a seven-day agenda from selected calendars, plus Google Tasks tracked by this integration. Event/Task, all-day, calendar name, timezone, refresh time and source failures remain explicit. A read failure never means no events.

Build approval does not authorize Google consent or live automation. Complete setup on the Mac:

1. Enable **Google Calendar API** in your chosen Google Cloud project. Keep **Google Tasks API** enabled. In Google Auth Platform, configure the audience and your test-user account when using External/Testing.
2. Use a Desktop OAuth client. Save its downloaded JSON at `~/.local-routines/personal-kb/calendar/events/credentials.json` with mode `600`, inside an owner-only mode-`700` directory. Keep it outside the workspace and chat. Never delete or widen the existing Tasks token.
3. With explicit permission, run from the workspace:

   ```sh
   .kb-venv/bin/python calendar_bridge.py calendar-login
   ```

   Alternatively pass `--credentials /absolute/private/calendar-client.json` for an explicitly chosen owner-only, nonsymlink client file. Consent uses a temporary Mac loopback callback. Phones use server-held authorization; they do not receive tokens.
4. Open Today → Upcoming calendar → **Settings and connection**, then **Refresh**. Choose read calendars, an owned event calendar, an existing Tasks list, an IANA timezone and individual allowed source files. Missing Tasks authorization requires the separate Tasks login below, not a combined grant.
5. **Save view (automation off)** to view calendars without publishing. **Review backlog and automation** lists exact outgoing titles, schedules, sources and destinations. Only then select the consent checkbox and **Enable automation**.
6. For live verification, separately approve one harmless dated item and one explicitly timed item with exact destinations. Do not activate a real backlog merely to test. Do not delete test items without permission.

Calendar requests `calendar.calendarlist.readonly`, `calendar.events.readonly` and `calendar.events.owned`, under `https://www.googleapis.com/auth/`. The write scope also permits modifying and deleting events on owned calendars, although this feature never does either. Tasks retains its Tasks-only grant. Calendar and Tasks failures are independent; rejected authorization requires reconnecting only the affected grant. No request opens login automatically.

### What is sent

- Sources are only selected task realms and actual interview `next_steps` entries. Private academic, employer and credential paths, symlink aliases and paths outside the workspace are excluded.
- A date creates a date-only, needsAction Google Task. Explicit local start/end plus an IANA timezone creates an attendee-free event instead. Undated work stays local. No date, duration or appointment is inferred from prose or application status.
- Only sanitized title, schedule and opaque identity fields leave the Mac. Notes, contacts, adjacent file text and preparation files are not sent. Tailnet dashboard viewers can see the selected agenda.
- Capture and Schedule save local source files first. Local checkbox changes do not depend on Google availability. Schedule is available on Today/Tasks rows and individual interview actions. Structured metadata is hidden from displayed titles and retained during toggles.
- Markdown example: `- [ ] Prepare agenda <!-- calendar: {\"date\":\"2026-11-16\"} -->`. Timed example: `<!-- calendar: {\"start\":\"2026-11-16T14:00\",\"end\":\"2026-11-16T15:00\",\"timezone\":\"America/New_York\"} -->`. The editor also preserves an opaque `id` for stable identity. Interview actions use date/start/end/timezone and `calendar_id`.
- Invalid dates, missing end/timezone and nonexistent or ambiguous DST local times are rejected. Ambiguous duplicate source entries require review rather than guessed identity.

### Automatic worker and recovery

While the dashboard service runs, one bounded pass checks enabled sources every 60 seconds, even without an open browser. GET requests cannot activate or publish. Source/destination changes require renewed backlog confirmation. **Pause automation** persists across restarts; a request already in progress may finish.

Create-only is deliberate: changes after publication show **Needs review** with the Google link. There is no automatic remote update, deletion, replacement, completion sync or import of remote edits. Local deletion never deletes the Google item. Keep private mappings: removing state discards duplicate protection.

Private state stays under `~/.local-routines/personal-kb/calendar/`: `events/credentials.json` and `events/token.json` hold the separate Calendar client/grant; `dashboard/policy.json` holds policy and local outcomes; `dashboard-publish.json` holds durable provider intents/IDs. Existing Tasks `token.json` and CLI `state.json` remain separate. JSON is owner-only and nonsymlink. Durable intents, Tasks marker reconciliation and deterministic event identities prevent blind retry after uncertain responses. An unresolved outcome remains Needs review, not a claimed success.

The dashboard uses the existing `.kb-venv` for Google calls; no new listener, database, frontend build, paid API or model is required. Restart after code changes with `launchctl kickstart -k gui/$(id -u)/com.cloudtransition.dashboard`.

Approved requirements, focused checks and design reference: [`docs/plans/dashboard-google-calendar/`](docs/plans/dashboard-google-calendar/rd.md).


## Local selection and preview

Run from the workspace, or invoke the CLI by absolute path from any directory. The default source is the workspace's `TASKS.md`, not the caller's working directory.

```sh
python3 calendar_cli.py list
python3 calendar_cli.py list --source /absolute/path/to/checklist.md
```

The JSON list contains unchecked boxes, heading labels and line-number selection IDs. Checked boxes and fenced examples are excluded. An empty source returns `[]` plus an explicit no-items message. Missing sources and invalid selections fail; there is no fallback to another source.

Choose existing task-list IDs with the separately authorized `lists` command below. Preview requires a destination ID and an explicit `YYYY-MM-DD` for every selection:

```sh
python3 calendar_cli.py preview --task-list LIST_ID \
  --item 12=2026-11-10 --item 19=2026-11-12
```

Replace `LIST_ID`, line IDs and dates with your choices. The entire outgoing batch is printed as JSON: destination, sanitized titles, date-only RFC3339 values, status, notes markers and fingerprint. Unselected checklist contents are not included. Secret-looking title values are masked before preview and publication; private keys and over-limit titles are refused. Google currently permits 1024 title characters and 8192 notes characters.

Preview prints only; it does **not** save an approval file. If you choose to save one, redirect into the private runtime with owner-only permissions:

```sh
mkdir -p "$HOME/.local-routines/personal-kb/calendar"
chmod 700 "$HOME/.local-routines/personal-kb/calendar"
umask 077
python3 calendar_cli.py preview --task-list LIST_ID --item 12=2026-11-10 \
  > "$HOME/.local-routines/personal-kb/calendar/preview.json"
chmod 600 "$HOME/.local-routines/personal-kb/calendar/preview.json"
```

Check command success and read the full JSON before approving. Do not put this file, tokens, mappings or private evidence into shared docs. Shell redirection is your explicit write, not an automatic preview side effect.

## Separate Google Tasks authorization

Use the already-installed `.kb-venv` interpreter for Google operations; no new dependency environment is required. Obtain permission before starting consent or enabling an API in Google Cloud.

1. Enable Google Tasks API in the explicitly chosen Cloud project if needed.
2. Use an explicitly chosen **Desktop app OAuth client**, preferably separate from the Gmail client to avoid merged grants. Save its downloaded configuration at `~/.local-routines/personal-kb/calendar/credentials.json`, mode `600`, inside the mode-`700` directory. Do not use or copy the Gmail token as Tasks authorization.
3. Start login only with permission:

```sh
.kb-venv/bin/python3 calendar_cli.py login
# Or explicitly choose a private, nonsymlink Desktop client JSON:
.kb-venv/bin/python3 calendar_cli.py login --credentials /absolute/private/client.json
```

The CLI warns about the breadth of Google's Tasks scope before launching consent. Only Tasks scope is requested; granted scope must be exactly Tasks. OAuth uses a temporary loopback callback and persists `calendar/token.json` atomically, mode `600`. Gmail credentials and token files are never read by this feature. `lists` and `publish` never launch login automatically; missing/revoked/wrong-scope authorization fails safely. An expired valid Tasks grant may refresh its own token.

```sh
.kb-venv/bin/python3 calendar_cli.py lists
```

This returns existing list IDs and sanitized titles. The app does not create task lists.

## Exact-batch publication

Review the saved JSON, then separately authorize its exact titles, dates and destination. Copy the complete `approval` value; do not approve an unseen hash or infer approval from previous build/login permission.

```sh
.kb-venv/bin/python3 calendar_cli.py publish \
  --preview-file "$HOME/.local-routines/personal-kb/calendar/preview.json" \
  --approve EXACT_PREVIEW_HASH
```

Publication refuses modified fields, added fields, stale source content, checked/deleted selections, changed destination or mismatched approval. Unique unchanged tasks survive unrelated source line shifts. Duplicate identities retain occurrence/count metadata; ambiguous movement or changed duplicate groups fail closed.

Output contains opaque source keys, returned task IDs and `published`, `already_published`, `failed` or `uncertain` outcomes. It never prints provider response text or source bodies. Exit is nonzero for failure or uncertainty. A stopped partial batch reports only attempted/already-mapped entries; later selections were not sent. Repeat the same approved preview to resume safely, subject to current-source validation.

### Recovery and idempotence

- A distinct calendar lock refuses concurrent publication. The Gmail ingestion lock is separate and unaffected.
- Atomic state saves a pending intent **before** each insert and records the returned ID after success. Inserts have no automatic client retries.
- A definitive HTTP rejection, such as 401/403/429, is recorded failed. A later explicitly invoked publication can retry that failed selection, while retaining successful mappings.
- Timeouts, 5xx responses, missing IDs and interrupted success persistence remain pending/uncertain. On a later invocation, the app paginates the chosen task list, including completed/hidden tasks, looking for the exact opaque marker and approved body.
- Exactly one matching task recovers its actual ID. Zero matches, conflicting content or multiple matches remain uncertain; **no blind insert** follows. A completed or externally edited uncertain task may require explicit account/state investigation.
- Already-published payload conflicts and changed duplicate groups require explicit resolution. There is deliberately no force-retry, state-reset, remote update or deletion command. Never delete `state.json` to clear an error: that discards duplicate protection.

Keep the original preview and state until an uncertain outcome is resolved. If the selected Markdown changes during recovery, do not manufacture a replacement fingerprint or remove state; investigate the stored intent and actual account together.

## Private runtime

Default: `~/.local-routines/personal-kb/calendar/`.

| File | Purpose |
| --- | --- |
| `credentials.json` | Explicitly provided Desktop OAuth client configuration |
| `token.json` | Separate Tasks grant; atomically saved/refreshed |
| `state.json` | Approved bodies, source identities, pending outcomes and returned IDs |
| `ingest.lock` | Calendar-only exclusion lock; never the parent KB lock |
| `preview.json` | Optional user-redirected preview, not automatically generated |

Runtime directories are mode `700`; runtime JSON is a nonsymlink owner-owned regular file with mode `600`. `--runtime PATH` is an explicit override for login/lists/publish, not an alternate source. Paths containing symlinks are refused; choose the canonical path. Keep overrides under a `personal-kb` directory or outside the workspace. Existing shared-index and HTTP privacy policies exclude `personal-kb` directories and all symlink aliases; Git ignores `personal-kb/` at every depth. Arbitrary private runtime names inside curated folders do not gain this directory-name protection.

The app creates no provider error log. Console errors use safe categories rather than provider bodies/credential URLs. If recording private diagnostics manually, keep them in the private runtime. Sanitized acceptance evidence belongs in the ignored `docs/plans/checklist-calendar/eval-evidence/`, never a shared index.

## Verification

```sh
python3 -m unittest discover -s calendar_tests
python3 -m unittest discover -s kb_tests
dashboard-app/venv/bin/python -m pytest dashboard-app/tests -q
python3 -m unittest discover -s second-brain/tests
python3 -m unittest discover -s visual-second-brain/tests
node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/checklist-calendar/eval.md
node ~/.agents/skills/write-evals/scripts/evals.mjs check docs/plans/checklist-calendar
```

Automated tests use synthetic Markdown, private temporary directories and an in-memory official-service-shaped Tasks fake. They exercise real CLI output, persisted recovery, index generation and dashboard file/toggle routes, without real tokens or network calls. Acceptance cases U6 (separate Tasks consent) and U5 (real publish, Calendar visibility, no duplicate on repeat) were verified on 2026-11-06 against the real account; sanitized evidence is kept in the ignored `docs/plans/checklist-calendar/eval-evidence/`.

A published task appears in the Calendar day's all-day row. To give a task a specific time of day (for example 4:00 p.m.), set it in Google Calendar or Google Tasks directly: the public API has no field for it and reports such tasks as date-only.

API references: [Task resource and scheduled-day semantics](https://developers.google.com/workspace/tasks/reference/rest/v1/tasks), [task insertion](https://developers.google.com/workspace/tasks/reference/rest/v1/tasks/insert), [paginated task listing and hidden/completed options](https://developers.google.com/workspace/tasks/reference/rest/v1/tasks/list).
