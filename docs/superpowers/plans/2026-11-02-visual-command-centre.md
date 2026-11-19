# Visual Command Centre Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` for sequential implementation, or `superpowers:subagent-driven-development` only for genuinely independent slices. Track the checkboxes below. Read this entire document before editing.

**Goal:** Upgrade the existing CloudTransition dashboard into a topic-first workspace front door with recent artifacts, daily shortcuts, truthful counts, and an interactive file map.

**Architecture:** Keep the existing dashboard shell and launchd service. Extend the existing Visual Second Brain rather than creating another browser or index. Its portable runtime remains one self-contained HTML file plus one generated JSON index; its existing Python refresh utility remains maintenance tooling.

**Tech stack:** Existing FastAPI/Jinja dashboard, vanilla JavaScript/CSS, standard-library Python indexing. No new framework, package manager, cloud model, vector store, database, or internet dependency for the new views.

**Spec:** The confirmed requirements and proposed design below form the specification. User approved the discovery choices, not implementation. This is a deferred handoff for the current agent or Fable 5.1 after usage resets. Do not execute until explicitly asked.

## Confirmed requirements

- Cover curated department-linked workspace content and `artifacts/`, not an indiscriminate whole-drive scan.
- Exclude credentials, employer-private content, personal academic records, dependencies, caches, and build output.
- Optimize search for **topic**, while retaining filename, path, project, and modified-date discovery.
- Preserve the existing **Orizuru paper/vermilion brand**.
- Daily destinations: Tasks, routine, active projects, recent artifacts, workspace search, and infrastructure Metrics.
- Recent agent-output source: **`artifacts/`**. Do not include runner transcripts or unrelated output directories.
- Search as typed; filter by type and folder; group by topic and folder; provide zoomable graph or grid, preview, full path, and copy action.
- Keep files in place. Provide exact runtime paths, refresh command, stable address, restart instructions, and a one-line explanation of each section.

## Evidence and reuse map

| Existing source | Observed behavior | Decision |
| --- | --- | --- |
| `visual-second-brain/refresh-index.py:26-95,395-498` | Scans whole workspace by default; stores absolute/relative paths, topic labels, previews, modified times; atomic JSON replacement | Tighten scope and privacy; retain schema and refresh entry point where possible |
| `visual-second-brain/visual-second-brain.html:674-879,917-974,1084-1200` | Fetches `workspace-index.json`; search/filtering, project grid, virtualized file rows, preview and copy | Extend, do not replace with a new implementation |
| `visual-second-brain/README.md:5-35` | Two runtime files plus refresh script; requires HTTP; documents obsolete workspace path and separate port 8765 | Update documentation to the dashboard-hosted route and current root |
| `dashboard-app/templates/pages/today.html:1-123` | Capture, Inbox, Next up, Quick tools, deterministic brain query and memory save | Extend Today without removing those working actions |
| `dashboard-app/templates/index.html:54-68,142-178` | Existing tab shell and versioned assets | Add one workspace-map tab; preserve current navigation and URLs |
| `dashboard-app/app.py:765-806,929-935` | `/second-brain` serves a separate RoboNuggets reference page; `/api/file` checks containment and extensions | Do not silently replace `/second-brain`; new map gets its own route |
| `artifacts/catalog.py:14-63` | Newest-first artifact scan, escaped titles, atomic HTML inbox generation | Reuse extraction logic for live recent-artifact data; do not scrape its generated HTML |
| `dashboard-app/launchd/com.cloudtransition.dashboard.plist:18-57` | Loopback :8000, RunAtLoad, KeepAlive gated by USB path, home-directory logs | Reuse launchd; do not add pm2 or another production listener |
| `CODE.md`, `CONTENT.md`, `AGENTS.md` | Department routers, artifact/sidecar contracts, curated-source rules | Follow routers to approved sources; record coverage and exclusions |

The source tree was inspected for this plan. No browser, live service, refresh script, or test suite was run during planning. Repository configuration is not proof of current service health.

Product context contains stale statements: the root product document still mentions Atmospheric Glass and one write endpoint. Current DESIGN.md describes Orizuru; current Today code also has capture and memory actions. Preserve current behavior; do not apply stale prose as a migration instruction.

## Proposed design and alternatives

**Recommended:** Extend Today as the command centre; embed the existing two-file viewer in a new Workspace map tab. This preserves the current dashboard and portable viewer, and avoids duplicate navigation/index implementations.

**Alternative:** Keep the viewer on a separate static server. This preserves portability but adds an address and service to maintain, contrary to the front-door goal.

**Rejected:** Rewrite the entire dashboard as one static HTML file. That would discard working task, capture, runner, and metrics behavior. The two-file limit applies to the portable map, not a destructive rewrite of the existing dashboard.

Use a **topic-first grouped grid**, not a force-directed graph. Grid clusters remain stable, support keyboard navigation, and make file retrieval predictable. Provide explicit density/zoom controls and folder drill-down; browser zoom remains enabled. No decorative moving nodes or invented semantic relationships.

### Page sections

1. **Today:** Preserve capture, inbox, next tasks, routine context, and existing tools.
2. **Daily shortcuts:** Six destinations from the confirmed list. Folder shortcuts open a folder-filtered browser view, not an OS command or unsupported `file://` link.
3. **Recent artifacts:** Eight newest eligible outputs, title, type, relative path, modified time, and open action; a link exposes the full artifact-filtered map. Use “Recent artifacts,” not “Agent-made,” unless provenance proves authorship.
4. **Workspace map:** Topic clusters, folder grouping/drill-down, type/folder filters, instant search, result counts, zoom controls, and details drawer.
5. **At a glance:** Open task/inbox counts from existing parsers, indexed-file count and index generation timestamp, eligible artifact count from the same artifact scan. Label configured project entries as configured, not live activity. Metrics remains a destination, not a second polling dashboard.
6. **Freshness:** Explicit index timestamp, coverage, excluded/error counts, and refresh instructions. Unsupported measurements say “Not connected” or “Unavailable,” never invented zeroes.

Desktop: compact shortcuts and counts above artifacts; the map gets a full-width panel with a details drawer. Phone: stacked sections, collapsed filter controls, full-width details with close/focus return. Maintain 44px controls, visible focus, reduced motion, and WCAG AA text contrast. Use existing tokens; no external font download is required for the viewer.

## Global constraints

- Preserve `metrics.py`, `server_activity.py`, `static/metrics.js`, Metrics polling, and metric semantics. Do not duplicate metrics collection on Today.
- Preserve task toggles, capture, memory save, skill runners, Mission Control, `/reader`, and `/second-brain`.
- No arbitrary filesystem HTTP mount, arbitrary shell/open endpoint, new write API, or public exposure.
- Read files only after canonical path containment, approved-root membership, and private-file exclusions. Never expose excluded filenames as metadata.
- Existing tailnet access makes new content reachable to existing dashboard clients. Do not broaden exposure or weaken the allowlist. Keep existing Tailscale configuration unchanged.
- No automatic refresh on every request, watcher, scheduler, embeddings, or paid model calls. Refresh remains an explicit local command.
- Preserve source files and image provenance sidecars. Never infer authorship from modification time or file location.
- Runtime portability: inline viewer HTML/CSS/JS + `workspace-index.json`; refresh utility is not a third browser dependency. Serve over local HTTP; do not promise double-click `file://` loading.
- New sections and extension seams receive concise comments, not a plugin framework.
- Update asset query versions when changing dashboard CSS/JS. No unrelated cleanup or theme migration.

## Review focus

1. Secret-looking files, private folders, symlinks, traversal, and files removed after indexing must never bypass content restrictions.
2. HTML/SVG artifacts and filenames containing markup must not execute in the dashboard origin or trigger external network requests.
3. Missing, corrupt, or stale indexes and missing USB storage must show an honest recoverable state, not an empty-success view.
4. Duplicate names, Unicode, spaces, and URL-reserved path characters must open/copy the exact intended file.
5. Large result sets, intersecting filters, keyboard focus, phone layout, and clipboard denial must remain usable.

## Task 1 — Curated, safe, reproducible index

**Modify:** `visual-second-brain/refresh-index.py`, `visual-second-brain/README.md`.
**Tests:** Add focused behavior tests under `visual-second-brain/tests/` using standard-library `unittest`, unless an existing suite is discovered at execution.
**Contract:** Retain `generated`, `workspace`, `files`, `projects`, `fileCount`, and `projectCount`; retain existing per-file fields. Add schema version, explicit coverage, and aggregate exclusion/read-error counts. Use timezone-qualified ISO timestamps. Excluded paths never appear in output.

- [ ] Follow the six department routers and resolve the exact curated source allowlist before scanning. Keep it in the existing configuration block, not a second manifest. Include eligible artifacts and image sidecars; omit generated catalog/index outputs, vendor trees, private material, and the viewer's own output.
- [ ] Change sensitive handling from “metadata only” to complete exclusion. Apply exclusions before opening files. Reject escaping symlinks; conservatively skip symlinks rather than following them.
- [ ] Preserve deterministic topic inference; use folder/title and eligible text or caption sidecars. Do not pretend binary formats have full-text previews. Show metadata and “Preview unavailable” where extraction is unsupported.
- [ ] Preserve atomic refresh; ensure a failed refresh leaves the last valid index intact and exits nonzero. Report skipped/error counts without logging sensitive paths. Do not silently publish an empty index when the source root is unavailable.
- [ ] Test inclusion/exclusion, symlink escape, private metadata omission, Unicode paths, duplicate names, deletion between scans, and replacement failure using temporary fixtures.
- [ ] Run the refresh utility on the approved real scope. Compare representative included/excluded paths and counts to actual files; record actual index size and elapsed time. Do not claim complete secret detection from filename rules.

## Task 2 — Topic-first portable viewer

**Modify:** `visual-second-brain/visual-second-brain.html` only for viewer UI.
**Consumes:** Task 1 index contract.
**Produces:** Same two-file runtime; query parameters `q`, `folder`, and `topic` initialize visible search/filter state.

- [ ] Preserve search, virtualized rows, previews, and copy behavior. Change landing clusters to topics; allow folder grouping/drill-down with breadcrumbs. Topic matches rank before preview-only matches; exact filename/path matches remain readily discoverable.
- [ ] Add true folder filtering independent of project inference. Combine search, folder, topic, and type filters with AND semantics; provide clear individual/reset actions and accurate unique-file counts.
- [ ] Add grid zoom/density controls with visible current state and reset. Keep controls and text usable at each density; do not shrink touch targets below 44px.
- [ ] Retain bounded text previews, full absolute path, relative path, and copy. Show success only after clipboard success; provide selectable-path fallback on denial. Never insert index text with `innerHTML`.
- [ ] Add loading, empty, no-results, malformed-index, unsupported-schema, and unavailable-index states. Always show generation time; do not claim the index is live. Document refresh instructions in error/help UI.
- [ ] Browser-smoke real data plus temporary fixtures: compound filters, exact paths with spaces/Unicode/#/%, duplicate names, no results, keyboard navigation, Escape/focus return, clipboard denial, zoom reset, and 200% browser zoom.
- [ ] Measure input-to-results latency with the real index and a temporary 10,000-file fixture. Target under 100ms at p95 after input processing begins on the development machine; report machine/sample conditions. Keep DOM rendering bounded rather than rendering every match.

## Task 3 — Safe dashboard hosting and artifact access

**Modify:** `dashboard-app/app.py`, `artifacts/catalog.py`.
**Create:** `dashboard-app/workspace_content.py` for reusable safe content resolution and artifact collection integration; `dashboard-app/tests/test_workspace_content.py` for consumer-visible boundaries.
**Contract:** `GET /workspace-map/` serves the existing HTML; `GET /workspace-map/workspace-index.json` serves the generated index; `GET /api/workspace/artifacts` returns current eligible artifact rows; `GET /workspace-file?path=<relativePath>` serves an eligible file preview/download. These are read-only routes.

- [ ] Extract artifact discovery from `artifacts/catalog.py` into a reusable `collect_entries(root: Path) -> list[dict]`; preserve `build(root)` and CLI output behavior. Return title, relative path, extension, bytes, and timezone-qualified modified time. Use the same discovery rules for dashboard and catalog; do not parse generated HTML or add another JSON index.
- [ ] Resolve every requested file against the current approved index and filesystem, rechecking containment and exclusions at request time. Never accept absolute paths or trust an index-supplied absolute path for serving. Missing file returns 404; denied file returns 403; unavailable/corrupt index returns 503.
- [ ] Serve only the two fixed viewer resources; do not mount the workspace or viewer directory wholesale. Prevent stale browser caching of the index.
- [ ] Provide safe artifact opening in one click. HTML/SVG must not run in the parent dashboard origin. Use a sandboxed document policy with no same-origin, popup, navigation, form, or network privileges; keep preview resources restricted to approved local paths. Offer original download separately. If an interactive artifact cannot work safely, explicitly label the restricted preview rather than granting it dashboard privileges.
- [ ] Keep standalone two-file viewer useful without these routes: previews/copy still work, while dashboard-only open actions are not shown as working links. Folder navigation remains internal filtering; no OS-launch API.
- [ ] Test traversal including encoded separators, absolute paths, symlink escape, excluded-but-indexed records, missing files, malicious names/HTML/SVG, approved local asset dependencies, and duplicate filenames. Prove with a browser fixture that artifact script cannot access the dashboard DOM or write APIs.

## Task 4 — Command-centre integration

**Modify:** `dashboard-app/templates/pages/today.html`, `dashboard-app/templates/index.html`, `dashboard-app/static/app.js`, `dashboard-app/static/style.css`, `dashboard-app/app.py`.
**Create:** `dashboard-app/templates/pages/workspace-map.html` following the existing tab/iframe pattern.

- [ ] Add Workspace map tab and route-backed iframe with a clear title and lazy loading. Keep RoboNuggets Second Brain separate; use distinct labels so reference material and file discovery are not confused.
- [ ] Extend Today with the six daily destinations, eight recent artifacts, and the truthful counts described above. Reuse existing task/routine context. A missing source affects only its own section.
- [ ] Route the routine shortcut to existing routine context or the reader, active projects to the existing Projects tab, and Metrics to the existing Metrics tab. Preserve hashes and existing landing behavior.
- [ ] Use the existing artifact scan for current recent outputs; show file modification time, not inferred creation or generation time. A new artifact appears after reloading Today without rebuilding the static artifact inbox. The map still requires explicit index refresh.
- [ ] Ensure the new map/home experience requires no internet: replace the shell's external font dependency with existing local assets or system fallbacks, without changing brand colors or layout identity. Do not claim legacy CDN-backed reference pages or remote infrastructure telemetry work offline.
- [ ] Keep capture, inbox, next tasks, quick tools, brain query/save accessible. Avoid adding a second search engine or second metrics panel. Add concise comments identifying data source and extension seam for each new section.
- [ ] Update CSS/JS version suffixes. Browser-smoke tab navigation, deep links, artifact opening, section failure isolation, task toggle/capture, and existing runner controls without launching paid agent work.

## Task 5 — Verification, documentation, and activation

- [ ] Before edits, recheck current repository guidance, changed files, route names, and service state. Use Context7 for framework/API questions during implementation. Do not treat line numbers in this plan as immutable.
- [ ] During development, run the dashboard on loopback scratch port 8011 using its existing virtual environment. Do not interrupt the launchd-owned :8000 service until the implementation is verified and rollout is authorized.
- [ ] Run focused boundary tests and the existing dashboard suite once after integration: `cd dashboard-app && venv/bin/python -m pytest tests/ -q`. Run index tests with the same interpreter and explicit unittest discovery directory. Follow current policy for obsolete implementation-only tests; do not re-pin incidental markup assertions.
- [ ] Browser verification at 390px, 768px, and 1440px: real content, no page overflow, usable 44px controls, readable contrast, keyboard-only flow, reduced motion, 200% zoom, screenshots of Today/map/detail. Block non-loopback requests and prove local discovery still works; Metrics may report unavailable.
- [ ] Test refresh end to end with a temporary approved artifact: create, refresh, search, open, remove, refresh, confirm disappearance. Remove only the fixture created for this check. Verify privacy fixtures never enter serialized JSON or HTTP responses.
- [ ] Run Impeccable's mechanical detector on changed UI targets after rendered verification; address relevant findings without unrelated redesign.
- [ ] Update `visual-second-brain/README.md`, relevant existing dashboard documentation, `CODE.md`, and `CONTENT.md`; include source allowlist, exclusions, supported previews, offline boundary, index recovery, and one-line section descriptions. Rebuild/check the curated knowledge index after documentation changes, following repository guidance.
- [ ] Inspect installed launchd configuration before changing anything. Reuse `com.cloudtransition.dashboard`; no pm2. Explain that a LaunchAgent starts after user login while the USB workspace is mounted, not before login and not with the drive missing. Restart only after approval; verify :8000 responds and new routes work.
- [ ] If a reboot/login test is not performed, explicitly say persistence configuration was checked but reboot behavior was not exercised. Do not reboot the user's machine to finish this task.

### Expected final addresses and commands

These are **planned**, not proof of currently deployed routes.

- Front door: `http://127.0.0.1:8000/#today`
- Workspace tab: `http://127.0.0.1:8000/#workspace-map`
- Portable viewer hosted by dashboard: `http://127.0.0.1:8000/workspace-map/`
- HTML: `/Volumes/SANDISK USB/work/Cloudtransition/visual-second-brain/visual-second-brain.html`
- Index: `/Volumes/SANDISK USB/work/Cloudtransition/visual-second-brain/workspace-index.json`

Refresh from any directory:

```bash
"/Volumes/SANDISK USB/work/Cloudtransition/dashboard-app/venv/bin/python" \
  "/Volumes/SANDISK USB/work/Cloudtransition/visual-second-brain/refresh-index.py"
```

Existing standalone artifact inbox refresh, only when that inbox also needs rebuilding:

```bash
"/Volumes/SANDISK USB/work/Cloudtransition/dashboard-app/venv/bin/python" \
  "/Volumes/SANDISK USB/work/Cloudtransition/artifacts/catalog.py"
```

Existing service restart, only after authorized rollout:

```bash
launchctl kickstart -k gui/$(id -u)/com.cloudtransition.dashboard
```

## Completion contract

Deliver working code, not another scaffold. Report actual addresses, paths, refresh command, section summaries, source coverage/exclusions, tested file types, test results, browser evidence, measured search performance, and any unavailable data. Keep changes limited to this upgrade. Rollback must preserve user files and concurrent edits: revert only this implementation's code changes, regenerate the prior compatible index if needed, and restart the existing service with approval. Never restore the entire workspace from a snapshot.

## Resume prompt

> Implement `docs/superpowers/plans/2026-11-02-visual-command-centre.md`. First confirm its proposed design and runtime boundary with me, then execute it against the current repository. Preserve Orizuru and all existing dashboard workflows. Upgrade the existing two-file Visual Second Brain, use topic-first curated discovery, exclude private metadata, and reuse launchd. Do not add a framework, a second production server, an AI dependency, or unsafe artifact execution. Verify the actual browser experience and report only observed results.
