# Explicit Codex Luna summary fallback

## Request

Roosevelt: “1 and can you add a codex luna as fallback?” Selected approach: **explicit** retry command, with an exact batch preview and separate approval, not automatic provider switching.

The preceding “1” authorizes a one-time pending-Claude-only Haiku backfill, no Gmail, maximum $6.11. That is not authorization to send a Codex batch; its preview must be approved separately. No Anthropic API key is currently configured.

## Approaches

- **Chosen:** explicit Codex preview/run for pending Claude items when Haiku is unavailable or failed. Preserves the user's control over each provider/data transfer.
- Automatic fallback was offered and declined: it would silently change recipient and use Codex subscription usage outside the Haiku dollar ledger.
- Keep Haiku only: preserves existing implementation but cannot run without an API key.

## Design

- Add `kb_codex.py` with `preview` and `run` CLI operations. Keep Haiku and six-hour raw ingestion unchanged. No background Codex calls.
- Default model `gpt-6-luna`, validated against visible entries in the installed Codex catalogue. Do not infer account entitlement from the catalogue.
- Preview a selected, bounded set of pending Claude items only. The owner-only manifest records model, source/item identity, sanitized-content hash, character/input-size bound, expected calls and a fingerprint. No Gmail data. Private titles/full payload may be reviewed locally, not copied into shared evidence.
- Run requires the exact preview fingerprint and explicit acceptance of Codex/OpenAI transfer and subscription usage. Reject stale/changed items, changed model, altered manifests, completed items and missing consent before launch. Serialize with the existing KB ingestion lock.
- One Codex invocation per approved item, no automatic retries or provider fallback. Existing signed-in Codex authentication is reused without copying credentials or changing trust/security settings. No API key is required for the Codex path.
- Send only `SYSTEM_PROMPT` plus `build_payload()` of that item's masked title/raw chunks, via stdin, not argv. Run from an empty private temporary directory with user/project config and rules ignored, ephemeral sessions, read-only sandbox, shell/delegation/search/MCP/plugins disabled. No bypass flags. A local mock-provider experiment must prove untrusted content cannot run a tool or reach canary files.
- Apply the existing `validate_summary()`/redaction/atomic item rewrite and source-hash cache conventions. Never replace or lose raw rows. Invalid JSON, unsupported tools, timeout, provider error or source drift leaves that item pending and reports a sanitized error.
- Record actual provider/model, input/output tokens and outcome. Codex dollar cost is **unknown**, not zero; the Haiku $6.11 ledger does not cover it. The manifest bounds item/call count but is not a hard dollar or output-token cap.
- Extend KB U12 to accept the explicitly approved Codex fallback when Haiku is unavailable, while preserving readonly Gmail evidence and Haiku estimate/consent gates. Never claim Codex proves a Haiku invocation.

## Non-goals

Automatic switching/retries, Gmail fallback, recurring paid scheduling, other providers/models, new login, security bypasses, embedding/vector search or changing ingestion/source retention.

## Verification

See `codex-fallback.eval.md`. CLI-only; no web UI/mockup. Use local executable/API fixtures without paid calls. Any live private-source invocation requires separate exact-manifest approval.
