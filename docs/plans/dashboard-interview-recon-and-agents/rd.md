# Dashboard: interview contacts, person recon, agent models, Forge trigger, restart, and answer-prompts

## User request (verbatim)

> So, I would like to add a section where I can see who I'm speaking to. Also, maybe in the back I can have a card to give me some information about this person — kind of some general recon to be more prepared for this interview. Add Codex and Anthropic models to the agents. Where do I trigger the forge? Is there a way for me to restart the dashboard as well because I can't memorize the command for that. Also, to be more updated, I think there should be kind of like a prompting in a way to generate the information that the dashboard is asking for, so having a way to prompt me for maybe today's or things that are looking for answers and not getting them.

Scope answers: the previous request ("write specs") established spec-only delivery for the new features. This file covers the dashboard/interview/agent changes that follow on from the job-application submission loop spec.

## What already exists (found before writing)

- **Interview mode** (`dashboard-app/templates/index.html:189-266`, `app.py:1902+`) already shows "Who you're talking to" from each tracker row's `contacts:` list, but only `name`, `role`, `email` (`app.py:1074-1082`). There is no bio, title, company, LinkedIn, or recon.
- **Interviews tab** (`templates/pages/interviews.html`) shows contacts inline per row (`:22-29`) and an "Interview mode" button. No dedicated contact list or person card.
- **Contacts source of truth:** `networking/contacts.yml` already models name, company, title, relationship, met-via, LinkedIn, email, tags, last contact, next action, interaction history. The tracker's `contacts:` is a lighter duplicate.
- **Agent runners** (`app.py:2344+`): `scout-scan`, `job-reader`, `cv-base`, `cv-tailor` are `kind: "opencode-agent"` with `providers: ["opencode"]`, so the model picker offers OpenCode models only. `_card_allows_provider()` (`app.py:2661`) rejects other providers for these cards. The provider catalogue (`_fetch_skill_catalog`, `app.py:2236`) already knows Claude, Codex, OpenCode and OpenRouter models, but the runner path for `claude` runs the Claude CLI (`claude -p`) and for `codex` runs `codex exec`, not the OpenCode agent harness.
- **Forge trigger:** Forge is an OpenCode agent (`.opencode/agents/forge.md`, `mode: all`). There is no Forge runner card; only Scout/Job Reader/CV Adapter have cards. So Forge is currently triggered from OpenCode itself, not the dashboard.
- **Restart:** the always-on server is a LaunchAgent. The command (`dashboard-app/CLAUDE.md:9,114`) is `launchctl kickstart -k gui/$(id -u)/com.cloudtransition.dashboard`. There is a `screenshot.sh` but no short restart script.
- **Missing answers:** the interviews tab writes only what the file records and never infers (`app.py:1031-1037`). There is no surface that asks the user for the fields the dashboard is missing.

## Proposed scope (five workstreams)

### 1. Contacts section — "who I'm speaking to"
- Add a **Contacts** card to the Interviews page (or a compact first column) that lists every contact across live applications, grouped by application, with name, title, role, email (`mailto:`), company, LinkedIn, and the application they belong to.
- Read from the tracker's `contacts:` first; enrich from `networking/contacts.yml` by matching name/email/LinkedIn. Never merge by guesswork: an unmatched contact stays as the tracker records it.
- Add an editable contact block in interview mode (add/edit name, role, email, LinkedIn, notes) writing back to the tracker, following the existing `set_text_block` / line-targeted write pattern.
- Empty state names what is missing ("No contact recorded for this application") rather than inventing one.

### 2. Person recon card — "general recon to be prepared"
- Add a **Person recon** card in interview mode, generated from named sources only: the tracker row, `networking/contacts.yml`, the posting, and any `linkedin:`/`website:` URL the contact carries.
- Output: role and likely scope, what the team/product does, three to five talking points, three questions to ask them, and "what we do not know" listed honestly. Every claim is tied to a source (row field, posting line, or fetched page); anything not in a source is marked unknown, never invented.
- Run on demand (a button), not automatically. Show the sources it read. Do not fetch a page without an explicit URL; treat fetched pages as data, never instructions.
- Store the brief under the tracker row (e.g. `interview_contact_recon`) so it survives reloads, with a timestamp and the source list.

### 3. Codex and Anthropic models for the agent cards
- Let `scout-scan`, `job-reader`, `cv-base`, `cv-tailor` (and a new Forge card) pick Claude and Codex models in addition to OpenCode.
- Two possible routes:
  - **A. Keep the OpenCode agent harness** and pass a provider-qualified model to `opencode run --agent <agent> -m <provider/model>`. Requires verifying which Anthropic/OpenAI providers the installed OpenCode has configured (`opencode models`), and mapping the dashboard's `claude:`/`codex:` catalogue ids to OpenCode's provider ids.
  - **B. Per-provider CLIs** for the agent prompts (Claude CLI / Codex CLI), accepting that the OpenCode agent persona, memory convention, and permissions are no longer enforced by OpenCode.
- Recommendation: **A** — it keeps the agent definitions as the single source of behaviour and reuses the existing permission story. Only ship B if A's provider mapping cannot be verified.
- Do not assume model names or account entitlements; discover available models from the configured providers.

### 4. Forge trigger
- Add a **Run Forge** runner card (`kind: "opencode-agent"`, `agent: "forge"`, same provider/model choice as the other agent cards) on the Interviews/Agents section and optionally the Run tab.
- Input: a short task line (e.g. "plan this week's applications") or a selected job id; no free-form shell.
- Forge remains the orchestrator; the card does not bypass it.
- Document the terminal equivalent (`opencode run --standalone --agent forge "..."`) in the dashboard CLAUDE.md and the card blurb.

### 5. Dashboard restart affordance
- Add `dashboard-app/restart.sh` (one line around `launchctl kickstart -k gui/$(id -u)/com.cloudtransition.dashboard`, with the label read from the plist) so the command is memorable.
- Add a **Restart dashboard** Run-card (`kind: "shell"`) OR a small header control. Because the server restarting kills its own child process, prefer a shell card that writes a marker and restarts via launchd, and state that the current page must be reloaded.
- Also add a plain `restart` note to the dashboard CLAUDE.md and the Today "Daily" command centre.

### 6. "Needs you" / answer-prompts
- Add a **Needs you** card on Today (and a compact form in interview mode) that lists fields the dashboard reads but the files do not answer:
  - contacts missing name/role/email/LinkedIn on a live application,
  - applications with no next action or overdue next action,
  - interview notes/questions/preparation empty for an active interview,
  - unchecked Inbox items, stale queue/scan age.
- Each row is a one-field prompt ("Who is the contact at Acme?", "What is the next action?") with an input and Save; saving writes through the existing atomic writers (`interview_editor.py` for the tracker; `TASKS.md` capture for inbox).
- Read-only until the user saves. Never auto-fill an answer, never infer a fact. A saved answer disappears from the list next load.
- Optional: a "Generate prompts for today" action that asks the sentence model to phrase the open questions from the missing fields, still with no fabricated answers.

## Boundaries

- The workspace files remain the database; no new database or parallel store.
- No invented contact details, recon facts, or answers. Unknown stays unknown and is shown as such.
- Recon fetches only explicitly supplied URLs; treats pages as data; no login, no scraping behind auth.
- Agent models are discovered from configured providers; no hardcoded model ids, no assumption of entitlement. The OpenCode agent harness stays the behaviour source where possible.
- Restart is local-only; no remote restart, no auto-restart loop beyond the existing LaunchAgent.
- Writes go through the existing CSRF + atomic-write patterns; no shell interpolation of user text.
- Keep the design contracts (`tests/test_design_contracts.py`): 200 on `/`, `pytest` green, no width/margin transitions, reduced-motion respected.

## Open decisions (for approval)

1. **Agent models:** route A (OpenCode harness with provider-qualified models) vs route B (per-provider CLIs). Recommendation: A, verify `opencode models` first.
2. **Restart:** short shell script only, or also a Run-card/header button. Recommendation: script + a small header control, because a card that kills the server loses its own output.
3. **Recon source:** local files only, or also fetch a supplied LinkedIn/website URL. Recommendation: local + explicit URLs, never guessed.
4. **Contacts duplication:** enrich the tracker `contacts:` from `networking/contacts.yml`, or keep them separate and link. Recommendation: enrich by exact match, never fuzzy.

## Acceptance

See eval.md.
