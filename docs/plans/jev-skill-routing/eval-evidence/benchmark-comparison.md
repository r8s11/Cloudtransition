# U4 — Ten historical tasks, pre-labelled live benchmark

User explicitly approved the exact ten texts plus 407 skill names/descriptions, existing TYPESAFE_API_KEY, model jev-1.14.0, at most 30 requests, no retries, maximum $0.10. Expected labels and ambiguity notes were saved in approved-benchmark.json before the first request. Full sanitized results and tournament traces are in benchmark-results.json. No skill bodies, source documents, helper tasks or conversation context were sent.

## Authorization and chronology recovered 2026-11-13

The original interactive authorization is now traced in `authorization-source.json`, not inferred from this report or its `approval` label. Source session `01a1c249-d6c9-72e2-a463-b38b82ddeb8c` asked for the exact ten texts, catalogue, destination, local-key use and $0.10/30-request/no-retry cap at **2026-11-11 00:56:20.715 UTC**. The matching tool-result response at **00:58:34.493 UTC** is `jev_live: yes`. Labels were saved at **00:59:07.811 UTC**, before the first benchmark invocation at **00:59:24.155 UTC**. The saved `20261110` approval identifier is just an identifier; the authoritative transcript timestamps above are November 11.

This later, pre-labelled benchmark is separate from the earlier unlabelled run described by the stale failing eval record. Existing task/result payloads were not rewritten, re-labelled or re-run. `node tools/jev-routing/benchmark-report.mjs` checks source references, expected/actual labels, chronology and accounting offline. The authorization is consumed and does not permit a refresh.

| Task/source prompt timestamp (UTC) | Expected acceptable skill(s) | Actual | Result |
| --- | --- | --- | --- |
| 1 — 2026-11-10 03:19:20, linking Second Brain via Jev | typesafe-ai | None | mismatch |
| 2 — 2026-11-10 02:59:51, bare plan path | None or executing-plans variants | None | accepted, ambiguous without file/action |
| 3 — 2026-11-10 02:37:51, “please rebuild” | None or resume-master-variant-sync | connection error | error; not retried |
| 4 — 2026-11-10 02:35:11, company-agnostic naming | None or resume-master-variant-sync | None | accepted, missing deliverable context |
| 5 — 2026-11-10 02:27:59, resume for posting | resume-master-variant-sync / resume-ats-optimizer / resume-design-generation | resume-design-generation | accepted |
| 6 — 2026-11-10 00:33:45, improve two projects from documents | brainstorming variants or codebase-design | article-prompts-to-skills | mismatch, ambiguous/multiple tasks |
| 7 — 2026-11-09 23:29:52, no subagents instruction | None | None | accepted |
| 8 — 2026-11-09 23:19:20, address referenced improvements | None or brainstorming/executing-plans variants | None | accepted, referenced file absent |
| 9 — 2026-11-09 21:50:56, capture dashboard into Second Brain | None / cloudtransition-data / domain-modeling | orca-computer-use | mismatch, ambiguous scope |
| 10 — 2026-11-09 19:08:23, pull Claude chat history | None | None | accepted |

Six accepted labels, three mismatches, one transport error. Of four unambiguous prompts, three matched. This is not a claim of perfect classification; context-dependent prompts and multi-skill tasks are shown explicitly.

Usage: 22 requests attempted, 321,110 input tokens reported, $0.01348662 from successful metered requests at $0.042/M input tokens (official docs.typesafe.ai/models.md checked in this session). One failed request did not report usage; a conservative 64k-token reservation of $0.002688 was retained. Total spent-or-reserved upper accounting: $0.01617462, below the $0.10 approved cap. No retries or further live calls were made. Approval is single-use and exhausted.

U4 evidence now substantiates the measured/reporting procedure, not an accuracy guarantee. Errors and poor choices remain visible and were not retuned against this benchmark. The parent must refresh the manual eval record against this evidence; no case expectation was changed.
