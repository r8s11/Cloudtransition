# Command Center — Design System & Technical Rationale

**Product:** Command Center, the dashboard of the CloudTransition workspace
**Runtime:** FastAPI + Jinja2 templates, plain CSS and ES-module JavaScript, no build step
**Companions:** `PRODUCT.md` (who and why), `CLAUDE.md` (file map, run commands)
**Contracts:** `tests/test_design_contracts.py` enforces everything marked **contract**

Read this before any styling, layout or motion work. Sections 3–7 are the
system; sections 8–12 are reference tables.

---

## 1. System overview

Command Center is one operator's instrument panel. Every value it shows is
read live from workspace Markdown/YAML; the only write is the task toggle and
the inline editors, which change those files in place. The design follows
from that: a dark instrument surface that stays quiet until something needs
attention.

**One world.** Every tab shares one surface (navy ground, navy panels, one
orange signal, ember corner brackets). Today, Interviews, Run and Agents
used to have their own worlds (a grey "deck" and a cyan "spatial" glass
face); on 2026-11-18 they were folded into the base surface. They keep
their components (list–detail, runner cards, the reticle hero), not a
separate look.

### Principles

1. **Colour is state.** Hue never decorates. Every coloured mark repeats
   something the text already says (section 5).
2. **One signal.** `--ember` orange marks the active tab, the primary action,
   progress, counts and live state. Nothing else competes with it.
3. **At a glance first.** Each page leads with one focal instrument; detail
   sits one step away (section 4).
4. **Deterministic first.** Local tools run before anything that calls a
   model, and every run states what it costs.
5. **Flat, honest data.** No image assets for data; charts, rings and arcs
   are drawn from the real values. When there is no timestamp, nothing
   pretends there is one.

---

## 2. Surface architecture

### 2.1 Shell layers

| Layer / selector | `z-index` | Role |
|---|---|---|
| `body` ground | — | `--void` navy, an orange glow top-right, a cool glow top-left, `background-attachment: fixed` |
| `body::before` | `0` | 48px instrument lattice behind everything |
| `body > *` | `1` | Masthead, navigation and the sheet sit above the lattice |
| `.masthead` | `100` | Title, `CloudTransition · Week N`, date, Update sheet |
| `.skip-link` | `200` | Skip to content, visible on focus |
| `.sheet-layout` | — | Grid: `.fold-column` (the week) on the left, `.sheet-faces` (the active page) on the right |
| `.page` panels | — | One `role="tabpanel"` per tab; only `.active` shows |
| Dialogs (`.interview-dialog-head` 2, `.ops-toolbar` 10) | 2–10 | Sticky heads inside dialogs and toolbars |

The reticle hero on Today is ordinary flow content inside its page, not a
layer: an inline SVG with HTML callout pills positioned in the same box.

### 2.2 Asset map

| File | Owns |
|---|---|
| `static/tokens.css` | Every colour, type and shape token (section 3). Single source for the dashboard, the reader and the skill registry |
| `static/style.css` | Shell, navigation, fold column, HUD layout grammar, base components |
| `static/deck.css` | Component scope `.deck`: list–detail, segmented filters, runner cards, hint dock. Its `--deck-*` tokens are aliases of the base tokens |
| `static/deck-interviews.*`, `deck-run.*`, `deck-agents.*` | Per-tab components and behaviour (selection, j/k, stage flow, runners) |
| `static/spatial.css`, `spatial.js` | Today's reticle hero and its live arcs |
| `static/app.js` | Tabs, View Transition, task toggle, weekly-step focus, copy actions |
| `static/metrics.js`, `calendar.js`, `work-search.js` | Metrics charts, calendar export, work-search report |

**Cache-busting.** Assets load as `/static/<file>?v=<key>` from
`templates/index.html` (and `reader.html`, `skills_registry.html` for
tokens/deck). Bump the key with every CSS or JS change; the live server runs
without reload under launchd.

### 2.3 Allowed engines

No CDN, no audio, no WebGL today. Two engines are approved for the reticle
roadmap (section 6.6) and must be vendored under `static/vendor/` with a
`?v=` key:

- **three.js `WebGPURenderer` + TSL** (`three/webgpu`, `three/tsl`): falls
  back to WebGL 2 itself. Materials as TSL node functions so one source runs
  on both backends. The canvas sits behind the SVG; the SVG keeps every
  readout and is the complete fallback. Render only while Today is visible
  and motion is on; cap pixel ratio at 2.
- **GSAP** (Today only): `gsap.matchMedia()` gates every timeline on
  `(prefers-reduced-motion: no-preference) and (hover: hover)`;
  `gsap.context()` scopes the hero; leaving Today or `document.hidden` pauses
  the global timeline. Existing motion (tab View Transition, Interviews stage
  flow, progress `scaleX`) is not migrated.

---

## 3. Tokens (`static/tokens.css`)

### 3.1 Ground and panels

| Token | Value | Use |
|---|---|---|
| `--void` | `#050b16` | Page ground |
| `--panel` | `#0e1d33` | Raised face: fold column, dialogs, readouts |
| `--panel-deep` | `#0a1628` | Recessed face: inputs, notes, readouts |
| `--panel-hi` | `#14294a` | Cards; hover and focus face |
| `--border` | `#223b60` | 1px hairlines |
| `--border-light` | `#182d4c` | Dividers inside a panel |

Cards add a cool 160° sheen on the upper-left edge and an inset 1px top
highlight. No blur, no glass, no light fields.

### 3.2 Ink

| Token | Value | Use | Contrast |
|---|---|---|---|
| `--ink-strong` | `#f5f9ff` | Headings, readout values | — |
| `--ink` | `#dbe6f5` | Body | — |
| `--ink-mid` | `#b4c5dc` | Secondary | — |
| `--ink-muted` | `#9db1cc` | Faint labels, metadata | ≥ 6.4:1 on every panel (**contract**) |
| `--bright` | `#e9f1fc` | Text directly on the ground | — |

### 3.3 Signal

| Token | Value | Use |
|---|---|---|
| `--ember` | `#ff7a1a` | Fills, bars, brackets, active pill, live marks |
| `--ember-deep` | `#c95a0a` | Pressed fill and borders; hover lifts to `--ember-light` (dark ink 4.4:1 on the deep fill fails AA) |
| `--ember-light` | `#ffa04d` | Lit edge |
| `--ember-text` | `#ff9a47` | Orange text on a panel (7:1+) |
| `--on-ember` | `#1c0e02` | Text on an orange fill (8:1) |
| `--gold` | `#ffc247` | Focus ring, active fold step |
| `--accent`, `--accent-soft` | `--ember`, 16% tint | Semantic aliases |

### 3.4 Hues

Re-lit for dark panels, each ≥ 4.5:1 on the panels. `SAFE_HUES` in `core/config.py`
mirrors them; a test pins the pairing (**contract**).

| Token | Value | Meaning |
|---|---|---|
| `--green` | `#5fcf8a` | Done, healthy, progressing |
| `--yellow` | `#f2c14e` | Warns, needs action, paid |
| `--red` | `#ff7b72` | Critical, overdue, blocked |
| `--blue` | `#6aa9ff` | Information, planned, new |
| `--purple` | `#aa9cff` | Category ink |
| `--teal` | `#4fd1c5` | Category ink |
| `--sage` | `#86d6a2` | Category ink |
| `--level-1…4` | OKLCH blue ladder | Proficiency magnitude (section 5) |

Each hue has a `-light` 12–14% tint for badge grounds.

### 3.5 Type and shape

| Token / role | Value |
|---|---|
| `--sans` | Inter — all UI text |
| `--mono` | JetBrains Mono — ids, dates, counts, paths, measured values; always tabular numerals |
| Page title (`.page-header h2`) | 24px / 700 |
| Panel title (`.card-title`) | 16px / 700 |
| Body | 14px, 1.5–1.6 leading |
| Meta | 12–13px; nothing under 12px |
| Readout value | mono 20px / 600 |
| Panels | square; small controls ≤ 2px; pills and badges stay round |
| `--ease` | `cubic-bezier(0.4, 0, 0.2, 1)`; state changes use an exponential ease-out |

`--deck-*` tokens in `deck.css` are aliases of the rows above, kept so the
component files do not need rewriting. Never give them their own values.

---

## 4. Layout grammar

Every tab follows the perimeter-HUD composition of the `hompage/` reference,
in the base colours.

| Element | Rule |
|---|---|
| **Header** | Title and one line of context left; the page's figures right as a telemetry readout (`readout()` macro → `<dl class="hud-readout">`; deck tabs `.deck-hud` + `.deck-readout`). Replaces the old row of stat boxes. Values `--ink-strong`. Under 900px it wraps under the title as a grid |
| **Command bar** | Filters, segmented controls and the page's main action in one bar under the header |
| **Stage** | 12-column grid: one focal panel (8 or 12 columns), 4-column wings beside it, full-width docks below. Source order is focal first. One column under 960px, or under 780px of page width (container query) |
| **Panels** | Square, 1px hairline, two 10px `--ember` corner brackets (top-left, bottom-right). Notes (`.card-dark`) keep a 2px orange top rule instead |
| **Rows** | Facts as key/value telemetry rows with 1px hairlines and mono values. Identity colour is an 8px swatch, never a side border over 1px |
| **Dock** | Keyboard hints as quiet pills at the foot of the page; hidden on touch and under 960px |
| **Rhythm** | 4-based scale: 4, 8, 12, 16, 24, 32, 48. Tight inside a group, generous between groups |

### Per tab

| Tab | Focal | Wings / dock |
|---|---|---|
| Today | Reticle hero, then Daily | Next up, capture, inbox, shortcuts, routine, artifacts, quick tools, brain |
| Overview | Crease map | Year Progress; projects strip; End of 2026 Goals rows |
| Tasks | Progress by Realm | Realm pills as command bar; realm lists 2-up |
| Projects | Project panels 2-up | Skills × Projects matrix |
| Interviews | Selected application (8) | Sticky list (4); hint dock |
| Career | Weekly work-search report, then success metrics | Networking, applications (empty state), checklist, goals |
| Money | Debt tracker | Weekly check note |
| Skills | Skill categories 2-up | Certifications, monthly checkpoints |
| Education | Degree Progress | Credits by Source; phases, actions, costs, Sophia table |
| Books | Category panels 2-up | Quarter strip on top; platform note |
| Run | Tool groups (8fr) | Activity (4fr); "How runs are bounded" opens in flow |
| Agents | Selected agent (8) | Sticky list (4); scan table; hint dock |
| Metrics, Workspace map, Mission Control | Their own content | Shared header and panel frame |

---

## 5. Colour is state

One matrix for the whole app. Every row pairs the colour with text.

| State | Colour | Text cue | Where |
|---|---|---|---|
| Active, primary, live, progress | `--ember` | Label, value | Active tab, primary button, progress fills, counts, review arc, current quarter/month (`now`) |
| Focus | `--gold` ring | — | Every focusable control; active fold step |
| Done, healthy, progressing | `--green` | `Done`, `Active`, status word | Year rings at 100%, cert status, interview stage progressing, telemetry live |
| Warns, needs action, paid | `--yellow` | `overdue`, `paid`, alert pill text | Daily rows flagged warn, reticle alert state, paid run tags, disk write |
| Critical, overdue, blocked | `--red` | `past target date`, `blocked` | Interview next-action overdue, failed runs, critical metrics |
| Information, planned, new | `--blue` | `Planned`, `New` | Project `Planned`, new books, week-elapsed arc |
| Paused, waiting, unknown | dashed `--border`, `--ink-muted` | `Deprioritized`, `Waiting` | Project paused, waiting badges, `No model · $0` |
| Category identity | `SAFE_HUES` ink | Realm/group name + icon | Task realms, book groups, credit sources |
| Magnitude | `--level-1…4` | Level word | Skill proficiency (no red/green: a level is not a verdict) |

**Run provenance.** Every run card states its cost in a small mono tag:
`No model · $0` is quiet and uncoloured; a model call or paid API takes the
marked ink. The words carry the meaning.

**Metrics series.** CPU/send orange solid; memory/receive blue solid;
capacity plum solid; disk read teal solid; disk write `--yellow` dashed.
Lines keep solid/dashed/dotted distinctions; unknown severity is hatched.

**Workspace map.** Embedded in its tab it takes the navy panels and orange
signal (`:root.embedded` in `visual-second-brain.html`); standalone it keeps
its washi sheet.

---

## 6. Components

### 6.1 Navigation

Fifteen tabs in four groups (Operate, Career, Learning, System), defined once
as `nav_groups` in `templates/index.html`, one divider between groups. The
active tab is the one filled pill at the same weight as its neighbours, so
the row never shifts. Reader is a link with a dashed outline because it
leaves the app. Opens on Today; an unknown hash falls back to Today. All
groups fit one row at 1280px; under 640px they scroll sideways with 44px
targets.

### 6.2 Fold column and weekly-step focus

The week as numbered steps (`.fold-step`) beside every tab. The focus card
(`#fold-focus-card`) shows the selected step's linked tasks: name, `n of m`,
a progress bar, remaining count and a small graph of the linked task groups.
Starts on the active step. Hover, focus or click selects; arrows move, Home
and End jump, `aria-pressed` marks the selection. The numbered list is the
complete no-JS fallback.

### 6.3 Task toggle

One click, Space or Enter checks or unchecks a task and writes the Markdown
through `/api/tasks/toggle`. The change paints at once on every copy of the
task (Today repeats Tasks rows); a failed write reverts every copy. Weekly
Review rows also say `Saving…`, `Saved` or `Not saved: <reason>`.

### 6.4 List–detail (Interviews, Agents)

A sticky filterable list beside the selected item's full controls. `/`
focuses the filter, j/k or arrows move the selection and the detail swaps
instantly, Enter moves into the detail, Esc returns. Edits save inline with
an aria-live confirmation. Interviews shows the agent pipeline (Read posting
→ Tailor CV → Tailored CV) on the selected application. Under 960px the list
stacks above the detail with a "Back to list" control.

### 6.5 Runner cards (Run, Agents, Today quick tools)

One row per tool: icon, name, description, cost tag, status word, Run
button. `deck-run.css` owns them on every tab. A running card is
`is-running`; output opens in a dialog.

### 6.6 Reticle hero (Today)

**Anatomy.** One inline SVG (viewBox 960 × 360): a faint lattice, three
rings, 72 ticks (12 major), a sweep, three lock brackets, a core with
crosshair, and a week + inbox readout. Leader lines run to four callout
pills: date/clock status and the first three Daily rows. It echoes the
Daily card, so the whole hero is `aria-hidden` with its links out of tab
order. Capped at 1120px wide so Daily starts inside the first screen.

**Colour.** Structure (lattice, rings, minor ticks, leaders) in
`--ink-muted`/`--border` hairlines; signal (sweep lead, major ticks,
brackets, review arc, core) in `--ember`; the week-elapsed arc in `--blue`.
Pills are square `--panel-deep` faces with a hairline and ember brackets, no
blur.

**State matrix.**

| Parameter | `idle` | `alert` (any Daily row flagged warn) |
|---|---|---|
| Signal ink | `--ember` | `--yellow` (sweep lead, major ticks, brackets, review arc, status pill) |
| Sweep period | 6s | 2.2s |
| Ticks | 120s per turn | 120s per turn |
| Brackets | 40s per turn, reverse | faster, reverse |
| Status dot | steady | pulses 0.72s |
| Text | `STANDBY` | the alert text in the status pill |

**Live arcs.** Two arcs that never spin carry real state from 12 o'clock:
outer (r 132) the Weekly Review read from `#routineReviewProgress` with a
`REVIEW n/m` readout; inner (r 60) the time elapsed Monday 00:00 → Sunday
24:00. Tasks have no completion timestamps, so there is no "done today".

**Lock-on.** A real event plays one ~0.7s lock-on: brackets snap in (scale
0.8, −8°, settle), a ring flashes out of the core, the SVG brightens.
Events: a Next up or Inbox toggle, an inbox count change, a review check, a
runner turning `is-running`. MutationObservers on existing markup detect
them, so `app.js` is untouched. Never animate `filter` on `.fui-hero` (it
drops the pills' compositing); animate the SVG only.

**Proposed next (not built).** Each keeps the hero contracts: decorative
layers `aria-hidden`, real values in normal markup, reduced motion shows the
final state, a `Motion` toggle in the status pill pauses everything longer
than 5s (WCAG 2.2.2) and persists in `localStorage`.

| Idea | What | State it carries |
|---|---|---|
| Reactor core | Radial plasma core, containment ring, coolant ring inside the r 60 arc; a lub-dub heartbeat (`1 → 1.06 → 1 → 1.035 → 1`) with one faint shock ring per beat | ~50 bpm idle in ember, ~90 bpm and `--yellow` on alert via `timeScale()`; lock-on events become one forced beat; the coolant ring turns while a runner is `is-running` |
| Layered reticle | SVG split into depth planes in a `perspective: 1200px` stage; parallax moves each plane at its own rate | — |
| Panel tilt | Today cards tilt ≤ ±3° toward the pointer with a specular highlight (`--spec-x/--spec-y`); keyboard focus gets the lit edge without tilt | — |
| Orbit plane | Next up rows as nodes on an ellipse (`rotateX(65deg)`) around the core | A flagged row's node in `--yellow` |
| Isometric week | Fold column as seven plates, today raised one step | The numbered list stays the source |
| Depth of field | Opening a run-output or interview dialog pulls the ground back (`scale(0.985)`, small blur) | — |
| Boot | First visit per session: rings draw, ticks stagger from 12 o'clock, leaders draw, core ignites (~1.2s, skipped by any input) | — |
| Readout decode | Changed hero readouts decode in mono glyphs; Daily updates instantly | `REVIEW n/m`, inbox count |
| Energy packets | A dash travels core → leader → pill when a pill's value changes | Which value changed |
| Radar ping | A new inbox item leaves a fading blip at the inbox readout's angle | New inbox item |

### 6.7 Metrics

Inter for captions (14/600), legends and axes (12/500); JetBrains Mono for
identifiers and measured values (12–13px) with tabular numerals. Long
identifiers wrap. The percentage axis reserves room for `100%`. Colour stays
in data and selected controls.

### 6.8 Now (Today) and Mark applied

**Purpose.** Today always answers "what should I be doing right now?". The
first card on the page is one directive, worked out on every load by
`core/now.py` from the clock, `routine.md` and the interview tracker, plus
the next two as a "Then" list. Each directive names the `routine.md` rule
it serves.

**Directive order.** Urgent items always lead; then the routine block.

| When | Directive |
|---|---|
| Any time | **Prep** a screen/assessment/interview/onsite whose next step is today to 2 days out; **Act** on a live conversation whose next step is overdue |
| Weekday 06:00–13:00 | **Apply** to the best unapplied lead until today's goal is met, then **Follow up** due ones |
| Weekday 13:00–19:00 | Still **Apply** if today's goal is short (says so), then follow-ups, then the **Freelance** block |
| Saturday morning / afternoon | **Build**: the first open SalsaSegura / DevOps task in `TASKS.md` |
| Sunday | **Review**: the first unchecked Weekly Review item, with the week's count |
| Evening, night or nothing due | **Rest**, with today's count and tomorrow's first block |

- **Goals** are read from `routine.md` (`N applications/day`, `N applications a week`); 2 and 10 are the fallbacks.
- **Counts** come only from `applied` entries in each row's `timeline`; Monday starts the week. "Leads left" is `new_lead` rows with no `applied` entry.
- **Best lead:** priority, then a tailored CV ready, then a posting link, then the oldest target date, then tracker order.
- **Follow-up due:** a `waiting`/`applied` row whose first next-step date has arrived, or 7 days after its last `applied` entry when it has no date.
- **Block clock times** (06:00, 13:00, 19:00) are the dashboard's; `routine.md` names the slots, not the hours.
- **Staleness.** The plan is built for one block. When that block ends, the card says so and offers **Refresh plan**; it never reloads on its own, so an unsaved form is safe.
- **Tone** follows section 5: the verb chip is orange for the signal, yellow for overdue, quiet for routine blocks and rest.

**Mark applied** (`POST /api/interviews/applied`, Today and every `new_lead` row on Interviews). One tap after submitting: an `applied` timeline entry dated today, status `waiting`, and the first next step becomes "Follow up if no reply" a week out, all in one atomic write. A row that is no longer a `new_lead` is refused, so a double tap cannot log two applications. A success reloads the page so Now recomputes.

---

## 7. Motion

| Element | Property | Timing | Trigger | Reduced motion |
|---|---|---|---|---|
| Tab switch | View Transition, clip-path circle from the clicked tab | 460ms | Tab click | Instant |
| Page appear | opacity | short fade, no movement | Panel shown | Instant |
| Progress bars | `transform: scaleX(0 → value)` from `data-width` (**contract**) | — | Panel shown | Final value |
| Task toggle | state | snaps | Click, Space, Enter | Same |
| Weekly-step focus | opacity, state | short | Hover, focus, click | State only |
| Component state | colour, background, border | 160ms exponential ease-out | Hover, select | Instant |
| Interviews stage flow | FLIP transform of the row into its new group | 380ms | `interview:status`, `interview:next` | Instant |
| Stage counts | odometer roll, clipped one-line track | 420ms | Count change | Instant |
| Status badge | cross-fade | short | Status change | Instant |
| Reticle sweep / ticks / brackets | rotate | 6s / 120s / 40s (alert faster) | Continuous on Today | Stopped |
| Reticle parallax | rotate ±5.5° | damped | Pointer (not touch) | Stopped |
| Lock-on | scale, rotate, opacity | ~0.7s | Real events (6.6) | Values update, no motion |

- **Layout never animates (contract).** No transition on `width`, `margin`
  or any layout property.
- **Reduced motion (contract)** is handled per surface with targeted
  overrides, never one wildcard. Selected state and hierarchy stay.
- A click during the tab transition applies at once and cancels the queued
  apply, so rapid navigation never snaps back. Focus and selection never move
  because of an animation. A hidden page never animates.

---

## 8. Controls and shortcuts

| Input | Where | Action |
|---|---|---|
| Click / Enter / Space on a tab | Navigation | Switch tab (arrows, Home, End move between tabs) |
| Arrows, Home, End | Fold column | Move the weekly-step focus |
| Click, Space, Enter | Any task row | Toggle the task and write the file |
| `/` | Interviews, Agents, Run | Focus the filter |
| `j` / `k`, ↓ / ↑ | Interviews, Agents | Move the selection |
| Enter | Interviews, Agents | Move into the detail (status select / runner) |
| Esc | Interviews, Agents, Run | Back to the list row / clear the filter |
| Pointer move | Today hero | Parallax (±5.5°) |
| Mark applied | Today Now card, Interviews `new_lead` rows | Log the application, park it as waiting, schedule the follow-up |

---

## 9. Responsive

| Width | Change |
|---|---|
| Desktop | Fold column left, page right; stage at 12 columns |
| ≤ 960px | Stage to one column, focal first; list–detail stacks with "Back to list"; dock hidden |
| ≤ 900px | Fold column becomes a horizontal strip above the page; header readout wraps under the title; hero pills stack under the reticle |
| ≤ 640px | Navigation scrolls sideways as one strip with 44px targets |
| ≤ 480px | Hero keeps only the status pill |
| `(pointer: coarse)` | Every control at least 44px tall |

---

## 10. Accessibility

- WAI-ARIA tabs pattern, skip link, visible `--gold` focus rings.
- Text holds WCAG AA on every panel (**contract** for `--ink-muted`).
- No meaning in colour alone (section 5). The active fold step repeats its
  number.
- Decorative echoes (the reticle hero, its pills and links) are
  `aria-hidden` and out of tab order; the real values live in normal markup.
- Heading order: `h2` page, `h3` panel, `h4` inside a panel.

---

## 11. Contracts and pinned markup

| Test | Pins |
|---|---|
| `test_design_contracts.py` | `--ink-muted` contrast; `SAFE_HUES` ↔ `tokens.css`; `transform: scaleX(0)` progress; no layout transitions; targeted reduced-motion; overview uses `var(--accent)` and no `border-left: 4px solid {{ p.color }}` |
| `test_now.py` | Now directive order (prep over apply, follow-ups after the daily goal, weekend blocks, rest), goals read from `routine.md`, counts from `applied` entries, and the Mark applied write (one entry, `waiting`, follow-up in 7 days, second tap refused) |
| `test_shortcuts.py` | Today card order (`dailyTitle`, Next up, `captureForm`, `inboxList`, `shortcutsTitle`, `routineTitle`, `artifactsTitle`, Quick tools, `brainAskForm`); exact `<a class="daily-row" href=…>`, `<span class="daily-row is-placeholder">`, `<div class="task-category-header">Name</div>` |
| `test_interview_waiting.py` | `interview-tools` with four fieldsets; `job-stats` label order; section order leads → `#interviewAgents` → waiting → closed |
| `test_wiring.py`, `test_skills.py` | Asset wiring, skill registry markup |

When a test pins markup, restyle with CSS or regroup at runtime in JS.

---

## 12. Extension guide

- **New tab.** Add it to `nav_groups`, create `templates/pages/<tab>.html`
  with `class="page"`, a `hud-header` with `readout()`, and a `hud-stage`
  with one focal panel. Use `class="page deck"` only to borrow the
  list–detail or runner components; it changes no colours.
- **New colour.** Add the token to `tokens.css`, the matching entry to
  `SAFE_HUES` if templates pass it, and a row to section 5. If it has no
  state to carry, it does not ship.
- **New run card.** Follow 6.5 and state the cost tag.
- **New readout figure.** Only values already true in the files; no
  invented counts.
- **Shipping.** Bump every changed asset's `?v=` key, run
  `venv/bin/python -m pytest tests/ -q`, then
  `launchctl kickstart -k gui/$(id -u)/com.cloudtransition.dashboard` and
  check that `/` returns 200 with the new keys.
