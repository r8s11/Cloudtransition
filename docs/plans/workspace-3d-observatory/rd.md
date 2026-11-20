# 3D Observatory

## Request and scope

User request: overdrive `visual-second-brain/` using `build-awwwards-quality-sites`, clarified to **the 3D section**. The user selected **A. 3D Observatory**: stronger spatial composition, refined lighting and materials, clearer labels, and one cinematic entrance. This direction selection is not approval of this requirements document, eval or study.

Mode: Operate. The real workspace diagram is the focal asset. Atlas, its folded sheet and opening choreography, the independent 2D renderer, search, filters, sidebar, drawer, file actions and privacy rules stay unchanged. No marketing page, invented records, relationships, metrics or award claims.

## Design

- Keep the current Graph shell, six cluster colors, Inter and JetBrains Mono, dark and Paper backgrounds. No new font, palette or remote runtime request.
- Spread real hubs into a wider near/middle/far composition. Start with existing deterministic placement, expanding hub x by 1.6, y by 0.9 and z by 1.3. Preserve near-spherical file clusters around their primary hub. Position is decorative, never evidence of semantic similarity.
- Render actual files as small matte painted beads, actual hubs as larger beads with one thin equatorial marker each. Start with file radius 4.5 and hub radius 9. Use instanced spheres and instanced torus markers, not new data objects. Markers are not separate pick targets.
- Use hemisphere fill, warm directional key and cool directional rim. Keep restrained roughness and near-zero metalness. No shadows, bloom, fog, textures, starfield, post-processing, continuous drift or automatic orbit.
- Labels show the real group name and membership count, with a lighter visual footprint and a 44px hit area. Preserve collision culling, the selected/focused label, semantic keyboard mirror and full-path disclosure. Show at most 12 floating group labels on desktop and 4 on phones. Sidebar access remains complete.
- Selection brightens real memberships and dims unrelated connections. Keep exact file identity, multi-group membership, open/copy behavior and the existing selection semantics.
- Fit includes the enlarged selected glyphs. Use a more side-on initial view on narrow screens so the wider world does not become a flat strip. Preserve orbit, pan, wheel/pinch zoom, zoom buttons and reset. Do not animate the camera or interfere with wheel gestures.

## One authored entrance

A first direct 3D entry gets one roughly 900ms assembly: file beads grow from 70% to final size, hubs and their markers settle, and real membership lines strengthen. Final positions already exist, so data and picking never wait for animation. No beads begin at zero size.

The entrance runs at most once per page load. Any pointer/key/search input, resize, hidden/offscreen state, disposal or live reduced-motion change finishes it immediately. Keyboard entry and reduced motion show the final scene instantly and consume the entrance allowance. Atlas-to-Graph already has the approved name gather: suppress the new entrance for that handoff rather than stacking animations. Missing GSAP shows the complete real 3D scene immediately. Missing or lost WebGL keeps the existing honest 2D fallback.

## Performance and lifetime

Use the existing local Three.js r180, matching OrbitControls and GSAP 3.15.1. Keep DPR capped at 1.5. On the current 689-file snapshot, target at most 6 draw calls, 250,000 triangles, fewer than 10 geometries, zero textures and no post-processing. Target 60fps during entrance and orbit; simplify if measured desktop timing falls below 50fps. Render on demand, with zero scene draws at settled idle and offscreen. Dispose every new geometry/material and cancel animation on teardown. Physical-phone performance must not be claimed from browser emulation.

## Implementation boundary

- `visual-second-brain/assets/constellation.js`: decorative 3D placement, instanced geometry/material/light changes, labels, bounded interruptible entrance, accurate bounds and resource cleanup. Preserve `hubPoint()` for the existing gather.
- `visual-second-brain/visual-second-brain.html`: 3D label styling if needed, entrance permission at the existing mount, changed-module cache version. Do not rewrite Atlas or 2D code.
- Existing constellation tests and actual browser interaction prove identity, membership, finite deterministic positions, controls, focus, fallback and lifetime. Add a small regression test only for an uncovered consumer-visible edge.
- Update README, DESIGN.md and department routers with the implemented contract and measured evidence.

## Study and approval

`mockup.html` is an isolated real-WebGL study, not production. Its reduced review chrome and Replay control are not proposed production UI. `study-data.json` includes only the current indexed paths, names, groups and decorative coordinates; no previews or file bodies. The study uses the actual 689 file identities, 17 groups and 1,088 membership edges. Its selected-file panel is explicitly a study and cannot open or copy files. Loading, empty and unavailable examples are labelled demonstrations, not fabricated live states.

Review the dark/Paper, desktop/phone and selected states, motion, budgets and eval cases before production edits. Detailed acceptance is in `eval.md`.

## Approval

The user approved these requirements, the interactive study and all ten acceptance cases on 2026-11-13, with no requested changes. Only the existing 3D section is authorized for implementation.
