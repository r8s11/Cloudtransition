# Folded Atlas

## Visual authority

Preserve the Workspace map's existing Orizuru paper-and-vermilion world. The user selected Folded Atlas on 2026-11-12 and approved its requirements, evals, and static study before implementation. This is an enhancement, not a replacement visual identity. The root product context describes a neighboring dashboard and does not override the actual map.

## Color and type

The CSS variables in visual-second-brain.html remain authoritative: paper `#f8f1e3`, high paper `#fdf9ef`, deep paper `#efe3cd`, folded paper `#f4ead8`, ink `#211d18`, secondary ink `#4f483c`, muted ink `#554d41`, border `#d8c9ab`, and vermilion `#b3212e`. Retain Inter and the existing JetBrains Mono treatment for paths and numeric data. Do not add a display face or change the palette because a detector considers these choices common.

## Composition

On the Atlas root, Opening Fold places a display statement beside a 420×340 sculpture and gives the tiles the full width below. In list states, viewports at least 1100px wide retain the 344px right gutter and 288×292 sculpture rail. Topic tiles keep existing density controls and responsive grid behavior. The rail scrolls with the main area, so moving it offscreen can stop rendering.

Narrower viewports show a compact static fold, at most 96px high. Results and details omit this compact visual. On desktop, file details also hide the rail and reclaim its space. The sculpture sits outside the virtualized rows; their 56px positioning contract remains unchanged.

## Object and lighting

Six non-indexed triangles form a folded sheet with an actual front ridge and recessed lower planes. Four paper facets and two vermilion underside facets use rough, nonmetallic MeshStandardMaterial. PerspectiveCamera, a warm directional key, and hemisphere fill reveal the folds without bloom, particles, environment downloads, or textures. One 512px shadow map gives a restrained ground shadow. DPR is capped at 1.5.

The static SVG is an exact geometric fold diagram used only when no GPU scene exists. It is never passed off as the requested real WebGL implementation. Canvas and diagram are decorative and hidden from the accessibility tree.

## Motion

One short, interruptible topic-pose transition takes 220ms with exponential ease-out. Topic poses are decorative and do not represent topic counts, similarity, or importance. Latest state wins.

Idle rotation and floating stay bounded, rather than turning the sheet continuously. Search focus, result work, and file details quiet idle movement. Pause motion is a normal keyboard-operable button with an explicit pressed state. Reduced motion applies live and disables animated transforms. Phone composition stays static regardless of preference.

## Failure and lifecycle

Useful map content paints before the optional scene loads. The locally shipped Three.js r180 modules initialize only when the wide-screen sculpture is visible. Missing imports or GPU failures leave the static fold and the complete core app intact. Context loss ends that scene without retrying. Hidden, offscreen, and back/forward-cache pages suspend rendering. Resize is observed. Full teardown aborts listeners, disconnects observers, cancels the frame, disposes geometry/material/shadow/renderer resources, and releases the context.

## Boundaries

The curated snapshot remains the only data input. No external runtime service, persistent scene state, new write route, index regeneration, or authorization change accompanies this visual layer. The dedicated asset mount serves only assets shipped with the app, with symlink following disabled. Keep license and pinned distribution together.

## Graph view (2026-11-12)

The user approved an additional Graph view, then requested a dark background and supplied five constellation/node-card references. Atlas remains unchanged and is still the default. This is an original composition, not a copied frontend: Knowledge Graph Kit has no frontend.

Graph uses a dark navy field (`#141e29`), a compact topic/folder sidebar, six stable cluster colors, fine membership links and the existing detail drawer. A Paper background toggle returns the graph and drawer to the incumbent palette. Only Graph owns these overrides; the dashboard shell and Atlas retain their existing identity.

Every matching indexed file appears once. The 2D renderer uses a stable sunflower layout without a perpetual force simulation. A file links to all its indexed topics, or to its top-level folder in Folders grouping. Colors identify primary membership; positions never imply semantic similarity, importance, memory temperature or AI confidence. We do not invent people, causal links, embeddings or relationships from the reference images.

SVG remains the independent 2D renderer and keyboard-semantic source. Labels stay screen-sized under zoom; below 30% zoom, 2D hub labels yield to small colored markers and the accessible group list. Focus/hover reveals a label. Arrow navigation recenters the focused node, and Enter/Space opens its existing drawer. Touch supports one-pointer pan and two-pointer pinch in 2D. The later Depth Constellation approval adds an optional GPU representation without changing these file semantics.

Pointer hover and keyboard focus trace only real index memberships: a file emphasizes its linked group hubs and edges; a group emphasizes its member files and edges. Unrelated nodes and links recede. Selection and keyboard focus take priority over pointer hover. Emphasis responds only to interaction; there are no idle flows, weighted links, or animated packets.

The existing snapshot, privacy policy, routes and refresh command remain authoritative. URL state adds only `view=graph`; background choice is page-local. View teardown aborts pointer/keyboard/wheel handlers and disconnects its ResizeObserver. Acceptance and representative visual study: `docs/plans/workspace-graph/`.

## Restrained app motion (2026-11-12)

The user approved the motion study and CSS/WAAPI approach in `docs/plans/workspace-map-motion/`. The cinematic skill supplies restraint and choreography, not a scroll-story framework: native scrolling and graph wheel gestures remain untouched.

Extend the existing `--ease` with `--motion-fast: 120ms` and `--motion-panel: 220ms`. Opening Fold supersedes the original once/page Graph opacity entrance with the state handoffs below. Pointer drawer entry/exit still uses opacity and a 3% rightward translation, 220ms in both directions; keyboard and programmatic handoffs remain instant. Pointer-only graph controls press to 0.97 over 120ms.

Reduced motion retains only opacity, 120ms. Live preference changes, keyboard input, graph gestures and page/view teardown cancel decorative work. Focus never waits for animation. Closing details become inert immediately; revision-guarded completion prevents an older exit from hiding a newly opened file. WAAPI absence leaves final usable states, never hidden content. Atlas's existing GPU scene and motion policy remain unchanged.

## Depth Constellation (2026-11-13)

The user selected real spatial depth over semantic-zoom cards or shared-element inspector effects, then approved `docs/plans/workspace-depth-constellation/`. Graph now prefers 3D with an explicit 2D choice; Atlas remains default. The dark/Paper identity, current index, file actions and approved keyboard/pointer motion are unchanged.

Instanced lit file/hub meshes and batched lines render actual index memberships. Stable sphere-like clusters provide spatial separation; depth is not a semantic metric. Keep the current six membership colors, modest hemisphere/key lighting and crisp screen-space hub/focus labels. No decorative starfield, bloom, textures, auto-spin, damping or continuous physics competes with file finding.

Drag orbits, wheel/pinch zooms, and right-drag/two-finger touch pans. Fit frames the result. Pointer picks resolve the real instance path; keyboard navigation remains immediate through the existing semantic graph, with visible focus feedback. Choosing 2D avoids scene loading; loading or failure leaves a usable SVG rather than a blank field.

The local r180 Three.js distribution owns no workspace data. A separate scene controller consumes the existing layout and delegates picks to the map. Draw only on invalidation, coalesce RAF, cap DPR at 1.5 and suspend hidden/offscreen work. Dispose controls, GPU resources, observers and listeners on replacement; reject or dispose late initialization. Missing modules, WebGL2 failure and context loss give an explicit 2D status with no automatic recovery loop. Device/GPU performance claims require the evidence recorded with the approved eval.

## Opening Fold (2026-11-13)

The user approved `docs/plans/workspace-opening-fold/`, including local GSAP rather than native-only handoffs. Mode remains Operate: no marketing CTA, new font, generated imagery, smooth-scroll engine or ScrollTrigger. The six-triangle paper sheet is the only hero asset.

The root heading states actual result and tile counts; vermilion marks the numbers. Inter at up to 84px, weight 650 and tracking -0.03em supplies one display moment. A supporting line names the largest current groups and latest change. Filtered/list/detail states keep compact context. Phones use the same statement with the existing static fold and no GPU scene.

A once/page intro folds the actual mesh from flat into its unchanged approved vertices, rises the heading words and deals the tiles. Search and controls never wait. Pointer topic handoffs carry a word-sized name box between tile and heading, glide the sheet between cover and rail, and settle the visible rows. Graph handoffs match names to real hub keys and projection; slow/unavailable projection fades the copies in place without blocking Graph.

The usable still frame stays visible while the optional GPU initializes. Desktop choreography starts on scene readiness (including failure), so shader compilation cannot stall the fold. Input cancels a pending intro. Gather reuses captured word rectangles rather than interleaving layout reads and tween writes; hub projection waits for the current stage size. Keyboard tile activation transfers focus directly to the first new row or child tile.

One GSAP context owns each handoff. Interruption reverts transient styles, removes copies, completes the fold and cancels pending frames. No timeline owns file data, focus or virtual row offsets. Keyboard is instant. Reduced motion skips transforms, keeps the fully folded sheet and permits only 120ms opacity. The existing drawer/press system remains independent. Changed module imports carry an explicit version query so existing browser caches cannot mix old controllers with the new caller.

GSAP and Flip 3.15.1 are pinned beside Three.js, with their own Standard License attribution. Missing motion libraries show final content immediately; missing/lost GPU retains the static fold. Existing resource disposal, visibility guards, privacy boundaries and safe routes remain authoritative.

## 3D Observatory (2026-11-13)

The user explicitly limited overdrive to the 3D section, selected the Observatory direction and approved `docs/plans/workspace-3d-observatory/`. Atlas, Opening Fold, the independent SVG renderer, page chrome, file actions and privacy boundaries are not redesigned.

Expand the deterministic hub field horizontally and in depth while keeping local file clusters near-spherical. Files use matte radius-4.5 instanced spheres; hubs use radius-9 spheres and one thin instanced ring each. Hemisphere fill, a warm key and a cool rim replace the flatter lighting. Keep the six existing membership colors. There are no textures, post-processing, bloom, shadows, fog, starfields, auto-orbit or permanent motion.

Screen-space labels separate the real name and monospaced count, with a thin membership-color rule and the existing 44px hit target. Retain collision culling, 12-desktop/4-phone caps, complete sidebar access and the semantic keyboard graph. Selection highlights real memberships and recedes unrelated glyphs. Production keeps its existing selection accent and per-membership line colors rather than the study's neutral line treatment.

The 3D focus readout presents the selected file's actual type, name and relative path; group focus shows its name and indexed count. Its thin membership-color rule borrows the reference's callout hierarchy in the existing paper palette. Pointer changes reveal it over 140ms; keyboard, reduced motion, missing GSAP and interruption settle instantly. Hover/focus emphasizes actual incident membership edges and connected nodes in both renderers, receding unrelated links without adding idle animation or inferred relationships.

The first direct 3D load assembles glyph sizes and line strength over approximately 900ms; actual positions and nonzero pickable geometry exist immediately. Initial layout observation precedes this entrance. Real input, window resize, active-scene resize, hidden/offscreen state, reduced motion or disposal completes it immediately. GSAP's frame renders directly rather than scheduling a second RAF, which otherwise halves visible cadence. The existing Atlas gather suppresses this entrance. Keyboard/reduced-motion entry and missing GSAP show final states.

Fit measures actual glyph bounds, including selection enlargement and hub markers. Narrow scenes start side-on; explicit Fit preserves the user's current viewing direction. New geometry, materials, instances and animation belong to the existing scene lifetime. The 689-file snapshot stays at five draw calls, 217,200 triangles, five geometries and zero textures, with DPR capped at 1.5. See the feature's evidence for measured timing and device limitations.
The 3D graph shell keeps its intrinsic minimum height so the complete phone canvas is reachable by scrolling instead of being clipped by the surrounding flex layout. This rule applies only while the 3D renderer is active; independent 2D sizing is unchanged.

## Spatial graph (2026-11-18)

The user asked the Graph section to follow the spatial FUI reference in `hompage/` (also the dashboard's Today face). The dark background becomes an optical void (`#04070d`) under cyan HUD hairlines: the graph panel and file drawer are frosted glass (`blur(20px) saturate(160%)`) over fixed cyan/blue/emerald light fields with a crosshair lattice, the panel carries two cyan corner brackets, and headings, sidebar, legend, buttons and 3D hub labels use JetBrains Mono kickers. Membership colours become azure, emerald, violet, amber, indigo and crimson (`--graph-c1…c6`), selection is bright cyan (`#9efaff`); the 3D scene reads these through the existing CSS variables. Paper background, Atlas, 2D semantics, layout and file actions are unchanged.

Two defects fixed with it: with nothing hovered, focused or selected, `updateHighlights()` copied every edge into the accent overlay, so the whole 3D graph drew in the accent colour and hid membership colours; and `.graph-focus` kept `display: grid` while `hidden`, leaving an empty chip in the stage corner.

### Search flythrough (2026-11-18, Overdrive)

Typing in the Graph search rebuilds the filtered 3D scene; the new scene now
starts from the previous camera pose and eases (700ms, ease-out cubic, rAF)
into the Fit framing of the matches, so each keystroke reads as a continuous
flight toward the result cluster. Enter in the search field lands on the top
match: it is selected in the scene and opened in the existing detail drawer.
Clearing the search flies back to the full framing. The flight is interruptible
by any pointer, key, wheel or zoom input (it cancels alongside the entrance);
reduced motion or a missing previous pose falls back to the instant Fit. The
2D renderer and Atlas are unchanged.

## Embedded navy (2026-11-18)

Inside the Command Center Workspace map tab (`html.embedded`), `:root.embedded`
remaps the washi tokens to the dashboard's navy panels and single orange
signal: masthead on `--paper-deep`, pressed segments filled orange with dark
ink, Paper-mode graph hues re-lit for navy. Standalone, the washi sheet is
unchanged.
