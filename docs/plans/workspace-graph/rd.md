# Workspace map: Graph view

## Request and decisions

User: “incorporate this https://github.com/GallagherSam/Knowledge-Graph-Kit” followed by “the visuals”.

Approved direction (2026-11-12): add Graph alongside the existing Atlas, not replace Atlas. No MCP server, embeddings or database. The referenced kit has no frontend; this is an original node-and-edge interface inspired by its graph concept, not a copied UI.

## Design

- Add Atlas / Graph beside the existing Topics / Folders switch. Atlas remains the default; `?view=graph` opens Graph directly.
- Render every matching indexed file once. Folder hubs mean top-level folder membership; topic hubs mean the indexer's topic tags. Lines show only those memberships, never inferred semantic relationships.
- Preserve paper/vermilion tokens outside Graph. Graph starts with a dark background and offers a Paper toggle (user addition at approval). Use a stable clustered SVG layout, readable hub labels, file labels on focus/hover/selection, zoom, fit and pan. No perpetual simulation or new dependency.
- Reuse existing search, type/folder/date filters and file detail drawer, including copy path and safe Open/Download routes. Keyboard node browsing and touch pan/zoom must work; Atlas remains an accessible alternative.
- Empty results show existing clear-filter guidance. No filesystem, index schema, exclusions, server configuration or external service changes.

## Approaches

Selected: local SVG graph using current index. Keeps data and privacy rules unchanged. Rejected: installing the Python kit, which supplies no visuals and adds a second store. Replacing Atlas rejected by user.

## Implementation plan

1. Modify `visual-second-brain/visual-second-brain.html`: view state, switch, graph styles, SVG rendering and scoped input/lifecycle handlers. Reuse `VIEW`, `apply`, `openDetail`, `closeDetail` and `syncAtlas`.
2. Add a small deterministic layout test if logic is extracted; otherwise verify the inline graph through real browser assertions. Check duplicate file identities, real membership edges, filtering, keyboard, path actions, empty state, zoom and touch.
3. Update `visual-second-brain/README.md`, `DESIGN.md` and `CODE.md` in the same change. Do not rebuild the privacy-filtered snapshot for a visual-only change.
4. Run existing index regression tests and parse the inline JavaScript once. Batch desktop/phone browser proof; fix observed defects, then confirm once. No unrelated suites or dependency installation.
