# Codex, OpenCode and OpenRouter models for Run executions

## Request

> Add Codex models as options for runs

Clarification of the preceding request: selectable execution models in the dashboard Run tab, not merely a tools-inventory entry.

> add opencode and its models as well

Added 2026-11-06: selectable OpenCode execution models alongside the Codex ones.

> add openrouter as well and only add free models for opencode and openrouter

Added 2026-11-06: selectable OpenRouter execution models alongside Codex and OpenCode. Only free models are offered for OpenCode and OpenRouter; Codex keeps its full visible catalogue.

## Existing surface

Run cards come from /api/skills/catalog; /api/skills/run accepts skill, model, effort and input. Model choices are currently Claude aliases sonnet/opus/fable. Executions use claude -p, a 30-minute timeout, per-skill duplicate protection, runs.log and dashboard-app/runs/. Today shares organizer runners. Audit is fixed-default; shell tools have no model. Read-only cards deny editing; polish allows only template/static edits and specific commands.

## Proposed requirements (approval assumptions)

1. Add provider-labelled Codex, OpenCode and OpenRouter choices to the existing model picker on configurable AI run cards; keep existing Claude defaults. Keep fixed Audit defaults and deterministic shell tools unchanged. No new global configuration or credential changes. Add a button on the Run tab to refresh (update) the model lists from the local catalogues without reloading the page; refreshing never starts a run.
2. Use visible selectable entries from the locally installed catalogues, deduplicated by model ID; omit hidden/reserved entries.
   - Codex: read `~/.codex/models_cache.json`; visible entries include GPT-6.1-Sol, GPT-6-Astra, GPT-6.1 Terra, GPT-6-Sol, GPT-6-Luna, GPT-5.6-Sol/Terra/Luna and Auto. All visible (non-hidden) Codex entries are offered; no free-model restriction applies to Codex.
   - OpenCode: run the installed `opencode models` catalogue; offer only free models — those whose provider/model ID ends in `-free` or `:free` (e.g. opencode/beam-free, opencode-go/crouton-alpha-free).
   - OpenRouter: read the curated catalogue (`~/.hermes.bak/cache/openrouter_curated_catalog.json`, refreshed from https://openrouter.ai/api/v1/models); offer only free models — those ending in `:free` or with zero pricing.
   Catalogue listings are not proof of account entitlement. Never guess model IDs. If a provider's catalogue is unavailable, retain Claude and the other providers and explain that provider's unavailability without inventing options.
3. Execute a selected Codex model with the installed noninteractive `codex exec` interface; a selected OpenCode model with the installed `opencode run` interface; a selected OpenRouter model via the OpenRouter chat API (https://openrouter.ai/api/v1/chat/completions) requiring OPENROUTER_API_KEY. Never `claude` except for Claude selections. Codex effort choices follow the selected model's supported levels plus Default. `opencode run` accepts no effort flag, so OpenCode effort stays Default and a non-default effort for OpenCode is rejected server-side. OpenRouter effort stays Default (API has no effort control). Default leaves provider reasoning unspecified. Reset incompatible effort when switching models; validate all combinations server-side.
4. Preserve skill inputs, dated prompts, workspace context and skill intent for Codex, OpenCode and OpenRouter. Translate skill references into usable provider instructions; do not assume Claude slash commands are automatically provider skills.
5. Preserve existing read/write and command boundaries. Claude enforces each card's read-only sandbox and file/command allowlist. Non-Claude providers (Codex, OpenCode, OpenRouter) run without machine-enforced boundaries; the user accepts this when choosing them. Codex read-only uses its sandbox for read-only cards; OpenCode effort stays Default; OpenRouter has no local sandbox. Never use approval/sandbox bypass flags or change trust/security settings. Show constraints in the UI.
6. Record selected provider/model, status, output and duration in existing history/log flow. No silent fallback to another provider/model on auth, model, quota or executable failures. Show actionable failure output and re-enable retry controls. Never display credentials.
7. Preserve API CSRF/input validation, duplicate-run protection and timeouts. Invalid provider/model/effort combinations are rejected before launching anything. Shell/fixed-default behavior is unchanged.
8. Keep the current Orizuru layout; accessible labelled pickers, keyboard use, mobile wrapping, loading/empty/error/running/completed states. Starting a run remains an explicit click. No model calls merely to load the page. The "update models" button refreshes pickers without starting a run.

## Verification and privacy

Only CLI help and the local model caches (Codex `models_cache.json`, OpenCode `opencode models` output, OpenRouter curated catalog) were inspected; no Codex, OpenCode or OpenRouter model call was made. Implementation verification uses isolated temporary executable fixtures for local lifecycle/security tests and browser checks, not paid live runs. A real authenticated model invocation needs separate permission for its payload and usage. This does not promise every catalogue entry is entitled for the account.

## Non-goals

New task types, arbitrary shell execution, runtime/model account configuration, authentication setup, billing dashboards, auto-retries, or changing fixed Audit defaults.
