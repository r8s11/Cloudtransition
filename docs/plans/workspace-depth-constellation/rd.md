# Depth Constellation

## Request and selected direction

User: “overdrive @visual-second-brain/”. Selected Depth Constellation: “A true 3D file galaxy: dimensional colored nodes, fine membership lines, orbit/zoom and crisp focus labels. Reuses locally shipped Three.js. Higher GPU cost; renders only when needed, with current 2D graph as fallback. No automatic spinning.”

The existing dark/Paper Graph and Atlas are visual authority. Mode: Operate. The signature upgrade is real spatial depth, not animated data, a new memory backend or inferred relationships.

## Design

- Keep Atlas default. Graph prefers 3D when supported, with visible 3D / 2D controls. A direct link can request `?view=graph&renderer=2d`; all other URL filters continue to work.
- Render every matching file once as an actual lit, instanced 3D mesh. Folder/topic hubs anchor the same real membership edges as 2D. Stable sphere-like cluster arrangements and depth are decorative placement only; positions never claim semantic similarity.
- Dark navy scene, current six membership colors, modest hemisphere/key lighting, fine lines and screen-sharp hub/focus labels. No bloom, textures, decorative stars, auto-rotation, perpetual physics, new fonts or changed factual copy.
- Drag to orbit, wheel/pinch to zoom, two-finger/right-button pan, Fit and existing zoom controls. Click a file opens its current drawer; click a hub filters using existing state. Hover can name a file without moving it.
- Keyboard stays immediate: existing node/hub semantics remain available, arrows identify/focus a real node, Enter opens, Escape closes and restores focus. A visible focus label/boundary accompanies the 3D representation. 2D remains an explicit accessible/low-power alternative. Do not create hundreds of extra HTML tab stops.
- Share search, type/folder/date filters, grouping, count, theme and safe path actions. Add no data source or new writable route. Empty results remain the existing honest empty state.
- Render only on invalidation (input, resize, theme or focus), coalesced with one requestAnimationFrame. No idle loop or momentum/damping. Lazy-load the existing Three.js r180; cap DPR at 1.5, use instancing/batched lines, avoid shadows/post-processing, and pause when hidden/offscreen.
- A missing module, WebGL2 initialization failure or lost context restores fully functional 2D with an explicit status. Never describe a fallback as real 3D. Do not retry automatically. Dispose geometry/materials/renderer/controls, observers, RAF and listeners when replaced or left. A late initialization must not attach to a removed view.
- Reduced motion keeps the same still 3D scene and direct manipulation; no animated camera transitions or idle movement. Preserve the approved pointer-drawer and once/page opacity policy, including keyboard and live preference cancellation.
- No package install. Reuse the local Three.js modules and license. If OrbitControls is needed, vendor only its matching r180 module under the same local asset mount and retain attribution. No remote runtime requests, changed scan rules, snapshot regeneration or exposure of arbitrary workspace files.

## Approaches

Chosen by user: Depth Constellation. Alternatives were SVG/HTML semantic zoom (less GPU, more label layout), and shared-element inspector transitions (lighter but less spatial spectacle). Do not mix those upgrades into this one.

## Implementation shape

- New `visual-second-brain/assets/constellation.js`: pure `constellationLayout(layout)` coordinates plus `async createConstellation(host, options)`, owning GPU/input/lifecycle only. Dynamic import of local Three.js. Layout receives existing `{groups, files}` from graphLayout with real keys, file objects, membership arrays, colors and 2D coordinates.
- Options: `{layout, dark, onPick, onZoom, onFailure}`. `onPick({type:'file',path}|{type:'group',key})` delegates to existing map actions; `onZoom(scale)` updates the real camera zoom readout. Failure callback identifies the fallback reason without a retry.
- Resolved controller: `{select(path|null), focus({type:'file',path}|{type:'group',key}), zoom(factor), fit(), theme(dark), destroy()}`. It never fetches workspace files, mutates source state or owns the drawer. `destroy` is idempotent; disconnected/late initialization rejects without a surviving canvas.
- `visual-second-brain/visual-second-brain.html`: renderer choice, stage wrapper, race-safe lazy mount, 2D/3D control routing, existing keyboard mirror/focus, and honest fallback status. Keep the existing SVG as the independent 2D renderer/semantic source. Do not copy search or file-opening logic.
- A small `tests/test_constellation.mjs` covers deterministic complete coordinates, duplicate/empty membership edges and stable path identity. Existing indexer privacy tests remain unchanged. Docs/routers update in the same change.

## Acceptance and proof

See eval.md and the self-contained real-WebGL composition study in mockup.html. The study is not the production implementation. Batch real desktop/phone layouts and GPU lifecycle/gesture tests; inspect actual frame timing during interaction. Target 60fps on available hardware, simplify below 50fps; never downsample files or claim physical-device coverage without running it.
