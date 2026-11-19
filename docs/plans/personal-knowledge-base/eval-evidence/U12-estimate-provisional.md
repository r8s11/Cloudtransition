# U12 provisional estimate — NOT for approval (backfill incomplete)

Generated 2026-11-06T07:30Z, read-only (`kb_summaries.estimate(..., record=False)`), no API key, no network.

Pricing source: https://www.anthropic.com/claude-haiku-5-5 (read 2026-11-06). Model `claude-haiku-5-5`. Per million tokens: input $0.10 / output $0.50 for prompts up to 100k tokens; $0.50 / $2.50 above 100k (applies to whole request). Context window 1M; max_output_tokens 8192.

Ingested so far: Claude 31 items (299 rows); Gmail 11,947 threads (30,807 rows), dates 2026-07-29 → 2026-11-06. Full mailbox was previously inventoried at about 40k threads, so this is roughly 30%.

| | Claude | Gmail (partial) | Total |
| --- | ---: | ---: | ---: |
| Long items pending summary | 25 | 5,254 | 5,279 |
| Oversized (not sent) | 0 | 4 | 4 |
| Raw characters | 1.10 M | 55.1 M | 56.2 M |

Expected input 24.4 M tokens → expected cost **$6.40**. Hard upper bound (1 token per UTF-8 byte, full 8,192-token output reserve each request): $76.21; with 2 attempts: $152.42.

Naive linear extrapolation to ~40k Gmail threads (unverified): expected ≈ $20, upper bound with retries ≈ $500. A real estimate must be regenerated from the completed inventory before asking for data-transfer and dollar-cap approval.
