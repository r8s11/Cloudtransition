# Workspace map motion

## Request

User invoked animate for `visual-second-brain/`, then invoked cinematic-gsap-lenis-motion-system and said “go”.

## Proposed design

Purpose: prevent a jarring initial scene change, preserve spatial consistency for pointer-opened details, and confirm pointer presses. This is a daily-use file browser, not a scroll narrative. Atlas and the dark/Paper Graph remain visually and functionally unchanged.

- Graph: once per page, initial load or first pointer entry gets a 220ms opacity settle from 0.85 to 1. File positions never move. Keyboard-triggered entry is immediate and consumes the first-entry allowance. Search, filters, group changes and subsequent view toggles stay immediate.
- Existing detail drawer: pointer opens/closes use opacity plus a small right-origin translation, 220ms on entry and exit. Keyboard opens/closes, Escape, filtering and programmatic dismissal remain immediate. Focus moves immediately; closing content becomes inert immediately. Latest interaction wins; reopening cannot be hidden by an older exit callback.
- Graph control press feedback: 120ms scale to 0.97 only during pointer press. Keyboard activation gets no transform. No animated node hover, camera drift, auto-rotation, magnetic cursor, scroll reveals, pinned sections or perpetual node simulation.
- Extend the existing `--ease` token and duration conventions. CSS for press feedback; WAAPI only for interruptible, programmatically dismissed panels/entry. No GSAP, ScrollTrigger or Lenis install: these short transitions need no library, and scroll interception would compete with native scroll and SVG wheel zoom. This tooling choice needs user approval with the evals.
- Reduced motion: pointer scenes/panels keep only a gentle 120ms opacity settle, never translation or scale. Enabling reduced motion or starting keyboard/graph gesture input cancels pending visual motion. No animation API support means the final, usable state appears immediately.
- Existing Atlas GPU motion and pause/reduced-motion behavior stay untouched. No new data, snapshot refresh, external requests, dependencies, file routes or server changes.

## Approaches

Selected proposal: existing tokens plus CSS/WAAPI. A full GSAP/ScrollTrigger/Lenis pipeline is rejected for this operational surface: no storytelling scroll exists, and its graph explicitly owns wheel zoom. Leaving everything static would preserve speed but omit the requested pointer feedback and spatial handoff.

## Implementation plan after approval

1. Modify `visual-second-brain/visual-second-brain.html` only for behavior: scoped duration tokens, pointer modality/press state, interruptible entrance/exit handles, hooks into `renderGraph`, `openDetail` and `closeDetail`. Keep node camera transforms and virtual row geometry independent.
2. Preserve existing immediate state paths. Cancel work on keyboard input, new gestures, view replacement, live reduced-motion changes and teardown. Do not delay focus or leave callbacks that hide a newly opened drawer.
3. Update `visual-second-brain/README.md` and `DESIGN.md` with the approved motion contract. Keep routers current.
4. Run scoped index regressions and JavaScript parse. Browser-check desktop/phone, keyboard/pointer, rapid reversal, live reduced-motion, no-animation fallback and existing zoom/pan/search/path actions. Save bounded proof under `eval-evidence/`.
