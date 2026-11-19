# Global Second Brain Implementation Plan

> Use executing-plans inline for integration. Independent adapter and extension/runtime slices may run concurrently. No automatic commits or worktree changes.

**Goal:** One globally discovered default-profile OMP extension uses the existing Second Brain CLI as its only active memory store.
**Spec:** rd.md and approved eval.md beside this plan.
**Architecture:** An argv-only Python subprocess adapter owns bounded execution; an OMP factory registers tools and fixed guidance. A small global .ts loader loads workspace implementation gracefully. Native backend changes only after verification and supported approval.
**Tech stack:** Node/Bun ES modules, existing Python standard-library CLI, installed OMP extension/SDK APIs.

## Global constraints

No paid inference, external service, transcript auto-retention, live synthetic memory writes, alternate per-cwd stores, or deletion of old native memories. Keep normal HOME; use external TMPDIR. Preserve all CLI statuses, cancellation and safe failure; retrieve data as untrusted evidence. Named profiles/disabled discovery/restricted tool lists retain their boundaries.

## Interfaces

core.mjs exports DEFAULT_ROOT (absolute Cloudtransition root), createBrainClient({root=DEFAULT_ROOT,python='python3',script?,timeoutMs=15000,maxBuffer=1048576}={}). Client methods recall({query}, {signal}={}) and remember({title,summary,body,supersedes?}, {signal}={}) return {exitCode,payload}; failures throw a sanitized BrainAdapterError with code and no private body in its message. Root/python/script overrides are trusted constructor-only fixture/installation options, never tool parameters. Extension options for fixture injection may use the constructor configuration, with normal default production binding fixed.

## Task 1 — CLI adapter and behavioral tests

- [ ] Create tools/second-brain-memory/core.mjs and core.test.mjs.
- [ ] Validate method keys and existing CLI limits; spawn argv with explicit --root, finite timeout/output cap, cancellation and no retries. Preserve legitimate nonzero CLI JSON statuses, reject malformed/protocol mismatches, fail clearly on missing storage.
- [ ] Tests exercise actual CLI fixtures and local controlled child processes. Include exact F2 and F3 test names from eval.md. Do not run suites mid-flight; integration owner runs once after both slices land.

## Task 2 — Extension and runtime proof

- [ ] Create tools/second-brain-memory/extension.mjs exposing second_brain_recall/second_brain_remember, mapping client results to truthful tool results; use host pi.zod, reject arbitrary roots, forward AbortSignal.
- [ ] Add before_agent_start fixed trusted guidance without replacing base instructions; skip irrelevant revive work and never preload retrieved prose. No custom UI/slash commands.
- [ ] Create runtime-smoke.mjs using real OMP runtime, disposable global agent directory/shared memory fixture/unrelated callers/local fake providers. Capture observed U/F/R manual evidence without live synthetic saves, real provider calls or widening child permissions.
- [ ] Build the graceful thin global-loader source as installation artifact, with clear missing-volume tool behavior; do not install or change global config in this slice.

## Task 3 — Integrate, install, verify

- [ ] Resolve slice contracts and inspect resulting code. Run adapter/Second Brain suites and syntax checks using approved eval commands after all source edits.
- [ ] Run real runtime smoke and fix demonstrated failures at their source. Record only observed manual cases, including rollback, missing storage and restricted-session boundaries.
- [ ] Back up prior memory setting and paths outside repo, install loader, use cfg:// supported setting writes and approval to switch memory.backend off; ask whether to persist session-only changes as required. Preserve old memory data and unrelated configuration.
- [ ] Verify fresh global default-profile discovery and read-only real recall. Update second-brain/README.md, tools README and CODE.md; run brain index/check/query after final docs.
- [ ] Run approved eval, record manual evidence, inspect saved statuses. Repository-wide check may report unrelated existing failures; do not rerun unrelated features.

## Review focus

Missing drive at startup and during a call; cancellation after a committed save; stale data with lock contention; prompt injection crossing the tool/system boundary; restricted child discovery. Cover with actual fixture/runtime observations, not registration mocks. Installation must not disable native memory until the replacement is usable.
