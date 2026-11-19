# U9 — Six-hour launchd job and internal-disk logs (re-verified 2026-11-10)

Result: PASS. Observed on this Mac; no mail or chat content, no credentials copied.

## Installed job (inspected 2026-11-10)
- Label `com.cloudtransition.personal-kb` (unique). `kb_runtime.install_schedule` writes only its own plist; the arms-routines (2026-10-28) and weekly-review (2026-09-14) plists predate it and the dashboard plist (2026-11-06 17:04) was changed by dashboard work, so no existing job definition was rewritten by the KB install.
- `~/Library/LaunchAgents/com.cloudtransition.personal-kb.plist` (mode 600, via `plutil -p`): `StartInterval` 21600, `RunAtLoad` false, `ProcessType` Background, stdout and stderr both `~/.local-routines/personal-kb/ingest.log`.
- `ProgramArguments` is an argv list of two absolute paths: `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3` and `/Users/roosevelt/.local-routines/personal-kb/launch.py`. No shell, no `sh -c`, no interpolation.
- `launch.py` (mode 600) checks that the workspace and `.kb-venv/bin/python3` exist (otherwise logs "KB workspace unavailable; mount the USB volume" and exits 1) and runs `ingest_all.py` through the venv interpreter as an argv list. No alternate database is created.
- `launchctl print gui/501/com.cloudtransition.personal-kb` finds the loaded job: type LaunchAgent, run interval 21600 s.
- Logs and runtime: `~/.local-routines/personal-kb/` is drwx------; `ingest.log` and `launch.py` are -rw-------. Documented check commands are in `KB-README.md` section "Schedule and logs" (`launchctl print`, `launchctl kickstart`, `cat ingest.log`, `launchctl bootout`).

## One observed run of the loaded job (interval-triggered, 2026-11-10 12:35-12:46 local)
`launchctl print` showed `state = running`, `immediate reason = interval`, pid owned by launch.py, `runs = 2` while the run was in progress, and after it finished `state = not running`, `runs = 2`, `last exit code = 0`. The run held the ingestion lock throughout, so no manual run was started on top of it.

Per-source counts logged at the end of that run (UTC timestamps from `ingest.log`):
- claude 2026-11-10T17:35:54Z: status ok; files 44, parsed 0, unchanged_files 44, new 0, updated 0, excluded 0, malformed_records 0, incomplete_tails 0, errors 0; 0.853 s.
- gmail 2026-11-10T17:46:27Z: status ok; pages 1, discovered 395, fetched 395, new 70, updated 2, unchanged 318, skipped_security 7, failed 0, pending_summaries 29; 633.7 s.

Both connectors ran with real data, in order, from the single scheduled invocation. The log carries only counts, timings and statuses. Log history: the 2026-11-05 runs recorded `GmailAuthError` for gmail (no Gmail login existed yet; safe message, claude still ingested) and two lock refusals ("Another KB ingestion is running") while the manual backfill held the lock on 2026-11-06; every scheduled run from 2026-11-06T20:46Z onward (ten consecutive claude+gmail pairs through 2026-11-10T17:46Z) is `status ok`.

## Raw-only
`ingest_all.py` never imports or calls `kb_summaries`; there is no `.env` in the workspace and no `ANTHROPIC_API_KEY` in the environment, so the job cannot make a paid call. `summarize` needs an approval file with `scheduled: true` that has not been created.

## History (superseded)
Earlier notes on this file (2026-11-05/06) recorded the job as installed but not yet run because the backfill held the lock. That condition is gone: the job has run repeatedly and exited 0.
