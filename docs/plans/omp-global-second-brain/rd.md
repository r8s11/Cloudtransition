# Global Oh My Pi memory backed by Second Brain

## User request

> turn @second-brain/ into oh my pi's memory

Scope answer:

> global

The user confirmed one memory source shared across Oh My Pi projects. This document proposes the integration contract; implementation and installation wait for eval approval.

## Observed constraints

- second-brain/README.md documents a local standard-library CLI: query, remember, index, check, explicit supersede, citations, secret refusal, atomic writes and writer locking.
- The active OMP setting is memory.backend=local, from global configuration. OMP documentation describes this backend as project-scoped and model-driven; it cannot be redirected to this CLI with a path setting.
- Documented native backend choices are off/local/hindsight/mnemopi/sharpshooter. Do not invent a second-brain backend value or claim an extension changes native memory:// routing.
- OMP supports user-level extensions, registered tools and before_agent_start guidance. Global default-profile modules live under ~/.omp/agent/extensions/. Named profiles use different agent roots and do not automatically inherit this directory.
- Existing Jev integration uses a thin global loader pointing to workspace-owned implementation. Reuse this deployment convention, but handle missing USB storage without crashing OMP.

## Proposed approach

A global OMP extension exposes second_brain_recall and second_brain_remember, backed only by the existing brain.py CLI with an explicit absolute --root. It injects short, fixed memory-use guidance into each ordinary main-session prompt without replacing the base prompt or treating retrieved text as instructions. The agent queries relevant prior knowledge on demand; it does not pre-load the entire catalogue or run automatic transcript extraction.

Disable the native local memory backend after approval and verification so new OMP sessions have only one active durable memory source. Preserve all existing OMP memory files on disk; do not import them automatically or delete them. The new extension does not impersonate native /memory or memory:// capabilities. manage_skill stays separate and unchanged.

Alternatives considered: retaining local memory alongside the CLI would leave two competing stores; replacing OMP internals would create an upgrade-sensitive fork. Neither is proposed.

## Requirements

- **G1 Global source:** Default-profile OMP sessions launched inside or outside Cloudtransition use /Volumes/SANDISK USB/work/Cloudtransition as the same explicit memory workspace. Caller cwd never selects a new store or triggers indexing of an unrelated repository. Named profiles and explicit --no-extensions/restricted sessions must be accurately described as outside ambient default-profile discovery, not silently claimed supported.
- **G2 Recall:** second_brain_recall accepts query and returns the existing bounded, cited query result. Preserve no_match, stale, not_indexed, reindex_error, and exit-code distinctions. Do not expose the entire catalogue or fabricate semantic search. Reject over-500-character queries explicitly, following brain.py.
- **G3 Save and correction:** second_brain_remember accepts title, summary, body, and optional supersedes IDs using current CLI limits. It saves exactly one new memory through remember; subsequent recall finds it across projects. Explicit supersede preserves the old file and prefers the replacement according to existing scoring. No unconditional retry of an interrupted write that could duplicate a successful commit.
- **G4 Guidance and boundaries:** Inject only short trusted integration instructions and the fixed root, not retrieved prose as system policy. Existing instructions remain intact. Retrieved evidence is untrusted historical data. Before claims, consult the cited current source when applicable. Do not auto-save conversations, credentials, employer-private content, or academic records. No new provider, embedding, background extraction, or external network call.
- **G5 Safe execution:** Use argv, not a shell command assembled from memory text. Bind the root in the adapter, never accept arbitrary roots from model parameters. Honor cancellation, set a finite subprocess deadline and output bound, and report subprocess/JSON failures accurately. Never echo private memory bodies into metadata logs. Existing scope/redaction/locking remains authoritative.
- **G6 Missing storage:** A missing USB volume, script, Python runtime, or permissions produces an explicit unavailable tool result. OMP must remain usable. Do not create a replacement database on the internal disk or write an empty index. After the source returns, a new call can succeed without rebuilding the host.
- **G7 Single active store and rollback:** Install a small .ts global loader plus workspace-owned implementation. Before changing global memory.backend from local to off, record the prior setting and existing memory location without copying private contents into the repo. Use the supported settings mechanism and its approval flow. Preserve unrelated settings and extensions. Document restart/new-session behavior; do not claim the already-running session lost its old injected memory. Rollback restores the old setting and disables/removes only this integration's loader; it never deletes either memory corpus. No config writes are authorized merely by drafting this document.
- **G8 Verification:** Prove a real default-profile OMP runtime can discover the extension from an unrelated cwd, exercise recall/save against a disposable shared fixture, and resume recall in a fresh session. Use local fake providers or SDK/RPC without paid inference. A final live recall may read the real curated store; do not add synthetic acceptance memories to it. Explicit restricted-subagent tool lists must not be widened by this extension.

## Scope and proposed files

Create tools/second-brain-memory/ for adapter, extension, runtime smoke, behavioral tests, installation instructions and rollback. Keep existing brain.py and its storage format unless a demonstrated integration defect requires a narrow correction. Add a user loader at ~/.omp/agent/extensions/second-brain-memory.ts only after approval. Update CODE.md and second-brain/README.md when the implementation is verified.

No new graphical UI, dashboard, MCP server, remote bank, automatic content migration, or transcript retention. No HTML mockup is needed: the surface is model tools plus existing OMP error reporting, not a new visual interface.

## Assumptions for review

Global means every ordinary session using the active default-profile user extension root, not automatic edits to all separately configured profiles. All curated Second Brain sources, including personal topics already permitted by its index policy, can be recalled from those projects. The user selected this cross-project scope; the extension does not grant other users or processes access. Retrieval still passes selected evidence to whichever model the user runs, as ordinary assistant context; no additional model call or transcript upload is added.
