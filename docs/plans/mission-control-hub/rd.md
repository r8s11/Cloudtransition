# Mission Control Hub — shared session, mailbox, orchestrator, session view

## Request (verbatim, 2026-11-16)

> wire Mission Control Hub
>
> 1. Reuse Mission as the shared session
> A Mission already supplies the goal and acceptance criteria. Its plan supplies task IDs. Runs provide execution history.
> Add only:
> - A durable agent mailbox.
> - A mission-scoped orchestrator.
> - Explicit subscriptions to run completion and new messages.
> - A dashboard projection of the resulting activity.
> Each handoff should contain:
> mission_id, task_id, in_reply_to
> from, to, type
> objective, done_when
> input_refs, output_refs
> result, evidence, decisions
> blockers, approval_needed
> Use artifact and source-file references instead of repeatedly copying complete documents into prompts.
> 2. Route through coordinators
> Roosevelt
>    ↓
> Chief of Staff
>    ├── Forge → Scout / Job Reader / CV Adapter
>    ├── Personal Growth Mentor
>    ├── Resume Tailor
>    ├── Organizational Psychologist
>    └── Coding/research specialists
> Chief of Staff owns the shared objective. Forge owns job-search execution. Neither should duplicate specialist work.
> Direct specialist-to-specialist messages should require an explicit task relationship. No broadcast messages by default.
> 3. Standardize every worker response
> Every agent finishes with:
> - Result: what it produced.
> - Evidence: files, URLs, commands, or measurements supporting it.
> - Decision: anything it decided within its authority.
> - Blocked: missing input, failed tool, or required approval.
> - Recommended receiver: who should act next, if anyone.
> The coordinator validates acceptance criteria before reporting completion. An exited process does not mean the Mission succeeded.
> 4. Preserve private memory and separate shared memory
> Keep each agent's existing private memory unchanged.
> Store shared session information separately:
> - Objective and acceptance criteria.
> - Current owner and task state.
> - Approved decisions.
> - Handoff artifacts.
> - Blockers and approvals.
> - Actual model usage and cost.
> Use Second Brain for durable knowledge retrieval. Do not turn it into the live message queue.
> 5. Add a session view, not another chat feed
> The dashboard should show:
> - One current objective.
> - Current phase and responsible agent.
> - Completed handoffs with artifact links.
> - Items waiting for you.
> - Running, blocked, and completed work.
> - Token and cost totals.
> - Pause mission and Stop all runs.
> Hide routine inter-agent messages behind an expandable audit view. Your default screen should protect attention, not display agent chatter.
> Essential guardrails
> - Maximum delegation depth and model-call budget per Mission.
> - Paid work requires approval, matching Forge's existing rule.
> - Task leases and idempotency keys prevent duplicate execution.
> - Agents cannot write another agent's private memory.
> - File ownership prevents parallel agents editing the same output.
> - Message content remains untrusted input; it cannot expand permissions.
> - Public writing, Git mutations, purchases, and irreversible actions require approval.
> - Keep mailbox APIs loopback-only. The existing tailnet dashboard must not expose unrestricted agent messaging.
> - Restart recovery must distinguish completed results from merely completed processes.
> Best first vertical slice
> Build one supervised "Prepare an application for this selected job" Mission:
> 1. You select the job and approve any paid step.
> 2. Chief of Staff assigns the Mission to Forge.
> 3. Forge coordinates the existing specialists.
> 4. Each result enters the shared handoff record.
> 5. The dashboard shows evidence, tailored-CV links, cost, and blockers.
> 6. Chief of Staff returns one concise recommendation.

## Answered questions (2026-11-16)

| Question | Answer |
| --- | --- |
| How much should the coordinators think? | Code-routed: the orchestrator follows the Mission plan and writes the assignments; Forge runs once to check the specialists' work, Chief of Staff runs once for the recommendation. About 4 model calls per Mission |
| Which models run the agents? | Free OpenCode models by default; any role can be switched to Claude per Mission, which counts as paid and waits for approval |
| Where can a Mission be controlled from? | Session view and all controls on the Mac only (`localhost:8787`); Command Center on the tailnet shows the same view read-only, plus **Pause mission** and **Stop all runs** and nothing else |
| Model-call budget per Mission | 10 |
| Maximum delegation depth | 3 |

## Assumptions (confirm at review)

- **A1 — Scope.** This RD covers the hub infrastructure the slice needs (mailbox, orchestrator, subscriptions, session view, guardrails) plus the "Prepare an application" slice. General multi-Mission orchestration beyond the slice's routing table is not in scope.
- **A2 — Missing roles.** Resume Tailor and Organizational Psychologist have no agent definition in this workspace. The routing table lists them as not installed; the slice never routes to them.
- **A3 — Workers are OpenCode agents.** The hub gains an `opencode` adapter that launches one named agent from an allow-list registry (role, coordinator, memory dir, output dir, cost class). Free OpenCode models only; a paid model on any role creates an approval and waits.
- **A4 — Handoff format.** A worker's final answer ends with one fenced `handoff` JSON block carrying result, evidence, decisions, blockers, approval_needed and recommended receiver. The orchestrator turns that block into a mailbox message; workers never post to the mailbox API themselves.
- **A5 — Subscriptions.** Subscriptions are durable rows (run completion, new message) scoped to a Mission, re-armed on restart instead of polling.
- **A6 — Stop all runs** ends every active hub run and pauses their Missions, from the Mac or the tailnet. Approving items stays Mac-only.
- **A7 — Session view reads** travel through the existing GET-only Command Center proxy, so the tailnet sees the audit view too; mailbox posting and every other write stay loopback-only.
- **A8 — Job selection.** The session starts from a tracked job picked in Mission Control on the Mac (company, role, posting URL), with an optional deep link from the Interviews row that only prefills the form.
- **A9 — Missing base CV.** If the base CV is absent, the CV tailoring task blocks with a clear message instead of silently building one.
- **A10 — Provider outage.** An unreachable model provider blocks the task with the error and waits for Roosevelt to retry or switch the model; each retry counts against the budget.
- **A11 — Plan tasks declare owner and dependsOn** (additive schema fields) so handoff routing can be checked against an explicit task relationship.

## Requirements

1. **Mailbox.** Durable messages scoped to a Mission with the full handoff field set (`mission_id`, `task_id`, `in_reply_to`, `from`, `to`, `type`, `objective`, `done_when`, `input_refs`, `output_refs`, `result`, `evidence`, `decisions`, `blockers`, `approval_needed`). Loopback-only writes. Idempotency key per message; a duplicate delivery is stored once.
2. **Orchestrator.** One per Mission, code-routed. It owns task order, leases, budget and depth; it writes assignments and validates handoffs. It never does specialist work and never advances a Mission because a process exited.
3. **Subscriptions.** Durable, mission-scoped subscriptions to run completion and new mailbox messages, re-armed after restart.
4. **Session view.** One screen per Mission: objective, phase and responsible agent, completed handoffs with artifact links, items waiting for Roosevelt, running/blocked/completed work, token and cost totals, Pause mission and Stop all runs. Routine inter-agent messages live behind an expandable audit view.
5. **Coordinator routing.** Roosevelt → Chief of Staff → Forge → specialists, per the routing table; specialist-to-specialist messages require an explicit task relationship; no broadcasts.
6. **Worker response contract.** Every worker finishes with result, evidence, decision, blocked, recommended receiver; the coordinator validates acceptance criteria before reporting completion.
7. **Shared vs private memory.** Agent private memories stay untouched; shared session state (objective, owner, task state, approved decisions, handoffs, blockers, approvals, usage) lives in the hub database. Second Brain stays a retrieval store, never the queue.
8. **Guardrails.** Budget 10 model calls and depth 3 per Mission; paid work needs approval; leases and idempotency keys prevent duplicate execution; a worker cannot write another agent's private memory or an output it does not own; message content cannot expand permissions; public writing, Git mutations, purchases and irreversible actions need approval; mailbox writes loopback-only; restart recovery separates accepted results from exited processes.
9. **Slice.** "Prepare an application for this selected job": select job and approve any paid step; Chief of Staff assigns to Forge; Forge coordinates Job Reader and CV Adapter; every result enters the handoff record; the session view shows evidence, tailored-CV links, cost and blockers; Chief of Staff returns one concise recommendation.
