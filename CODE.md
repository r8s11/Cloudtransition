# Code Index

Applications, scripts and tooling. Pointers only: each project's README or plan holds the detail.

## Active projects

| Project | Location | What |
| --- | --- | --- |
| Dashboard (Command Center) | `dashboard-app/` | FastAPI + Jinja2 at `127.0.0.1:8000`. **Read [`dashboard-app/CLAUDE.md`](dashboard-app/CLAUDE.md) first** (file map, data sources, recipes) |
| Dashboard references | `dashboard-app/` | [README](dashboard-app/README.md), [`DESIGN.md`](dashboard-app/DESIGN.md), [browser contract](dashboard-app/static/README.md), [weekly report logic](dashboard-app/core/work_search.py), [weekly report controller](dashboard-app/static/work-search.js), [drift report](dashboard-app/docs/2026-11-12_DRIFT_REPORT.md), [agent registry](dashboard-app/docs/agent-registry.md) (definition folders, loader rules, memory writer and exposure), `scripts/screenshot.sh`, `tests/` |
| Agentic OS | `agentic-os/` | TypeScript/Bun mission-control monorepo (`apps/`, `packages/`); API on `127.0.0.1:8787` via `agentic-os/launchd/`; this workspace is its project `Cloudtransition`. See `agentic-os/README.md`. Mission Control Hub (mailbox, orchestrator, session view, first application slice): [evals in review, not built](docs/plans/mission-control-hub/) |
| Deterministic Second Brain | `second-brain/` | Stdlib Python retrieval and memory store (`brain.py`). See `second-brain/README.md`; [global OMP adapter](tools/second-brain-memory/README.md) and [approved integration evals](docs/plans/omp-global-second-brain/) |
| Visual Second Brain | `visual-second-brain/` | Workspace map with Atlas and dark/Paper Graph views at `/workspace-map/?view=graph`; `refresh-index.py` rebuilds its index. See its `README.md` and `DESIGN.md` |
| ARMS Review | `tools/arms/` | Loopback review app (`127.0.0.1:8790`), parked feedback, routine reports, clipper. See `tools/arms/README.md` |
| Artifact inbox | `artifacts/` | HTML brand book, sources and exports; `catalog.py` builds `index.html` |
| Personal knowledge base | [`KB-README.md`](KB-README.md) | Private Gmail/Claude search (`kb.py`) and scheduled ingestion (`ingest_all.py`) |
| Checklist items in Calendar | [`CALENDAR-README.md`](CALENDAR-README.md) | `calendar_cli.py` publishes dated Google Tasks from `TASKS.md` |
| Metrics charts | `dashboard-app/collectors/metric_charts.py`, `dashboard-app/static/metrics.js` | Metrics tab graphs |
| Job autofill | `job-autofill/` | MV3 Chrome extension plus local helper. See `job-autofill/README.md` and its [plan and evals](docs/plans/job-autofill-extension/). Agents tab (tracker, Job Reader, CV Adapter, Scout leads, local email lookup): [evals in review, not built](docs/plans/extension-agents/) |
| Jev routing | [`tools/jev-routing/`](tools/jev-routing/README.md) | Omp extension: `/jev on` and `/jev skills on`; opt-in optional-skill adapters for Claude Code, Codex, Gemini CLI, OpenCode and pi (not installed globally) |
| Global OMP memory | [`tools/second-brain-memory/`](tools/second-brain-memory/README.md) | Default-profile CLI-backed recall/save, fixed shared root, native-memory cutover and rollback |
| Button Runner | `button-runner/` | Standalone headless Claude skill buttons |
| Brain home base | `bot/` | OpenCode V2 personal assistant (brain + workspace agents), phone pairing via `start.sh` on tailnet :8443. Live dashboard read access: [evals in review, not built](docs/plans/bot-dashboard-access/) |
| RoboNuggets reference | `robonugget-second-brain-app/` | Static page; open `index.html` directly (the dashboard does not serve it) |
| Pomodoro timer | `orca-plugins/pomodoro-timer/` | Orca desktop plugin. See its README |

## Scripts and smaller projects

| Path | What |
| --- | --- |
| `Python/` | `devops/`, `security/recon/`, `webscraper/`, `fb.py` |
| `React/tictac/`, `powershell/` | Practice app; PowerShell scripts |
| `projects/` | `project1-asset-management`, `project2-infrastructure`, `project3-portfolio`, `ReactNative/Mytvapp`, `week1-task-manager`, `rendercv` |
| `archive/dashboard.html` | Superseded single-file dashboard prototype |

## Design and build docs

| Path | What |
| --- | --- |
| `docs/briefs/` | Dashboard invariants and Workspace map briefs |
| `docs/superpowers/` | Mission Control and Second Brain specs and plans |
| `docs/plans/<feature>/` | Feature requirements, design notes and supporting evidence |
| Dashboard features | `docs/plans/command-center-shortcuts/`, `codex-runs/`, `metrics-charts/`, `visual-second-brain-overdrive/`, `workspace-graph/` (Graph design/evals), `workspace-map-motion/` (pointer/scene motion), `workspace-depth-constellation/` (3D renderer, fallback and lifecycle contract), `workspace-opening-fold/` (Atlas cover and local GSAP handoffs), `workspace-3d-observatory/` (approved 3D-only composition, materials, labels and entrance), `dashboard-interview-recon-and-agents/`, `interview-waiting-status/` (Waiting status card and grouped Update application panel) |
| Dashboard Google Calendar | [`docs/plans/dashboard-google-calendar/`](docs/plans/dashboard-google-calendar/rd.md): approved agenda and automatic dated Tasks/timed events; `calendar_bridge.py`, `dashboard-app/core/google_calendar.py`, `core/calendar_sources.py`, Calendar UI and [setup guide](CALENDAR-README.md). Default off; separate consent and reviewed policy required. |
| Other features | `docs/plans/checklist-calendar/`, `personal-knowledge-base/`, `jev-command/`, `jev-skill-routing/`, `job-autofill-extension/`, `job-application-submission-loop/` |
| `docs/plans/2026-11-*.md` | Dated plans: Command Center refinement, Second Brain improvements, Agentic OS and ARMS additions, agent suggestions |
| `docs/plans/2026-10-28-*.md`, `2026-03-19-consulting-*.md` | Memory and ARMS research; consulting business plans |

## Tooling and config

| Path | What |
| --- | --- |
| `.claude/` | Claude Code config, skills, agents, hooks |
| `.opencode/agents/` | OpenCode agents: Forge, Scout, Job Reader, CV Adapter, and six subagents synced from `.claude/agents/` |
| `workspace/agents/` | Per-agent outputs and memory for the job-hunting team. See its README |
| `opencode.json`, `netlify.toml` | OpenCode and Netlify configuration |
| `skills/skills-inventory.yml` | Skill inventory, including AI coding tools (OpenAI Codex models; proficiency unassessed) |
| `AGENTS.md` | Canonical department map, memory/search workflow and graph guidance |

Generated and vendored paths are not indexed.

## Related

- Artifact sources, brand book, image captions and generation prompts → [CONTENT.md](CONTENT.md).
