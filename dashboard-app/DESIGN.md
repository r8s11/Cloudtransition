# CloudTransition — Design Rationale (The Orizuru)

> Replaces the former "Atmospheric Glass" world. One uncut sheet of vermilion
> washi, becoming a crane through discrete, numbered folds.

## The world

The career is **one uncut sheet**. Every task is a **fold** in that sheet. The
weekly routine maps to the fold steps. The gold dot marks today's active
position. The finished shape still carries every crease — files are
recoverable, every fold can be unmade.

That model maps 1:1 onto the product truth: the dashboard and its source files
can never disagree. A checked box is a fold made; details are preserved in the
file's history; nothing is welded shut.

## Fold-state vocabulary → task states

| Fold state | Task state | Visual |
| --- | --- | --- |
| flat | unchecked | empty crease-tick square |
| creased | checked (sterile) | folded, ink-checked corner |
| collapsed | completed/task-done | dimmed row |
| based | blocked | halts in the numbered column |
| locked | completed item | gold step-dot |
| finished | done, shipped | crease-line drawn full |
| recoverable | every toggled file | atomic write, git history |

## Visual authority

- **Palette** — vermilion washi ground (`#b3212e`) with visible kozo fiber,
  crease lines in faded fold-white (`#f4ead8`), one gold dot for the active
  step (`#c9a227`), notes in sumi black ink (`#171512`). Content faces show
  the undyed washi (`#f8f1e3`) so sumi ink stays readable — ink is written on
  the white folds, never on the dye.
- **Materials** — kozo-fiber washi texture is layered CSS gradients + a faint
  feTurbulence tooth. No external images, no glass, no glossy gradients.
- **Type** — Inter (quiet humanist sans) beside JetBrains Mono step numbers
  and crease-count figures.
- **Composition** — the seven (eight with Money) pages are faces of the uncut
  sheet; the week's routine is a numbered fold column folded into the left
  margin; the whole dashboard is one continuous sheet.

## Signature interaction

The **toggle** — one click folds (checks) or unfolds (unchecks) a task. The
fold-state changes **atomically**. Every fold is recoverable; the gold dot
(active step) moves with the toggle.

The **fold-map focus** — hovering or focusing a numbered weekly step opens a
small paper-card preview of the related task ledger and its current progress.
Arrow keys traverse the map; Enter, Space, and click hold the selected
context. Without JavaScript, the numbered weekly list remains the complete
fallback.

## Navigation and run provenance

The product is named **Command Center**; CloudTransition is the secondary line
beside it. It opens on Today.

The fifteen faces sit in four groups — Operate, Career, Learning, System —
separated by a single crease line. Inactive tabs carry no outline; the active
tab is the one fold-white pill, at the same weight as its neighbours so the row
never shifts. Reader keeps a dashed outline because it leaves the sheet. All
four groups hold one row at 1280px; under 640px they scroll sideways as one
strip with 44px targets.

Deterministic first: every run card states what it spends in a small mono tag
beside its title. `No model · $0` is the quiet, uncoloured default. A paid API
takes the ochre ink and a model call the vermilion ink, so cost is the marked
state; the words carry the meaning without the colour. Local tools are listed
before anything that calls a model.

## Motion grammar

Fold/unfold is a **discrete snap** — no continuous spatial animation. Progress
bars ride a quiet crease (width `0 → data-width`, the one sanctioned
animation). Pages unfold with a tiny non-spatial fade. Fold-map focus uses only
a short opacity/state transition; `prefers-reduced-motion` removes transitions
while preserving the selected state and hierarchy.

## Responsive adaptation

- **Desktop:** the week as a numbered fold column (1..N) on the left, pages as
  faces of the sheet on the right.
- **Mobile (≤900px):** fold steps become a horizontally-scrollable numbered
  column; each page is a full-width face.

## Accessibility

- Fold lines + the numbered margin column carry state **independently of
  color**; the gold dot is **redundant** with the fold number.
- Contrast is held on the washi (ink on undyed washi, fold-white on vermilion).
- WAI-ARIA tabs pattern, focus-visible rings, skip link, reduced-motion.

## Anti-goals (why)

Glass/gradient panels (the old world), neon/dark command consoles, external
image assets for data, and spatial/continuous animation all fight the one-sheet
thesis. The sheet is calm, flat, and honest.

## Token map

| Design token | Value | Concept |
| --- | --- | --- |
| `--vermilion` | `#b3212e` | the ground / masthead / column |
| `--vermilion-deep` | `#8e1a24` | shadowed folds, page bg |
| `--fold-white` | `#f4ead8` | crease lines + nav active |
| `--paper` | `#f8f1e3` | unfolded faces |
| `--gold` | `#c9a227` | active step dot |
| `--sumi` | `#171512` | ink |
| `--washi-fiber` | layered gradients | paper tooth |

## Metrics typography

Metrics is an Operate surface: Inter carries chart captions (14px/600),
legends and axes (12px/500); JetBrains Mono carries identifiers and measured
values (12–13px). Measurements use tabular numerals to stay stable during
refresh. Sparkline ranges use 12px with 1.5 leading. Long workload and device
identifiers wrap without truncation; captions remain distinct from metadata.
The percentage axis reserves space for the full `100%` label at narrow widths.

## Metrics color

Color stays concentrated in data and selected controls, not panel decoration.
CPU/send use vermilion; memory/receive use blue; capacity uses plum across
its card bar, sparkline, legend and history. Disk reads use teal, writes use
deep ochre (`#805b0a`) with a dashed stroke. Green means up/healthy or safe
storage capacity; ochre and red retain warning/critical meanings. Ranking
selection uses the same CPU or memory ink as its bars. Lines retain solid,
dashed and dotted distinctions; unknown severity stays hatched, and every
status remains named in text.
