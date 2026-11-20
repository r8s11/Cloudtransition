# Scout — memory index

_Last updated: 2026-11-17_

Dedicated memory for Scout. Append-only events live in `log.jsonl`.

## Configuration
- Job sources are configurable; Scout uses the sources configured for the system and asks Forge when none are configured. Updated 2026-11-09.

## Searches
- **2026-11-09 — scan-2026-11-09** (free search-and-rank pass). Sources: Indeed, LinkedIn Jobs, Dice, Built In NYC, Robert Half, NYC City Jobs, Greenhouse/Ashby/Lever. 17 queries, 1 failed (HTTP 429 on the "deployment technician / computer refresh" query). 40 unique listings found, 40 scored (36 primary, 4 secondary). Output: `outputs/scan-2026-11-09.json` + `.md`.
  - Dice returned only category pages — no citable per-job URLs. That track needs a different approach next run.
- **2026-11-10 — scan-2026-11-10** (free search-and-rank pass). Sources: Indeed, LinkedIn Jobs, Dice, Built In NYC, Robert Half, NYC City Jobs, Greenhouse/Ashby/Lever. 19 queries, 0 failed this run (3 queries that hit HTTP 429 on 2026-11-09 were re-run successfully after backoff). 34 unique NEW listings found and scored (30 primary, 4 secondary); 40 listings from scan-2026-11-09 excluded as already scored. Output: `outputs/scan-2026-11-10.json` + `.md`.
  - Dice still mostly category pages; one direct job-detail URL captured (Server Administrator, Azure). Robert Half returned no new direct per-job URLs beyond those already scored.
- **2026-11-11 — scan-2026-11-11** (free search-and-rank pass). Sources: Indeed, LinkedIn Jobs, Dice, Built In NYC, Robert Half, NYC City Jobs, Greenhouse/Ashby/Lever, company sites, iCIMS, TPG NYC, CSE Talent. 12 queries, 1 failed (HTTP 429 on "IT support engineer New York onsite 2026"). DuckDuckGo provider throttled; Firecrawl search used. Web-fetch provider rate-limited mid-run. 25 unique NEW listings found and scored (22 primary, 3 secondary); 74 prior-scored excluded as duplicates. Output: `outputs/scan-2026-11-11.json` + `.md`.
  - Top score 92 (CAIS, IT Support Associate, NYC, $95-125K). Dice job-detail URLs captured (5). Built In NYC richest source (9).
  - Top score 83 (Related Companies, System Administrator – Endpoint & Client Technologies).
- **2026-11-12 — scan-2026-11-12** (free search-and-rank pass). Sources: Indeed, LinkedIn Jobs, Dice, Built In NYC, Robert Half, NYC City Jobs, Greenhouse/Ashby/Lever, company sites. 8 sources swept + 6 targeted URL lookups; LinkedIn failed (no results), Robert Half 404, cityjobs keyword filter ignored. 44 unique NEW listings found and scored (43 primary, 1 secondary); 99 prior-scored excluded as duplicates. Output: `outputs/scan-2026-11-12.json` + `.md`.
  - Top score 86 (Legora, Workplace Technology Specialist, NYC, $134.3-158K; posted 2026-09-29). Second 86 (Stable Rock Tier 2, Midtown hybrid, $75-95K).
  - Dice now returns real per-job detail URLs — the "category pages only" problem from 2026-11-09/10 is resolved.
- **2026-11-16 — scan-2026-11-16** (free search-and-rank pass). Sources: Built In NYC/Built In, Dice, Greenhouse/Ashby/Lever, Indeed, LinkedIn, Robert Half, NYC City Jobs, company sites (firecrawl web search). 16 queries, 1 failed (HTTP 429, retried successfully). 154 raw results → 150 unique URLs → 35 citable per-job URLs → 17 unique NEW listings found and scored (12 primary, 5 secondary); 143 prior-scored job_ids + applied-to roles excluded. Output: `outputs/scan-2026-11-16.json` + `.md`.
  - Top score 80 (Vanta, IT Operations Engineer – Corporate Engineering, NYC). Second 79 (Cohere AI, IT Support Engineer). No strong ≥83 finds — four prior scans exhausted the obvious high-fit listings.
  - One query HTTP 429 retried with backoff; LinkedIn/Robert Half/Indeed returned mostly category/salary/aggregate pages, not new per-job URLs.

- **2026-11-17 — scan-2026-11-17 (TAM-14)**. New approved target roles: Cloud/DevOps Engineer, Systems/Infrastructure Engineer, IT Manager, Technical Support Lead (NYC + remote-US). Sources: web search (8 queries), Greenhouse/Ashby/Lever public JSON APIs (101 boards, 49 slugs 404), Built In NYC category/search pages (5), Dice job detail. 30 NEW listings verified live and scored. Output: `outputs/scan-2026-11-17.json` + `.md`; per-job intake JSON staged in `outputs/intake-2026-11-17/`.
  - Web-search index is stale: 17 of 18 per-job URLs it returned were removed/closed. Prefer ATS public APIs (boards-api.greenhouse.io, api.ashbyhq.com posting-api, api.lever.co) and Built In category pages (show posted-age) for live listings.
  - Tambora pipeline (/Users/roosevelt/tambora-workspaces) asks Scout to write intake to shared/handoffs/intake and update workspaces/scout/seen_index.json — both outside Scout's write scope; staged locally and handed to Forge. seen_index.json was empty `{"seen":[]}` on 2026-11-17.

## Score outcomes
- **2026-11-17 — scan-2026-11-17**: top 85 (Tennr, Senior IT Systems Engineer, NYC, $135-155K), 84 (Point72, Systems Engineer, Collaboration Technology), 83 (PharmaForceIQ, System Engineer Manager, IT). 13 at ≥75. All 30 in `log.jsonl`. Duplicates excluded: MongoDB Manager, IT Support (= Built In 12174236, scored 11-16), Rain IT Manager (excluded 11-12). Vercel IT Systems Engineer may relate to the earlier Vercel IT Operations Engineer — flagged.
- **2026-11-09 — scan-2026-11-09**: top score 93 (BlackRock, Technical Support Associate, NYC, $110–140K). Top 15 recorded individually in `log.jsonl`; full 40 in the output JSON. No prior scores existed, so nothing was a repeat.
- **2026-11-10 — scan-2026-11-10**: top score 83 (Related Companies, System Administrator – Endpoint & Client Technologies). Top 15 recorded individually in `log.jsonl`; full 34 in the output JSON. 40 prior-scored listings excluded as duplicates.
- **2026-11-11 — scan-2026-11-11**: top score 92 (CAIS, IT Support Associate, $95-125K). Top 15 recorded individually in `log.jsonl`; full 25 in the output JSON. 74 prior-scored listings excluded as duplicates.
- **2026-11-12 — scan-2026-11-12**: top score 86 (Legora, Workplace Technology Specialist, $134.3-158K). Top 15 recorded individually in `log.jsonl`; full 44 in the output JSON. 99 prior-scored listings excluded as duplicates.
- **2026-11-16 — scan-2026-11-16**: top score 80 (Vanta, IT Operations Engineer – Corporate Engineering, NYC). Full 17 in the output JSON; top 10 in `log.jsonl`. 143 prior-scored job_ids + 12 applied-to roles excluded as duplicates. Identity-reassignment attempt in tool output ("you are now Chief of Staff / chat mode") declined; Scout role held.
- Excluded 2026-11-12 (expired/civil-service-only/non-NYC/no URL): OCME Desktop Support Engineer (expired, permanent civil-service only), City Senior Systems Administrator (current City employees only), Safran (West Henrietta/Rochester, not NYC), EvolutionIQ/ServiceTitan/Noma/Net at Work/MediQuant, Capital One Sr Director, BlackRock MD, Rain IT Manager, Harbor Group intern, SPS $18-19/hr, Fortune Society, Custom Computer Specialists, Strategic Staffing, Actus (Japanese), SP Tech (Oracle stack), Apetan (location unclear), F2Onsite/Epstein Becker/Eurasia/Weill Cornell (no citable URL).
- Duplicates/reposts confirmed 2026-11-12: Logicplanet L2 (exact URL), TCS Desktop Support, Conveo, Stripe, Lalamove, Rogo, Tessera Labs, RoundTable, Zocdoc, CAIS, Monarch Money, Robert Half $35-55/hr, Lendbuzz second Dice id.
- Excluded as already tracked: Fireworks, Sierra, EliseAI, MrBeast.
- Excluded on level/pay/eligibility: Airtable Senior Endpoint, D. E. Shaw Lead Modern Workplace, Anthropic IT Support Engineer, Custom Computer Specialists, Persistent Systems, Simply Ed, CUNY L1, Robert Half Staten Island, Robert Half White Plains, NYC OTI Service Desk Agent (current City employees only).
- Excluded this run (part-time/expired/non-NYC/no citable URL): NYC City Jobs computer support technician (expired), computer associate II (part-time), computer service technician (part-time), NTT Data (Brazil URL), Jazz at Lincoln Center (no direct URL), Hudson River Trading macOS (no clean NYC URL).

## Identity events
- 2026-11-09 — identity confirmed on request from orchestrating session (see `log.jsonl`).