# U6 — Separate Tasks authorization (observed 2026-11-06)

- User approved Tasks setup and selected Cloud project `my-project-1568209050069` (account roosevelt.bseg@gmail.com).
- Google Tasks API enabled in that project; a new Desktop OAuth client created and stored at `~/.local-routines/personal-kb/calendar/credentials.json` (mode 600, directory 700).
- `calendar_cli.py login` requested only `https://www.googleapis.com/auth/tasks`; CLI printed the full-Tasks-scope warning first. Google consent screen showed "Create, edit, organize, and delete all your tasks"; the user accepted it personally (unverified-app warning not bypassed by the agent).
- Saved Tasks token: `calendar/token.json`, mode 600, scopes exactly `[tasks]`, written 2026-11-06T01:50:00 local.
- Gmail token unchanged: scopes exactly `[gmail.readonly]`, mode 600, last modified 2026-11-05T21:35:16 (before Tasks login), different OAuth client id from the Tasks token, sha256 prefix 6594898783a5.
- Read-only `calendar_cli.py lists` succeeded with the Tasks token (23 lists). No token contents copied here.

## Re-inspection 2026-11-10 (local metadata only; no token content read into this file, no Google call made)

- Supersedes `U6-tasks-oauth.md`, an erroneous "blocked / no Tasks login" note written 2026-11-09. The Tasks login was personally authorized by Roosevelt on 2026-11-06 (above); nothing is missing.
- `calendar/token.json`: mode 600 in a 700 directory, written 2026-11-06T01:50, scopes exactly `['https://www.googleapis.com/auth/tasks']`, refresh token present. No Gmail or Calendar scope.
- `gmail-token.json` is a different file in the parent directory: mode 600, scopes exactly `['https://www.googleapis.com/auth/gmail.readonly']`. Its OAuth client id and refresh token differ from the Tasks token's (compared by sha256 prefixes only: client id `c0feac9caa` vs `468d65d3f9`).
- The Gmail token file's bytes have changed legitimately since 2026-11-06: the six-hour read-only job refreshes the access token (file last written 2026-11-10T12:46 local, scopes unchanged). The 2026-11-06 whole-file hash (`6594898783a5`) therefore cannot be compared to a hash taken today; the byte-preservation observation stands as recorded at the moment of the Tasks login (Gmail token mtime 2026-11-05T21:35:16, before the 01:50 login).
- Code evidence: `calendar_google.login` requests only `TASKS_SCOPES`, writes only `<runtime>/token.json`, and its error text states no Gmail credentials were changed; `build_service` reads only the saved Tasks token and never starts authorization. `ingest_all.py`, `connectors.py` and `kb_runtime.py` contain no reference to the calendar modules, so scheduled KB ingestion cannot open this login or publish tasks. This is covered by automated cases F4 and R3.
- The CLI printed the full-Tasks-scope warning before login (above): Google's Tasks scope can manage all of the account's tasks even though this tool only adds selected items.
