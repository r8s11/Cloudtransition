# Dashboard Surface Brief

## Job and audience

Single-user IT professional, now job-searching after the Ross contract ended. Context: running a career as an operation — two career lanes, money, learning, routine. Need: a ten-second answer to "what's active, what's due, what's on track" and one right action from there. Situations: desk, phone on the go, weekend at home.

## Outcome and proof

One loaded page gives the complete honest operational picture: overview + 7 pages (Education, Books, Tasks, Projects, Skills, Career, Money) + a weekly calendar grid for Routine & Schedule. Clicking a checkbox writes back into the real `.md`/`.yml` files. The dashboard and the source of truth can never disagree — that is the product-specific truth.

## Direction contract

### World

The Orizuru — one uncut sheet of vermilion washi becoming a crane through discrete, numbered folds. Every task is a fold; the finished shape still carries every crease. Files are recoverable — every fold can be unmade.

### Visual authority

- Palette: vermilion washi ground (`#b3212e`) with visible kozo fiber, crease lines in faded fold-white (`#f4ead8`), one gold dot marking the active step (`#c9a227`), notes in sumi black ink (`#171512`).
- Materials: kozo-fiber washi, fold-white creases, sumi ink, gold step-dot.
- Type: quiet humanist sans beside numbered step names; folds numbered 1–32 in a strict margin column; the week's routine mapped to fold steps.
- Composition: the seven pages as faces of the uncut sheet; the weekly routine as a numbered fold column; the whole dashboard as one continuous sheet.

### Structural/interaction thesis

The career is one uncut sheet. Every task is a fold in that sheet. The weekly routine maps to the 32 fold steps. The gold dot marks today's active position. The fold-state vocabulary (flat, creased, collapsed, based, locked, finished, recoverable) maps directly to task states (unchecked, checked, collapsed, blocked, locked/completed, finished, recoverable/versioned).

### Signature interaction

The toggle: one click folds (checks) or unfolds (unchecks) a task. The fold-state changes atomically. Every fold is recoverable — the underlying file retains its history. The gold dot (active step) moves with the toggle.

### Motion grammar

Fold/unfold: a discrete snap to the next fold-state, no continuous animation. The gold dot shifts to the next active position on toggle. Responsive: discrete fold-state blocks stack on phones; no spatial animation required.

### Responsive adaptation

- Desktop: the week as a numbered column (1–32 fold steps) on the left, the seven pages as faces of the sheet on the right.
- Mobile: fold steps stack vertically; each page is a full-width face.

### First viewport

The week as a numbered fold column (1–32), the gold dot on today's step, the seven pages orbiting around it. The overview shows totals as crease patterns — density of folds per domain.

### Weekly calendar blocks

From `routine.md`:
- Weekday job-search and career-portfolio blocks (Ross employment has ended)
- 1 project block per week (A/B alternating)
- 1 DevOps block per week
- Weekend: Money + review

These map to fold steps in the numbered column. The gold dot tracks today's position in the sequence.

## Scope and boundaries

- Production-ready screen. Full 7-page dashboard + weekly calendar blocks.
- Built on the incumbent FastAPI + Jinja2 + Tailwind engine.
- Remains untouched: files-as-database, atomic-tempfile toggle, path allowlist, `X-Requested-With: XMLHttpRequest` guard, `venv/bin/uvicorn app:app --port 8000`, progress bar `width:0→data-width` animation.
- `routine.md` defines the weekly rhythm; REALMS drives page visibility.
- No image generation → code-led build only.

## Anti-goals

- Glass/gradient surfaces (the old Atmospheric Glass world).
- Neon/dark command-center aesthetics.
- External image assets for data.
- Spatial/continuous animations (fold states are discrete).

## Constraints

- Incumbent engine: FastAPI + Jinja2 + Tailwind. Visual world replaces CSS/templates, not the engine.
- No image generation on this machine.
- Accessibility: fold lines + numbered margin column carry state independently of color; gold dot is redundant with the fold number.
- Platform: web, responsive (macOS Chrome + phone).
