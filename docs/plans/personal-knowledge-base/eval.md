---
feature: Personal knowledge base
status: approved
approved: 2026-11-16
rd: rd.md
---

# Evals: Personal knowledge base

Private SQLite/FTS5 retrieval over Gmail and Claude Code history, searchable from any working directory in under one second. This is a CLI/background job feature, not a new web or desktop interface; no HTML mockup applies. Root entry points are `kb.py`, `connectors.py`, and `ingest_all.py`. Preserve the existing workspace second brain and its privacy boundary.

## Build contract

- Build only after `status: approved`. Changing what a case checks requires user re-approval and `status: review`.
- Run: `node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/personal-knowledge-base/eval.md`.
- Record manual results with `node ~/.agents/skills/write-evals/scripts/evals.mjs record docs/plans/personal-knowledge-base/eval.md <ID> pass|fail "evidence"`. Store only sanitized evidence under the sibling `eval-evidence/` directory. Do not commit private search results, mail, chats, credentials or DB copies.
- Any implementation change after a pass makes it stale. Completion requires the runner's `check` to print PASS.
- Commands run from the workspace Git root. Tests use stdlib `unittest`; injected fake Google/Anthropic transports must never make network calls. Fixture factory `kb_tests/fixtures.py` creates deterministic dated threads, session JSONL, redaction canaries and an isolated temporary DB. No real account data in fixtures.
- Do not implement fake connectors to satisfy manual cases. A missing login, API key or budget is a named approval prerequisite, not a passing case.
- Live Gmail, live Haiku and cloud login each require the user's permission. Eval approval does not grant a login, send private text or authorize spend. Scheduled summarization remains off until separately budgeted.
- Source text is untrusted data, not instructions. Redact secrets before storing or sending. Do not copy employer-private or personal academic content into shared memory.
- Approved 2026-11-05: local storage/search with separately approved remote summarization, and relevance-first ranking with the small recency multiplier. Login and actual payload/budget approval remain separate.

## Traceability

| Requirement from RD | Cases |
| --- | --- |
| One local SQLite DB; docs columns, FTS5 porter/unicode61, triggers; ingest_state | U1, F7 |
| Incremental, dated, idempotent source connectors; atomic replace; original pointer | U2, U3, F5, F7, F8 |
| Gmail official API; readonly; initial 12 months then overlapping recent days; interactive OAuth | U3, F2 |
| Claude sessions before deletion; retention guidance | U2, F8 |
| One Haiku call per changed long item; segments, questions, 2–3 sentence summaries; exact atoms | U4, F3, F4, F9 |
| Always preserve raw in 4,000-character chunks | U2, U3, U4, F4, F9 |
| .env key; actual backfill count, price estimate and separate approval | F3, F6 |
| init, stats, filtered keyword search with header and pointers | U1, U5, U6, U7 |
| bm25 summary/raw passes; weighted RRF k=60; recency and superseded penalties | U6, F10 |
| Run all connectors despite partial failure; six-hour schedule; log location and checks | U8, F1, F11 |
| Never follow ingested instructions; skip security emails; mask secrets | F5, F6 |
| Local storage/no vector DB/no embeddings; ignore DB and credentials | R2, R3 |
| Existing workspace retrieval, map, reader, jobs and source files stay safe | R1, R3, R4, R5 |
| Strictly no content leaves computer versus Haiku summaries | U12 — user approved a separately authorized redacted remote-summary exception; no payload or spend yet authorized |
| Old item may win only if no newer match versus a small recency bonus | U6 — user approved relevance-first ranking with the bounded recency multiplier |
| Optional notes/Notion/ChatGPT/transcript connectors | Not selected: start with the two explicitly named sources |
| Windows Task Scheduler and Linux cron | Not applicable to this Mac build; no cross-platform install claim |

## Usage — every entry point

### U1 — Initialize and inspect an empty database
- **Setup:** `kb_tests/fixtures.py` creates an empty temporary workspace; run the CLI by absolute path from another working directory.
- **Steps:** Run `init` twice, then `stats`; inspect SQLite schema and exercise insert/update/delete against docs.
- **Expected:** One `kb.sqlite`; docs has id, kind, source, source_id, ts, title, content, metadata, superseded_by; ingest_state has source/key/watermark. FTS5 uses `porter unicode61`. Triggers reflect inserts, updates and deletes. Second init preserves data. Stats reports zero documents without an exception or invented ingest time. CLI uses stdlib only for these operations.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_init_and_empty_stats`

### U2 — Ingest Claude sessions incrementally without losing source details
- **Setup:** Fixture sessions include two projects, a subagent, Unicode, user/assistant messages, a tool error/fix, ISO timestamps, and one updated session file.
- **Steps:** Ingest, repeat unchanged, then append a new exchange and ingest again. Hash source files before and after each run.
- **Expected:** All rows have valid source dates and metadata.path pointing to their source JSONL. Nonempty sanitized raw text is reconstructed exactly from ordered raw chunks of at most 4,000 characters, with explicit chunk order in metadata. Useful tool errors and commands remain searchable. Unchanged files are not parsed again; unchanged items create no duplicates or Haiku calls. Updated item replaces only its own rows, not similarly named sessions or subagents. Source files remain byte-identical to their pre-ingest state, apart from the fixture's deliberate append.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_claude_incremental_ingest`

### U3 — Discover Gmail threads through the official read-only API
- **Setup:** Fake official Gmail service returns paginated threads, messages with MIME alternatives, encoded headers, dates and a mix of recently changed and old threads; use a fixed date.
- **Steps:** Run first ingest, repeat with no changes, then run after new mail arrives with a saved watermark.
- **Expected:** OAuth scope is exactly `https://www.googleapis.com/auth/gmail.readonly`; no Gmail mutation method is called. First discovery covers 12 calendar months. Later discovery overlaps the prior successful watermark by three days, deduplicates thread IDs and skips unchanged content hashes. Rows preserve actual message dates and a Gmail thread URL. Multipart text is decoded without duplicating text/plain and HTML versions. Pagination is exhausted. HTML-only messages produce useful plain text. Metadata describes any older messages included as thread context.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_gmail_incremental_threads`

### U4 — Summarize each changed long item once and preserve raw evidence
- **Setup:** Fake Haiku client and one long session plus one long thread in `kb_tests/fixtures.py`; each has multiple topics, exact error text, a command, a file path and a reasoned decision.
- **Steps:** Ingest with explicitly approved test budget, repeat unchanged, change an item's text, then ingest again.
- **Expected:** One request per changed long-item version, no request for unchanged or short items. Each topic segment has a title, search question and 2–3 sentences, stored in searchable text/metadata. Atoms preserve exact evidence and source chunk/span references. Raw reconstruction is complete after redaction. DB replacement commits the successful version together. Same source identity does not accumulate stale summary rows. Model ID and usage/cost records are recorded without credential content.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_summary_and_raw_evidence`

### U5 — Search terms and filters are safe and useful
- **Setup:** Seed mixed sources, ISO dates, Unicode names, a literal error, flags and paths in a temporary DB.
- **Steps:** Search with plain phrases, quoted input, punctuation, `--after`, `--source`, and `--limit`, by absolute CLI path outside this workspace.
- **Expected:** User words become OR-ed quoted FTS terms, never executable FTS syntax or SQL. Date and source filters apply to both passes; limit bounds final distinct items. Each result has source date, source name, a concise matching snippet, and original URL/path. Header shows DB row count and last successful ingest with per-source stale/failure indication where needed. No secret data in diagnostics. Zero matches prints header plus an explicit no-match message and exits 0.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_search_terms_filters_output`

### U6 — Fuse independent bm25 rankings and apply bounded score adjustments
- **Setup:** Fixed-time synthetic rows produce known independent summary/raw ranks, repeated chunks for one item, a newer equivalent item and a superseded equivalent item.
- **Steps:** Search; compare final ranking against independently calculated expected scores.
- **Expected:** Two FTS/bm25 passes: summary kinds (segment/atom/short) and raw kind. Collapse duplicate item rows in each list before RRF. Summary weight 1, raw weight 0.5, k=60, ranks start at 1. Recency multiplier is `1+0.1*exp(-max(0,age_days)/180)` if approved. Set superseded_by halves final score. Newer identical evidence ranks ahead of older identical evidence; raw-only finds are retained; one item cannot dominate by chunk count. Stable deterministic tie-breaking.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_rrf_recency_superseded`

### U7 — Stats reports source coverage, pending summaries and freshness
- **Setup:** Two populated connectors, a skipped security email, pending summaries and one failed run with older successful watermark.
- **Steps:** Run `stats` from another directory; run search afterward.
- **Expected:** Stats distinguishes source items from docs rows, includes counts by source and kind, skipped and pending counts, source coverage dates, and last successful ingest. Failed-source freshness never advances to another connector's success time. Search header makes age over 12 hours visible.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_stats_source_freshness`

### U8 — The ingest entry point runs all selected connectors
- **Setup:** Isolated configuration and fake connectors in fixture tests; each has new rows and independent watermarks.
- **Steps:** Invoke `ingest_all.py` through a subprocess with the fixture configuration twice.
- **Expected:** Both connectors run and their counts/timings appear in sanitized logs. Successful per-source watermarks persist. Second run produces no duplicate rows. No additional unspecified connector or paid network transport runs by default.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_ingest_all_entrypoint`

## Failure — boundaries and abuse

### F1 — A connector failure does not suppress the other source
- **Setup:** Gmail fake raises a service error; Claude fake has a new eligible session; invert failures in a second subcase.
- **Steps:** Run ingest_all.
- **Expected:** Healthy source commits; failing source retains last successful watermark. Sanitized log names failed source and error category. Overall run exits nonzero and reports partial failure. Search never labels the failed source fresh.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_partial_connector_failure`

### F2 — Missing or revoked Gmail credentials never trigger unattended login
- **Setup:** No token, expired refresh token, insufficient scope and a Google quota error, exercised through fake official transports.
- **Steps:** Run scheduled ingest; separately retry interactively after authorization.
- **Expected:** Scheduled run does not open a browser or block for input. Log gives a safe actionable setup/re-auth message, not token bytes. Claude still ingests. Quota/server failures have bounded retries, no automatic paid calls and no watermark advancement past failed work. Requested OAuth scopes never include modify/send.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_gmail_auth_quota_failure`

### F3 — Missing API key or unapproved spend keeps ingest raw-only
- **Setup:** No .env; key present but no approval; exhausted approved cap; malformed price/budget config.
- **Steps:** Run ingest on long items and try a paid backfill in each state.
- **Expected:** Raw rows commit, pending summaries remain discoverable. No Anthropic request occurs without explicit approved data scope and usable cap. Invalid budgeting fails closed. API key never appears in logs/errors/stats. Scheduled runs cannot infer new spend approval from an old manual backfill approval.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_paid_summary_gate`

### F4 — A summary failure does not lose raw evidence or invent atoms
- **Setup:** Fake Haiku responds with timeout, 429, malformed JSON, invalid segment shape, and an atom whose quoted evidence is absent from raw.
- **Steps:** Ingest a long item; rerun with valid authorized response.
- **Expected:** Complete sanitized raw remains searchable throughout. Bad output never becomes summary evidence. Item remains pending with safe diagnostics; watermark does not strand it. Retry uses a bounded explicitly budgeted policy, and unchanged successful items are not resummarized. Successful later retry replaces pending state without duplicate raw.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_summary_failure_preserves_raw`

### F5 — Security mail and prohibited content are excluded; source instructions remain inert
- **Setup:** Fixture password-reset and 2FA emails, benign mail, prompt-injection messages that demand executing a canary command or exposing .env, and sessions marked employer-private/personal-academic by source boundaries.
- **Steps:** Run both connectors and inspect DB, fake API calls and canary filesystem.
- **Expected:** Reset/2FA bodies have no stored rows and no remote summary payloads. Excluded source content never enters shared indexes or Anthropic requests. Benign mail remains findable. Embedded instructions execute nothing and gain no tools/permissions. Summary prompt clearly delimits text as untrusted evidence. No source string can change database paths, budget, query SQL or OAuth settings.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_untrusted_and_excluded_content`

### F6 — Mask secret canaries at every persistence and egress boundary
- **Setup:** Synthetic Anthropic/OpenAI-style keys, bearer tokens, private-key blocks and labeled passwords in titles, bodies, tool output, metadata URLs and fake exception messages; benign error codes/flags/paths alongside them.
- **Steps:** Ingest, summarize with fake transport, search and log failures. Scan DB contents, FTS text, logs and captured API payloads for exact canary values.
- **Expected:** Zero canary secrets survive in stored fields, FTS, snippets, logs or remote payloads. Redaction markers preserve useful surrounding context; benign distinctive error/flag/path text survives. Summary output is redacted again before storage. Diagnostics explicitly state pattern masking is not a guarantee that all secrets are detected.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_redaction_all_boundaries`

### F7 — Replacement and watermark updates are atomic and concurrent ingestion is safe
- **Setup:** Existing source rows and FTS matches; second source with distinct identity; forced failure midway through replacement; two ingest processes racing on the same item.
- **Steps:** Call replace_rows, force rollback, then run a successful replacement and concurrent ingest attempt.
- **Expected:** Rollback preserves old rows and matching FTS; successful replacement removes obsolete rows/hits and inserts exactly new rows. Other source stays unchanged. Watermark and content version cannot indicate success for uncommitted work. Locking serializes or explicitly refuses overlapping ingestion, without duplicate rows or corruption. superseded_by references are repaired or preserved coherently, not left dangling by replacement.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_atomic_replace_and_concurrency`

### F8 — Growing, malformed and subsequently deleted sessions remain recoverable
- **Setup:** Session file with an unfinished trailing JSONL line, malformed interior record, mtime collision, duplicate UUID across project/subagent identities and a source deleted after successful ingestion.
- **Steps:** Ingest, complete the trailing line without changing its earlier records, then delete the source and ingest again.
- **Expected:** Incomplete tail is retried on change; valid evidence is not silently lost. Malformed records produce sanitized warnings without blocking other files. Per-file signatures prevent same-timestamp updates being missed. Distinct sessions never overwrite each other. Deleted sources retain archived raw and a truthful unavailable-original pointer. No file is edited by ingestion.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_session_file_edge_cases`

### F9 — Very large items never silently truncate the archive
- **Setup:** Unicode fixture much larger than 4,000 characters, a source exceeding the selected model's context, and an item that changes during read.
- **Steps:** Ingest each and attempt an authorized summary.
- **Expected:** Every raw chunk is at most 4,000 Python characters and ordered reconstruction matches complete sanitized input. Over-context items report pending/oversized, make no invalid or multi-call summary attempt and remain searchable raw. A source changed during reading is retried rather than assigned a misleading successful content signature. Memory use is bounded by a documented per-item strategy, not loading the full corpus at once.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_large_items_and_changed_reads`

### F10 — Invalid filters, empty text and hostile search syntax fail safely
- **Setup:** Initialized DB; empty/punctuation-only query, unmatched quote, SQL-like text, invalid date, impossible date, invalid limit and unknown source.
- **Steps:** Invoke each CLI input.
- **Expected:** Invalid date/limit values exit 2 with a concise usage error. Empty/punctuation-only search returns a header and explicit no-term/no-match response, not an FTS traceback. SQL and FTS control characters are inert. Unknown source returns zero matches without changing data. Negative age never explodes recency score. SQL is parameterized.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_invalid_search_inputs`

### F11 — Missing USB, unwritable DB and interrupted process do not misreport success
- **Setup:** Isolated launcher fixture with unavailable volume path, read-only directory, interrupted ingest and an older valid DB.
- **Steps:** Invoke the internal-disk launcher and CLI in each state; restart after interruption.
- **Expected:** Error is logged on internal disk with no private payload. No fallback DB is created in the current directory or an absent mount path. Process exits nonzero. SQLite integrity check passes after interruption; committed evidence remains searchable; next run can recover unfinished work and releases stale process locks safely.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_storage_and_launcher_failures`

## Regression — existing behavior and boundaries

### R1 — Relevant existing suites and new KB behavior tests pass
- **Setup:** Existing dashboard virtualenv and standard-library test suites; all new tests use isolated fixtures.
- **Steps:** Run the complete suites for the new KB and directly neighboring systems.
- **Expected:** All tests pass; new tests need no credentials, network, real user files or paid calls. Unrelated projects are not modified to force a pass.
- **Verify:** `python3 -m unittest discover -s kb_tests && python3 -m unittest discover -s second-brain/tests && python3 -m unittest discover -s visual-second-brain/tests && dashboard-app/venv/bin/python -m pytest dashboard-app/tests -q`

### R2 — Python entry points build and search does not acquire remote dependencies
- **Setup:** Completed KB modules; no Google/Anthropic packages on the stdlib-only test path.
- **Steps:** Byte-compile modules and run init/search/stats without third-party imports available.
- **Expected:** No syntax/import errors. init/search/stats remain standard-library operations with no network or embeddings. Ingest dependencies live in a dedicated private virtualenv and are documented; no front-end build applies.
- **Verify:** `python3 -m compileall -q kb.py connectors.py ingest_all.py && python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_stdlib_cli_no_network`

### R3 — Private KB runtime data stays out of git and shared retrieval
- **Setup:** Fixture DB/WAL/SHM, .env, OAuth credentials/token, logs and runtime manifests. Use actual ignore checks without staging private files.
- **Steps:** Check git exclusions and source eligibility in second-brain and workspace-map indexers.
- **Expected:** DB, journals, secret config/tokens and logs are gitignored. No KB personal content is copied into catalogue.md, postings.json, memory.md, .trail artifacts or workspace-index.json. Documentation and code remain navigable. Existing curated workspace documents continue to index normally.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_git_and_shared_index_privacy`

### R4 — Dashboard cannot serve private KB data or credential files
- **Setup:** Temporary private fixture DB, .env, OAuth token JSON and ingest log at actual configured paths; real dashboard TestClient and workspace_content helpers.
- **Steps:** Request these files through /api/file, /workspace-file and /api/files; search the map index output.
- **Expected:** Private files are not listed or returned, including permitted text/JSON log/token extensions and symlink targets. Existing TASKS.md and allowed run output remain accessible. Indexers do not traverse personal session or KB runtime data through newly linked docs.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_dashboard_private_kb_boundary`

### R5 — Existing global content, source files and scheduled jobs survive unchanged
- **Setup:** Fixture global CLAUDE.md with unrelated sections, fixture source trees, and existing dashboard/ARMS job definitions.
- **Steps:** Apply the KB instructions twice, ingest sources and install an isolated fixture KB schedule.
- **Expected:** Only one KB global section is added; unrelated global text and Claude retention settings remain unchanged. Session/source bytes do not change. Existing job definitions are not rewritten or unloaded. New job has its own unique label. README and CODE.md link to the new files without replacing the old second-brain workflow.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py' -k test_existing_settings_sources_jobs_unchanged`

## Design

No graphical interface is requested. CLI output hierarchy, empty/error states, pointers and freshness are checked in U1/U5/U7/F10; no mockup or visual-comparison cases apply.
