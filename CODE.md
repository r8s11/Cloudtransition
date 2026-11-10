# Code Index

Applications, the monorepo, scripts, and tooling configuration.

## Active Projects

| Project | Location | Stack / Purpose |
| --- | --- | --- |
| Dashboard | `dashboard-app/` | FastAPI + Jinja2 + Tailwind. Renders workspace `.md`/`.yml` live. **Read `dashboard-app/CLAUDE.md` first** |
| Agentic OS | `agentic-os/` | TypeScript/Bun monorepo — API, CLI, runtime, storage, policy, memory. See `agentic-os/README.md` |
| Button Runner | `button-runner/` | Standalone headless Claude skill buttons |
| Second Brain | `robonugget-second-brain-app/` | Static reference page, served by the dashboard |
| Deterministic Second Brain | `second-brain/` | Standard-library Python retrieval, atomic memory storage, catalogue checks and benchmarks |
| Visual Second Brain | `visual-second-brain/` | Topic-first workspace map (curated, privacy-filtered snapshot index). Served by the dashboard at `/workspace-map/` and the **Workspace map** tab. See `visual-second-brain/README.md` |
| ARMS Review | `tools/arms/` | Loopback review app, parked feedback, passive routine reports and browser clipper |
| Artifact inbox | `artifacts/` | HTML brand book, editable sources, exports and searchable generated index |
| Personal knowledge base | [`KB-README.md`](KB-README.md) | Private Gmail/Claude SQLite FTS5 search (`kb.py`), raw-only scheduled ingestion (`ingest_all.py`); [approved requirements, eval and implementation plan](docs/plans/personal-knowledge-base/) |
| Checklist items in Calendar | [`CALENDAR-README.md`](CALENDAR-README.md) | `calendar_cli.py` lists/previews selected `TASKS.md` items and explicitly publishes dated Google Tasks (shown on the Calendar day; time-of-day not settable via API) with a separate Tasks token, exact-batch approval and private recovery state; [approved requirements/eval](docs/plans/checklist-calendar/), verified against the real account |
| Metrics graphs and charts | `dashboard-app/metric_charts.py`, `static/metrics.js` | Metrics tab charts: host capacity bars + sparklines, network/disk I/O history, storage bars, ranked workloads, probe timeline, log volume by severity; `/api/metrics/rates?window=1h\|6h\|24h`. [Approved requirements, eval and mockup](docs/plans/metrics-charts/) |

### Dashboard entry points

| Path | What |
| --- | --- |
| `dashboard-app/app.py` | All backend: `REALMS`, parsers, `build_context()`, routes, skill runner |
| `dashboard-app/templates/pages/` | One file per tab |
| `dashboard-app/static/style.css` | Orizuru design system; design tokens live at the top |
| `dashboard-app/tests/` | Design-contract regression tests |
| `dashboard-app/screenshot.sh` | Headless review screenshots at exact desktop/phone viewport widths; checks the live server and writes gitignored `runs/shots/` images |
| `dashboard-app/workspace_content.py` | Read-only workspace file access (`/workspace-file/…`) and live artifact list for Today; reuses `refresh-index.py` scope/privacy rules |
| `dashboard-app/agents.py` | Read-only Forge agent roster, memory/events and latest Scout scan loader for the Agents tab |
| `dashboard-app/static/fonts/` | Self-hosted Inter and JetBrains Mono (OFL) so the dashboard needs no internet |
| `dashboard-app/DESIGN.md` | Visual rationale — read before styling work |

### Orca plugins

| Path | Purpose |
| --- | --- |
| `orca-plugins/pomodoro-timer/` | Pomodoro timer for the Orca desktop app: sidebar panel, palette commands, end-of-phase notifications. See its README |

### Agentic OS entry points

`agentic-os/apps/` holds `api` and `cli`. `agentic-os/packages/` holds `core`, `runtime`, `storage`, `policy`, `memory`, `config`, `connectors`.

## Scripts & Smaller Projects

| Path | What |
| --- | --- |
| `Python/` | `devops/`, `security/recon/`, `webscraper/`, `fb.py` |
| `React/tictac/`, `powershell/` | Practice app; PowerShell scripts |
| `projects/` | `project1-asset-management`, `project2-infrastructure`, `project3-portfolio`, `ReactNative/Mytvapp`, `week1-task-manager`, `rendercv` |
| `archive/dashboard.html` | Superseded single-file dashboard prototype |

## Design & Build Docs

| Path | What |
| --- | --- |
| `docs/briefs/` | `orizuru-build-plan.md` (dashboard invariants), `dashboard.brief.md` |
| `docs/superpowers/` | Mission Control / Second Brain specs and plans |
| `docs/plans/2026-11-09-second-brain-improvements.md` | Second Brain gaps closed on 2026-11-09 (self-healing index, supersede, recency, duration intent) and what is still open |
| `docs/plans/2026-11-09-agentic-os-arms.md` | Agentic OS additions from the ARMS guides (skill buttons, model/effort, run cost view, artifacts panel), open items, level status deltas |
| `docs/plans/codex-runs/` | Review proposal: Codex execution choices for configurable Run cards, provider-specific effort, retained permission boundaries; requirements, acceptance evals and HTML mockup. Not implemented. |

## Tooling & Config

| Path | What |
| --- | --- |
| `.claude/` | Claude Code config, skills, agents, hooks |
| `.opencode/agents/` | Persistent OpenCode agent definitions — Forge orchestrator plus Scout, Job Reader, and CV Adapter specialists |
| `workspace/agents/` | Isolated per-agent outputs and on-disk memory for the job-hunting team. See its README |
| `opencode.json`, `netlify.toml` | OpenCode and Netlify configuration |
| OpenAI Codex models | AI coding tools recorded in `skills/skills-inventory.yml` under Tools & Frameworks; selected through the Codex client/model picker. Proficiency and years are unassessed; no account entitlement or fixed model roster is assumed. |
| `AGENTS.md` | Canonical department map, memory/search workflow and graph guidance |

Generated and vendored paths are not indexed.

## Related

- Artifact sources, brand book, image captions and generation prompts → [CONTENT.md](CONTENT.md).
