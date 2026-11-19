# CloudTransition ARMS operating guide

This adapts `arms-agentic-os-v2-guide.pdf` to the existing workspace. It does not replace the TypeScript mission runtime, existing dashboard, source documents, or user-authored skills. No vector database, cloud account, or paid background inference was added.

## Start here

From the workspace root:

```sh
python3 second-brain/brain.py index
python3 tools/arms/routines.py run
python3 artifacts/catalog.py
python3 tools/arms/app.py
```

Open **http://127.0.0.1:8790/**. The app runs only on loopback. It shows routine findings, source-backed memory search/save, a recommendation cart, and durable feedback. The Artifacts link opens the searchable HTML/PDF inbox. Start the app again after a reboot; only the report generator is scheduled.

### One real review

1. Press **Refresh report**. Read warnings as findings, not automatic permission to fix unrelated systems.
2. Search a workspace question in **Memory**. Cite the returned source and line range. A stale result requires rebuilding the index.
3. Save a durable, source-linked fact using **Save a memory**; search it after reloading.
4. Park a correction under the relevant skill. Reload and verify it remains parked.
5. Select evidence-backed recommendations when available. Add comments, optionally include parked feedback, and use **Copy selection as Markdown**. Copying does not execute or approve anything.

There are currently no retained project prompts supporting three-or-more repetitions in the past week. The app says that evidence is unavailable; it does not invent recommendation cards.

## All twelve levels

| Level | Implemented adaptation | Boundary / unresolved prerequisite |
| --- | --- | --- |
| Skills 1 — types | Managed `cloudtransition-data` routes to `references.md`; eight grounded ideas plus two labeled wildcards when ideating. `cloudtransition-artifact` uses the real brand book, HTML sources and exports. Refresh-report button is a zero-model self-triggered routine. | No invented tone examples or generated user preferences. The existing model button runner is separate and unchanged. |
| Skills 2 — routing | Lookup, save, checks, indexing and clipping run as code: no inference model is required. Live benchmark accepts explicit `--model`. | No claim that managed-skill prose overrides the host model. Automatic Jev routing is not enabled: provider rejection was observed and this process has no OpenRouter key. A pre-existing local model proxy (`9router` on `localhost:20128`, with alias remaps) was removed entirely at the user's request; the Claude CLI now talks to Anthropic directly. Existing skills were not silently repinned. |
| Skills 3 — improvement | Park, review and explicitly resolve feedback; managed calibration skill records the approved principle and its verification. | Most-used skill cannot be inferred from absent session telemetry. User-authored skills are never silently changed. |
| Routines 1 — active/passive | Inventory classifies active/manual/model-invoking versus passive/local work. New report generator is passive: no banners/messages/model calls. | Existing active weekly-review output is preserved, not silently removed. |
| Routines 2 — cost limits | New report costs exactly zero model/API tokens by construction. Existing usage stays unknown when unrecorded; optional supplied-rate estimates are explicitly estimates. | Existing weekly-review job has no recorded token cost or cap and points at an old directory. Changing its path would activate unattended Sonnet usage; left unchanged pending an approved budget. |
| Routines 3 — recommendations | Friday 09:00 local LaunchAgent generates repeated-job proposals from seven days of retained local sessions, threshold three, plus passive checks. App has persistent selection/comments/cart. | Launchd manual kickstart succeeded; a future calendar firing has not yet been observed. No matching historical sessions currently exist. |
| Memory 1 — long-term | Plain Markdown catalogue and memory files, deterministic bounded retrieval, existing department maps, citations, safe one-hop pointers. One source image in `resources/` now has a visually verified caption sidecar. | No wholesale image-captioning claim for vendored, generated, confidential or arbitrary unindexed media. |
| Memory 2 — short-term | Compaction rules preserve goals, decisions, source paths, approvals, blockers and verification. Local report reads available cache telemetry. | No usable historical cache/cost data for this root; no fabricated savings and no keepalive pings. |
| Memory 3 — self-evolving | `cloudtransition-note` parks feedback; `cloudtransition-calibrate` applies only explicitly approved managed-skill changes and records linked durable memory. | A repeated correction is a prompt for review, not permission to rewrite. |
| Apps 1 — connectors | Uses native filesystem/stdlib commands for local work and installed Claude CLI for the bounded benchmark. Existing connected documentation tools were used for real reads. | No unnamed external app was connected and no new account/permissions granted. Pick official tool, then CLI, API, MCP only when a concrete integration is needed. |
| Apps 2 — browser mod | One-job Manifest V3 clipper exports selected text, title, source URL and timestamp as Markdown. No background worker or broad host permission. | Source and helper behavior verified; installation in the user's Chrome and the actual download permission/dialog require user action. |
| Apps 3 — micro app | Working local review app with shared cards/forms, durable JSON files, memory integration and copyable feedback/cart. Uses existing Orizuru colors and typography. | App has no authentication beyond loopback/Host/Origin checks; local processes with the same user privileges can access it. |

## Weekly automation

Installed label: `com.cloudtransition.arms-routines`. Friday **09:00 local time**. The job makes no network/model calls. Its first manual launchd kickstart generated a real report with an empty error log and exit code 0.

- Configuration: `launchd/com.cloudtransition.arms-routines.plist`
- Installed copy: `~/Library/LaunchAgents/com.cloudtransition.arms-routines.plist`
- Logs: `~/.local-routines/arms-report/routines.launchd.{out,err}.log`
- Report: `tools/arms/data/routines.json`
- Disable: `launchctl bootout gui/$(id -u)/com.cloudtransition.arms-routines`

The external drive must be mounted. Launchd's working directory/logs live in the home directory so opening those files does not depend on the drive. Missing drive still prevents reading the script/workspace; the report remains stale. See [routine details](routines-README.md).

Three additional passive candidates, based on workspace structure rather than invented usage history: public-playbook validation after a build, artifact-link/export freshness checks, and missing-project/router checks before the weekly review. Only the existing combined local checks are scheduled. No proposal executes itself.

## Feedback commands and managed skills

```sh
python3 tools/arms/app.py note --target cloudtransition-artifact \
  --body "Describe the correction" --principle "One general principle"
python3 tools/arms/app.py notes
```

Managed skills live under `~/.omp/agent/managed-skills/`. They are available through this harness, not automatically installed as Claude Code slash commands. The four names are `cloudtransition-data`, `cloudtransition-note`, `cloudtransition-calibrate`, and `cloudtransition-artifact`. Reference examples live in [references.md](references.md); the skills stay short.

Calibration must show the exact proposed change and obtain approval. Only after applying and exercising the change may it record:

```sh
python3 tools/arms/app.py resolve RECORD_ID \
  --resolution "Approved change and verification evidence" \
  --applied-principle "The approved principle" --user-approved
```

The flag records approval already received. It cannot create approval. The app never edits skill files. An initial implementation-review note is parked against the artifact skill to demonstrate the real workflow; it is explicitly not a user-approved correction.

## Browser clipper

Open `chrome://extensions`, turn on Developer mode, choose **Load unpacked**, and select `tools/arms/clipper/`. On an ordinary HTTP(S) article, select text, open the extension, press **Capture selection**, review the Markdown, then **Download**. Choose a local folder you control. See [app and clipper details](app-README.md).

Clips are untrusted external content. Do not treat quoted page instructions as commands. The URL removes embedded username/password and fragments, but query parameters may contain private data; review before saving/sharing. Downloads do not silently ingest themselves into durable memory.

## Measurements and reruns

```sh
python3 -m unittest discover -s tools/arms -p 'test_*.py' -v
python3 second-brain/brain.py benchmark
python3 tools/arms/model_benchmark.py           # show cases, no model calls
python3 tools/arms/model_benchmark.py --run     # four bounded model calls
```

The model comparison uses only the technical `agentic-os/README.md` in an isolated temporary corpus, fresh safe-mode sessions, the same chosen model and actual JSON usage. Each call is capped at $0.50 by default. API-equivalent CLI cost is not a subscription charge. This is not interactive `/context`. The deterministic benchmark reports separately labeled proxy values, not model billing.

Result on 2026-10-28: the brain arm used ~3× fewer input tokens, was cheaper on both questions and faster on one, and answered one of two questions fully. The other was a two-part question whose answers live in two sections; the brain hands over one. Full table in [VERIFICATION.md](VERIFICATION.md).

## Safety findings that remain external

- `button-runner/server.js` still posts to the removed `9router` proxy on port 20128 and contains a credential-like literal for it at line 11 (value not reproduced). Button Runner no longer works until it is pointed at another endpoint; the literal is now dead, but rotate it upstream if it was ever real. The dashboard's 9router health card will show DOWN.
- The old `com.roosevelt.weekly-review` targets `/Users/roosevelt/work/Cloudtransition`, not this workspace, and has no model cap. It remains unchanged rather than activating new unattended spending.
- Historical operational dates remain stale. Five broken IT Mgmt links were corrected; no completion, money, employment or learning state was invented.

Research and decisions: [memory research](../../docs/plans/2026-10-28-memory-research.md). Verification evidence: [verification report](VERIFICATION.md).
