# Research 05 — Scout sources and free tooling for the daily NYC scan

- Date: 2026-11-18
- Ticket: `.scratch/job-hunting-pipeline/issues/05-scout-sources.md`
- Method: direct primary-source investigation (official docs, first-party API references, live endpoint checks). The `research` skill asks for a background agent; this harness exposes no subagent/delegation tool, so the investigation ran inline in the spawned research subagent. Same substance: claims trace to the source that owns them.
- Constraint honored: no PR, throwaway branch `research/scout-sources`, unrelated working-tree changes untouched.

## Context that shapes the answer

Scout's current setup (from `workspace/agents/scout/memory/index.md` and `.opencode/agents/scout.md`):

- Scout's `websearch` permission is **denied** (one-time consent form would abort a dashboard run). Actual discovery runs through **Firecrawl web search** plus public ATS APIs.
- 2026-11-17 note: the web-search index is **stale** — 17 of 18 per-job URLs it returned were removed/closed. ATS public APIs and Built In category pages gave live listings. **Prefer first-party APIs over search results.**
- 2026-11-17 note: 101 Greenhouse/Ashby/Lever boards tried, **49 slugs 404** — bad/expired board tokens, not a broken API. The token list needs validation and pruning, not a new tool.
- HTTP 429 has appeared on several scans (2026-11-09, 11-11, 11-12, 11-16) and was cleared by retry with backoff.
- Known defects (2026-11-16): Indeed works but yields mostly category/salary pages; LinkedIn no results; Dice mixes category and real per-job URLs; Robert Half NYC 404; cityjobs keyword filter ignored; Built In NYC and Greenhouse/Ashby/Lever work and yield citable per-job URLs.

**Bottom line:** keep Greenhouse/Ashby/Lever + Built In NYC. Add (1) more ATS public APIs, (2) USAJOBS, (3) NYC Open Data `kpav-sd4t`. Repair cityjobs and Robert Half through their real endpoints. Treat LinkedIn and Dice as replaceable-by-ATS, repairable only as brittle fallbacks. Move discovery off generic web search toward first-party APIs to cut 429s and stale URLs.

## 1. Replacement / additional sources with citable per-job URLs

### 1a. More ATS public APIs (best additions — same shape as the three that already work)

Nine ATS platforms expose a public, unauthenticated JSON (Personio: XML) endpoint that powers their own careers widget. Every record carries a stable per-job apply/hosted URL. Verified live 2026-08-04: [ATS Job API Reference](https://conorscode.github.io/ats-api-reference).

| ATS | Endpoint | Per-job URL field | Free / auth | Notes |
| --- | --- | --- | --- | --- |
| Greenhouse | `GET boards-api.greenhouse.io/v1/boards/{token}/jobs` | `absolute_url` | Free, no key | Already used. `?content=true` adds full description. No pagination. |
| Lever | `GET api.lever.co/v0/postings/{site}?mode=json` | `hostedUrl` | Free, no key | Already used. Bare array response; `createdAt` is epoch ms. |
| Ashby | `GET api.ashbyhq.com/posting-api/job-board/{slug}` | `jobUrl` | Free, no key | Already used. `?includeCompensation=true` documented by [Ashby](https://developers.ashbyhq.com/docs/public-job-posting-api). Trim titles (leading spaces observed). |
| **Workday** | `POST https://{tenant}.{shard}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs`, body `{"limit":20,"offset":0,"searchText":""}` | `externalPath` → `https://{tenant}.{shard}.myworkdayjobs.com/{site}/job{externalPath}` | Free, no key | Largest untapped NYC employer pool. Tenant/site/shard cannot be guessed — start from a real board URL. `postedOn` is relative text; multi-location shows "2 Locations". **Not vendor-documented** — check each host's `robots.txt` first. |
| **SmartRecruiters** | `GET api.smartrecruiters.com/v1/companies/{identifier}/postings?limit=100&offset=0` | per-posting detail URL | Free, no key | `totalFound` + offset pagination; `location.remote`/`hybrid` booleans. Description needs one call per posting. |
| **Workable** | `GET apply.workable.com/api/v1/widget/accounts/{slug}?details=true` | `application_url` | Free, no key | Company name included; `telecommuting` boolean; descriptions in same call. |
| **Recruitee** | `GET https://{slug}.recruitee.com/api/offers/` | `careers_url` | Free, no key | Keep trailing slash; trust `locations[]` over flat `city`. |
| **Personio** | `GET https://{slug}.jobs.personio.de/xml` | position URL in feed | Free, no key | XML, not JSON. Non-customer returns 307 to marketing site — disable follow-redirects. |
| **BambooHR** | `GET https://{slug}.bamboohr.com/careers/list` | `/careers/{id}/detail` | Free, no key | Location fields often null; non-customer returns 302. |

Priority additions: **Workday** (largest untapped NYC employer pool), **SmartRecruiters**, **Workable** — all give clean per-job URLs and complement the existing three. Recruitee/Personio/BambooHR are lower-yield for NYC IT support but cost little to add once a normalizer exists.

Practical normalizer (from the same reference): treat IDs as opaque strings scoped to `(platform, companySlug)`; model `locations[]` as an array; prefer each platform's explicit remote boolean; accept `null` posted dates on Workday/BambooHR; double-entity-decode Greenhouse `content`.

### 1b. USAJOBS — federal IT roles in NYC

Official [USAJOBS Job APIs](https://developer.usajobs.gov/api-reference/job-apis): `GET data.usajobs.gov/api/Search`. Free API key via the [request form](https://developer.usajobs.gov/General/Quick-Start) (no card). Headers: `Host: data.usajobs.gov`, `User-Agent: <email used to register>`, `Authorization-Key: <key>`.

Query for Roosevelt: `?JobCategoryCode=2210` (Information Technology Management) `&LocationName=New+York,+NY` `&Keyword=desktop+support` (or `PositionTitle=...`). Each `MatchedObjectDescriptor` has `PositionURI` and `ApplyURI` — citable per-job URLs.

Limits (official [Rate Limiting](https://developer.usajobs.gov/guides/rate-limiting)): 250 rows/page default, max 500 (`ResultsPerPage`), max 10,000 rows per query, `Page` for pagination. Search defaults to public jobs only; "Status" jobs need a separate request. Codelist endpoints need no key. [Terms](https://developer.usajobs.gov/API-Reference/GET-api-Search) let OPM vary limits at any time. Caveat: many federal IT roles require US citizenship and sometimes current federal status — filter before scoring.

### 1c. NYC Open Data `kpav-sd4t` — reliable keyword filter for city jobs

The cityjobs keyword filter is broken (see §3), but DCAS publishes the same postings as a weekly Socrata dataset: [Jobs NYC Postings](https://data.cityofnewyork.us/City-Government/Jobs-NYC-Postings/kpav-sd4t), 2,546 rows, 30 columns, weekly automated updates, last updated 2026-10-27.

Live query verified 2026-11-18:

```
GET https://data.cityofnewyork.us/resource/kpav-sd4t.json
  ?$select=job_id,business_title,civil_service_title,work_location,posting_type
  &$where=upper(business_title)%20like%20%27%25DESKTOP%25%27
           %20OR%20upper(business_title)%20like%20%27%25IT%20SUPPORT%25%27
  &$limit=5
```

Returned `789790 DESKTOP SUPPORT SPECIALIST`, `803221 AV Desktop Technician`, etc. Free, no key for low-volume reads; Socrata SoQL gives real keyword filtering and a `job_id` to build/track the cityjobs per-job URL. Cavaet: weekly refresh, so a posting can be closed on cityjobs but still in the dataset — validate final URLs with a HEAD/GET before scoring. Use this instead of the broken `?keyword=` param.

### 1d. Keep what works

- **Built In NYC / Built In** category pages (`builtinnyc.com/job/...`, `builtin.com/job/...`) — best current yield; show posted age. Keep.
- **Greenhouse / Ashby / Lever** — keep, after pruning the 49 dead board tokens.
- **Indeed** — keep as low-yield web-search track only; it mostly returns category/salary pages.

## 2. Free tooling and limits

| Tool | Cost / free tier | Limit that matters | Fit |
| --- | --- | --- | --- |
| ATS public APIs (9 platforms above) | Free, no auth | No published rate limits; no `Retry-After` headers seen. Be polite: 150–300 ms between calls, real User-Agent, cache. Lever's terms allow third-party scraping with a **1 request/s** crawl delay; Workday hosts should be treated as shared infra. | Primary discovery. Citable URLs, live data, no search-index staleness. |
| Firecrawl (already used) | **1,000 credits/month** free, no card; keyless tier also available | **10 req/min** on `/scrape`, `/map`, `/search`; **2/min** on `/crawl`, `/agent`, `/interact`; 2 concurrent browsers. Exceeding → **429**. Search = 2 credits per 10 results. Keyless capped per IP/day (numbers unpublished) → 429. Failed-but-returned 403/404 still costs 1 credit. | Discovery/fallback only. Official [rate limits](https://docs.firecrawl.dev/rate-limits) and [billing](https://docs.firecrawl.dev/billing). |
| USAJOBS API | Free key | 25–500 rows/page, 10,000 rows/query | Federal NYC IT (2210). |
| NYC Open Data Socrata | Free, no key at low volume | SoQL `$limit`; dataset weekly | Reliable NYC keyword filter. |
| Adzuna API | Free self-serve key immediately | Default **25 hits/min, 250/day, 1,000/week, 2,500/month**; description is only a snippet; attribution required; free tier is for evaluation/personal use | Broad backup for NYC IT. Official [overview](https://developer.adzuna.com/overview), [search](https://developer.adzuna.com/docs/search), [terms](https://developer.adzuna.com/docs/terms_of_service), limits as published in [CleanJobData](https://cleanjobdata.com/articles/how-to-integrate-adzuna-free-job-api). |
| JobSpy (`python-jobspy`, MIT) | Free open source | Inherits board limits: LinkedIn ~10 pages/IP then 429; ~1,000 results/search cap; Indeed/Glassdoor bot management; PyPI release lags GitHub fixes | Optional local fallback for Indeed/LinkedIn; proxy costs appear past toy volume. [Repo](https://github.com/speedyapply/JobSpy). |
| RSS | Free | Greenhouse/Lever/Ashby publish **JSON, not classic RSS**. Wrap with [RSS-Bridge](https://rss-bridge.org/) or a tiny polling script; Teamtailor has a native RSS feed. | Convenience layer only; a script that diffs job IDs is simpler and more reliable. [Feed write-up](https://jobnotify.net/blog/job-posting-rss-feeds). |
| Apify / Scrappa (free credits) | Apify $5 free usage; Scrappa 500 free monthly credits | Then paid per result/credit | Optional, not needed for a daily single-person scan. [Apify ATS feed](https://apify.com/factpipe/ats-jobs-feed), [Scrappa](https://scrappa.co/apis/dice-api). |

Recommendation: implement a single stdlib-Python fetcher that polls the ATS endpoints + USAJOBS + Socrata, diffs `(source, company, job_id)` against the seen index, and uses Firecrawl **only** for web-search discovery when first-party sources return nothing. No new paid dependency.

## 3. Broken sources — repairable vs replaceable

| Source | Verdict | Concrete repair / replacement |
| --- | --- | --- |
| **LinkedIn Jobs** — no results | **Replaceable** (recommended). Repairable but brittle and against ToS. | No official read API exists; Job Posting API is write-only and closed to new partners ([Linked API guide](https://linkedapi.io/guides/linkedin-jobs-scraper), [Microsoft Learn overview](https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/overview)). Only logged-out route: `GET linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=<q>&location=New+York%2C+NY&start=0` (HTML cards, `start` += 25); detail: `/jobs-guest/jobs/api/jobPosting/{id}`. ~10 pages/IP then 429/IP block, markup drift, LinkedIn's User Agreement prohibits bots ([guide](https://archonum.com/guides/how-to-scrape-linkedin-without-getting-banned)). **Decision:** drop from daily scan; rely on ATS + Built In. Optional manual fallback only, never logged-in/automated account. |
| **Robert Half NYC** — 404 | **Repairable.** | Citable per-job pattern: `https://www.roberthalf.com/us/en/job/{city-state}/{slug}/{req-id}-usen` (e.g. `/new-york-ny/desktop-support-analyst/02940-0013518053-usen`). Verified 2026-11-18: an expired req id returns a live "N results for Desktop Support Analyst in New York, NY" page with real current listings; the old 404 came from stale req ids / wrong city slug, not a dead site. `?q=`/`?l=` on `/us/en/jobs` renders the generic landing page and ignores filters — do not use it. Repair: harvest fresh per-job URLs from the results page / sitemap, validate with GET, discard expired. Because the yield is recruiter-duplicated listings, treat as secondary to ATS. |
| **NYC cityjobs** — keyword filter broken | **Repairable.** | Confirmed: `https://cityjobs.nyc.gov/jobs?keyword=desktop` returns **1,646 unfiltered results** (2026-11-18). `?q` and `searchText` are ignored. Working filters are `?category=Technology%2C%20Data%20%26%20Innovation` and opaque `?options=<hash>&page=N` — neither is a keyword search. Repair: query NYC Open Data `kpav-sd4t` with SoQL `$where` on `business_title`/`civil_service_title`, then open the resulting `cityjobs.nyc.gov/job/{slug}-jid-{job_id}` URL (pattern seen in prior scans; validate before scoring). Also filter `posting_type=External` and watch for civil-service-only eligibility. |
| **Dice** — no citable per-job URLs | **Repairable but fragile; replaceable by ATS is cleaner.** | Citable URLs do exist: `https://www.dice.com/job-detail/{uuid}` (prior scans captured these; the "category pages only" issue was a 2026-11-09/10 search problem, partly resolved by 11-12). Repair: use Dice's own search URL `https://www.dice.com/jobs?q=<query>&location=New+York%2C+NY` and extract `job-detail` links, or scope web search to `site:dice.com/job-detail`. Third-party paid APIs exist (Anysite, Scrappa, everyinfra) but add cost for data ATS sources already give free. Decision: demote to opportunistic web-search track; do not depend on it. |

## 4. Anti-bot / rate-limit risks and staying within terms

Observed risk: HTTP 429 on 4 of 6 recorded scans, all cleared by retry with backoff. Causes are now identifiable:

- **Firecrawl keyless per-IP daily caps** and **10 req/min** on `/search` — a 16-query sweep with scraping options can burst past this. Use a free API key, keep searches ≤10/min, `parsers: []`, `limit` results, and avoid scraping every result (12 credits per search+scrape of 10).
- **LinkedIn guest endpoint** — ~10 pages/IP then 429/block; ToS prohibits automated access. Do not automate daily; never use a logged-in session.
- **JobSpy/Indeed/Glassdoor** — inherited blocks; ~1,000 results/search cap; LinkedIn ~10 pages; Glassdoor ~2 req/s.
- **ATS APIs** — no documented rate limits and no `Retry-After` observed, which means **be conservative**, not "unlimited". Lever's own terms allow third-party scraping with a 1 req/s crawl delay; Workday career sites are shared enterprise infra — check `robots.txt` per host.
- **USAJOBS** — terms let OPM vary limits without notice; honor `ResultsPerPage`/`Page` caps.
- **Adzuna** — 25/min, 250/day free-tier hard caps; personal/evaluation use only.

Guardrails for the daily run:

1. One sequential pass per host; 200–300 ms between ATS calls, ≥1 s for Lever, ≥250 ms for Workday and check `robots.txt`.
2. Firecrawl: free API key, ≤10 searches/min, no result scraping by default, cap `limit`, cache responses for the day.
3. On 429/5xx: exponential backoff with jitter, honor `Retry-After`, max 2–3 retries, then log a source failure and continue (Scout's standing rule). Stop on CAPTCHA/restriction notice.
4. Validate/pin board tokens and per-job URLs each run; prune 404s instead of retrying them daily (the 49/101 dead slugs are the largest avoidable waste).
5. Track `(source, company, job_id)` and posted/first-seen date; diff against the seen index before scoring. Never re-score an unchanged posting.
6. Use a real, identifying `User-Agent` (USAJOBS requires the registered email); no proxy rotation, no login, no personal data beyond public postings.
7. Respect each company's terms; ATS endpoints are public syndication feeds, not an invitation to bulk-scrape. Attribute by linking to the original apply URL.

## Proposed `## Answer` section for the ticket

```markdown
## Answer

Keep Greenhouse/Ashby/Lever and Built In NYC; prune the 49 dead board tokens found on 2026-11-17 rather than adding tools. Add three sources with citable per-job URLs: (1) more ATS public APIs — Workday (POST /wday/cxs/{tenant}/{site}/jobs, robots-gated), SmartRecruiters and Workable, all free/no-auth with stable per-job links; (2) USAJOBS GET /api/Search, free key, JobCategoryCode=2210 + LocationName=New+York,+NY, 500 rows/page, 10k rows/query, PositionURI is citable; (3) NYC Open Data Socrata kpav-sd4t, free SoQL $where on business_title, which supplies the keyword filter cityjobs lacks. Free tooling: one stdlib-Python poller over those APIs with job-ID diffing; Firecrawl stays discovery-only (free 1,000 credits/month, 10 req/min search, 2 concurrent — exceeding returns 429); Adzuna free key (25/min, 250/day) as backup; JobSpy/RSS are optional fallbacks, not primary. Broken sources: LinkedIn REPLACE (no read API; guest endpoint lasts ~10 pages/IP and breaches ToS); Robert Half REPAIR via /us/en/job/{city-state}/{slug}/{req-id}-usen and re-harvest expired reqs; cityjobs REPAIR via Socrata kpav-sd4t + cityjobs.nyc.gov/job/... URLs (?keyword= is ignored); Dice REPAIR opportunistically via site:dice.com/job-detail/{uuid} but prefer ATS. Stay in terms: one sequential pass per host with 200-300 ms gaps (1 s Lever, robots check Workday), identifying User-Agent, cache, ≤10 Firecrawl searches/min with parsers:[], Retry-After + exponential backoff with jitter (max 2-3 retries), stop on CAPTCHA, prune dead tokens, and diff by (source, company, job_id).
```

## Sources

Primary / first-party:
- [Greenhouse Job Board API](https://docs.greenhouse.io/job-board) — no auth for GET, `absolute_url`, `content=true`.
- [Ashby Job Postings API](https://developers.ashbyhq.com/docs/public-job-posting-api) — public, `includeCompensation=true`.
- [Greenhouse API overview](https://support.greenhouse.io/hc/en-us/articles/10568627186203-Greenhouse-API-overview) — requests may be rate-limited.
- [USAJOBS Job APIs](https://developer.usajobs.gov/api-reference/job-apis), [Search](https://developer.usajobs.gov/api-reference/get-api-search), [Auth](https://developer.usajobs.gov/guides/authentication), [Rate limiting](https://developer.usajobs.gov/guides/rate-limiting), [Terms](https://developer.usajobs.gov/API-Reference/GET-api-Search).
- [NYC Open Data — Jobs NYC Postings](https://data.cityofnewyork.us/City-Government/Jobs-NYC-Postings/kpav-sd4t) and live SoQL query (verified 2026-11-18).
- [cityjobs results page](https://cityjobs.nyc.gov/jobs?keyword=desktop) — 1,646 unfiltered results; per-job page pattern.
- [Firecrawl rate limits](https://docs.firecrawl.dev/rate-limits), [billing](https://docs.firecrawl.dev/billing), [search costs](https://docs.firecrawl.dev/features/search), [pricing](https://firecrawl.dev/pricing).
- [Adzuna overview](https://developer.adzuna.com/overview), [search](https://developer.adzuna.com/docs/search), [terms](https://developer.adzuna.com/docs/terms_of_service).
- [LinkedIn rate limiting](https://learn.microsoft.com/en-us/linkedin/shared/api-guide/concepts/rate-limits), [Job Posting API overview](https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/overview).
- [Lever XML feed terms](https://help.lever.co/s/article/Using-Lever-s-XML-job-posting-feed), [ATS feed reuse terms](https://apify.com/factpipe/ats-jobs-feed).
- [JobSpy repo/README](https://github.com/speedyapply/JobSpy), [JobSpy review](https://jobspipe.dev/blog/jobspy-review).

Live-verified endpoint measurements (2026-08-04, every call actually run):
- [ATS Job API Reference — 9 platforms](https://conorscode.github.io/ats-api-reference).

Repo-local evidence:
- `.opencode/agents/scout.md` (websearch denied), `workspace/agents/scout/memory/index.md` (source history, 429s, stale index, 49/101 dead slugs), `workspace/agents/scout/outputs/scan-2026-11-16.md` (source failures), `.scratch/job-hunting-pipeline/issues/05-scout-sources.md` and `06-source-repairs.md`.
