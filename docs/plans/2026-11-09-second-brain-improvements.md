# Second Brain improvements plan (2026-11-09)

Sources: `Second Brain - Principles and Starter Prompts.pdf` (five principles) and `knowledge-base-prompt.md` (personal knowledge base design). Both were already implemented: the principles in `second-brain/brain.py`, the knowledge base as `kb.py` (see `KB-README.md`). This plan covers the gaps that remained. Authoritative behaviour is in `second-brain/README.md`; this file records what was decided and what is still open.

## Findings before the work

- `check` reported 18 problems (9 `stale_sig`, 9 `unindexed_source`). Nothing rebuilt the index after source edits, so principle 4 ("an index that's always true") depended on remembering to run `index`.
- Memories had no way to replace each other. With equal relevance the *older* memory won, because ties broke on path and paths start with the date.
- The benchmark had drifted from 20/21 and 9/9 (2026-10-28) to 15/21 and 8/9 on the grown corpus (177 sources, 63 memories).
- `agentic-os/PRODUCT.md` was indexed although the README lists `PRODUCT.md` as an excluded agent file. Only the root file was excluded.

## Done

| Item | Decision | Proof |
| --- | --- | --- |
| Self-healing index | `query` rebuilds once and answers again when the catalogue is missing, the postings come from an older version, or the answering source / pointer target changed. Failure to rebuild returns the original `stale` with `reindex_error`. `--no-reindex` keeps the old report-only behaviour. Added files are still found only by `index` / `check`: detecting them needs a full scan (about 0.7 s) on every 25 ms query. | `SelfHealTests` (2 tests) |
| Supersede | `remember --supersedes ID`. The old file is never edited. The relation lives on the new memory's `_Supersedes:` line and in `postings.json`; the superseded memory scores at half; `memory.md` marks it. Catalogue line format unchanged, so no migration. | `SupersedeAndRecencyTests` (3 tests) |
| Recency | Memories only: `1 + 0.1·exp(-age_days/180)` from the file-name date, the same shape as `kb.py`. Sources get none: the catalogue records no trustworthy date. | same class |
| Duration intent | "how long", "how much time", "how many minutes/…", "duration" set `intent: duration`. Sections that state a duration carry a synthetic `~dur` term in the postings (version 3). It lifts sections and documents that already match a keyword; it never matches alone. | `DurationIntentTests` (2 tests); benchmark question `ops-devops-block` now passes |
| Nested `PRODUCT.md` | Excluded everywhere, as the README already said. | benchmark question `am-api-binding` now passes |
| Benchmark upkeep | Three expected strings had been reworded out of their documents; the brain's answers were correct. Strings updated to the current wording. | 19/21 and 9/9 on 2026-11-09 |

Test suite: 35 tests pass (28 before). Four older tests now pass `--no-reindex` to keep testing drift detection itself.

## Open

1. **`code-button-runner`**: "What is Button Runner in the code router?" picks `tools/arms/README.md` (12.3) over the `CODE.md` row (11.4). A router-row prior for questions that name a router ("in the code router") would fix it. Not done: one question is not enough evidence for a new ranking rule.
2. **`code-dashboard-stack`**: "technology stack" shares no word with `FastAPI + Jinja2 + Tailwind`. This is the documented lexical limit. Options: a small synonym table (`stack` → framework names is not generalisable), or accept it.
3. **"How much" / "how many"**: no intent handling. Add only when a real question misses.
4. **Added-file detection in `query`**: a cheap directory-mtime check could trigger the rebuild. Not done: mtimes are unreliable on the exFAT USB volume this workspace lives on.
5. **Knowledge base summaries**: `kb.py stats` shows 17,488 items pending Haiku summaries. This spends money and sends redacted mail text to Anthropic; it needs the explicit approval and dollar cap described in `KB-README.md`. Not part of this work.
6. **One search over both stores**: `brain.py` (curated workspace) and `kb.py` (mail and sessions) stay separate tools on purpose: different privacy boundaries. A wrapper that calls both is possible; no need shown yet.

## Rerun

```bash
python3 -m unittest discover -s second-brain/tests
python3 second-brain/brain.py check
python3 second-brain/brain.py benchmark --repeat 3
python3 second-brain/brain.py benchmark --questions second-brain/holdout-questions.json --repeat 3
```
