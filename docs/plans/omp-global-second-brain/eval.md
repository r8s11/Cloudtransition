---
feature: Global OMP memory backed by Second Brain
status: passed
approved: 2026-11-16
rd: rd.md
---

# Evals: Global OMP memory backed by Second Brain

Replace the active default-profile local memory pipeline with a globally discovered CLI-backed extension. One curated Second Brain remains the source of truth. No new visual interface; no HTML mockup.

## Build contract

- Build/install only after user approval changes status to approved. Changes to expectations require re-approval.
- Run: `node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/omp-global-second-brain/eval.md`
- Record manual cases with `node ~/.agents/skills/write-evals/scripts/evals.mjs record docs/plans/omp-global-second-brain/eval.md <ID> pass|fail "<observed evidence>"`.
- Save sanitized evidence under eval-evidence/. No real memory bodies, credentials, private configuration dumps, or synthetic acceptance writes to the live store.
- Any source change stales automated results. Every automated case must pass; a recorded manual failure blocks delivery. Do not claim unrelated repository evals pass.
- The builder supplies tools/second-brain-memory/core.mjs, extension.mjs, core.test.mjs and runtime-smoke.mjs. Runtime smoke must use a temporary agent directory and temporary shared workspace, local fake providers, and no paid inference. It must retain normal HOME for OMP native extraction and use a writable external TMPDIR where necessary.
- Named tests below must assert real subprocess/filesystem outcomes, not mock echoes, source-text patterns, or tool-registration copies.

## Traceability

| Requirement | Cases |
| --- | --- |
| G2 Bounded, cited recall | F2 |
| G3 Save and explicit supersede | F3 |
| G5 Safe execution, cancellation and bounds | F2, F3 |
| G8 Real runtime and no live synthetic writes | R1, R2 |

No requirements are unmapped. Authentication, UI responsiveness, public endpoint abuse, and remote retention are outside this local CLI integration. Filesystem permissions and local subprocess failure are covered instead.

## Usage — every entry point

## Failure — validation, storage and lifecycle

### F2 — Limits, secrets and shell syntax remain data
- **Setup:** core.test.mjs test named `validation and argv preserve the fixed memory boundary`; it uses the actual brain.py against a disposable workspace, plus a local marker path outside it.
- **Steps:** Exercise empty/over-500-character queries, title 121 characters, summary 501 characters, body 8001 characters, unknown supersede ID, credential-shaped synthetic canary, shell metacharacters, and a model-supplied alternate root property.
- **Expected:** Existing CLI invalid-input distinctions are retained. Secret-shaped content is refused before persistence. Shell syntax cannot create the marker or run a command. An alternate root is rejected, never honored. Invalid saves leave the memory set unchanged. Non-secret valid boundaries remain accepted.
- **Verify:** `node --test --test-name-pattern='validation and argv preserve the fixed memory boundary' tools/second-brain-memory/core.test.mjs`

### F3 — Lock contention, cancellation and malformed subprocess results
- **Setup:** core.test.mjs test named `subprocess failure and cancellation never acknowledge an unsaved memory`; use disposable fixture, real writer lock contention, and local child scripts for hanging, oversized, malformed-JSON and nonzero-exit responses.
- **Steps:** Contend for the writer lock; cancel a pending operation; trigger deadline/output limits; return malformed JSON; simulate interruption after a real committed save.
- **Expected:** Lock exit 4 and other CLI statuses remain distinguishable. Timeout/cancellation terminate the owned child and produce no success claim; a genuinely committed save remains discoverable. No automatic write retry duplicates it. Bad JSON/output/exit is explicit, bounded and does not crash OMP. Logs omit memory bodies.
- **Verify:** `node --test --test-name-pattern='subprocess failure and cancellation never acknowledge an unsaved memory' tools/second-brain-memory/core.test.mjs`

## Regression — existing contracts and safe cutover

### R1 — Existing brain behavior and adapter tests pass
- **Setup:** Workspace root, writable TMPDIR and local Python/Node. No live provider usage.
- **Steps:** Run the entire existing Second Brain unittest suite and adapter behavioral suite.
- **Expected:** Both suites pass. Current exclusions, citations, bounded extraction, lock safety, explicit supersede and memory-index synchronization remain valid.
- **Verify:** `python3 -m unittest discover -s second-brain/tests -v && node --test tools/second-brain-memory/core.test.mjs`

### R2 — No build or package-install requirement
- **Setup:** The implemented source files, Node for syntax checks and Bun/OMP for the real runtime smoke.
- **Steps:** Parse the JavaScript entry points; run the isolated runtime smoke as in U1.
- **Expected:** Entry points parse without errors. The documented OMP loader runs them without a new build, package install or fork. No existing typecheck/production-build command exists for this CLI bridge; do not invent a pass for one.
- **Verify:** `node --check tools/second-brain-memory/core.mjs && node --check tools/second-brain-memory/extension.mjs && node --check tools/second-brain-memory/runtime-smoke.mjs`

## Design

No graphical surface is added or redesigned. Existing OMP tool-result and error rendering is reused; no D cases or HTML mockup. New user-facing commands, panels or custom widgets require renewed scope review rather than being invented during implementation.

## Usage — smoke (added 2026-11-17 after manual-case trim)

### U100 — Surface responds (smoke)
- **Setup:** dashboard test client; no live services beyond the local app.
- **Steps:** Run the documented recall command against the local index.
- **Expected:** Exit 0 with JSON results; no network, no provider call.
- **Verify:** `python3 second-brain/brain.py query "workspace" >/dev/null`
