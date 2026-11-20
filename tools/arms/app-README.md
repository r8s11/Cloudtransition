# ARMS review app and clipper

A local micro app for the weekly workspace review, plus an unpacked Chrome extension
for clipping selected text. Python standard library and vanilla JS only; no paid model
calls, no network access beyond `127.0.0.1`, no external assets.

## Start

```bash
python3 tools/arms/app.py                       # http://127.0.0.1:8790/
python3 tools/arms/app.py --port 8800           # other port (0 = any free port; the URL is printed)
python3 tools/arms/app.py --data-dir /tmp/arms-smoke --root /tmp/fixture-root   # throwaway smoke run
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--port` | `8790` | TCP port. The server always binds `127.0.0.1`; there is no host flag. |
| `--data-dir` | `tools/arms/data` | Where the app reads `routines.json` and keeps `feedback.json`, `cart.json`. |
| `--root` | repository root | Workspace root passed to `second-brain/brain.py --root` and `routines.py --root`. |

Stop with Ctrl-C. A port already in use exits with the OS error; pick another `--port`.

## What the page does

1. **Routine report**: renders `<data-dir>/routines.json` (written by `routines.py`): checks, routine inventory, session usage. Missing file shows "not generated yet"; unknown numbers show `unknown`, never 0. The *Refresh report* button runs exactly
   `python3 tools/arms/routines.py run --root ROOT --output <data-dir>/routines.json`
   (deterministic checks; no agent, no paid model). Nothing else can be run from the page.
2. **Suggestions and cart**: tick suggestions into a persistent cart, add a comment to each, then *Copy selection as Markdown* (optionally with parked feedback). Suggestions are proposals only; `proposed_action` text is displayed, never executed.
3. **Memory**: *Search* calls `python3 second-brain/brain.py --root ROOT query QUESTION`; *Save* calls `... remember --title=T --summary=S --body=B`. Stale or missing index states are shown with the exact rebuild command (`python3 second-brain/brain.py index`); the app does not rebuild it.
4. **Feedback parking**: record a target skill plus a principle and/or comments. Items can be marked reviewed, dismissed or re-parked in the page. **The app never edits skill files.** Applying a principle is a separate, explicit, reviewed step by the assistant; it is then recorded with the CLI below.

Keyboard: `/` focuses memory search, `Ctrl/⌘+Enter` submits the focused form, all controls have labels and visible focus. Layout is responsive (steps become a scrolling row under 900px) and follows `dashboard-app/DESIGN.md` tokens (vermilion ground, washi faces, sumi ink, gold step dot, no animation beyond reduced-motion-safe state changes).

If `artifacts/index.html` exists the masthead shows an *Artifacts* link; the app serves `/artifacts/<path>` read-only from `<repo>/artifacts` (extensions `html css js svg png jpg jpeg webp woff2 txt json pdf`; no dotfiles, no traversal). HTML/CSS/JS artifacts are served with `default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'` (inline script/style work, but nothing can reach the network); PDFs get only `frame-ancestors 'none'`. The target-skill suggestions list skill directory names (never contents) from `<root>/.claude/skills`, `<root>/.agents/skills` and `~/.omp/agent/managed-skills`.

## Feedback CLI (same store as the page)

```bash
python3 tools/arms/app.py note --target frontend-design --body "Buttons need 44px targets" [--principle "Touch targets >= 44px"]
python3 tools/arms/app.py notes [--status parked|reviewed|dismissed|resolved|all] [--target SKILL]
python3 tools/arms/app.py resolve fb-0123456789ab --resolution "Applied after review" --user-approved [--applied-principle TEXT]
python3 tools/arms/app.py resolve fb-0123456789ab --outcome dismissed --resolution "Not wanted"
```

All commands accept `--data-dir`, print one JSON object and exit `0` (ok) or `2` (error JSON `{"status":"error","error":...}`). `resolve` with the default outcome `applied` **requires `--user-approved`**, which asserts that the user explicitly approved applying the principle; it only records the outcome and edits no file. Resolved/dismissed-by-CLI items are closed records (the page cannot reopen them).

### `feedback.json`

```json
{"version": 1, "items": [{
  "id": "fb-0123456789ab", "created_at": "ISO-8601", "updated_at": "ISO-8601",
  "target_skill": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,79}$", "principle": "<=300 chars, one line",
  "comments": "<=4000 chars", "status": "parked|reviewed|dismissed|resolved",
  "applied": false, "user_approved": false, "resolution": "", "applied_principle": "", "resolved_at": null
}]}
```

`cart.json` is `{"version":1,"updated_at":…,"items":[{"suggestion_id":"sug-…","comment":"<=2000"}]}` (max 100). Both files are written atomically (temp file + `os.replace`, mode 600) under a process-shared file lock, so the server and the CLI cannot interleave writes. Data files are local state: do not commit them.

## Security boundary

* Binds `127.0.0.1` only. `Host` must be `127.0.0.1:<port>` or `localhost:<port>` (blocks DNS rebinding); a present `Origin` must be the same origin; `Sec-Fetch-Site` other than `same-origin`/`none` is rejected. There is no CORS.
* Mutations (`POST`/`PUT`) require `Content-Type: application/json`, a `Content-Length` of at most 64 KiB and a JSON object with only known fields; every field is length- and character-validated.
* Subprocesses use fixed argument arrays (`shell=False`, no stdin, timeouts, 1 MiB output cap, minimal environment). Browser text is passed only as a single `QUESTION` argument (not allowed to begin with `-`) or `--key=value` pairs, never as a command.
* Source text (report, memory evidence, feedback) is inserted with `textContent`; responses carry a strict CSP (`script-src 'self'`, no inline script or style), `nosniff`, `no-store`, `X-Frame-Options: DENY`.
* Single user, no authentication: other local processes running as you can still call the loopback API. Do not expose the port with a tunnel or `--host` hack.

## Clipper (`tools/arms/clipper/`, unpacked Manifest V3 extension)

One job: when you press **Capture selection** in the popup, the extension reads the selected text, page title and URL of the *current tab only*, shows the Markdown, and downloads it as `arms-clips/<YYYYMMDD-HHMMSS>-<ascii-slug>.md` when you press **Download .md** (Chrome's save dialog opens). Markdown has YAML front matter (`title`, `source`, `captured`, `type: web-clip`), the source URL and the selection as a blockquote. URL credentials and `#fragment` are removed; only `http(s)` pages are clippable.

Permissions: `activeTab`, `scripting`, `downloads`. No `host_permissions`, no content scripts, no background worker, no network requests. Chrome grants `activeTab` only after you open the popup on that tab.

**Installation is manual and is not done by this repo or the app:**

1. Open `chrome://extensions`, enable *Developer mode*.
2. *Load unpacked*, choose the `tools/arms/clipper` folder.
3. Pin *ARMS Clipper* if wanted. Remove it any time from the same page.

Limits: selection of the top frame only (not iframes), at most 100,000 characters (truncation is noted in the file), pages Chrome protects (`chrome://`, Web Store) cannot be read. Moving a clip into memory is a separate, explicit step (e.g. paste into the page's *Save a memory*).

## Tests

```bash
python3 -m unittest tools/arms/test_app.py -v
```

Starts the server on a random port with a temp root/data dir and stand-in `brain.py`/`routines.py` scripts, and checks observable behaviour only: loopback bind, Host/Origin/Sec-Fetch rejection, JSON/size/field validation, that no command, path or root can be supplied by the browser, memory status/exit-code mapping and input validation, durable feedback shared between server and CLI, the approval requirement, skill files left untouched, cart Markdown, artifact serving/confinement (including PDF), known-skill name discovery, and (if `node` exists) the clipper's real Markdown and filename generation. It does not assert on mocked command echoes or on source text; the extension itself is validated by loading it in a browser.
