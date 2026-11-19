---
feature: Explicit Codex Luna summary fallback
status: passed
approved: 2026-11-16
rd: codex-fallback.md
---

# Evals: Explicit Codex Luna summary fallback

## Build contract

Build only after user approval. No live source-content transmission without a separate exact-preview approval. CLI-only; no mockup. `python3 -m unittest discover -s kb_tests -p test_codex_fallback.py` exercises local fixtures, not real model access. Save manual evidence under eval-evidence/.

## Traceability

| Requirement | Cases |
| --- | --- |
| Explicit selected Claude-only preview, current model and sizes | U1, F1 |
| Separate OpenAI transfer/subscription consent | F2 |
| One invocation, existing validation, raw preservation | U2, F3 |
| Existing Haiku/ingest/search preserved | R1, R2 |

## Usage

### U1 — Preview exact pending Claude items without calls
- **Setup:** Isolated KB with pending Claude/Gmail items, completed Claude item and visible Codex catalogue fixture including gpt-6-luna.
- **Steps:** Preview selected Claude identities and inspect owner-only manifest.
- **Expected:** Only selected pending Claude versions appear; manifest includes model, content hashes, sizes, bounded call count and fingerprint. Missing/hidden model, Gmail or completed items are refused. No provider process starts.
- **Verify:** `python3 -m unittest discover -s kb_tests -p test_codex_fallback.py -k preview_scope`

### U2 — Run approved batch and preserve raw
- **Setup:** Isolated KB and local executable returning valid summary JSON and token usage.
- **Steps:** Approve manifest, run once, inspect KB; run the same approved batch again.
- **Expected:** One invocation per pending item. Validated segment/atom rows appear with provider/model/usage metadata; raw text is unchanged. A successful unchanged item is not sent twice. No Haiku request, automatic retry or provider switch occurs. Dollar cost is unknown, not zero.
- **Verify:** `python3 -m unittest discover -s kb_tests -p test_codex_fallback.py -k approved_run`

## Failure

### F1 — Source/model/manifest drift invalidates approval
- **Setup:** Approved fixture preview, then change raw content, selected identities, model, or manifest bounds.
- **Steps:** Run each stale/altered manifest.
- **Expected:** Reject before process launch and require a fresh reviewed preview. No rows changed.
- **Verify:** `python3 -m unittest discover -s kb_tests -p test_codex_fallback.py -k stale_preview`

### F2 — No separate consent means no egress
- **Setup:** Missing/wrong fingerprint, no OpenAI transfer acknowledgment, no subscription-usage acknowledgment, or unattended/scheduled invocation.
- **Steps:** Attempt run with each condition.
- **Expected:** Zero provider processes; concise refusal. Existing Haiku consent is not reused as OpenAI consent.
- **Verify:** `python3 -m unittest discover -s kb_tests -p test_codex_fallback.py -k consent_gate`

### F3 — Provider/output/timeout failure preserves pending data
- **Setup:** Local fixtures for nonzero exit, timeout, malformed JSON, invented atom, source drift during execution and a secret-like output canary.
- **Steps:** Attempt one approved item per failure.
- **Expected:** Raw data preserved; no invalid summary committed, no canary persisted/logged, no retry or provider fallback. Item remains pending and failure is sanitized.
- **Verify:** `python3 -m unittest discover -s kb_tests -p test_codex_fallback.py -k failure_preserves_raw`

## Regression

### R1 — KB behavior suite
- **Expected:** Existing deterministic store, connector, privacy, budgeting and summary behavior remains passing.
- **Verify:** `python3 -m unittest discover -s kb_tests -p 'test_*.py'`

### R2 — Syntax and entry points
- **Expected:** Existing kb.py and kb_summaries.py CLI entry points still parse; fallback module compiles. No scheduled Codex work added.
- **Verify:** `python3 -m py_compile kb_codex.py kb_summaries.py kb_store.py && python3 kb.py --help && python3 kb_summaries.py --help && python3 kb_codex.py --help`
