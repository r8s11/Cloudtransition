# Explicit Codex Luna Summary Fallback Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline. Roosevelt prohibits subagents; implement and review this plan without delegation.

**Goal:** Add an explicit, separately approved Codex Luna retry path for selected pending Claude summaries.

**Architecture:** One standard-library CLI module owns preview validation and isolated Codex transport. Reuse `kb_summaries` payload construction, output validation and atomic item replacement; keep its Haiku ledger separate. No automatic fallback or scheduled execution.

**Tech Stack:** Python stdlib, SQLite, installed Codex CLI `gpt-6-luna`.

**Spec:** `docs/plans/personal-knowledge-base/codex-fallback.md`; approved acceptance: `codex-fallback.eval.md`.

## Global Constraints

- Claude-only, exact item/content hashes, one approved manifest and one invocation per item; no implicit provider switch/retry.
- Explicit OpenAI transfer and unmetered subscription acknowledgment. Haiku cap $6.11 is not a Codex cost guarantee.
- Raw rows never lost; all summaries/atoms validated and redacted. No user config/trust changes, tool execution or credential copying.
- No live source-content test before approval of its exact preview.

## Review Focus

- Source changes after preview or during a provider call: reject/refuse commit rather than summarizing an unapproved version.
- Repeated approved batch: do not re-send successfully summarized unchanged items.
- An installed CLI may expose built-in tools even with a read-only sandbox: inspect actual local-provider requests, not argv alone.
- Malformed output/timeout: preserve pending raw and avoid secrets in diagnostics.
- Dollar cost unavailable: report null/unknown, never zero or charge to the Haiku ledger.

## Task 1 — Exact preview and consent boundary

Files: create `kb_codex.py`, `kb_tests/test_codex_fallback.py`.

Interfaces: `preview(conn, identities, model='gpt-6-luna') -> dict`; `run(conn, manifest, fingerprint, *, transfer_ack=False, usage_ack=False) -> dict`.

- [ ] Add failing `preview_scope`, `stale_preview` and `consent_gate` tests: reject Gmail/completed items, hidden/missing models, altered item hashes/model/bounds and missing acknowledgments before any process.
- [ ] Build a versioned owner-only preview manifest using existing pending-item identities and sanitized content hashes; compute its deterministic fingerprint.
- [ ] Validate model against the visible local Codex catalogue and its context bound; never truncate a source item.
- [ ] Implement CLI preview/run with selected identities, explicit manifest path and fingerprint; forbid scheduled mode.
- [ ] Run the three focused test groups and observe pass.

## Task 2 — Isolated Codex transport and validated persistence

Files: `kb_codex.py`, tests above; reuse `kb_summaries.py` APIs without adding automatic provider switching.

- [ ] Add failing `approved_run` and `failure_preserves_raw` behavior tests with executable fixtures: successful validated segments/atoms and unchanged raw; nonzero/timeout/malformed/invented atoms/secret outputs/source drift leave pending data.
- [ ] Use stdin, private temporary directory, ephemeral CLI, ignored user config/rules, project-doc bytes zero, disabled shell/delegation/web/MCP/plugins, read-only sandbox and no bypass flags. Capture JSON event usage and last response; do not log source text.
- [ ] Validate response using `kb_summaries.validate_summary`, re-redact, recheck source hash, atomically preserve raw/add summary rows and record provider/model/usage with unknown dollar cost.
- [ ] Reuse the KB ingestion lock; do not resend successful unchanged items or retry failures automatically.
- [ ] Run focused tests.

## Task 3 — Installed CLI isolation proof

- [ ] Use a loopback mock Responses endpoint and synthetic hostile source. Inspect the actual tools advertised by the installed CLI and reject unexpected tool execution.
- [ ] Confirm private canary files unchanged/unread and no arbitrary command/network/MCP request; save sanitized evidence. Fix configuration only using installed help/current official documentation.
- [ ] Do not treat executable fixtures as proof of installed CLI isolation.

## Task 4 — Integration, docs and exact live approval

Files: `KB-README.md`, `CODE.md`, original PKB RD/eval, fallback evidence.

- [ ] Document explicit preview/run, data recipient, unknown subscription cost and failure behavior; route new module/spec/plan from existing code index.
- [ ] Apply the user-approved U12 alternative: accept separately approved Codex fallback when Haiku is unavailable, never call it a Haiku invocation.
- [ ] Run `python3 -m unittest discover -s kb_tests -p 'test_*.py'` and syntax/help checks; run fallback eval automation.
- [ ] Prepare one exact nonsensitive Claude-item preview and ask approval at the transmission point before any live Codex invocation. Record actual tokens or a precise approval prerequisite.
- [ ] Complete all other repair evidence, then run/record all evals on the final stable workspace. Do not commit unrelated user work.
