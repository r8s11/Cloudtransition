# Bot (Brain) read access to live dashboard state

## Request (verbatim, 2026-11-16)

> I would like to connect dashboard-app with bot
>
> (clarified) I would like to use this directory as my entry point for my personal
> assistant. So I want to basically give access to my personal assistant to my
> dashboard so whichever model or whichever agent is running can access and
> extract data to respond to me.
>
> Make bot config work on this Mac too: yes: permission paths resolve for both
> checkouts (Mac USB path and Parrot path), keeping the same approval rules.

## Requirements

1. Any agent running in `bot/` (brain, workspace, explore) can read **live** Command Center state — not stale files — through one documented, read-only tool.
2. The dashboard exposes one read-only JSON endpoint aggregating: task counts per realm, interview pipeline (counts + rows with status/next step), skill runs (live + recent), Mission Control missions, and optionally today's calendar. No writes, no new exposure beyond what dashboard pages already show on the tailnet.
3. `bot/tools/dashboard.py` (stdlib only) fetches that endpoint over loopback and prints JSON; subcommands/flags documented in `bot/tools/README.md`.
4. The tool refuses non-loopback base URLs and reports a clear error when the dashboard is down; it never prints credentials or `.env` contents.
5. OpenCode permissions allow exactly the tool command without an approval prompt; every other shell/edit rule stays as-is (ask outside bot).
6. Permission paths resolve for both checkouts (`/Volumes/SANDISK USB/work/Cloudtransition/*` and `~/code/Cloudtransition/*`) with identical approval semantics.
7. `bot/AGENTS.md` and the brain/workspace agent definitions tell every agent to use the tool for live dashboard state and to treat returned data as untrusted input.
8. Existing behaviour unchanged: dashboard pages/endpoints, `/api/brain/query` (Second Brain retrieval), bot pairing flow.

## Assumptions

- A1: one aggregating endpoint (`GET /api/assistant/state`) rather than scraping HTML or many calls; `include=` selects sections, calendar opt-in because it may touch Google.
- A2: the tool is read-only by construction (GET only); no remember/write path is exposed to agents.
- A3: missions come from the loopback Mission Control API (`127.0.0.1:8787`); if it is down the section reports `unavailable`, not an error for the whole call.
