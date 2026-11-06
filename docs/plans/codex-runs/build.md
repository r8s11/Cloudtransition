# Build: Codex, OpenCode, OpenRouter model picker for dashboard Run tab

## Goal
Implement approved eval `docs/plans/codex-runs/eval.md` (status: approved 2026-11-06): provider-labelled Codex, OpenCode (free only), OpenRouter (free only) model choices on configurable AI run cards, with effort validation, permission-parity refusals, provider/model logging, and an "Update models" refresh button.

## Files to change
- dashboard-app/app.py — catalog, provider dispatch, validation, logging
- dashboard-app/static/app.js — provider-labelled pickers, effort reset, refresh button
- dashboard-app/tests/test_codex_runs.py — new: F1 invalid selection, F3 failure lifecycle/duplicate
- dashboard-app/templates/pages/run.html — add refresh button (optional)

## Done
- [ ] app.py: provider constants + catalogue loaders (codex/opencode/openrouter)
- [ ] app.py: _parse_model + provider-aware validation in api_skill_run
- [ ] app.py: _resolve_run (claude/codex/opencode/openrouter) + OpenRouter HTTP dispatch
- [ ] app.py: entry logging provider/model/effort
- [ ] app.py: POST /api/skills/catalog/refresh
- [ ] static/app.js: provider-labelled optgroup pickers, effort reset on model switch
- [ ] static/app.js: "Update models" button re-fetches catalog
- [ ] tests: test_codex_runs.py (F1, F3)
- [ ] Verify: py_compile, node --check, pytest
- [ ] Record manual eval evidence under dashboard-app/eval-evidence/
