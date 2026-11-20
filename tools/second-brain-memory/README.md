# Global OMP Second Brain memory

The default-profile loader exposes `second_brain_recall({query})` and `second_brain_remember({title, summary, body, supersedes?})` in ordinary OMP sessions, including sessions outside this workspace. Both tools call the existing Python CLI with the fixed root `/Volumes/SANDISK USB/work/Cloudtransition`. Tool arguments cannot select another root, executable or script.

Recall returns `{exitCode, payload}` with the CLI's status, bounded evidence, source path and inclusive line ranges. Retrieved text is untrusted historical evidence, never policy. Base session instructions stay intact. Save writes one curated Markdown memory and updates the existing catalogue, postings and memory index. Explicit corrections use `supersedes` and retain the original file. This bridge does not automatically save transcripts or extract memories.

## Installation and boundaries

Copy `loader.ts` to `~/.omp/agent/extensions/second-brain-memory.ts`. The loader lives on the internal disk and dynamically imports this workspace implementation. Set `memory.backend` to `off` using OMP's supported configuration interface, then persist the approved setting and start a fresh session. Do not disable native memory before verifying discovery and recall.

Existing native memory artifacts remain untouched. The running session may still contain previously injected native memory. `/memory`, `memory://` and `manage_skill` retain their native behavior; this extension does not redirect those interfaces.

Named profiles and alternate agent directories have separate discovery roots. `--no-extensions` skips automatic discovery. SDK children with explicit restricted tool sets must retain those restrictions. CLI `--tools` selects built-in tools; it is not a general extension-tool permission boundary. No claim covers profiles where this loader is not installed.

## Failures and recovery

Each call uses argv-only subprocess execution without a shell, a 15-second deadline and a 1 MiB combined output limit. Existing input and credential checks apply. The CLI's exit codes 0–4 remain visible; missing storage, unavailable Python, malformed results, cancellation, deadlines and excessive output produce sanitized errors. No fallback corpus or automatic write retry exists.

If the drive is absent at startup, OMP still starts and the loader exposes unavailable-memory tools. Mount the drive and restart OMP to load the implementation. If storage disappears after startup, restore it and make a new call. A cancelled or timed-out save might already have committed: recall before deciding whether another save is needed.

## Rollback

Set the previous native `memory.backend` value through the supported interface and disable only `~/.omp/agent/extensions/second-brain-memory.ts` by moving it outside the extensions directory. Start a fresh session. Keep both corpora; do not delete or import native memories. Do not overwrite unrelated current settings with an old full configuration backup.

## Verification

```bash
python3 -m unittest discover -s second-brain/tests -v
node --test tools/second-brain-memory/core.test.mjs
node --check tools/second-brain-memory/core.mjs
node --check tools/second-brain-memory/extension.mjs
node --check tools/second-brain-memory/runtime-smoke.mjs
TMPDIR="/Volumes/SANDISK USB/work/omp-test-tmp" node tools/second-brain-memory/runtime-smoke.mjs
```

The runtime smoke uses real OMP RPC sessions, normal HOME, a temporary shared workspace, a disposable agent directory and a loopback fake provider. Its copy of the actual loader changes only the installation path; its copied adapter changes only the fixture root. No paid provider or synthetic write to live memory is used. Temporary files are removed after the run. Acceptance criteria and recorded evidence live in [`../../docs/plans/omp-global-second-brain/`](../../docs/plans/omp-global-second-brain/).

Use a writable temporary directory outside this workspace when the internal disk is full. The existing CLI suite tests nearest-ancestor discovery, so placing its temporary directory inside this workspace changes the test's root. The smoke preserves HOME and isolates OMP runtime/config state externally; `--installed` discovers the real default-profile loader and performs only a read-only query, emitting citations without source bodies.
