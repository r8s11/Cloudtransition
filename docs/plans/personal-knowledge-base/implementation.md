# Personal Knowledge Base Implementation Plan

> **For agentic workers:** Use executing-plans to implement this plan task-by-task. Read the approved RD and eval before editing.

**Goal:** Private, incremental Gmail/Claude retrieval with local SQLite FTS5, optional separately approved Haiku summaries, and six-hour ingestion.

**Architecture:** Standard-library storage/search core, sanitized connector inputs, separately gated remote summaries. Each source item is replaced transactionally; source watermarks advance only after successful processing. Root CLI paths are independent of working directory.

**Tech Stack:** Python 3, SQLite FTS5, official Google Gmail API client and Anthropic Python client for optional ingest paths, launchd.

**Spec:** rd.md and eval.md in this directory.

## Global constraints

- No login or paid request without separate approval. Approval of this plan is not a recurring API budget.
- DB/runtime files are private and gitignored before real ingestion; no private data in shared indexes or HTTP routes.
- Keep existing second-brain behavior unchanged.
- RRF k=60, summary weight 1, raw weight 0.5; recency multiplier 1+0.1*exp(-age_days/180), superseded half-score.
- Raw chunks contain at most 4,000 sanitized characters. Exact source evidence must survive except secret redactions.
- No commits, dependency changes outside private ingest environment, credential printing or source-file edits.

## Task 1: Storage and search

Files: kb_store.py, kb.py, kb_tests/test_store.py. Owner: storage slice.

Interfaces: `kb_store.connect(path=None)` returns sqlite3.Connection with Row factory and schema initialized; default path is workspace-root kb.sqlite. `replace_rows(conn, source, source_id, rows)` atomically replaces one item, each row having kind/ts/title/content/metadata, with metadata a dict. `get_state(conn, source, key, default=None)` and `set_state(conn, source, key, value)` JSON encode watermarks. `stats(conn)` and `search(conn, query, after=None, source=None, limit=10)` return JSON-compatible results. `kb.py init|stats|search` exposes the requested flags and human-readable search results.

- [ ] Create isolated tests for schema triggers, replacement rollback, FTS escaping, dual ranking, source/date filters, short/empty results and CLI outside cwd, matching U1/U5/U6/U7/F7/F10.
- [ ] Implement SQLite schema/triggers, item identity grouping, transactional replace, independent bm25 passes, weighted RRF and exact source pointers.
- [ ] Smoke actual CLI on an isolated database, observe formatted evidence and timing. No live personal content in test output.

## Task 2: Privacy, connectors and summarization

Files: kb_privacy.py, connectors.py, kb_summaries.py, kb_tests/test_connectors.py. Owner: connector slice.

Consumers use Task 1 signatures exactly. Connector functions `ingest_claude(conn, root=None)` and `ingest_gmail(conn, service=None)` return count dictionaries and update own state. Never import Google/Anthropic on the search path. Core reusable helper `store_item(conn, source, source_id, ts, title, content, metadata)` sanitizes, hashes, chunks raw and writes short rows for <=4000 characters. Long items record pending summary work without paid calls.

- [ ] Create deterministic isolated fixtures for timestamps, growing session tails, Gmail pagination/MIME, token canaries and redaction, never real API tests.
- [ ] Implement secret masking, security-mail skips, private/academic source exclusions, JSONL parsing preserving useful message/tool text, signature-based incremental ingest and read-only original pointers.
- [ ] Implement official Gmail API reads with readonly scope, thread discovery, first-year and overlapping watermark discovery, full pagination and failure-safe state.
- [ ] Implement Haiku structured summaries with exact evidence validation, content-hash cache, pending-work retry, explicit approved budget/payload gates, estimate before spend, complete raw retention and no silent context truncation.
- [ ] Smoke fixture ingestion twice and compare item counts, raw reconstruction and no duplicate summaries.

## Task 3: Integration, runtime privacy and operations

Files: ingest_all.py, kb_runtime.py as needed, kb_tests/fixtures.py and remaining eval tests, .gitignore, CODE.md, KB-README.md, existing privacy filters only where necessary. Owner: integration.

- [ ] Integrate independent slices after inspecting their exported interfaces. Add per-source error isolation, safe logging, process locking, secret environment loading without output and last-success freshness.
- [ ] Extend runtime exclusions so DB/journals, tokens, private logs, approvals and summaries never enter shared index or HTTP file routes. Check source/private eligibility before real ingestion.
- [ ] Run real Claude ingest locally, repeat unchanged, report actual stats. Do not send source content remotely.
- [ ] Create internal-disk launcher/log paths and six-hour launchd job using StartInterval 21600, explicit interpreter paths and failure on missing USB. Preserve existing jobs.
- [ ] Add requested global CLAUDE.md section idempotently with quoted full path; explain cleanupPeriodDays without changing it.
- [ ] Run the approved eval tests and real CLI smoke searches. Record observations without sensitive evidence. Live Gmail and Haiku cases remain blocked until user grants login/payload/budget.
- [ ] Guide OAuth one step at a time after asking login permission. Only after source inventory, present item count and conservative named-model cost estimate for separate paid approval.
- [ ] Refresh workspace documentation index, update router and report files, real stats, timings, log checks and exact remaining prerequisites.

## Self-review

All approved cases map to the tasks above. No UI build applies. Billing and login gates remain explicit, not substituted by fixture passes. The named tests required by eval.md are the acceptance interface, not permission to change its requirements.
