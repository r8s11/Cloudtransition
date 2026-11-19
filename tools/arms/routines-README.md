# ARMS routines: inventory, usage, suggestions, passive checks

`tools/arms/routines.py` is a standard-library Python script (runs on 3.9 and 3.14) that produces one JSON report for the review app. It is **read-only** and **deterministic**: it makes no model or network calls, so every run costs **0 API tokens and 0 API dollars**. Its only subprocesses are fixed argument lists: `launchctl list`, `crontab -l`, `git ls-files`, and (Python < 3.14 only) `zstd -dc` for compressed Codex logs.

It never emits raw prompts, assistant text or credential values. Output contains counts, fixed taxonomy labels, session ids, dates and `path:line` locations only. A final scrub masks anything credential-shaped in the serialised JSON.

## Commands

```bash
python3 tools/arms/routines.py                       # same as `run`; writes tools/arms/data/routines.json
python3 tools/arms/routines.py run --stdout          # print instead of writing
python3 tools/arms/routines.py --root DIR --output FILE
python3 tools/arms/routines.py --rates rates.json    # add a supplied-rate USD estimate (see below)
python3 tools/arms/routines.py --threshold 3 --cold-minutes 60
python3 tools/arms/routines.py schedule              # print the weekly launchd plist
python3 tools/arms/routines.py schedule --write      # (re)write tools/arms/launchd/<label>.plist
python3 -m unittest discover -s tools/arms -p 'test_routines.py'   # fixture tests
```

`--root` defaults to the workspace this file lives in. `--home` (default `$HOME`) exists for fixtures. The report is written atomically (temp file + rename). `tools/arms/data/` is git-ignored.

## Report contract (`tools/arms/data/routines.json`)

Exactly four top-level keys: `inventory`, `usage`, `suggestions`, `checks`. Each is an object with its own `schema_version` (1) and `generated_at`. Any number may be `null`, meaning **unknown**, never zero.

| Key | Fields |
|---|---|
| `inventory` | `generated_at`, `root`, `items[]`, `counts{classification:n}`, `unknown[]` |
| `inventory.items[]` | `id`, `name`, `kind` (`launchd` `cron` `claude-scheduled` `codex-automation` `workspace-file` `on-demand-app` `arms-managed`), `source`, `schedule`, `status` (`installed-loaded` `installed-not-loaded` `available-not-installed` `on-demand` `unknown`), `classification` (`local-deterministic` `model-invoking` `external` `manual` `unknown`), `model_spend` (`none-by-design` `possible` `unknown`), `external`, `review_mode` (`active` `passive` `unknown`), `token_telemetry` (`zero-by-design` `none-recorded` `not-applicable`), `summary`, `notes`; launchd items may add `script`, `model`, `workspace`, `recent_runs{outcomes,last_run}` |
| `usage` | `status` (`ok` `partial` `unknown`), `window_days` (30), `window_start/end`, `sources[]`, `totals{sessions,messages,input_tokens,output_tokens,cache_read_tokens,cache_creation_tokens}`, `by_tool`, `by_day[]`, `cache{read_ratio,observations[],cold}`, `skills{status,items[],most_used,reason}`, `estimate{status,usd,by_tool,rates,reason}`, `notes[]` |
| `suggestions` | `window_days` (7), `threshold` (3), `items[]`, `notes[]` |
| `suggestions.items[]` | `id` (`sug-<category>` or `sug-rep-<salted hash>`, stable across weeks), `kind` (`taxonomy` `verbatim`), `title`, `summary`, `evidence_count`, `session_ids[]` (`claude:<uuid>` / `codex:<uuid>`), `days[]`, `tool`, `proposed_action`, `safe_to_schedule`, `model_spend`, `status` (`suggested`), `requires_approval` (true) |
| `checks` | `summary{pass,warn,fail,unknown}`, `cost{api_tokens:0,api_usd:0,note}`, `items[]` |
| `checks.items[]` | `id`, `title`, `status` (`pass` `warn` `fail` `unknown`), `message` (= `detail`), `evidence[]` (max 20) |

## What each part does

**Inventory (read-only).** Reads `~/Library/LaunchAgents/*.plist` (only those that reference this workspace, `~/.local-routines`, or the `claude`/`codex` CLIs are listed; other vendor agents are only counted), `launchctl list` for loaded state, `crontab -l`, `~/.claude/scheduled-tasks`, `~/.codex/automations`, `routine.md`, `button-runner/`, and this tool's own schedule artifact. Scripts referenced by a launchd job get a static scan (does it invoke `claude`/`codex` non-interactively, does it mention the network, which `MODEL`/`WORKSPACE`), and its sibling `routine.log` is summarised as outcome counts for 30 days. Classification is a heuristic and is labelled as such. Active vs passive follows the ARMS guide: active = hands you an output to review every run; passive = only surfaces when something needs attention.

**Usage (30 days).** Project-specific only. Claude: `~/.claude/projects/<root path with non-alphanumerics replaced by "-">*`, filtered again by each record's `cwd`; token usage de-duplicated per message id. Codex: `~/.codex/sessions/YYYY/MM/DD` and `~/.codex/archived_sessions` (including `.zst`) limited by filename date, then filtered by `session_meta.cwd`; usage = deltas of cumulative `token_count` (uncached input = input - cached; cache read = cached input; cache creation = `cache_write_input_tokens`). `~/.claude/history.jsonl` supplies session ids/timestamps only. No whole-home scan.

* **Cache observations:** read ratio, and for Claude an idle-gap analysis: turns that arrive >= `--cold-minutes` (default 60, the guide's "about an hour") after the previous turn and re-created cache. Counts and tokens only. Savings from keep-warm pings are reported as `unavailable`: they depend on the real cache TTL, plan and ping cost, none of which transcripts reveal. **No pings are sent.**
* **Skills:** `most_used` is the real count of Claude `Skill` tool calls (Codex: reads of `.../skills/<name>/SKILL.md`, inferred). `unknown` when there are no sessions.
* **Dollar estimate:** `unavailable` unless `--rates rates.json` is passed. Prices are never guessed. File shape:

```json
{"claude": {"source": "where these prices came from",
            "per_million_tokens": {"input": 0.0, "output": 0.0, "cache_read": 0.0, "cache_write": 0.0}},
 "codex":  {"source": "...", "per_million_tokens": {"input": 0.0, "output": 0.0, "cache_read": 0.0, "cache_write": 0.0}}}
```

The result is tokens x your rates, not a bill; subscription usage is not API-billed. Cold-reload cost uses (cache_write - cache_read) x reload tokens.

**Suggestions (past 7 days, threshold 3).** From project prompts, in memory only: each prompt is matched against a fixed keyword taxonomy (weekly review, TASKS.md, DASHBOARD.md, work log, git summary, money check-in, study prep, career docs, graft refresh, second brain) and, separately, a salted HMAC of the normalised prompt catches verbatim repeats (salt in git-ignored `data/.routines-salt`, mode 0600). A category/hash with >= 3 occurrences becomes one card. Titles and actions come from the fixed taxonomy, never from session text, and nothing is executed. Verbatim-repeat cards show only an id, count, days and session ids; look the sessions up in your own transcripts.

**Passive checks (all deterministic):** `zero-model-spend`, `core-files` (9 root routers/state files), `state-freshness` (older than 14 days warns), `router-links` (relative links in routers/state files), `weekly-review-drafts` (<= 10 days), `launchd-workspace` (scheduled routine targets this root), `credential-scan` (git tracked + untracked, ignoring ignored files, saved `.html`/`*_files/` pages and binaries; prints `path:line kind` only), `disk-space`, `agent-clis` (presence only; auth, plan and billing are not queried), `session-data`.

## Weekly Friday local schedule (installed and verified running)

`tools/arms/launchd/com.cloudtransition.arms-routines.plist` runs `routines.py --root <root> run` every **Friday 09:00 local time** (Weekday 5), low priority. `WorkingDirectory` is your home directory and logs go to `~/.local-routines/arms-report/routines.launchd.{out,err}.log` (created by `schedule --write`), so launchd itself touches nothing on the external volume before Python starts; only the script path and `--root` point at the USB workspace. It only generates the local report, so it spends no tokens or dollars. It has no `RunAtLoad`: a run missed while the Mac was asleep fires on wake; one missed while powered off or with the volume unmounted is skipped (run the command by hand). The plist embeds absolute paths for the Python that generated it and for this workspace; regenerate with `schedule --write --python /path/to/python3` after moving either.

**State history.** This tool never installs anything; the plist artifact was first only *available*. On 2026-10-28 the parent session installed it (copy to `~/Library/LaunchAgents/`, `launchctl bootstrap gui/501 ...`, `launchctl kickstart ...`).

1. First plist (external-volume `WorkingDirectory` and log paths): the kickstart ended with last exit status **78** (`EX_CONFIG`), no logs, and no run. Cause is inferred, not proven: launchd could not use paths on `/Volumes/SANDISK USB` before spawning Python.
2. Fixed by moving `WorkingDirectory` and logs under `$HOME` (above). The corrected plist was reloaded and kickstarted by the parent. Observed afterwards (read-only checks): `launchctl print` shows `runs = 1`, `last exit code = 0`; `~/.local-routines/arms-report/routines.launchd.err.log` is empty; `routines.launchd.out.log` holds the one-line `wrote .../tools/arms/data/routines.json | sessions(30d)=None ... checks pass=5 warn=3 fail=1 unknown=1` summary; `routines.json` `generated_at` is 2026-10-28T11:31:39 from that launchd run; the installed plist is identical to `tools/arms/launchd/com.cloudtransition.arms-routines.plist`. The inventory reports it as `installed-loaded`.

**Verified vs not.** Verified: launchd can start the job and it writes a correct report to the USB workspace. Not yet observed: an unattended Friday 09:00 firing (that happens on 2026-10-30; check `generated_at` and `launchctl list | grep arms-routines` afterwards).

**Remaining risk.** The workspace and `routines.py` live on an external volume. If `/Volumes/SANDISK USB` is not mounted at 09:00 Friday the run fails (visible as a non-zero exit status and a Python error in `err.log`) and `routines.json` stays stale; the schedule has no catch-up, so run `python3 tools/arms/routines.py` by hand. macOS may also revoke or re-prompt removable-volume access; if so, grant it or uninstall the job (commands below).

```bash
# status
launchctl list | grep arms-routines          # second column = last exit status
launchctl print gui/$UID/com.cloudtransition.arms-routines | grep -E "state|last exit|runs"

# (re)install from the artifact (bootout first if an older copy is loaded)
launchctl bootout gui/$UID/com.cloudtransition.arms-routines 2>/dev/null
plutil -lint tools/arms/launchd/com.cloudtransition.arms-routines.plist
cp tools/arms/launchd/com.cloudtransition.arms-routines.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.cloudtransition.arms-routines.plist
launchctl kickstart gui/$UID/com.cloudtransition.arms-routines         # optional: run once now

# uninstall
launchctl bootout gui/$UID/com.cloudtransition.arms-routines
rm ~/Library/LaunchAgents/com.cloudtransition.arms-routines.plist
```

The install block is the same one the parent used, plus the leading `bootout`.

## Real findings (run on 2026-10-28)

1. **One live schedule, and it is model-invoking.** `com.roosevelt.weekly-review` is loaded: Sundays 18:00 plus `RunAtLoad`, running `~/.local-routines/weekly-review/run.sh`, which calls `claude -p ... --model sonnet --permission-mode acceptEdits`. Classified `model-invoking`, `review_mode: active`. Per-run tokens and cost are not recorded anywhere readable (`diagnostic.log` has no usage), so its cost is **unknown**; whether it bills a plan or API credits is also unknown.
2. **That routine targets the wrong directory.** Its `WORKSPACE` is `/Users/roosevelt/work/Cloudtransition`, a separate directory that holds only `drafts/` and `shared/`. This workspace is `/Volumes/SANDISK USB/work/Cloudtransition`. In the last 30 days its log shows 5 `SUCCESS_NO_INPUT` (it found none of TASKS.md/DASHBOARD.md/routine.md and exited before any model call) and 15 `SKIPPED`, and no real review was drafted. **Deliberately left unchanged (as of this writing)**: line 13 of `run.sh` (`WORKSPACE=`) and the plist `WorkingDirectory` still hold the old path. Repairing it would start an unattended Sonnet run (`claude -p --model sonnet --permission-mode acceptEdits`, 900 s timeout, no `--max-budget-usd`/`--max-turns`, unknown billing basis) at the next ISO-week catch-up or Sunday trigger. Prerequisite before fixing: your explicit authorisation plus a known budget or cap. Pause with `launchctl bootout gui/$UID/com.roosevelt.weekly-review`.
3. **Nothing else was scheduled locally at first run** (the ARMS Friday job was added later, see above): no crontab, no `~/.claude/scheduled-tasks`, no `~/.codex/automations`. Eleven other LaunchAgents are vendor helpers and are not listed. `button-runner` is an on-demand local UI (not scheduled); `routine.md` is the manual rhythm.
4. **Credential finding (needs your action):** `button-runner/server.js:11` contains a hard-coded `sk-...` style API key literal. The value is not copied into any report. Move it to an environment variable and rotate the key if it was ever real or shared. (`runs.log` and `button-runner/runs.log` log command lines/prompts; their content is not copied into the report.)
5. **Usage is unknown, not zero.** No Claude transcript directory exists for this root; `~/.claude/history.jsonl` has no session for it; Codex had 12 session files in the window and all belong to other projects (`salsasegura-mobile`, `WODCard`). Retained transcripts may have been pruned and the omp harness is not parsed. So there are no totals, no cache numbers, no most-used skill and no cost.
6. **No repeated-job suggestions**, because there are no project prompts in the past 7 days. The report says so instead of inventing any.
7. **State files are stale:** TASKS.md, DASHBOARD.md and routine.md carry a 2026-09-19 stamp (39 days). The only weekly-review draft in `drafts/` is from 2026-09-14.
8. **Five broken links (historical, since fixed by the parent session):** `DASHBOARD.md` lines 15, 25, 46, 64 and `routine.md` line 16 linked to `IT Mgmt /...` (trailing space) but the directory is `IT Mgmt`. The latest run reports 58 relative links checked, 0 broken. Staleness (item 7) is unchanged in the latest run: all three state files still carry the 2026-09-19 stamp.

## External blockers (cannot be resolved locally)

* Claude cloud Routines (claude.ai) and Codex cloud automations cannot be enumerated offline: unknown.
* No token/cost telemetry exists for scheduled `claude -p` runs; "capped routines" (ARMS level 2) cannot rank by tokens until runs are recorded.
* Price rates, billing basis (plan vs API) and the actual prompt-cache TTL must be supplied by you; keep-warm savings stay `unavailable`. No warm pings are sent and none are scheduled.
* Auth/login state of `claude` and `codex` was not queried.
* The ARMS weekly job is installed and a launchd-run (kickstart) succeeded; the first unattended Friday firing is not yet observed, and it depends on the USB volume being mounted at 09:00.
* The existing paid `com.roosevelt.weekly-review` stays broken-by-path until you authorise its unattended model spend and a cap.
* Suggestions never apply themselves; turning one into a routine needs your explicit approval, and any model-assisted routine needs a separately approved cap.
