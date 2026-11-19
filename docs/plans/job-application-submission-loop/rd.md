# Job application submission loop

## User request (verbatim)

> https://github.com/qbeka/jev-job-search/blob/main/README.md what feature can be added to my exisiting app

Scope answers (from follow-up):
- Target app: the job-hunting agent system (Forge / Scout / Job Reader / CV Adapter), which already covers discovery → reading → CV tailoring but stops before sending.
- Feature drawn from jev-job-search: the `/apply` loop — open form in its own browser tab, map fields with a typed decision model, fill with real input events, write open questions, read every value back, walk multi-page forms, submit only when all wanted values are present and the user asked, record to CSV, leave blocked forms open with a resume path.
- Deliverable requested: write specs (this file). No implementation yet.

## Approved scope

Add an application submission loop to the job-hunting agent system that takes a job already read and (optionally) tailored, drives its application form in an isolated browser profile, verifies every value on the page before sending, records outcomes to plain CSV, and leaves forms it cannot finish truthfully open for the user with a resume path.

Invariants carried over from jev-job-search's "What the tool will not do":
- Never change facts to suit a job (work authorization, education, dates come from the profile).
- Never invent facts; written answers are refused if they name a number/tool/company the profile does not hold.
- Never send a form it has not checked (every answer read back first).
- Never send unless the user asked (`--submit` / explicit approval).
- Never sign, pick interview slots, pass "prove you are human" checks, or read email beyond one verification email.
- Never create an account or sign in unless the user set it up.
- A required question the profile cannot answer holds the form.

## Existing behavior to preserve

- Scout discovers and scores jobs; Job Reader extracts structured job data; CV Adapter tailors resume/cover from profile facts; Forge orchestrates and reports. None of these are replaced.
- Records already live in `workspace/agents/` and the dashboard renders workspace files; new CSV records must remain plain, fixed-column, top-of-project readable, consistent with the repo's "every record is a plain CSV" convention.
- Agentic OS storage/policy/runtime packages own persistence, policy, and run orchestration; the loop should reuse them rather than invent a parallel store.
- Browser access: prefer the existing browser tooling; jev-job-search uses Chrome over the DevTools protocol with its own profile and no browser library. Reuse that approach only if no equivalent exists in the repo; otherwise extend the responsible layer.

## Components

1. **Form reader (in-page)** — read every control on the page: labels, options, required flags, which file box wants which file. Captured once per form/page.
2. **Field mapper (typed decision)** — one call decides which profile detail goes in each box, which option is true, which boxes stay empty. Unchanged forms reuse the mapping. Reuse the JEV typed-decision pattern already specced in `docs/plans/jev-command/` and `docs/plans/jev-skill-routing/` rather than a free-text LLM pick.
3. **Filler** — real input events, one control at a time on boards that save as you type; open-and-click dropdowns; turn calendars to month/day; put the resume only in the resume box.
4. **Writer** — open questions and low-confidence fields go to the sentence writer with profile facts, drafts (bank), and voice guide; answers are remembered and invalidated when profile/drafts/voice change. Reuse the answer-memory pattern from jev-job-search.
5. **Read-back verifier** — re-read every value from the page; a mismatch fails the fill and holds the form; an optional box the site refused is reported as left blank.
6. **Multi-page walker** — repeat read/map/fill/write/verify per page.
7. **Submitter** — submit only when every wanted value is on the page, no required box is empty, and the user asked; the post-click page must be a confirmation before the application counts.
8. **Recorder** — write `applications/applied.csv` (newest first), `applications/manual.csv` (blocked, with reason and link), `applications/takehome.csv`, `applications/all.csv`. Fixed column names.
9. **Resume path** — forms blocked by a code/robot-check/sign-in/account stay open in the browser profile; `/resume` (or CLI `resume`/`reconcile`) finishes them and records once. A Submit clicked with no confirmation seen is reconciled, never sent twice.
10. **Policy + daily run** — standing policy (count, employers never, per-board pacing, full stop on human-check) with `dry` rehearsal, `run`, `schedule`, `pause`, `stop`. Optional; can ship after the core loop.
11. **Dashboard triage ("Needs you")** — list blocked forms with a box to save an answer for next run; forms waiting for a code/sign-in with "Show the form"; unconfirmed submissions. Reuse dashboard-app patterns.

## Boundaries

- Browser automation is the only new external surface; everything else reuses existing packages. No second persistence store.
- No invented facts: written answers are checked against the profile in code (numbers, tools, companies); a draft claiming unsupported content is sent back once with claims named, then refused.
- No silent account creation or sign-in; only with explicit user setup and per-employer opt-in; never retry a refused password; never make an account in a rehearsal; never tick marketing boxes.
- No passing "prove you are human" tests or reading email beyond one verification email for account creation.
- Cost: typed decisions are cheap (JEV-style, ~fraction of a cent per form); sentence writing only when open questions exist; cache mappings and remembered answers.
- Privacy: nothing about the user leaves the machine except the form submission itself; site knowledge (control kinds) may be shared, user data never.
- Records are git-ignored user data; only code and shared site knowledge are committed.

## Acceptance

See eval.md (to be written). Core acceptance: a single job with a known Greenhouse/Lever/Ashby form can be filled, read back, submitted on explicit approval, and recorded to applied.csv; a form with an unanswerable required question holds and appears in manual.csv with reason and link; a blocked form stays open and `/resume` records it once; a second run of an unchanged form reuses its mapping and remembered answers.

## Open questions

- Which browser driver layer exists in the repo today (check `agentic-os/packages` and dashboard before choosing Chrome-CDP vs. reuse)?
- Should the loop live in agentic-os as a package or as a job-hunting agent skill? Decide during design.
- Typed-decision backend: reuse JEV via OpenRouter (as jev-job-search) or the in-house `typesafe-ai` (Jev) already referenced in plans? Prefer the in-house one if it can answer typed choice questions; verify capability first.
- Scheduling: OS-level (cron/launchd) vs. agentic-os runtime scheduler. Decide during design.