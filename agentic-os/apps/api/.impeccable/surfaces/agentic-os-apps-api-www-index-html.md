---
version: 1
slug: "agentic-os-apps-api-www-index-html"
primary_target: "agentic-os/apps/api/www/index.html"
related_targets: []
---

# Surface Brief — Mission Control

<!-- impeccable:surface-brief 1 -->

## Scope and Visitor Mode

Operate. Local, single-operator workstation dashboard at `/`. User confirmed expanding Mission Control to project registration, agent-run creation, process inspection, and interrupt/terminate controls while refining the existing Control Room identity.

## Direction contract

**THESIS:** One workspace for deliberate decisions, with Missions and Agent runs as adjacent tabs. Keep workflow state distinct from process state. No navigation rail or ornamental metrics.

**OWN-WORLD:** Preserve deep navy ground, blue selected states, mint success, amber attention, and coral failure. System sans, compact controls, quiet borders, rounded panels, restrained header wash. Color communicates actions and state; headings use solid text.

**STORY:** Scan the mission pipeline and pending approvals, inspect a selected item, and act. Switch to runs to choose a repository and installed agent, submit a prompt, read process output, and explicitly stop work when needed.

**FIRST VIEWPORT:** Compact branded header with connection state and clock. Workspace tabs and context-specific creation action below. Wide work area at left, narrower inspection column at right. Mission board prioritizes open statuses; terminal statuses remain reachable. Creation forms open inline rather than permanently occupying the inspector.

**FORM:** Incumbent single-screen command workspace, expanded to two task tabs. Native buttons, selects, disclosure controls, scrollable board and output. On narrow screens the inspector follows the work; controls wrap without page overflow.

**SIGNATURE:** User-selected overdrive: fluid inspection. Selection resolves into a stable inspector with a brief directional reveal; workspace tabs use same-document View Transitions when supported. Immediate updates remain the fallback and reduced motion disables transitions. Five-second refresh never animates, replaces in-progress forms, resets selection, or steals focus. Output follows new chunks only when the operator was already at its end.

Seed: none (incumbent world refinement; no replacement-world roll).

## Content and Behavior

Live SQLite-backed missions, plans, history, approvals, projects, adapters, runs, and events. No synthetic activity in production. Mission creation requires acceptance criteria. Only legal transitions are offered. Runtime launch clearly warns that agents use local permissions and credentials, and approvals are not sandbox enforcement. Interrupt and terminate require an inline confirmation naming the run. Prompt/output displayed as text, never HTML. Runtime failures must not hide working mission data.

## States and Constraints

Loading, empty, populated, selected, submitting, error, offline, unavailable CLI, active run, terminal run, paginated history. Preserve drafts and keyboard focus across polling. Desktop-first; verify at 1440px and 390px. Honor reduced motion and visible focus. No external network assets, scheduler, orchestration, provider SDK, interactive terminal, or API contract changes.
