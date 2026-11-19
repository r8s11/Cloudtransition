# Image description coverage

Generated 2026-11-02 by `python3 tools/arms/image_descriptions.py inventory`. Built from file metadata and local SHA-256 only: no image was decoded or sent to a model. Regenerate after adding images or sidecars.

Scope: workspace-owned images. Sidecar rule, schema and prompt capture: [tools/arms/image-descriptions-README.md](../tools/arms/image-descriptions-README.md). No image or folder is moved. Captions are searchable machine descriptions in the sidecars, not repeated here.

## In scope: 4 of 4 images have a sidecar

- `dashboard-app/static/icon-180.png` (571 bytes, sha256 a6900d7c7d67)
  - sidecar: `dashboard-app/static/icon-180.png.md`
  - described by claude-haiku-5-5 (requested alias: haiku; actual model read from Claude CLI modelUsage); prompt: unknown
- `dashboard-app/static/icon-512.png` (2420 bytes, sha256 e9a7054987fd)
  - sidecar: `dashboard-app/static/icon-512.png.md`
  - described by claude-haiku-5-5 (requested alias: haiku; actual model read from Claude CLI modelUsage); prompt: unknown
- `la chispa.avif` (229198 bytes, sha256 b7730087c60f)
  - sidecar: `la chispa.avif.md`
  - described by claude-haiku-5-5 (requested alias: haiku; actual model read from Claude CLI modelUsage); prompt: unknown
- `resources/1779037629264.jpeg` (147924 bytes, sha256 078cc4a85388)
  - sidecar: `resources/1779037629264.md`
  - described (pre-existing sidecar, viewed by agent; see file); prompt: unknown

## Excluded (counted, never decoded, never uploaded, never captioned)

Only the unmodified Expo template originals were byte-hashed, locally, to prove provenance.

- `agentic-os/node_modules/`: not enumerated. Reason: dependency, build or generated output.
- `node_modules/`: not enumerated. Reason: dependency, build or generated output.
- `.git/`: not enumerated. Reason: hidden directory (tool-owned or generated).
- `.impeccable/`: 2 image file(s). Reason: hidden directory (tool-owned or generated).
- `agentic-os/.impeccable/`: 4 image file(s). Reason: hidden directory (tool-owned or generated).
- `IT Mgmt/.git/`: not enumerated. Reason: hidden directory (tool-owned or generated).
- `IT Mgmt/Employer-IT-Playbook-Private/`: 2 image file(s). Reason: name matches private/employer policy; contents are never decoded or uploaded.
- `College Planning/`: 110 image file(s). Reason: personal academic records; contents are never decoded or uploaded.
- `projects/rendercv/`: 66 image file(s). Reason: third-party project, not workspace-authored.
- `projects/ReactNative/Mytvapp/assets/images/ (only the matching files)`: 10 image file(s). Reason: unmodified Expo create-app template asset: SHA-256 equals the original in expo-template-default@54.0.63 (third-party/generated; local hash comparison only).
- 0 image files in 8 directories (`agentic-os/apps/api/dist/`, `artifacts/__pycache__/`, `dashboard-app/__pycache__/`, `dashboard-app/tests/__pycache__/`, `dashboard-app/venv/`, `second-brain/__pycache__/`, `second-brain/tests/__pycache__/`, `tools/arms/__pycache__/`). Reason: dependency, build or generated output.
- 0 image files in 26 directories (`.agentic-os/`, `.claude/`, `.codegraph/`, `.firecrawl/`, `.grok/`, `.playwright-mcp/`, `.pytest_cache/`, `.ruff_cache/`, `.superpowers/`, `.trail/`, `.vscode/`, `agentic-os/.agentic-os/`, `agentic-os/apps/api/.agentic-os/`, `agentic-os/apps/api/.impeccable/`, `dashboard-app/.agents/`, `dashboard-app/.claude/`, `dashboard-app/.pytest_cache/`, `dashboard-app/.ruff_cache/`, `dashboard-app/tests/.ruff_cache/`, `graft/.cache/`, `IT Mgmt/.claude/`, `IT Mgmt/.obsidian/`, `projects/ReactNative/Mytvapp/.vscode/`, `resume/.claude/`, `shared/.stfolder/`, `visual-second-brain/.ruff_cache/`). Reason: hidden directory (tool-owned or generated).
- 0 image files in 1 directory (`r8s11/`). Reason: standalone nested git repository (own .git); workspace ownership not established.
- 0 image files in 1 directory (`andrej-karpathy-skills/`). Reason: third-party project, not workspace-authored.
- Symlinked image files: 0. Reason: link targets may sit outside the workspace.
- Any other directory not listed above containing no images has nothing to describe.
