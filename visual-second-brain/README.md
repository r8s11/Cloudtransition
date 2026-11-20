# Visual Second Brain (Workspace map)

A local, private, offline map of this workspace. It lets you find files by topic, folder or name. It only reads files; it never changes them.

## Open it

- **Dashboard (usual way):** `http://127.0.0.1:8000/#workspace-map`, or the full page at `http://127.0.0.1:8000/workspace-map/`. The dashboard adds **Open** and **Download** buttons to each file.
- **Standalone:** serve this folder over loopback, then open `http://127.0.0.1:8765/visual-second-brain.html`:

  ```bash
  cd "/Volumes/SANDISK USB/work/Cloudtransition/visual-second-brain"
  python3 -m http.server 8765 --bind 127.0.0.1
  ```

  When it runs standalone, the map shows previews, paths and **Copy full path**, but it cannot open files. Opening the HTML with `file://` does not work because browsers block `fetch()` on that scheme. In that case the page shows the command above.

Deep links set the view: `?q=`, `?topic=`, `?folder=` (`.` means workspace root files), `?type=`, `?date=1|7|30|365`, `?group=folder`, `?view=graph`.

## Graph view

Choose **Graph** beside **Atlas**, or open `http://127.0.0.1:8000/workspace-map/?view=graph`. Atlas remains the default.

- Dark spatial background by default (optical void, frosted-glass panels, cyan HUD type, matching the dashboard's Today face); **Paper background** switches the graph and its file drawer without changing Atlas. Theme choice lasts for this page session.
- Each matching file appears once. Colors identify its primary topic or top-level folder. Lines connect it to every indexed topic, or its top-level folder when grouped by Folders. Topics are deterministic indexer tags, not semantic analysis.
- Hover or keyboard-focus a file or group to emphasize its actual membership edges and connected nodes; unrelated nodes and links recede.
- The group sidebar filters to a topic/folder and shows matching counts. On phones, expand its heading.
- In **3D**, drag to orbit; right-drag or two-finger touch pans. Wheel/pinch and **− / +** zoom; **Fit** frames the complete result. In **2D**, dragging pans the existing SVG. Zoom readouts describe the active camera.
- Click a file for the existing preview, paths, copy button and safe Open/Download actions. Keyboard: Tab into the graph, arrows browse files then hubs, Home/End jump, Enter/Space opens or filters, Escape closes details and restores graph focus.
- Search and all filters apply to both renderers. In 3D, typing flies the camera into the matching cluster (search flythrough) and Enter opens the top match. Graph prefers **3D** using locally shipped Three.js; **2D** explicitly avoids the GPU scene. Neither renderer runs an idle simulation.

This original visual layer borrows the graph concept from [Knowledge Graph Kit](https://github.com/GallagherSam/Knowledge-Graph-Kit) and the user's dark graph references, not its backend. It installs no server, database, embeddings or MCP tools. [Design and checks](../docs/plans/workspace-graph/) record the approved scope.

### Depth Constellation

The 3D renderer shows real instanced geometry, perspective, restrained lighting and membership lines. Depth and spacing are decorative layout, not inferred meaning. Nodes stay still until the camera is manipulated.

- `?view=graph&renderer=2d` requests the independent SVG renderer directly. Default Graph prefers 3D when available; Atlas remains the default map view.
- While a scene loads, the usable SVG remains. Missing modules, unavailable WebGL2 or a lost context restore 2D with an explicit status, not a fake 3D indicator or automatic retry.
- The existing SVG owns keyboard/file semantics even when 3D is visible. Keyboard focus gets a visible label/proxy; no duplicate canvas tab stops or delayed camera movement.
- Rendering is invalidation-driven, capped at DPR 1.5, and suspended when hidden/offscreen. Replacing a view releases controls, observers, GPU resources and pending work. Late initialization cannot attach a canvas to a removed view.
- The source index, exclusions, refresh command and safe file routes do not change. [Approved 3D design, study and checks](../docs/plans/workspace-depth-constellation/) record the scope and actual verification coverage.

### 3D Observatory

The 3D-only refinement widens the same real graph into near/middle/far clusters. Matte file beads, larger hubs with thin ring markers, warm key/cool rim lighting and lighter name/count labels make depth easier to read. The six cluster colors, dark/Paper backgrounds, sidebar, Atlas and independent 2D renderer are unchanged.

A direct 3D page load gets one approximately 900ms glyph-and-line assembly. Positions and picking are final from the start. Any input, actual window resize, hidden/offscreen state or reduced-motion change finishes it immediately. Initial layout measurement does not swallow the entrance. Atlas-to-Graph retains its existing name gather instead of stacking another intro. Without GSAP, 3D appears fully settled.

Fit includes enlarged selected glyphs and ring markers; narrow screens start from a more side-on view. Rendering remains on demand, with no idle drift. The current 689-file snapshot uses five draw calls, 217,200 triangles, five geometries and no textures. Physical-phone performance is not established by browser emulation. [Approved study, acceptance checks and measured evidence](../docs/plans/workspace-3d-observatory/).



## Motion

Opening Fold makes the Atlas root a cover: real file/group counts, the enlarged paper sculpture, and full-width tiles. List and detail states keep their compact headings and 56px rows. On phones the fold stays static.

On the first root load, words rise, the sheet folds and tiles deal out once. Pointer topic changes carry the name into the heading and the sheet into its rail. Returning reverses the handoff without refolding. Switching to Graph carries topic/folder names onto their matching real hubs; a slow scene never delays graph use.

Keyboard input, pointer presses, search, scrolling, resizing, live reduced-motion changes and page teardown cancel decorative work. Keyboard handoffs stay instant; reduced motion uses final states and at most 120ms opacity. Missing GSAP/Flip gives instant usable states. Missing WebGL leaves the static fold.

GSAP and Flip 3.15.1 are shipped locally under the retained GSAP Standard License. There is no ScrollTrigger, Lenis or smooth-scroll wrapper. Existing pointer drawer entry/exit remains CSS/Web Animations (220ms), and control press feedback remains 120ms. [Approved Opening Fold study and checks](../docs/plans/workspace-opening-fold/).

## Refresh the index

The map is a **snapshot**. New, moved or deleted files appear only after a refresh. From the dashboard, press **Refresh map** under Quick tools on Today (or Local tools on Run). From a terminal:

```bash
"/Volumes/SANDISK USB/work/Cloudtransition/dashboard-app/venv/bin/python" \
  "/Volumes/SANDISK USB/work/Cloudtransition/visual-second-brain/refresh-index.py"
```

It needs only the Python standard library: no pip, no npm and no network. A full run takes less than a second. If the workspace is missing (for example, the USB drive is unplugged) or the scan finds no files, the script exits with a nonzero code and keeps the previous index. Writes are atomic.

## Files

| File | Role |
| --- | --- |
| `visual-second-brain.html` | Core app: inline HTML, CSS and JS. File finding remains independent of WebGL |
| `assets/atlas.js` | Optional Folded Atlas scene, motion controls, visibility and GPU lifecycle |
| `assets/constellation.js` | Depth Constellation: pure spatial layout, instanced rendering, picking, controls and GPU lifetime |
| `assets/vendor/three.module.min.js`, `assets/vendor/three.core.min.js` | Locally shipped Three.js 0.180.0 (r180); excluded from future index refreshes by the existing vendor rule |
| `assets/vendor/OrbitControls.js` | Matching r180 mouse/touch camera controls, shipped locally under the retained Three.js MIT license |
| `assets/vendor/LICENSE.three.txt` | Three.js MIT license, retained with the pinned distribution |
| `assets/vendor/gsap.min.js`, `assets/vendor/Flip.min.js`, `assets/vendor/LICENSE.gsap.txt` | Pinned GSAP/Flip 3.15.1 and Standard License attribution; distinct from Three.js's MIT license |
| `DESIGN.md` | Folded Atlas visual rationale and implementation constraints |
| `workspace-index.json` | Generated index, schema version 2. It is the app's only data input |
| `refresh-index.py` | Rebuilds the index. The dashboard also imports its scope and privacy rules |
| `tests/test_refresh_index.py` | Scope, privacy and refresh-safety tests. Run them with `python3 -m unittest discover -s visual-second-brain/tests` |
| `tests/test_constellation.mjs` | Deterministic complete coordinates, real membership edges and immutable input checks |
| `tests/test_atlas_fold.mjs` | Approved final sculpture coordinates, flat/intermediate fold geometry and reusable output buffer checks |

## Folded Atlas

The optional folded-paper sculpture uses a real mesh, perspective camera, paper PBR materials, directional light, and hemisphere fill. It sits beside the index on wide screens. Topic selection changes its pose decoratively: the shape does not encode relationships, importance, or file counts.

- **Pause motion / Resume motion** controls desktop idle movement. Search, results and file details quiet the sculpture automatically. The motion preference is page-local, not saved.
- **Reduced motion** takes effect without a reload. Narrow screens use a compact static fold, omitted from result/detail views. No GPU scene or Three.js download is needed for the phone composition.
- **Offscreen and hidden pages** stop rendering. Resize is observed; leaving the page releases the scene's resources. A page retained in the browser's back/forward cache pauses and resumes instead.
- **No WebGL, missing module, or lost context:** the static fold remains. Search and file access never depend on the visual enhancement. There is no automatic recovery loop.
- **Offline:** all modules are local, with no external runtime requests. The dashboard serves the dedicated public `assets/` folder at `/workspace-map/assets/`; it does not broaden `/workspace-file/` access. Standalone uses the same assets directly.

The data remains the same privacy-filtered snapshot; this visual change does not refresh it. [Requirements, approved evals, and visual study](../docs/plans/visual-second-brain-overdrive/) record the design and acceptance contract.

## What is indexed

The configuration block at the top of `refresh-index.py` is the single source of truth:

- `INCLUDE_ROOTS`: the folders that the department routers link to (`OPERATIONS.md`, `CODE.md`, `MONEY.md`, `LEARNING.md`, `CONTENT.md`).
- Document, PDF and image files at the workspace root.

Everything else is excluded completely. Excluded files are never opened and never named in the index. They are only counted by reason in **About this snapshot**:

- Secret-looking names: `.env` and `*.env`, keys and certificates (`.pem`, `.key`, `.p8`, `.p12`, …), `*token*`, `*password*`, `client_secret`, `deploy_key`-style names, `kubeconfig`, Terraform state and variables (`.tfstate`, `.tfvars`), VPN profiles (`.ovpn`), and similar names.
- Private or employer folders and files.
- Work logs.
- `College Planning`, including copies nested deeper (for example `docs/backup/College Planning`).
- Dependencies and caches: `node_modules`, `venv`, `__pycache__`, build output and run logs.
- Hidden files and Office lock files (`~$…`).
- Generated outputs, including `artifacts/index.html` and this index.
- Vendored repositories.

Symlinks are never followed. Filename rules reduce the risk of indexing secrets, but they do not find every secret.

Topics come from deterministic word rules. They match the path and name, and fall back to preview text. A top-level folder also adds its department topic: for example, `resume/` adds **career**. Previews cover text files and image caption sidecars (`photo.png.md`). Other binary files show **Preview unavailable**.

## Dashboard file access

`/workspace-file/<relative path>` serves a file only when both conditions are true:

1. The file is in the current index, or it is a live artifact in `artifacts/`. New artifacts can be opened before a refresh.
2. The file still passes the indexer's rules when it is requested. The dashboard checks the approved root and excluded names, rejects symlinks anywhere in the path, and checks that the path stays inside the workspace.

Errors use these status codes: 403 for a denied file, 404 for a missing file and 503 for an index that is unavailable or outdated. HTML, SVG and XML files are served with a CSP `sandbox`, which blocks scripts, forms, popups and network requests. Source and text files are shown as plain text.

## Maintenance rule

The filesystem is the source of truth. Do not edit `workspace-index.json` by hand. Refresh the index after files move or the workspace changes substantially.
