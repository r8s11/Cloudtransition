# KB local acceptance re-verification — 2026-11-10

## U9 — schedule

Fresh scheduled-run observations are in U9-schedule.md: six-hour interval 21600, loaded LaunchAgent, private internal logs, real Claude/Gmail connector counts, last exit 0, raw-only (no recurring paid approval).

## U10 — actual Claude connector

Ran the real `python3 ingest_all.py --source claude` twice from /tmp. Both exit 0:
- files 44, parsed 0, unchanged_files 44, new 0, updated 0, excluded 0, malformed_records 0, errors 0.
- durations 0.062 s and 0.070 s.
- SHA256 of all 44 original JSONL files before/after: identical. No original session edited.

Actual post-run stats: 107,546 docs rows / 40,805 source items. Claude: 41 retained items, 532 rows (520 raw, 12 short), 29 pending summaries, coverage 2026-08-28 to 2026-11-10. Gmail: 40,764 items, 107,014 rows, 17,505 pending summaries, 203 skipped, coverage 2025-11-06 to 2026-11-10. Pending summaries are not fabricated as completed.

## U11 — root cause and fix

Before the fix, three real end-to-end CLI searches measured 1.6184 s, 0.4415 s and 0.1499 s. A phase profiler reproduced 1.5578 s total: imports 0.0135 s, connect 0.0044 s, search 1.5398 s. Header `SELECT DISTINCT source FROM docs` consumed 818.6 ms and `SELECT COUNT(*) FROM docs` 636.3 ms, scanning covering indexes from the USB volume. Memory mapping did not fix this (2.4880 s).

Schema 2 maintains exact per-source row/item counts through transactional insert/delete/identity-update triggers. Header/freshness now read the tiny source_counts table, not full indexes. The existing partial-index hint for superseded items remains. Migration preserves docs/FTS and is atomic; fixture tests cover replacement, deletion, identity moves, rollback, and schema-1 data preservation.

After `python3 kb.py init`, fresh subprocesses from /tmp, including startup/header/formatting:

| Query | Seconds | Source/date | Original verification |
| --- | ---: | --- | --- |
| Orizuru | 0.1541 | Claude, 2026-11-05 | Original JSONL exists and contains Orizuru |
| workspace map privacy | 0.1764 | Claude, 2026-11-05 | Original exists and contains workspace/privacy terms |
| playbook-exclusions | 0.0687 | Claude, 2026-10-30 | Original exists and contains the exact term |

Each query used `--after 2026-10-01 --source claude --limit 1 --json`; all exit 0. Originals were opened locally for the literal-topic check; no private session bodies are copied here. These measurements supersede earlier failing timing evidence, which remains preserved in U11-searches.md.

## U13 — global guidance

Inspected actual ~/.claude/CLAUDE.md: exactly one `## Knowledge base (search it first)` heading; literal quoted absolute kb.py search command; distinctive-word retry, open-original and 12-hour refresh rules all present. Executed the documented absolute-path command from /tmp above. Existing KB README and CODE router remain in place. No retention settings changed. README now documents exact-count migration and rollback.

U12 is separate: Gmail readonly authorization and actual ingest exist. User authorized a one-time Claude-only Haiku backfill with a $6.11 cap, but no Anthropic API key is configured. They additionally requested and approved the design/evals for an explicit separately approved Codex Luna fallback; this file does not claim that fallback or any Haiku invocation has run.
