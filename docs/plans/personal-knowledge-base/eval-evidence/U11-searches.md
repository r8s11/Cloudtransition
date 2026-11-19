# U11 real search verification — final-storage-fix snapshot

Each end-to-end `python3 kb.py search` ran from `/tmp` against the actual Claude archive with `--after 2026-10-01 --source claude --limit 1`. No private body copied here.

| Query | Time | Source date | Verified result |
| --- | ---: | --- | --- |
| Orizuru | 1.9845 s | 2026-11-05 | Dashboard design rationale / Orizuru |
| workspace map privacy | 0.1598 s | 2026-11-05 | Workspace reader imports map scope/privacy rules |
| playbook-exclusions | 0.1034 s | 2026-10-30 | Local playbook exclusion-file reference |

Result: FAIL. The initial Orizuru process exceeded the strict 1.000-second acceptance threshold; do not replace that observation with a warm-cache pass.

Opened all three original JSONL sources returned by the real CLI. Confirmed the Orizuru rationale heading, the workspace_content.py map/privacy-rule description, and the local exclusion-file reference. All originals existed. Recorded only the topics and dates here, not message bodies.

Diagnostic replay with cProfile completed in 0.2038 seconds for the full subprocess, with 0.040 seconds in kb_store.search and 0.037 seconds in SQLite execute calls. Three bare Python startup samples were 0.0478, 0.0354 and 0.0355 seconds. These do not establish the cause of the initial outlier; no speculative performance code change was made. A final real three-query verification remains required; cold-cache latency is not proven.

An independent `/usr/bin/time -p python3 .../kb.py search ...` cross-check reproduced the failure: Orizuru 2.08 seconds, workspace-map privacy 0.11 seconds, exclusion policy 0.10 seconds. A separate import-timed direct CLI run took 1.08 seconds while its largest cumulative imports were under 0.017 seconds. These confirm that the original threshold miss was not merely the enclosing Python timer.

Direct-file cProfile runs for the three queries later measured 0.16/0.13/0.12 seconds including process time; observed search bodies took about 0.037/0.052/0.037 seconds. An instrumented execution observed imports 0.0169 seconds, parser 0.0273, connection open 0.0010, search 0.0421 and formatting under 0.0001. The slow unprofiled runs are therefore real but not explained by a captured deterministic application hotspot. Active backfill/storage contention is a hypothesis, not a proven cause. Keep U11 failing and repeat controlled, unprofiled measurements after the backfill releases the ingestion workload; do not weaken the acceptance threshold.

The prior owner-approved U11 revision replaced an absent Pomodoro example with actual Orizuru/workspace-map/exclusion-policy topics. That scope remains unchanged.

## Observations 2026-11-06 02:30–02:40 local (backfill still writing)

- First search after a long idle period (playbook-exclusions, from /tmp, `/usr/bin/time -p`): 3.69 s real. Header 30,780 rows / 11,850 items.
- Immediately afterwards, two rounds of all three queries with `/usr/bin/time -l`: 0.10–0.16 s each, 0 block input operations (everything already in memory).
- In-process phase timing (4 runs): imports 0.014–0.026 s, connect 0.001–0.002 s, search 0.058–0.154 s.
- Header queries use covering indexes (`docs_ts`, `docs_item`), not table scans. DB 170 MB on a USB volume (4 KB pages, 41,746 pages); FTS data 41.8 MB in 10,520 blocks; WAL 7.7 MB.
- Pattern so far: slow only on the first run after idle, fast once the file is in the page cache. That fits a cold USB-read cause but does not prove it; a cache purge needs an admin password, so cold reads could not be reproduced on demand. U11 stays failing. Next step after the backfill: measure a genuinely cold first search (after reboot or idle), and if confirmed, test an FTS `optimize` merge to reduce random reads before considering other changes.
