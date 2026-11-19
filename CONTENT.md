# Content & Visuals Index

Editable artifacts, drafts, prompts, reference material, and searchable image descriptions. Files stay in their existing folders; this router is navigation, not another content store.

## Start here

| Path | What | Use when |
| --- | --- | --- |
| `artifacts/` | HTML-first decks, infographics, reports and final exports | Creating or finding a finished artifact |
| `resources/image-coverage.md` | Image-to-sidecar coverage and exclusion reasons | Checking which images are searchable |
| `tools/arms/image-descriptions-README.md` | Caption and exact-prompt capture commands | Registering a new image or describing old ones |
| `artifacts/brand-book.html` | CloudTransition colors, type, spacing and identity rules | Matching the approved brand |
| `artifacts/index.html` | Searchable newest-first artifact inbox | Browsing HTML sources and exports |
| Dashboard **Today → Recent artifacts** | Eight newest `artifacts/` files, read live and opened sandboxed | One-click access to recent output |
| Dashboard **Workspace map** (`visual-second-brain/`) | Opening Fold Atlas cover, independent 2D Graph and 3D Observatory of curated files, with topic/folder filters, preview and copy-path | Finding files or exploring their indexed memberships |
| Dashboard **Today → Shortcuts** | Find-a-file field plus tiles for apps, key files and key folders (`SHORTCUTS` in `dashboard-app/app.py`) | Jumping to a file, folder or local app in one click |
| `drafts/` | Working drafts and reviews | Continuing unfinished writing |
| `prompts/` | Saved reusable prompts | Reusing a writing or generation brief |
| `resources/` | Reference images, caption sidecars, guides and templates | Finding supporting material |
| `resources/architecture-diagrams/` | Architecture diagrams | Explaining technical structure |
| `resources/templates/` | Reusable source templates | Starting from an existing pattern |
| `resources/guides/`, `resources/cheat-sheets/` | Guides and quick references | Looking up a procedure |
| `dashboard-app/static/` | Dashboard-owned icons and assets | Reusing existing product visuals |
| `la chispa.avif`, `la chispa.avif.md` | Loose root flyer and searchable description, kept in place | Finding the original asset or its visible text |

## Image description contract

Every workspace-owned image has a linked Markdown sidecar beside it. Preserve existing sidecars; prefer `<image-filename>.md` for new ones so `cover.png` and `cover.jpg` cannot collide. The sidecar records:

- A relative link to the image and a factual, searchable description of visible content.
- The exact generation prompt and actual generator model when known; otherwise **Original prompt: unknown**. A caption is not an original prompt.
- Caption source, actual model and date. Model captions are machine descriptions, not manually verified facts; flag uncertainty and unreadable text.
- Source/reference links when known. Do not infer creator, ownership, identity or licensing from the picture.

For new images, save the exact prompt at generation time alongside the output, before declaring the artifact complete. For old images, use a verified low-cost vision model and preserve existing verified descriptions rather than paying to regenerate them.

Only workspace-owned, non-sensitive images are in the approved caption scope. Record vendor, dependency, build output, saved web-page asset and private exclusions explicitly; do not send employer material or personal academic records to a cloud model. No image or folder is moved by this workflow.

Capture a new image's prompt with `python3 tools/arms/image_descriptions.py register IMAGE --prompt-file PROMPT.txt --model GENERATOR_MODEL`. The prompt file must contain the exact text sent to the generator; a description written afterward is not provenance. The helper refuses to overwrite an existing sidecar.

Run `python3 tools/arms/image_descriptions.py describe` for a dry run, or add `--run` to caption missing descriptions using the low-cost model. Run `python3 tools/arms/image_descriptions.py inventory` to refresh [coverage](resources/image-coverage.md). See the [command guide](tools/arms/image-descriptions-README.md) for model verification and exclusions.

## Search and maintenance

- Search sidecars as ordinary text; use `python3 second-brain/brain.py query "question"` for curated references.
- Run `python3 second-brain/brain.py index` after descriptions change; run `python3 artifacts/catalog.py` after artifact saves/exports (the dashboard's Recent artifacts list is live and needs no rebuild); run `python3 visual-second-brain/refresh-index.py` after files move so the Workspace map stays current.
- Existing verified example: [Cybersecurity templates infographic](resources/1779037629264.md).
- Root map: [AGENTS.md](AGENTS.md). Source-code work: [CODE.md](CODE.md). Study references: [LEARNING.md](LEARNING.md).
