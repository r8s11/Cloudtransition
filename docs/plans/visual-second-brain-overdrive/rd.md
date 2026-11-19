# Visual Second Brain — Folded Atlas

## Request and decision

Original request, verbatim:

> overdrive @visual-second-brain/ use it with  /skill:webgl-3d-object

The user selected **Folded Atlas** from three Overdrive directions on 2026-11-12. This approves the direction, not the implementation or the acceptance evals.

## Intent

Enhance the existing Workspace map with one real, lit, folded-paper WebGL object. The map remains a practical, private file-finding tool. Preserve its paper-and-vermilion identity, existing copy, index schema, filtering, file details, and safe file access.

The rendered incumbent at `/workspace-map/` is authoritative. The root PRODUCT.md describes the neighboring Command Center and includes historical details; it is not a reason to replace this map's current identity.

## Requirements

- **A — Composition:** Place one folded-paper sculpture beside the topic index on desktop. Keep the existing masthead, search, filters, topic/folder entry points, snapshot information, and file list primary. The sculpture must not become a marketing hero or obscure a control. Preserve existing topic cards, result row density settings, and meaningful content.
- **B — Real geometry:** Use a perspective camera, an actual folded mesh, a PBR material, directional light, and ambient or hemisphere fill. Form must read through crease geometry and light, not bloom, particles, or CSS 3D tricks.
- **C — State response:** Selecting a topic updates the sculpture's orientation or selected facet with a short, interruptible transform transition. Do not imply that facets encode real file relationships or topic counts. Search and all filters continue to use the existing state and ranking; the sculpture is not another source of truth. Use the neutral pose for folder browsing or no topic.
- **D — Motion and lifecycle:** Allow subtle, bounded desktop rotation and floating only while visible and idle. Pause movement while typing or using results/details. Provide a discoverable Pause motion control, honor reduced motion, and show a compact static composition on phones. Pause rendering when hidden or offscreen; handle resize, context loss, and teardown without leaking GPU resources. Lazy-load enhancement after the useful map is ready. Cap pixel ratio at 1.5 or lower on constrained devices.
- **E — Progressive enhancement:** Missing WebGL, an unavailable local module, or context loss must leave the normal map usable. Show a static geometric fold, or omit it cleanly when space is tight. No repeated recovery loop and no user action required to search. Do not present a decorative failure as an index failure.
- **F — Offline and privacy:** Ship any library locally, with its license. No CDN, remote fonts, analytics, providers, uploads, new storage, write endpoints, index schema changes, or index regeneration as part of this enhancement. Continue to use only the curated snapshot. Preserve separate dashboard and standalone capabilities.
- **G — Accessible and responsive:** Preserve keyboard shortcuts, HTML topic buttons, result navigation, focus restoration, readable contrast, and existing screen-reader names. Treat the decorative canvas as hidden from accessibility; expose motion control as a standard button with its state. At 390px and at 200% zoom, do not force horizontal scrolling or push useful search/results below a large visual.
- **H — States:** Keep truthful loading, missing/malformed/outdated/empty-index, no-match, stale-snapshot, and file-detail/copy feedback. The sculpture never promises a live index or successful operation before data is available.
- **I — Performance:** Target 60fps on the inspected desktop, simplify if sustained animation falls below 50fps. Test a real available phone/tablet if accessible; otherwise disclose the missing device proof rather than infer it from emulation. Search must not wait for WebGL initialization, model animation, or a topic transition. Large result lists remain virtualized.

## Approaches considered

1. **Folded Atlas — selected.** One paper object supports the existing index. Lowest GPU cost and implementation complexity of the three directions; mobile stays compact and static. Keeps conventional file finding intact.
2. **Topic Archipelago — not selected.** Sculpted topic islands would create a more immersive map, with greater GPU cost, labeling complexity, and navigation risk.
3. **Kinetic Index — not selected.** A small specimen with animated list transitions would be less disruptive, but the sculpture would have less presence.

## Proposed implementation boundaries

Primary source: `visual-second-brain/visual-second-brain.html`. Add local enhancement assets only as needed. Do not modify `refresh-index.py`, `workspace-index.json`, or dashboard file authorization for visual work. Confirm local asset routing before choosing their location. The current HTML has no build step or typecheck; preserve that operating model.

A 280–340px desktop sculpture rail is proposed, collapsing before the map becomes cramped. On phone use a compact fold at most 96px high or omit it in result/detail views. Retain the 56px virtualized result-row contract unless a separately verified layout correction requires otherwise. These values are proposed design decisions, not prior user requirements.

## Mockup and review scope

`mockup.html` is a self-contained static design study, not the product implementation. Its fold is a geometric pose diagram, not evidence that real WebGL rendering exists. The runtime object will use real geometry after approval. The study includes overview, selection/results, loading, no-match, unavailable-index, copy feedback, fallback, and phone composition.

Review the requirements and `eval.md` together. No app code changes before explicit approval.
