# Jev routing implementation plan

Implement inline; no subagents. Approved specifications: rd.md, eval.md and ../jev-skill-routing/rd.md.

1. Add tools/jev-routing/core.mjs for pinned Jev requests, validated Choices, recursive 254-option grouping with None, task difficulty, full available-model selection, private metadata-only logs, secret rejection and conservative request-budget reservations. Add behavior tests for None, unknown responses, large-catalogue coverage, arbitration, failures and budget exhaustion before implementation.
2. Add an Omp extension: session-scoped /jev on|off|status and /jev skills on|off, explicit transmission/budget confirmation, sequential input routing, selected skill-body loading after classification, and child SDK sessions on exact available Anthropic/OpenAI models. Forward parent tool approvals to the UI and inherit parent system instructions; do not replace the main model or bypass its rules. Child discovery must not recurse into the router. Reset mode on session switches and cancel work on off/shutdown.
3. Install a thin global Omp loader, exercise the actual extension through Omp RPC without paid calls, and document other detected agent runtimes as unsupported until their native hooks are integrated and verified; do not claim universal enforcement.
4. Obtain separate approval for bounded live smoke inputs to Jev and helpers. Keep the previously authorized historical-task budget separate. Run and record the approved manual evals honestly, leaving unavailable prerequisites explicit rather than marking them passing.

Choice-group probabilities are never compared directly: a fresh Choice arbitrates group winners. This is a tournament and can eliminate a globally preferable candidate early; retain group answers in test evidence. No original task or key is written to routing pick logs.

## Acceptance repair evidence (2026-11-13)

- U2 requires fake **or** authorized providers, not live helper spending. `tools/jev-routing/runtime-acceptance.mjs` observed real Omp 18.19.0 RPC and SDK helper sessions for easy/medium/hard tasks, Claude and Codex models, one helper request per task, classifier-before-helper ordering and distinct metadata-only picks/outcomes. Evidence: `eval-evidence/acceptance-runtime.json`. The historical inability to enforce a promised live 64-output-token cap does not block this approved fake-provider path.
- The same experiment observed skill-routing R2: optional-fixture or None first, binding required-skill instruction in native model input, then a real required-skill read result in both cases. No mandatory instruction was suppressed.
- `harness.mjs` now isolates fixture auth/config/cache under external `TMPDIR` using HOME-relative `PI_CONFIG_DIR`; HOME and real credentials stay unchanged. Nothing was installed globally.
- Native optional-skill adapter implementation and remaining exact human-trust prerequisites are recorded in `../jev-skill-routing/eval-evidence/runtime-inventory.md`. Neither native trust nor a saved benchmark approval authorizes new Jev spending.
- Unit suites, full Omp matrices and eval-runner refresh are the parent's final verification step after all source edits. No eval expectation or result record was edited by this repair.
