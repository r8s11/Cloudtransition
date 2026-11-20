# 3D Observatory evidence

Captured 2026-11-13 in Chrome 157.0.8103.51 on macOS arm64. These are real browser screenshots, not generated images. Generation prompt: not applicable. Generative image model: none. Source references: the approved `../rd.md`, isolated `../mockup.html` at `http://127.0.0.1:8012/mockup.html`, and production `http://127.0.0.1:8000/workspace-map/?view=graph`.

## Captures

| Image | Source and factual caption |
| --- | --- |
| `study-desktop-dark.png` | Isolated study, 1440x1000; widened real 689-file graph, matte glyphs and labels |
| `study-desktop-paper.png` | Same study and camera, Paper background |
| `study-desktop-selected.png` | Study pointer selection of the real `SQL/README.md` path and its memberships |
| `study-phone-dark.png` | Study at 390x844; side-on narrow-screen framing, dark background |
| `study-phone-paper.png` | Same phone study, Paper background |
| `study-unavailable-example.png` | Explicitly labelled study-only unavailable-state demonstration, not a live failure |
| `desktop-3d-dark.png` | Production 3D, 1440x1000, settled after the entrance |
| `desktop-3d-paper.png` | Production 3D with its existing Paper background and page chrome |
| `desktop-3d-selected.png` | Production native pick of `SQL/README.md`, with the existing drawer and safe file actions |
| `phone-3d-dark.png` | Production 390x844, reduced motion; cropped to the graph after the 3D-only shell-clipping fix |
| `phone-3d-paper.png` | Same production phone state with Paper background |
| `atlas-unchanged.png` | Existing Atlas root: real 689-file/17-topic cover and approved folded sculpture |
| `atlas-graph-gather.png` | Existing Atlas-to-Graph name gather landing on the new real 3D hub positions |
| `independent-2d-unchanged.png` | Existing independent SVG renderer, selected explicitly; 689 actual files and 1,088 memberships |
| `webgl-fallback.png` | Real WebGL2-denial fault injection; explicit unavailable status and usable existing 2D graph |

## Results and repeatable checks

- `browser-results.json`: production assertions, native pick/copy/open/download, keyboard, filters, empty state, camera fit, real loading/failure injection, handoff, resource disposal, contrast and timing.
- `study-results.json`: isolated-study measurements only, not production proof.
- `render-probe.js`: init-script observer of real Three.js render/disposal calls. It does not change scene data, geometry, controls or timing.
- `observatory-smoke.js`: run immediately after a fresh uninterrupted normal-motion desktop entrance with the probe installed. It catches an initial layout resize swallowing the entrance, zero/invalid glyph scale, nested-RAF cadence loss and GPU-budget regressions.
- `phone-smoke.js`: run on the settled 390x844 production graph. It catches a fitted canvas being clipped by its shell and horizontal page overflow.
- Automated geometry/privacy/syntax case results are recorded in `../eval.results.json` by the eval runner.

The entrance and orbit both measured approximately 60fps. The scene used five draw calls, 217,200 triangles, five geometries and zero textures at DPR 1.5. Settled idle and offscreen samples had zero additional scene draws. Ten 3D/2D replacement cycles disposed 50 geometries and 50 materials; root listener counts stayed equal and each disposed renderer reported zero remaining geometries.

Three regression checks failed before their fixes: initial layout observation cancelled the entrance, a second RAF reduced rendering to roughly 30fps despite a roughly 60Hz GSAP ticker, and the phone flex shell clipped the bottom of its fitted canvas. The checks passed after narrow fixes.

## Deliberate study differences

Production retains its real page header, filters, sidebar, drawer, safe file actions, selection accent and per-membership line colors. Study-only Replay and demonstration controls are not shipped. The phone shell grows to contain its canvas rather than cropping the world; only the active 3D class receives that sizing rule. Atlas and independent 2D code and appearance remain unchanged.

## Coverage limits

Phone dimensions are browser emulation, not physical iPhone/GPU evidence. The browser backend kept native `document.visibilityState` visible during attempts to background or minimize its window; native hiding is **not verified**. A separately labelled Page Visibility API simulation exercised the real hidden-state handler: the active entrance finished, all glyphs settled, and scene draws stopped, then resumed only for the settled visible state. Actual offscreen suspension was measured independently.

Console history contains the intentional GSAP request abort and an earlier test-probe import on `about:blank`; neither is an application exception. The saved probe now ignores non-map pages. The final production console sample contained no new errors.
