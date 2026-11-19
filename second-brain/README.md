# Second Brain

Deterministic, model-free retrieval over this workspace. A generated index is scored first; exactly one source file is opened second; the model (if any) only ever sees the cited evidence. Standard-library Python, no network, no paid calls.

The design follows the five principles in *Second Brain - Principles and Starter Prompts.pdf*: research first, borrow ideas (plain markdown, one small index, cited answers) without copying, deterministic code before the model, one always-true catalogue, and make it prove itself.

## Commands

All commands print exactly one JSON object on stdout. `--root PATH` selects the workspace. Default: the nearest ancestor of the current working directory that contains `second-brain/brain.py` (so running from the workspace folder or any subfolder uses that folder as the root), otherwise the parent of `second-brain/`. The CLI therefore works from any working directory and against temporary fixtures.

```bash
python3 second-brain/brain.py index
python3 second-brain/brain.py query "How do I save a new memory?"
python3 second-brain/brain.py remember --title "Nebulizer settings" \
    --summary "Runs at 40 psi" --body "The nebulizer runs at 40 psi. Replace filters monthly."
python3 second-brain/brain.py remember --title "Nebulizer settings update" \
    --summary "Runs at 55 psi" --body "Raised to 55 psi." \
    --supersedes 2026-11-09-nebulizer-settings      # the old memory now scores at half
python3 second-brain/brain.py query --no-reindex "…"   # report drift (exit 3) instead of repairing it
python3 second-brain/brain.py check
python3 second-brain/brain.py benchmark
python3 second-brain/brain.py --root /tmp/fixture check     # fixture / other workspace
```

`--root` is also accepted after the subcommand. Option values that start with `-` are accepted (`--body "-x"`). A question that starts with `-` needs `--`: `brain.py query -- "-x"`.

`query` never answers from a file that changed since indexing. When the catalogue is missing, the postings were written by an older version, or the source (or pointer target) it would answer from has changed, it rebuilds the index once under the writer lock (under a second) and answers again with `"reindexed": true`. If the rebuild cannot run (lock busy, hand-written `memory.md`), it returns the original `stale` / `not_indexed` result with `reindex_error`. `--no-reindex` turns the repair off. A file that was **added** and never indexed is not seen by `query`; run `index` after adding sources, and `check` to list drift.

### `query` contract

```json
{
  "status": "ok | no_match | stale | not_indexed | empty_question",
  "question": "…",
  "evidence": [{"path": "agentic-os/README.md", "start_line": 91, "end_line": 94, "text": "…"}],
  "files_opened": 1,
  "elapsed_ms": 0.9,
  "keywords": ["port", "agentic", "dashboard"],
  "intent": "duration",
  "source": {"path": "…", "title": "…", "kind": "source|router|memory", "area": "code", "score": 12.3, "superseded_by": "2026-11-09-newer-memory"},
  "pointer": null,
  "pointer_status": "followed | stale | empty",
  "candidates": [{"path": "…", "score": 12.3}],
  "opened": ["agentic-os/README.md"],
  "bytes_opened": 10963,
  "redactions": 0,
  "reindexed": true,
  "reindex_error": "locked",
  "message": "present for no_match / stale / not_indexed / empty_question"
}
```

`evidence` is non-empty only for `ok`. Paths are root-relative POSIX; lines are 1-based and inclusive and refer to the real file. `pointer_status` is present only when a pointer was considered; `intent` only for a duration question; `source.superseded_by` only when the answering memory has been superseded (prefer the newer memory); `reindexed` only when this query rebuilt the index; `reindex_error` only when that rebuild failed.

### Other outputs

| Command | JSON |
| --- | --- |
| `index` | `{status:"indexed", catalogue, memory_index, catalogue_bytes, sources, memories, entries, skipped:{reason:n}, excluded_secret_paths:[…], recovered_tmp_files, elapsed_ms}` |
| `remember` | `{status:"saved", id, path, catalogue, memory_index, indexed:true, supersedes:[id], adopted_orphans, recovered_tmp_files, elapsed_ms}` |
| `check` | `{status:"ok"\|"problems", problems:[{kind,path,detail}], counts:{sources,memories,catalogue_bytes}, elapsed_ms}` |
| `benchmark` | `{status:"ok", disclaimer, totals, totals_technical_only, results:[…], …}` |
| any failure | `{status:"error", error, message}` |

Problem kinds from `check`: `not_indexed`, `bad_line`, `stale_sig`, `dangling_entry`, `duplicate_entry`, `unindexed_source`, `excluded_in_catalogue`, `orphan_memory`, `stray_tmp`, `postings_drift`, `memory_index_drift`, `memory_index_foreign`.

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | ok, saved, indexed, `no_match`, `empty_question` |
| 1 | `check` found problems, or internal error |
| 2 | invalid input or arguments (`remember` limits, bad root, question over 500 chars) |
| 3 | `query` is `stale` or `not_indexed` and the automatic rebuild was disabled (`--no-reindex`) or failed |
| 4 | writer lock busy (retryable; `BRAIN_LOCK_TIMEOUT` seconds, default 10) |

`remember --supersedes ID` (repeatable, at most 5) names memories the new one replaces. Each id must be an existing memory (`YYYY-MM-DD-slug`), otherwise exit 2 and nothing is written. The old file is never edited or deleted: the new memory carries a `_Supersedes: id_` header line, the superseded memory scores at half, and `memory.md` marks it `(superseded by id)`.

`remember` limits: title 1-120 chars, summary 1-500, body 1-8000; title and summary are single-line; control characters are rejected; content that looks like a credential (private-key header, AWS/GitHub/Slack/OpenAI-style tokens, JWTs) is refused.

### Global OMP memory

The [global memory extension](../tools/second-brain-memory/README.md) exposes `second_brain_recall` and `second_brain_remember` from ordinary default-profile OMP sessions, independent of their working directory. Its fixed shared root is this workspace. Recall preserves the query contract; saves and explicit supersedes use this same store. No transcript auto-ingestion or second corpus is introduced.

The installed loader belongs in `~/.omp/agent/extensions/second-brain-memory.ts`; native `memory.backend` must be `off` for the approved cutover. Restart sessions after installation or a backend change. Native memory files remain preserved; native `/memory`, `memory://` and `manage_skill` are not redirected. Missing storage returns an error without fallback. See the extension guide for profile restrictions, recovery, rollback and acceptance evidence.

## Retrieval ladder

1. Strip the question to keywords (stop words dropped, light consistent stemming: `weekly`→`week`, `server`/`serve`→`serv`, `configuration`/`configure`→`configur`). A duration question ("how long", "how much time", "how many minutes/hours/days/…", "duration") sets `intent: duration`: `long` is dropped as filler, and a section that states a duration (`45–60 min`, `3 weeks`) is preferred. The marker is recorded per section at index time, so no file is opened to apply it, and it only lifts sections that already match a keyword.
2. Score every catalogue entry without opening it: field-boosted BM25 over the term counts recorded in `postings.json` at index time, plus file name, directory, title, headings, summary and the catalogue's `kind · area` columns. Dated design snapshots (`docs/superpowers/`, `specs/`, `briefs/`, `drafts/`, `YYYY-MM-DD-*`) get a mild prior so living docs win ties. Memories get a bounded recency bonus from the date in their file name (`1 + 0.1·exp(-age_days/180)`), so the newer of two equally relevant memories wins; a superseded memory scores at half.
3. Re-rank the top five by their single best section, using per-section term counts stored in the postings: a document that answers in one section beats one that mentions every word in different places, because only one bounded section is handed on.
4. Open the single best source and verify its size+hash signature. On a mismatch, rebuild the index once and restart the ladder (otherwise `stale`).
5. Extract one section (heading-based for Markdown, top-level keys for YAML, paragraphs for text), bounded to 40 lines / 3000 characters around the keyword hits. A document's title/preamble section cannot win on the title words alone.
6. If that section only points elsewhere (little prose, or a router row), follow at most one pointer: a Markdown link or backticked `*.md|yml|yaml|txt` path that resolves inside the root and is present in the catalogue (so excluded files can never be followed). The pointer target is opened with the same symlink/containment/signature checks, reported `stale` if it fails them, and never chained. Maximum `files_opened` is therefore 2.

No match is reported as `no_match`, never guessed: at least 40% of the known question terms must match, and the opened section must actually contain a keyword.

## Files and storage

| Path | Role |
| --- | --- |
| `second-brain/catalogue.md` | The human-readable catalogue: one line per source and memory (`[title](link) · kind · area · sig · summary ‖ k: keywords ‖ h: headings`). Generated; read this first. |
| `second-brain/postings.json` | Machine index written with the catalogue: per-document and per-section term counts keyed by path + signature. Lets code score every file and section without opening sources. An entry whose signature differs from the catalogue is ignored (metadata-only scoring) and reported by `check`. |
| `second-brain/memories/YYYY-MM-DD-slug.md` | Plain-Markdown memories written by `remember` (title, `> summary`, saved timestamp, optional `_Supersedes: id_` line, body). Indexed (catalogue and postings) in the same locked step. |
| `memory.md` (workspace root) | Short generated index of memories: one Markdown line per memory (`- [title](second-brain/memories/…md) — summary`, summary capped near 160 characters), never the body. Rewritten by `index` and `remember` under the same writer lock with the same atomic write, so orphans are adopted and deleted memories drop out. Titles and summaries come from the same redacted catalogue metadata, labels are Markdown-escaped, link targets are percent-encoded root-relative paths. Not a source: it is excluded from indexing so it cannot drift from itself. `check` reports `memory_index_drift` when it is missing or differs from what the memory files produce (`index` repairs it), and `memory_index_foreign` when a file named `memory.md` was not generated here: the writers then refuse (exit 2, `memory_index_foreign`) instead of overwriting it. |
| `second-brain/benchmark-questions.json` | 21 real workspace questions with expected answer strings and source paths (used while tuning). Expected strings are quotes from living documents: when a document is reworded, update the string. |
| `second-brain/holdout-questions.json` | 9 further real questions written after tuning and never used for it. |
| `second-brain/tests/test_brain.py` | Boundary regression tests. |
| `second-brain/.lock`, `.brain-*.tmp` | Writer lock and in-flight atomic-write files (git-ignored). |

Areas and one-line descriptions come from the existing routers (`OPERATIONS.md`, `CODE.md`, `MONEY.md`, `LEARNING.md`, `HEALTH.md`, `CONTENT.md`): their tables are parsed for path to area and description. The routers are read, never modified.

### Concurrency and recovery

* One advisory `flock` guards every writer (`index`, `remember`); readers never lock. Contention fails with exit 4 rather than blocking forever.
* Memory, catalogue and `memory.md` are written with temp file, `fsync`, atomic `os.replace`, in that order. The memory file lands first, so a crash between the steps leaves an orphan memory (and a stale `memory.md`, which `check` reports), never a catalogue line without a file.
* The next `remember` or `index` removes leftover `.brain-*.tmp` files and adopts orphan memories; `check` reports them beforehand. A corrupt or unrecognised catalogue is treated as `not_indexed` and rebuilt by `index` (or the next `remember`), which keeps existing memory files.
* Memory file names are slug-only and never overwrite; a repeated title gets `-2`, `-3`.

## What is (and is not) ingested

Included: `.md`, `.yml`, `.yaml`, `.txt` under the workspace that are curated knowledge: the operational core (`TASKS.md`, `DASHBOARD.md`, `routine.md`), the six area routers, plans, books, per-topic READMEs, `agentic-os/`, `visual-second-brain/`, dashboard docs, `IT Mgmt/` playbook, finance/goal/career trackers, `resume/master.md` and top-level resume files, interview/freelance/networking notes, `resources/` Markdown (including image caption sidecars), `tools/` Markdown, and this README.

Excluded by policy (counted per reason in `index` output `skipped`):

* secrets: `.env*`, credential/secret/password/token-named files, key/cert files, and any file containing a private-key header or a high-confidence token pattern (listed in `excluded_secret_paths`);
* generated, vendored, or tool-owned: dot-directories, `node_modules`, `venv`, `dist`, `build`, `runs`, `graft`, test directories, Playwright output directories (`test-results/`, `playwright-report/`, at any depth), saved web pages (`*_files/`), `*.min.*`, generated `*_REPORT.md` / `*_SUMMARY.txt`, `requirements*.txt`, nested third-party projects (`projects/rendercv`, `andrej-karpathy-skills`);
* employer-private: any path whose directory or file name contains `private`, `employer`, `secret`, `credential` (this includes `IT Mgmt/Employer-IT-Playbook-Private/`) and contractor work logs (`*work-log*`);
* agent instruction files: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `CURSOR.md`, `SKILL.md`, `AGENT-CONTRACT.md`, `PRODUCT.md`; and the generated root `memory.md`;
* personal academic records (`College Planning/`, which `LEARNING.md` routes at folder level only), archived material (`archive/`), resume variants/archive (only top-level `resume/*.md` kept), the implementation plan for this system, and byte-identical duplicate files (first path kept);
* symlinks, binary files, empty files, files over 300 KB.

## Benchmark

```bash
python3 second-brain/brain.py index
python3 second-brain/brain.py benchmark --repeat 3
python3 second-brain/brain.py benchmark --questions second-brain/holdout-questions.json --repeat 3
```

For each question it runs the brain path and a deterministic baseline that scans every eligible file, ranks files by keyword hits, and reads the top K (default 3) whole. It reports whether an expected answer string was present in the text each side would hand to a model, bytes opened, bytes handed to the model, a token proxy (`ceil(bytes / 4)`), file counts and median wall time of the Python code.

**This is a proxy.** It is not a Claude `/context` reading, not billing, and the baseline is not a real default Claude session. Wall times exclude model latency. The live fresh-session comparison is `tools/arms/model_benchmark.py` (see `tools/arms/VERIFICATION.md`).

Measured on 2026-11-09 (176 sources, 63 memories):

| Set | Answer found: brain / scan | Token proxy handed to model: brain / scan | Median ms: brain / scan |
| --- | --- | --- | --- |
| Tuning set, all 21 | 19 / 17 | 6,983 / 276,030 | 24.7 / 85.4 |
| Tuning set, 16 technical | 14 / 12 | 5,156 / 222,622 | 24.7 / 85.4 |
| Held-out, 9 | 9 / 7 | 3,620 / 125,609 | 24.3 / 84.8 |

History. 2026-10-28 (138 sources, 1 memory): 20/21 and 9/9; the one miss was "How long is the weekly DevOps block?". By 2026-11-09 the same code scored 15/21 and 8/9 on the grown corpus: three expected strings had been reworded out of their documents (questions updated, answers were correct), a nested `PRODUCT.md` was indexed against the stated policy (now excluded), and the duration miss remained (fixed by the duration intent). Two tuning questions still miss: "What is Button Runner in the code router?" (`tools/arms/README.md` outranks the `CODE.md` row) and "Which technology stack does the dashboard app use?" (no shared vocabulary with `FastAPI + Jinja2 + Tailwind`).

## Tests

```bash
python3 -m unittest discover -s second-brain/tests -v
```

The tests build throwaway workspaces and cover: exclusion canaries, one-source-only opens with real line citations, no-match / empty / stale / not-indexed, pointer bounds (escape, absolute, URL, excluded, symlink, post-index symlink swap, no chaining), bounded extraction, secret redaction, save/index/query consistency, traversal-safe memory names, input limits, concurrent writers, lock contention, crash-leftover recovery, corrupt catalogue, short memory index sync / drift / repair / removal, safe links and redaction in `memory.md`, refusal to overwrite a hand-written `memory.md`, the `CONTENT.md` router, working-directory independence, the benchmark report shape, automatic reindex on a missing or drifted index (and the busy-lock fallback), supersede scoring / marking / id validation, memory recency, and the duration intent (including that it never matches on the marker alone).

## Design limitations

* Lexical BM25, not semantic search: a question that shares no vocabulary with its answer will rank it poorly or `no_match`. Stemming is light and English-only. The only question intent understood is duration ("how long"); "how much" / "how many" get no special handling.
* `postings.json` holds per-section term counts for every source (about 1.3 MB for 138 files), loaded on each query. That is the cost of scoring buried facts without opening files; it grows linearly with the corpus.
* Exactly one source is opened. Questions that need two independent files get the best one (plus at most one pointer), not a merge.
* Staleness is checked, and repaired, on the opened source and pointer target only. A new or deleted file elsewhere is detected by `check`, not by `query`.
* Recency applies to memories only (date in the file name). Sources carry no trustworthy date, so an old document is not demoted by age.
* Supersede is explicit: nothing detects that two memories contradict each other. A `_Supersedes:` line in a hand-written memory file is honoured the same way.
* Router rows and thin sections trigger pointer-following; a prose-heavy section never does, even if it contains a relevant link.
* Redaction is pattern-based and line-preserving (credential-like values after `password:`-style keys, backticked mixed-case/digit/symbol strings, `DC=`/`OU=`/`CN=` names, known token formats). It cannot recognise an arbitrary plain-text secret or personal detail; unindexed means unexposed, so keep sensitive material in excluded locations.
* The catalogue is one file of roughly one line per source (a few hundred bytes each). It is meant to be read by code; it is not guaranteed small enough to be loaded into a model's context wholesale as the workspace grows.
* Saving a memory re-renders the catalogue under a lock; it is fine for thousands of memories, not for concurrent multi-machine syncing of the same directory.
* Windows is untested: the lock falls back to an exclusive lock file with no stale-lock takeover.
