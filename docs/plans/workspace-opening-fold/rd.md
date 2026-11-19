# Opening Fold

## Request and selected direction

User, 2026-11-13: “overdrive @visual-second-brain/ /skill:build-awwwards-quality-sites”. From three offered directions the user selected **A. Opening Fold**: the Atlas itself becomes the authored first viewport, the folded sheet becomes the focal object, tiles deal out on load, a clicked tile morphs into the file-list heading, and switching to Graph sends the tiles into their hubs. The user also selected **GSAP, shipped locally**, over the previously approved CSS / Web Animations rule.

Mode: Operate. The Workspace map is a search tool, so the Awwwards skill supplies art direction and choreography, not a marketing page. The Orizuru paper-and-vermilion world, Inter, JetBrains Mono, the snapshot data and every existing route stay authoritative.

## Direction

- **Visual thesis:** one sheet of paper holds the whole workspace; opening the map folds it.
- **Hero focal asset:** the existing real-time Folded Atlas sheet (Three.js r180), enlarged. No generated imagery, stock media, avatars, logos or new icons.
- **Type:** Inter only. The cover statement is the page's single display moment; everything else keeps its current scale.
- **Color:** existing tokens. Vermilion marks the two real numbers in the statement, as it already marks tile counts.
- **Motion narrative:** fold (load) → deal (tiles) → carry (a topic's name travels to the heading, the sheet travels to the rail) → gather (topic names travel onto their Graph hubs). Names are the only things that travel between states.
- **Smooth scroll:** none. Native scrolling stays, because the file list is virtualized. No ScrollTrigger.
- **Three.js:** reuse the existing sculpture module; add one fold progress value. No shader, post-processing or new scene.

## Design

- **Cover.** Shown only on the Atlas root (tiles, no search/type/date/topic filter, no file open; in Folders grouping only at the top level). `h2#title` becomes a statement built from real values: “689 files, folded into 17 topics.” (or “… folders.”), using the current result count and the number of tiles shown. One supporting line of real facts follows (largest groups, latest change). No eyebrow, no call-to-action buttons, no new claims. Every other state keeps today's compact heading.
- **Layout ≥1100px.** The cover is a band above the tiles: statement left, sheet right at about 420×340 CSS px. Tiles use the full width below. In list mode the existing 288px rail, topic pose, caption and 56px row contract are unchanged. The Pause motion button stays available wherever the sheet moves.
- **Layout <1100px.** Typographic cover with the existing compact static fold. No canvas, as today.
- **Load intro, once per page load.** Statement words rise in sequence; the sheet folds from flat into its approved pose; tiles deal out in reading order. About 1.2s in total. The masthead, search and toolbar never animate and accept input from the first frame. Any key press, pointer press or search input completes the intro instantly.
- **Tile → topic (pointer).** The tile's name travels to the heading position, the sheet glides from cover to rail and takes its topic pose, and the first screenful of rows rises in. Old tiles are removed immediately; data is never delayed for an exit animation.
- **Topic → root (pointer).** The reverse: the name travels back to its tile, the sheet returns to the cover, tiles settle in quickly. The sheet does not refold.
- **Atlas → Graph (pointer, from the root).** Each tile's name travels to its own hub and lands on the hub label while the tile card dissolves in place and the graph stage appears. This replaces the existing once-per-page 0.85→1 opacity entry. From any other state, and for Graph → Atlas, the handoff is a short settle only. If hub positions are not available in time the names fade in place; the graph is never held back.
- **Rules kept from the approved motion policy.** Keyboard-initiated changes are instant. Reduced motion renders final states at once and keeps at most a 120ms opacity change. Latest state wins: a new state kills running timelines, removes travelling copies and clears inline transforms. Focus never waits for motion. The existing drawer transition and press feedback are not rewritten.
- **Degradation.** GSAP missing or blocked: every state is instant and fully visible. WebGL missing or lost: the static fold sits in the cover; text and tile motion still run. Nothing is hidden by CSS waiting for a script.

## Approaches

Chosen by the user: Opening Fold with GSAP. Not chosen: a separate scroll-driven cover page (full skill compliance, new surface, three libraries) and transitions only (no layout change). Do not mix those in.

Deliberate deviations from the Awwwards skill, because this is a tool: no smooth-scroll engine, no ScrollTrigger, no generated or licensed imagery, no call to action, footer, logo wall or avatars. No award or recognition claim is made anywhere.

## Implementation shape

- `visual-second-brain/assets/vendor/gsap.min.js` and `Flip.min.js`, pinned 3.15.1, loaded as local deferred classic scripts, plus a license note pointing at GSAP's standard no-charge license. No package install and no remote runtime request.
- `visual-second-brain/assets/atlas.js`: export a pure `foldPositions(progress)` (0 = flat sheet, 1 = exactly the approved vertices) and accept a fold progress in `update`. Lifetime, context-loss, offscreen and reduced-motion behavior unchanged.
- `visual-second-brain/visual-second-brain.html`: cover statement and layout classes, one motion controller (intro, carry, gather, interrupt), flip ids on tile names and the heading, ghost overlay. Search, filtering, URL state, virtualized rows and file actions are not touched.
- `visual-second-brain/assets/constellation.js`: one read-only controller method returning a hub's screen point, used by the gather handoff.
- `visual-second-brain/tests/test_atlas_fold.mjs`: the fold ends on the approved vertices exactly, starts flat, stays finite, and does not mutate its source.
- README, DESIGN.md and the department routers update in the same change. The page comment that says “no dependencies” is corrected.

## Acceptance and proof

See eval.md and mockup.html. The study runs the real GSAP 3.15.1 build and the real Three.js sheet with representative data; it is not the production implementation, and its graph is a placeholder for the existing Depth Constellation. Serve the plan folder over HTTP to see the 3D sheet; opened from disk it shows the static fold, exactly as production would without WebGL.
