# Verification record — 2026-10-28

Evidence for the two guides as built in this workspace. Everything below was run, not inferred, unless marked **not verified**.

## Second Brain (`second-brain/`)

| Check | Command | Result |
| --- | --- | --- |
| Boundary tests | `python3 -m unittest discover -s second-brain/tests` | 23 passed |
| Index | `python3 second-brain/brain.py index` | 138 sources, catalogue ~82 KB, postings ~1.3 MB |
| Consistency | `python3 second-brain/brain.py check` | `ok`, 0 problems (catalogue and postings in sync) |
| Tuning benchmark | `brain.py benchmark --repeat 3` | brain 20/21 vs scan 20/21; technical 16/16 vs 15/16; 4,993 vs 229,126 token proxy; 16 ms vs 57 ms median |
| Held-out benchmark | `brain.py benchmark --questions second-brain/holdout-questions.json --repeat 3` | brain 9/9 vs scan 9/9; 2,707 vs 96,993 token proxy; 16 ms vs 57 ms |
| Save through the app | Memory form in the review app | Saved `second-brain/memories/2026-10-28-arms-review-app-location-and-approval-boundary.md`; catalogue and postings updated in one locked step |
| Retrieve the saved fact | `brain.py query "Where does the ARMS review app run, and what is its approval boundary?"` | Memory ranked first, 1 file opened, ~21 ms, cited lines 1–7 |

The first engine scored metadata only and found 12/21: the guide's "keep optimising until it wins" step was needed. The changes were body-term postings (BM25), per-section postings used to rerank the top five, a fix so a document's title section cannot win on title words alone, scoring of the catalogue's `kind · area` columns, and consistent stemming. A fixture regression from the earlier half-finished pointer refactor (`choose_pointer` signature) was fixed first. The held-out questions were written after tuning and never used to tune.

These are proxy measurements (bytes/4), not Claude `/context` readings.

## Live fresh-session comparison

The first attempt failed with `ECONNREFUSED` (0 tokens). `~/.claude/settings.json` routed the CLI to a local proxy at `http://localhost:20128` that was not running, and it remapped the model aliases to proxy-only `cc/…` names. Neither guide calls for such a proxy, and at the user's request it was removed completely:

- the five proxy keys in `~/.claude/settings.json`: `ANTHROPIC_BASE_URL`, the proxy's `ANTHROPIC_AUTH_TOKEN`, and three `ANTHROPIC_DEFAULT_*_MODEL` remaps;
- both global `9router` npm installs, under `~/.local` and `/opt/homebrew`;
- its data directory `~/.9router`, which held provider logins, a database, a JWT secret and tunnel config.

Nothing listens on port 20128 any more. The CLI authenticates directly (`authMethod: claude.ai`, first party). Deleting local login data does not revoke provider tokens upstream.

`python3 tools/arms/model_benchmark.py --run` then made four fresh safe-mode calls. Both arms got the same model: the requested `haiku` alias resolved to `claude-sonnet-5-5`. Inputs include cache reads and cache writes.

| Question | Arm | Input tokens | Output | API-equivalent $ | Wall | Correct |
| --- | --- | --- | --- | --- | --- | --- |
| Unfinished runs after supervisor exit | default (reads the README itself) | 20,840 | 523 | 0.024 | 18.2 s | yes |
| | brain evidence | 6,978 | 232 | 0.014 | 3.4 s | yes |
| Bind address + does policy sandbox tools | default | 24,628 | 392 | 0.035 | 6.3 s | yes |
| | brain evidence | 6,967 | 595 | 0.018 | 6.0 s | **partial**: answered sandboxing correctly but said the bind address was not in its evidence |

The brain arm used ~3× fewer input tokens and roughly half the cost. On the two-part question it was incomplete. The answers sit in two different sections (line 20 and lines 191–193), and the brain hands over one section. This is the documented one-section limit, not a scoring error. The run used the Pro subscription; dollar figures are what the same tokens would cost on the API. Raw rows are in `tools/arms/data/model-benchmark.json`.

## ARMS review app, routines and artifacts

| Check | Result |
| --- | --- |
| `python3 -m unittest discover -s tools/arms -p 'test_*.py'` | 23 passed. Includes a new regression test that failed before the fix. |
| Bug found in the live log | Idle keep-alive sockets crashed the handler thread: `AttributeError: 'Handler' object has no attribute 'command'` in `log_message`. Reproduced with a raw idle socket, then fixed and the server restarted. |
| Weekly report LaunchAgent `com.cloudtransition.arms-routines` | Loaded, Friday 09:00. A manual kickstart wrote the report: `last exit code = 0`, empty stderr. The first install exited 78; moving launchd's working directory and logs under `$HOME` fixed it. **Not yet observed:** an unattended calendar run (first due 2026-10-30). |
| Report in the browser | Checks, inventory, usage and notes render; the "unknown, not zero" usage states display. |
| Feedback | Parked an item against `cloudtransition-artifact`; it persisted across reload and was included in the copied Markdown. |
| Cart | Using an isolated data directory with one synthetic suggestion: select, comment, copy as Markdown, reload. The comment and the count (1) persisted. The synthetic data lived only in a temporary directory. |
| Artifacts | `brand-book.html` and the weekly-review sheet rendered; PDF exported; the inbox lists HTML+PDF newest first; search filters; served read-only through the app. 390 px width: no horizontal overflow. |
| Routers | Five broken `IT%20Mgmt%20/` links fixed (0 broken in the latest report). `CODE.md` was missing `visual-second-brain/`; added. |

## Not verified

- **Clipper:** the browser clipper's Markdown and filename logic runs under Node in the test suite. Loading it unpacked into the user's Chrome, and its download dialog, were not exercised.
- **Managed skills:** the four managed skills (`cloudtransition-data`, `-note`, `-calibrate`, `-artifact`) were exercised only through the commands they call. They were not pressure-tested with fresh subagents.
- **Cache keep-warm:** no keep-warm pings; savings stay unknown because no session telemetry exists for this workspace.
