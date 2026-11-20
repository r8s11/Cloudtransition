# U12 live verification — Codex verified; Gmail reauthorization deferred

Current status: see the 2026-11-13 update below. The original 2026-11-09 Haiku estimate follows unchanged.

## Prerequisites confirmed
- Gmail OAuth token present at `~/.local-routines/personal-kb/gmail-token.json`, scope exactly `https://www.googleapis.com/auth/gmail.readonly` (no modify/send). Refresh token present. Expires 2026-11-09T21:46Z.
- `~/.local-routines/personal-kb/gmail-credentials.json` present.
- `.kb-venv/bin/python3` exists; `anthropic` SDK importable for summarize path.
- No `ANTHROPIC_API_KEY` in environment or workspace `.env` — ingest stays raw-only until a key is supplied.

## Pricing (source: https://www.anthropic.com/claude-haiku-5-5, read 2026-11-09)
Model `claude-haiku-5-5`. Input $0.10 / output $0.50 per Mtok up to 100k tokens; $0.50 / $2.50 above 100k (whole-request). Context 1M, max_output 8192.

## Inventory (completed, 2026-11-09)
| Source | Items | Oversized (not sent) | Raw chars |
| --- | ---: | ---: | ---: |
| Claude | 27 | 0 | 1,314,530 |
| Gmail | 17,457 | 4 | 200,209,579 |
| **Total** | **17,484** | **4** | **201,524,109** |

## Cost
| | USD |
| --- | ---: |
| Expected (4 chars/token, 1,500 out) | **$21.58** |
| Upper bound (1 token/byte, 8,192 out) | $282.79 |
| Upper bound with 2 attempts | **$565.59** |

## What would be sent
Per item: sanitized (secret-masked) title + full raw text in chunk order. Not sent: source metadata, original URL/path fields, skipped security emails, excluded sources. File paths and URLs occurring in raw text ARE included.

## NOT YET DONE — requires explicit user approval (all four)
1. **Data transfer** — acknowledge that sanitized Gmail/Claude content leaves the computer to Anthropic
2. **Dollar cap** — explicit `max_usd` (suggested ≤ $21.58 expected; worst case $565.59)
3. **`ANTHROPIC_API_KEY`** — env or workspace `.env` (never printed or logged)
4. **`approval_id`** — unique identifier for this approval

Until all four are granted, `summarize` stays blocked and the KB remains raw-only with pending summaries. No paid call has been made.

## Update 2026-11-13 — Codex Luna fallback ran; Gmail authorization expired

U12 was amended with the owner's approval on 2026-11-13: a separately approved Claude-only Codex Luna batch may stand in for the Haiku backfill when Haiku is unavailable. The sections above remain the Haiku estimate; no Haiku call has ever been made and no `ANTHROPIC_API_KEY` is configured.

**Summary verification (done).** One pending Claude item, approved by the owner in an interactive form that showed the exact payload, recipient (OpenAI via signed-in Codex), model and the absence of any dollar figure:
- Manifest fingerprint `3887da50d9c6128d063da8fbebd79416a1fac1ea50f47d0deca3b2a50a32ff8e`, model `gpt-6-luna`, 1 invocation, no retries. Manifest kept owner-only in the private runtime, not here.
- Result: 1 summarized, 0 failed; 6,631 input and 342 output tokens reported by Codex; dollar cost unknown (subscription), recorded as null, outside the Haiku ledger.
- Raw rows hashed before and after: identical. The item now has 2 raw rows (status done), 1 segment and 6 atoms, provider `codex`. Details: `codex-live-2026-11-13.json`.
- Installed-CLI isolation was checked first against a loopback mock provider: `codex-isolation-2026-11-13.json`.

**Gmail verification (not done — U12 stays failing).**
- Scope on the saved token is exactly `gmail.readonly`. Scheduled six-hour ingests succeeded through 2026-11-13T00:45Z; the last five runs fetched 467–528 threads each with 415–469 unchanged, 17–64 new, 0–1 updated, 0 failed, which is the no-duplicate behaviour on real mail.
- From 2026-11-13T05:51Z every Gmail run fails with `GmailAuthError` before any read (0 pages). Google rejects the refresh token: it was first granted on 2026-11-05, and refresh tokens for an OAuth client whose consent screen is in "Testing" status expire after 7 days. The connector correctly refused to open a login on its own.
- The owner approved an interactive readonly reauthorization, then chose to skip it for now. No token was replaced. Until someone runs `.kb-venv/bin/python3 ingest_all.py --gmail-login` and accepts Google's consent, Gmail ingestion (manual and scheduled) stays down while Claude ingestion keeps working.
- Not claimed: a same-day pair of manual Gmail runs. That is the remaining step for U12, and it will lapse again every 7 days unless the consent screen is published to production.
## Update 2026-11-16 — Gmail reauthorized; same-day pair of manual runs done

- The saved token's granted scope is exactly `https://www.googleapis.com/auth/gmail.readonly` (checked by reading only the scope list; no token value printed). Gmail reads resumed before 2026-11-16T20:29Z, after the owner's interactive readonly reauthorization.
- Two manual runs, same day, back to back with `.kb-venv/bin/python3 ingest_all.py --source gmail`:

| Run | Start (UTC) | Discovered | Fetched | New | Updated | Unchanged | Security skipped | Failed | Seconds |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 21:29:34 | 430 | 430 | 98 | 0 | 328 | 4 | 0 | 648 |
| 2 | 21:40:22 | 313 | 313 | 2 | 0 | 310 | 1 | 0 | 474 |

- No duplicates: Gmail items went 41,459 → 41,559, exactly the 98 + 2 new threads. Run 2 re-read the overlap window and stored nothing again except 2 threads that arrived between runs.
- `kb.py stats` after run 2: gmail 41,559 items, 108,976 rows, coverage 2025-11-06..2026-11-16, status fresh, 17,857 pending summaries.
- Summary verification remains the approved Codex Luna batch recorded above (manifest `3887da50…`). No Haiku call has been made and none is authorized.
- Known limit: the OAuth consent screen is still in Testing status, so the refresh token lapses 7 days after grant unless the app is published.
