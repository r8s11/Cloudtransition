# Agent suggestions (2026-11-09)

Suggested improvements for the agents in this workspace: the Forge job-hunting team (`.opencode/agents/`, state in `workspace/agents/`), the dashboard runners (`dashboard-app/app.py`, `SKILL_RUNNERS`) and the agentic-os runtime. Each item says what was observed, what to change and what it needs. Nothing here is built; pick items and ask for them.

Related: `docs/plans/2026-11-09-agentic-os-arms.md` (agentic-os open items), `docs/plans/2026-11-09-second-brain-improvements.md`.

## State on 2026-11-09

- Scout has run once (`workspace/agents/scout/outputs/scan-2026-11-09.*`). Forge, Job Reader and CV Adapter have empty `outputs/` folders.
- The Interviews tab now has an Agents card: Scout leads with **Add to tracker**, and runner cards for Scout, Job Reader, base CV and tailored CV. Row buttons fill a card; the card's Run button starts the agent.
- The three new runners were tested for validation, allowlisting and prompt assembly. **No live Job Reader or CV Adapter run was made**: a run fetches an outside page and writes files, and was not asked for.

## Do first

1. **One real pass through the pipeline.** Pick one tracker row with a `job_url`. Run *Read a posting*, then *Build base CV*, then *Tailor CV to a job*. Check three things: the JSON has the five expected keys, the Interviews row switches from **Read posting** to **Tailor CV** to **Tailored CV**, and the tailored CV contains no fact that `resume/master.md` lacks. Fix prompts in `SKILL_RUNNERS` from what the run shows. Cost: free OpenCode model; about 15 minutes.
2. **Check the tailored CV by code, not by eye.** CV Adapter's rule is "only facts from the base CV". Add a small check that lists every number, employer and certification in `tailored-<job id>.json` that does not occur in `base-cv.json`, and show the list next to the **Tailored CV** button. Plain string comparison, no model. This is the one place where an agent error reaches an employer.
3. **Write output file names into the agent definitions.** `.opencode/agents/job-reader.md` and `cv-adapter.md` name no file paths; only the dashboard prompts do (`<job id>.json`, `base-cv.json`, `tailored-<job id>.*`). A run started from the terminal or by Forge would pick its own names and the dashboard would not find the result. Add the three paths to the definitions.

## Worth doing next

4. **Keep Scout's job id on the tracker row.** The scan gives each job a `job_id` (for example `blackrock-technical-support-associate-nyc`). The dashboard derives a different id from company and role. **Add to tracker** could store the Scout id in a `scout_job_id:` field, so the scan's rationale and score stay linked to the application. Needs one optional field in `interview_editor.add_application`.
5. **Feed Job Reader output into the lead second opinion.** `leads_jev.py` judges each `requirements:` line of a tracker row against the resume; only 8 rows have that field, typed by hand. Job Reader's `required_skills` is the same data. Offer a button that copies the extracted list into `requirements:` (through `interview_editor`, shown before saving). Jev calls cost money and send text out: keep the existing permission rule.
6. **A Forge runner for the whole chain.** Forge orchestrates but has no card. A `forge-pipeline` card with a job id and URL could run read, then tailor, in one go. Do this only after item 1 shows each step is reliable alone; a chain hides which step failed.
7. **Scan age on the leads list.** Leads come from the latest scan whatever its date. Show the scan date beside the heading and mark it stale after 7 days, from `generated_at`.
8. **Interview prep agent.** The tab has `interview_questions` and `interview_preparation` fields, filled by hand. A fifth specialist could draft both from the Job Reader output and `interviews/interview-prep-star.md`, writing to its own `outputs/` folder; the dashboard would offer the draft for copying, never write it into the tracker itself.

## Runners and cost

9. **Record usage for dashboard runs.** `runs.log` keeps command, status and duration, not tokens. agentic-os now stores tokens and cost per run but only for runs it starts. Either start Claude runs with `--output-format json` in the dashboard too and log the usage, or move model runs to agentic-os and let the dashboard link to its Usage panel. One place for cost is better than two.
10. **Retire `button-runner/`.** `tools/arms/README.md` records it as broken (it posts to a removed proxy and holds a credential-like literal). agentic-os skill buttons and the dashboard Run tab cover its job. Remove the literal first, then archive the folder and update `CODE.md`.
11. **Per-run budget.** See agentic-os plan, open item 2 (`--max-budget-usd` from a fixed list).
12. **Verify the Claude usage report.** See agentic-os plan, open item 1.

## Agent hygiene

13. **Memory files grow without bound.** Each agent appends to `memory/log.jsonl` and reads it "before assuming something is new". Cap what is read (last 200 lines) in the prompt, or rotate the log monthly.
14. **Treat fetched pages as data.** The Job Reader prompt now says so. Add the same sentence to Scout's definition: it reads search results from outside sources.
15. **One test per agent contract.** `tests/test_agents.py` covers reading the roster and scan. Add a fixture scan, reading and tailored CV, so a change in an agent's output shape fails a test instead of showing an empty card.

## Not suggested

- Automatic runs on a schedule for Job Reader or CV Adapter: each needs a human choice of job.
- Letting an agent write `interviews/job-applications.yml`: all tracker writes stay in `interview_editor.py`.
- Automatic model routing through Jev: needs a key, money and outside data transfer; see agentic-os plan, open item 4.
