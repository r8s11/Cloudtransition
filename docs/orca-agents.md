# Orca bots → dashboard agents

The Orca bots Forge, Scout, Job Reader and CV Adapter are the same OpenCode agents the dashboard runs. Do not call `opencode run --agent …` directly from a bot and do not copy the agent files.

## One source of truth

| What | Where |
| --- | --- |
| Definitions | `~/.config/opencode/agents/{forge,scout,job-reader,cv-adapter}.md`. The workspace `.opencode/agents/<id>.md` (untracked, main checkout) is byte-identical; the dashboard hashes it and refuses to launch if OpenCode resolves different instructions (`_verify_opencode_agent`, `dashboard-app/routes/runs.py`). |
| Run gates | `SKILL_RUNNERS` in `dashboard-app/core/config.py`: card id, prompt, input pattern, OpenCode-only provider |
| Runner | `POST /api/skills/run` → `_resolve_run` → `_execute_run` in `dashboard-app/routes/runs.py` |
| Memory and outputs | `workspace/agents/<id>/memory/{index.md,log.jsonl}` and `workspace/agents/<id>/outputs/` |
| Run record | Run tab and `GET /api/skills/runs` (in memory until a server restart), `runs.log`, `dashboard-app/runs/<run id>.txt` |

## Entry point

```sh
DASH="/Volumes/SANDISK USB/work/Cloudtransition/dashboard-app"
"$DASH/venv/bin/python" "$DASH/scripts/agent_run.py" <agent> [args] [--wait]
```

`scripts/agent_run.py` runs nothing itself. It reads the dashboard's OpenCode catalogue (free models only), picks the first model, and posts the card id and input to `POST /api/skills/run` on `127.0.0.1:8000` with the CSRF header. The dashboard then applies every gate it applies to a button press. The command prints the run id and returns. Add `--wait` to poll every 10 s until the run ends; the command then exits 1 if the run failed. If the dashboard is down or refuses, the command prints the reason and exits non-zero, and nothing runs.

Raw HTTP equivalent (for example `<model>` = `opencode-go/beam-free`, from `GET /api/skills/catalog` → `provider_models.opencode`):

```sh
curl -s -X POST http://127.0.0.1:8000/api/skills/run \
  -H 'X-Requested-With: XMLHttpRequest' -H 'Content-Type: application/json' \
  -d '{"skill":"scout-scan","model":"opencode:<model>"}'
```

## Per agent

| Agent | Command | Card | Input | Results land in | Unattended? |
| --- | --- | --- | --- | --- | --- |
| Scout | `agent_run.py scout` | `scout-scan` | none | `workspace/agents/scout/outputs/scan-<today>.{json,md}`; Scout updates its own `memory/index.md` and `log.jsonl` | Yes. Free search-and-rank, reads no full postings |
| Job Reader | `agent_run.py job-reader <job-id> <url>` | `job-reader` | job id (`^[a-z0-9][a-z0-9-]{0,79}$`) and one http(s) URL | The agent writes only `staging/<run id>/`. The dashboard validates it, publishes `workspace/agents/job-reader/outputs/<job id>.json` atomically, appends `jd_read` or `jd_read_failed` to `memory/log.jsonl`, and deletes the staging folder | **No.** Only for one job Roosevelt picked |
| CV Adapter (base) | `agent_run.py cv-adapter base` | `cv-base` | none | `workspace/agents/cv-adapter/outputs/base-cv.json`, memory event | **No.** Rebuilds the base CV that every tailoring depends on. Run only when `resume/master.md` changed |
| CV Adapter (tailor) | `agent_run.py cv-adapter tailor <job-id>` | `cv-tailor` | job id; needs `base-cv.json` and that job's Job Reader output | `workspace/agents/cv-adapter/outputs/tailored-<job id>.{json,md}`, memory event | **No.** Only for one job Roosevelt picked |
| Forge | `agent_run.py forge` refuses | none | — | — | Forge coordinates; it has no dashboard card. Running it directly through OpenCode would bypass the gates and the run record, so the wrapper refuses |

## Gates

- **Job id required.** Job Reader and CV tailoring refuse without a job id at three levels. The wrapper's argument parser exits 2 before any call. The server returns 400 "… is required" or "Not a valid …" and starts nothing. Job Reader's OpenCode rules allow edits only under its `staging/` folder.
- **Cost.** All four agents are `costClass: free` in `agentic-os/config/agentic-os.yaml`. The dashboard lists only OpenCode models whose id ends in `-free`, so no paid model can be selected. The "paid" step is the run for one picked job, which needs Roosevelt's choice, not money. The dashboard has no confirmation step or spending cap. Treat a Job Reader or tailor run as user-initiated only.
- **One run per agent.** A second run for the same agent, or for the same card, gets 409 while one is running. `cv-base` and `cv-tailor` share the agent and cannot overlap.
- **Definition check.** Every run hashes `.opencode/agents/<id>.md` and compares it with OpenCode's resolved agent before launch. A mismatch fails the run and launches nothing.

## Never run unattended

- `job-reader` and `cv-adapter tailor`: only after Roosevelt names the job.
- `cv-adapter base`: only after `resume/master.md` changed and Roosevelt asked.
- Never call `opencode run --agent <id>` directly. That skips staging, publishing, the memory writer and the run record.
- Never write `workspace/agents/*/memory/` from another machine. The Mac is the single writer; see `dashboard-app/docs/agent-registry.md`.

## Verified

2026-11-19: `agent_run.py job-reader` with no arguments exited 2 and made no call; with a bad URL, the dashboard returned 400 and recorded no run. `agent_run.py scout` started run `bcabea63b9f342d0b39c68f70a176f09` (`opencode-go/beam-free`), which appeared in `/api/skills/runs` and on the Run tab. `dashboard-app/tests/test_agent_run.py` covers the mapping and both refusals without a model call.
