# Agent workspace

An isolated workspace for Forge, its three specialist teammates, and Personal Growth Mentor. Each agent writes only inside its own directory.

| Agent | Outputs | Memory |
| --- | --- | --- |
| Forge | `workspace/agents/forge/outputs/` | `workspace/agents/forge/memory/` |
| Scout | `workspace/agents/scout/outputs/` | `workspace/agents/scout/memory/` |
| Job Reader | `workspace/agents/job-reader/outputs/` | `workspace/agents/job-reader/memory/` |
| CV Adapter | `workspace/agents/cv-adapter/outputs/` | `workspace/agents/cv-adapter/memory/` |
| Personal Growth Mentor | — | `workspace/agents/personal-growth-mentor/memory/` |

Personal Growth Mentor is independent of the Forge job-hunting pipeline. Mentor answers stay in the dashboard run output; durable notes stay in its memory directory.

Memory is on disk so it survives separate conversations and system restarts. Each `memory/` holds:

- `index.md` — the agent's current summary, read at the start of every task.
- `log.jsonl` — append-only event log, one JSON object per line.

Agents are defined in `.opencode/agents/`. Role boundaries: Forge orchestrates; Scout searches and ranks; Job Reader reads one full job description; CV Adapter builds and tailors CVs.
