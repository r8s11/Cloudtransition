# Research 04 — KB/Gmail ingest and 24-hour incremental feasibility

Status: findings complete (2026-11-18)
Branch: `research/ingest-24h` (throwaway, pushed, no PR)

## Method and limits

Read-only investigation of the scripts and docs that own the behavior. No interactive
login was run, no live Gmail/Google API call was made, and no mail body or credential
was reproduced. One read-only `python3 kb.py stats` was run to observe freshness/counts
only (no content). All findings cite the owning source file and line.

## 1. Where the scripts live and exact invocations

The KB is a set of Python files at the workspace root, not inside `second-brain/`.
`KB-README.md:3` states the split explicitly: `kb.py` et al. are the private KB;
`second-brain/brain.py` indexes curated workspace documents and is a different system.

| File | Role (source) |
| --- | --- |
| `ingest_all.py` | CLI that runs sources with per-source error isolation, lock, safe counts (`ingest_all.py:19-66`, `:69-105`; `KB-README.md:15`) |
| `connectors.py` | `ingest_claude`, `ingest_gmail`, OAuth helpers, Gmail error taxonomy (`connectors.py:484-635`, `:665-717`, `:1013-1145`) |
| `kb.py` | stdlib-only `init`/`stats`/`search` CLI (`kb.py:106-159`) |
| `kb_store.py` | SQLite schema, FTS5, transactional item replace, state, ranking (`kb_store.py:57-92`, `:268-286`, `:546-628`) |
| `kb_privacy.py` | secret masking, security-mail skip, private dir (`kb_privacy.py:19-29`, `:93-160`) |
| `kb_runtime.py` | singleton lock, global guidance, launchd install (`kb_runtime.py:13-16`, `:36-48`, `:95-150`) |
| `kb.sqlite` | private archive; default DB beside `kb.py` (`kb_store.py:30-31`) |
| `.kb-venv/`, `kb-requirements.txt` | venv with Google/Anthropic SDKs (`KB-README.md:67-72`; requirements pins `google-api-python-client==2.201.0`, `google-auth-oauthlib==1.5.0`) |
| `second-brain/brain.py` | separate curated-document index CLI: `index`, `query`, `remember`, `check`, `benchmark` (`brain.py:2087-2109`) |

Exact commands (from `KB-README.md:25-29`, `:46-51`, `:110-115`, and code):

```sh
cd "/Volumes/SANDISK USB/work/Cloudtransition"
# ingest (Gmail needs .kb-venv for the lazy Google imports)
.kb-venv/bin/python3 ingest_all.py                      # both sources
.kb-venv/bin/python3 ingest_all.py --source gmail
.kb-venv/bin/python3 ingest_all.py --source claude
.kb-venv/bin/python3 ingest_all.py --gmail-login        # interactive, human only
.kb-venv/bin/python3 connectors.py gmail-login          # equivalent entry point

# read/search (standard library only; system python3 is fine)
python3 kb.py stats
python3 kb.py search "application received" --source gmail --after 2026-11-17 --limit 20 --json

# scheduling is launchd today, not cron
python3 kb_runtime.py schedule
```

`ingest_all.py` flags are only `--db`, `--source {all,claude,gmail}`, `--claude-root`,
`--runtime`, `--gmail-login` (`ingest_all.py:70-76`). There is no date-window flag.
`kb.py search --after YYYY-MM-DD` is a *search* filter, not an ingest filter
(`kb.py:116`, `kb_store.py:501-509`).

## 2. Incremental behavior today — and the smallest date-window change

### What already exists

Gmail ingest is already incremental with a *lower-bound* watermark and overlap:

- State key `gmail`/`watermark` and per-run checkpoint `gmail`/`pending_run` are read at
  `connectors.py:1032-1033`.
- Fresh window: `window_start = watermark - GMAIL_OVERLAP_DAYS` (3 days), or
  `months_ago(started, GMAIL_FIRST_RUN_MONTHS)` (12 months) on the first run
  (`connectors.py:54-55`, `:1038-1046`).
- Discovery query is `after:{int(window_start.timestamp())}` — no `before:` upper bound
  (`connectors.py:1053`; asserted in `kb_tests/test_connectors.py:462`, `:487`).
- Every page and completed thread position is checkpointed; a resumed run keeps its
  original window and start watermark (`connectors.py:1069-1071`, `:1093-1115`,
  `:1128-1132`; `KB-README.md:76-82`).
- The watermark advances to the *run start* only after the whole window finishes, giving
  catch-up for mail that arrived during a long backfill (`connectors.py:1128-1132`).
- Claude ingest is a full `rglob("*.jsonl")` walk, but skips unchanged files via sha256/size
  signatures, so steady-state cost is small (`connectors.py:514-547`).
- Steady state after the 12-month backfill is therefore roughly a 3-day Gmail window per
  run, not a full mailbox scan.

**Verdict:** a 24-hour *incremental* daily step is already feasible today with zero code
change — call `.kb-venv/bin/python3 ingest_all.py --source gmail` from the wrapper. What
does not exist is an explicit *single-day / calendar-day window* (a `--after`/`--before`
or `--days` ingest option). Shrinking `GMAIL_OVERLAP_DAYS` from 3 to 1 would make it a
literal 24h overlap, but that removes the safety margin for late-arriving or
label-changed mail and clock skew; treat that as a deliberate risk choice, not a free win.

### Smallest change that adds an explicit one-day window

1. Add optional flags to `ingest_all.py:70-76`, e.g. `--gmail-days N` and/or
   `--after YYYY-MM-DD --before YYYY-MM-DD` (reuse `kb_store.parse_day`, `kb_store.py:163-171`).
2. Extend `ingest_gmail`'s signature (`connectors.py:1013-1019`) with `window_start` /
   `window_end` (or `days`) and use them when building the checkpoint at
   `connectors.py:1038-1046`; add `before:{int(window_end.timestamp())}` to the query at
   `connectors.py:1053`. Gmail search accepts epoch seconds, as the existing `after:`
   already proves.
3. Leave checkpoint/resume and the watermark advance at `connectors.py:1128-1132`
   unchanged. Critical invariant: never reset or rewind `watermark` per day — doing so
   would make future runs skip older mail permanently.

Default behavior must remain today's (12 months first run, 3-day overlap) when no flag is
passed, so `kb_runtime.py schedule` and existing tests (`kb_tests/test_connectors.py:458-501`,
`kb_tests/test_gmail_resume.py:17-28`) keep passing.

### Cron feasibility (ticket 08)

Yes, with constraints: today's scheduler is launchd (`StartInterval=21600`, six hours,
`kb_runtime.py:133-149`; `KB-README.md:108-117`), not cron. A cron wrapper must (a) run
from the workspace root with the USB volume mounted, (b) use `.kb-venv/bin/python3` for
Gmail, (c) expect the singleton `flock` at `kb_runtime.py:36-48`, and (d) treat a nonzero
exit from `ingest_all.py` as failure — it returns 1 if any source failed
(`ingest_all.py:99`). Logs go to the wrapper's own location; the existing KB log is
`~/.local-routines/personal-kb/ingest.log`. Scheduled ingestion must never call
`--gmail-login` (`connectors.py:59`, `:665-669`).

## 3. Application-confirmation email → structured applied-company records

### What exists

- Every non-security Gmail thread is stored as item `(source='gmail', source_id=thread_id)`
  with sanitized raw/short rows and rich metadata: `url`/`pointer` (thread URL),
  `thread_id`, `subject`, `message_count`, `first_message_date`, `last_message_date`,
  `messages[]`, `window_start`, `context_note` (`connectors.py:952-1010`, `:1104-1108`;
  `kb_store.py:57-92`).
- Password-reset/2FA mail is dropped before storage (`connectors.py:967-969`,
  `kb_privacy.py:141-160`), which keeps confirmation detection cleaner.
- `kb.py search ... --source gmail --json` returns that metadata per result
  (`kb.py:148-149`, `kb_store.py:611-626`), so confirmation threads are already findable
  and machine-readable by keyword. Forge did exactly this manually on 2026-11-16 and
  derived the applied list (Stripe, BlackRock Associate TPM, BETSOL, NYC DSS 789790,
  Eon, Stability AI, Nightingale, InfoTrack) — `workspace/agents/forge/memory/log.jsonl:9`.
- `interviews/job-applications.yml:7-29` is the human-readable tracker with
  `company`, `role`, `status`, and `timeline` entries with `stage: applied`;
  `interviews/CLAUDE.md` requires a row there before prep work.
- Scout scans carry the dedup result only as prose notes plus per-job `company`/`job_id`
  fields (`workspace/agents/scout/outputs/scan-2026-11-16.json`: `notes`, `jobs[].company`),
  with prior `job_id`s and manually supplied applied roles excluded.
- Ticket 07 proposes the target machine state: Scout-owned
  `workspace/agents/scout/memory/dedup-state.json` holding seen listing ids plus
  applied-company keys (`.scratch/job-hunting-pipeline/issues/07-dedup-floor.md:9`).

### What is missing

- No classifier for application-confirmation mail. `build_thread_item` treats all
  non-security threads uniformly; there is no `application` label, no company/role/date
  extraction, and no sender-domain allowlist (`connectors.py:952-1010`). Grep across the
  code found no applied-company extraction anywhere in the KB.
- No structured applied record, canonical company key, or writer from KB to
  `dedup-state.json`. No `dedup-state.json` or `applied-companies.md` file exists yet
  (only ticket 07 mentions them).
- No verification gate. `map.md:26` lists auto-marking listings applied from Gmail
  confirmations as explicitly *not yet specified*. A false positive (newsletter,
  rejection, "application" in another sense) would corrupt the dedup floor.

### Smallest coherent change

1. Add a pure, offline `classify_application_email(subject, from_header, body)` next to
   `is_security_email` in `kb_privacy.py` or `connectors.py`, using conservative subject
   patterns ("application received", "we received your application", "thank you for
   applying", "your application for") plus ATS sender domains (Greenhouse/Ashby/Lever,
   Workday, iCIMS). Return `{company, role, applied_date, confidence}` or `None`.
2. Call it in `build_thread_item` (`connectors.py:960-981`) and attach
   `metadata["application"]` to the stored item. Note this changes the content hash
   (`connectors.py:155-162`, `:236-239`), so affected threads are rewritten once.
3. Consumer side: a small wrapper reads `kb.py search ... --json` (no new KB command
   needed) and emits proposed applied keys — normalized company name (lowercase,
   punctuation/legal-suffix stripped) to match `jobs[].company` in Scout scans. A Forge
   step writes/ merges into Scout-owned `dedup-state.json` to respect workspace isolation
   (`map.md:14`).
4. Keep the merge HITL until calibrated: stage proposals to a review file, require
   Roosevelt or Forge confirmation, then promote to the dedup floor. Never auto-apply —
   submission stays manual (`map.md:12`).

## 4. Exact interactive auth repair checklist (ticket 03)

Failure signature on 2026-11-16: `ingest_all.py --source gmail` failed with `GmailError`
in 0.006 s and 0 pages, while Claude still succeeded
(`workspace/agents/forge/memory/log.jsonl:9`). Zero pages means the failure happened in
`build_gmail_service()` before the list loop (`connectors.py:1035-1037`), i.e. token
missing/unreadable/wrong-scope/revoked — an `auth`-category condition.

**Important current-state observation:** at investigation time `python3 kb.py stats`
reported `gmail` status `fresh`, last success `2026-11-18T18:35:32Z`, coverage
2025-11-06..2026-11-18 (41,802 items). The 2026-11-16 outage therefore appears already
repaired. Still run the verification step below; the checklist remains the precise
re-authorization procedure if it recurs.

Prerequisites:

1. USB volume mounted at the repo root (`ROOT.is_dir()` guard, `ingest_all.py:77-78`).
2. Google Cloud project with Gmail API enabled; OAuth consent screen configured (add the
   account as a test user if required); a **Desktop app** OAuth client
   (`KB-README.md:61-62`).
3. Client JSON saved as `~/.local-routines/personal-kb/gmail-credentials.json`
   (`connectors.py:648-650`, `kb_privacy.py:24-29`; overrides `$KB_GMAIL_CREDENTIALS`).
   Never paste it into chat (`KB-README.md:63`).
4. Google SDKs installed in `.kb-venv` (`kb-requirements.txt`; `KB-README.md:67-72`).
5. A human at the Mac with a browser. Cron/launchd never opens a browser
   (`connectors.py:59`, `:665-669`).

Repair steps:

```sh
cd "/Volumes/SANDISK USB/work/Cloudtransition"
.kb-venv/bin/python3 ingest_all.py --gmail-login
# alternative: .kb-venv/bin/python3 connectors.py gmail-login
```

Expected flow (from `ingest_all.py:84-91` and `connectors.py:701-717`):

1. `--gmail-login` short-circuits before any DB connect or ingest and calls
   `authorize_gmail_interactive()`.
2. The function verifies the credentials file exists; then builds
   `InstalledAppFlow.from_client_secrets_file(credentials, ['https://www.googleapis.com/auth/gmail.readonly'])`.
3. `flow.run_local_server(port=0)` starts a temporary localhost server on an ephemeral
   port, prints a Google consent URL, and opens the default browser.
4. The human signs in, confirms the request is **readonly only**, and grants consent.
5. The token is written owner-only (dir 0700, file 0600) to
   `~/.local-routines/personal-kb/gmail-token.json` (override `$KB_GMAIL_TOKEN`;
   `connectors.py:653-662`, `:643-646`).
6. Success prints `Gmail read-only token saved to <path> (owner-only). Scope: https://www.googleapis.com/auth/gmail.readonly`
   and exits 0 (`ingest_all.py:87`, `connectors.py:1161`).

Self-diagnosis strings (all from `connectors.py:665-717`):

- `OAuth client file not found at ...` → Desktop OAuth client JSON missing; do step 3.
- `google-auth-oauthlib is not installed in the ingest virtualenv.` → install requirements in `.kb-venv`.
- `Google client libraries are not installed in the ingest virtualenv` → install `google-api-python-client`.
- `Gmail token scope is not exactly gmail.readonly.` → token has extra scopes; re-run login with a correct Desktop client.
- `Gmail authorization expired.` / `was revoked or expired.` → refresh token invalid; re-run login.

Verify after repair:

```sh
.kb-venv/bin/python3 ingest_all.py --source gmail
python3 kb.py stats          # expect gmail status fresh, last_success updated, no last_error
python3 kb_runtime.py schedule  # only if the launcher must pick up a newly created .kb-venv
```

Never commit, share, or index `gmail-token.json`, `gmail-credentials.json`, `kb.sqlite`,
or `.env` (`KB-README.md:125-129`).

## Answer

Today's ingest is two root-level Python tools: `ingest_all.py` (per-source lock, error
isolation, safe logs) driving `connectors.py`, plus `kb.py`/`kb_store.py` for search and
`kb_runtime.py` for a six-hour launchd job. Gmail is already incremental: each run lists
`after:{watermark - 3 days}` (12 months on first run), checkpoints every page/thread, and
advances the watermark only after the whole window completes; unchanged Claude JSONL files
are skipped by hash. So a daily cron can run `.kb-venv/bin/python3 ingest_all.py --source
gmail` now and stay small — an explicit one-day window does not exist, but the smallest
addition is an optional `--gmail-days`/`--after`/`--before` flag threaded into
`ingest_gmail` to set the checkpoint window and add a `before:` bound, leaving
watermark/checkpoint logic untouched. Confirmation emails are already stored as searchable
Gmail threads with subject/URL/date metadata and were mined manually for the applied list,
but there is no confirmation classifier, no structured applied record, and no bridge to
Scout's proposed `dedup-state.json`; add a conservative offline classifier, stage proposed
company keys for human confirmation, then merge by normalized company name. Auth repair is
human-only: save the Desktop OAuth client JSON to `~/.local-routines/personal-kb/gmail-credentials.json`
and run `.kb-venv/bin/python3 ingest_all.py --gmail-login`, approve readonly scope in the
browser, then verify with a Gmail ingest and `kb.py stats`. Note that as of this research
Gmail already reports fresh (last success 2026-11-18T18:35:32Z), so the 2026-11-16 outage
appears fixed; verify rather than assume.
