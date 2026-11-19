# Folded Atlas main-thread acceptance proof

Observed 2026-11-12. All listed measurements came from the actual browser or runtime; no screenshot study is treated as evidence of WebGL. The approved geometric SVG study is replaced by real folded BufferGeometry in the live desktop view.

## Case coverage

| Case | Observed result |
| --- | --- |
| U1 | PASS. Real scene rendered at 1440×1000 with 17 topic/untagged tiles and 542 of 542 files. Canvas 360×365 backing pixels for 288×292 CSS pixels (DPR 1.25). The first contentful paint was 192ms; the large Three.js module started at 193.1ms. atlas.js began loading at 179.3ms but never blocked useful content. Source inspection confirms PerspectiveCamera, six-triangle folded BufferGeometry, MeshStandardMaterial, DirectionalLight and HemisphereLight. Actual GL draw calls and rendered depth are captured separately from that source inspection. |
| U5 | PASS. `/` focused search. ArrowDown and Enter opened DASHBOARD.md details and focused its H2. Escape restored row 0 focus. Further Escape and Reset restored topics. The canvas/diagram is absent from the accessibility tree; the normal Pause motion button is present. Pause changed its label to Resume motion and aria-pressed to true; subsequent sampling found zero draw calls and zero pending frames. |
| F2 | PASS. At 390×844 the static fold measured 85px high, with no canvas and no Three.js request. Reduced motion changed live: its media query became true, motion control hid, draw count stayed unchanged across 350ms, and pending frames were zero. Changing back to no-preference restored the control without reload. |
| R4 | PASS. Production browser resource origins were exclusively http://127.0.0.1:8000. Only local atlas.js and vendor/Three.js modules loaded. Local/session storage both had zero entries. The curated index and indexer hashes match their pre-edit values below. The only backend change is a dedicated StaticFiles asset mount with follow_symlink=False; workspace-file authorization and index/scoping rules were not changed. Third-party code and MIT license are under assets/vendor/, which the existing index rule excludes. |
| D1 | PASS. The actual paper sculpture sits beside the existing topic grid, not above search. Inter, the paper/vermilion palette, topic labels, existing controls, footer, and tile-density behavior remain. Actual object lighting was tuned toward paper and its shadow restrained. Computed contrast: body 14.90:1, sculpture caption 8.04:1, masthead 5.55:1. Existing adaptive grid shows four columns at standard density on this desktop, rather than the study's three; retaining the incumbent density contract is deliberate. |
| D3 | PASS for the available browser surface. Actual browser captures at 390×844 and 768×1024 had no horizontal overflow, 85px static folds, no GPU canvas and no Three.js download. Real Chrome Page zoom was set to 200% through its Appearance settings, not CSS zoom or a viewport substitute: a 1440×1000 viewport became 720×500 CSS pixels with DPR 2.5, no horizontal overflow, and the static layout. The original 100% setting was restored. Embedded-pane proof is in regression-proof.md. Real phone/tablet hardware was not tested. |
| D5 | PASS for desktop and simulated lifecycle conditions; real-device status disclosed. Ten seconds of visible animation produced 583 callbacks, 58.30fps, median frame 16.7ms and p95 16.8ms. Five real input-to-result samples had 74.1ms median with motion allowed versus 69.8ms paused: 4.3ms overhead, below one 60Hz frame. Pause and reduced-motion states each stopped all draw calls and pending frames. Resize preserved the camera/canvas layout. Offscreen and teardown proof follows. |

## Offscreen regression found and fixed

The first observer tracked the entire rail. At Large tile density and 1440×500, the canvas stage ended at y=1, above the main scroll viewport beginning at y=123. A 5px sliver of the rail's button region still intersected the scroll viewport, so the old observer rendered 273 draw calls over 350ms. This was a real enhancement bug, not a test timing problem.

The observer now tracks the canvas stage. Repeating the same geometry yielded stage bottom y=1, viewport top y=123, zero draw calls over 350ms and zero pending animation frames.

## Hidden and teardown boundaries

The managed headless browser kept document.hidden false even when another target was brought forward. Do not claim that native tab visibility changed. A controlled script set document.hidden to true in the actual application world and dispatched visibilitychange. The application's real handler then produced zero draws and zero pending frames; the override was removed and visibilitychange dispatched again.

Lifecycle event checks used actual PageTransitionEvent dispatches. Persisted pagehide stopped pending frames without destroying the cached scene. A full pagehide disposed two geometries, five materials and one shadow render target, removed the canvas, released the GL context (isContextLost=true), and left zero pending frames. These are controlled lifecycle checks, not a claim that a physical device was backgrounded.

## Source preservation and delivery

SHA-256 before and after:

- workspace-index.json: `8e05f1037f33c36378ec140f9340260f5537ec1769d814a9489ee27f93278f81`
- refresh-index.py: `57cc924b1de850a64c6b53e30112a3f61e4502fd5c2e536164aa96c95f59e65a`

Vendored Three.js 0.180.0:

- three.module.min.js: `e2b5ee6bccd38fd6d8a2428546b83c5f2426d84b152ef82be8055556e3b40eb6`
- three.core.min.js: `61ba0df005b05991361d040d8ff670e1aadfd0ce7aeebd1fdb0725957a8957de`
- License: visual-second-brain/assets/vendor/LICENSE.three.txt.

Restarted the existing launchd dashboard after adding the asset mount. Production `/workspace-map/` rendered the real canvas; `/` and `/reader` returned HTTP 200. No JavaScript page errors were observed. Production page resources were same-origin only. Final screenshot is production-desktop.png. Default screenshot temporary storage ran out of space late in verification; the final screenshot had already been saved directly on the external workspace volume.

## Existing suite issue

Initial Visual Second Brain suite: 14 passing, one failure in Content.test_unicode_and_duplicate_names_keep_distinct_exact_paths. A one-off filesystem diagnostic showed that `café` was enumerated as `cafe` plus combining acute: strings differed, but NFC-normalized strings matched. This behavior comes from the filesystem, not the untouched indexer. The test now proves each absolute and relative indexed path identifies the intended original file, including both duplicate basenames, rather than pinning a Unicode normalization form. Production paths and indexer rules remain unchanged. Final map-suite status is supplied by the eval runner.

Dashboard regression suite: 320 passed in 11.62 seconds, before the isolated JavaScript visibility correction. No backend code changed afterward.

## Detector findings

Ran the Impeccable detector once over the changed product HTML and enhancement module. It warned about incumbent segmented-control padding, Inter and the cream palette. The palette/type are approved identity, not free design axes. Actual rendered text in Topics/Folders had 13.25px top and 14.75px bottom insets; Standard had 14px/15px. These measurements do not support its flush-wrapper warning. No unrelated controls were restyled.

## Evidence and scope

- main-proof.json contains measured values, input timing samples, keyboard observations, responsive states and actual zoom metrics.
- desktop.png and production-desktop.png show actual desktop rendering.
- responsive-390.png and responsive-768.png show viewport-emulated phone/tablet composition.
- native-zoom-200.png shows actual browser page zoom.
- regression-proof.md and failure-proof.md cover the other ten manual cases with supporting artifacts.

No real phone/tablet test was performed. Standalone font resource 404s are inherited and documented in regression-proof.md; optional modules load and no JavaScript exception occurred. No source data was regenerated, no provider used, and no privacy rule expanded.
