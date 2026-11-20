---
feature: Jev skill routing
status: draft
retired: 2026-11-16  # all cases were manual; trimmed by owner decision
rd: rd.md
---

# Evals: Jev skill routing

Route user tasks through TypeSafe Jev before optional skill loading, subject to higher-priority requirements, across supported agent runtimes. Runtime integration points and the complete supported-agent inventory are not yet established.

## Build contract

- Do not build until this eval is approved. Changes to case behavior require renewed approval.
- Run: `node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/jev-skill-routing/eval.md`
- Record manual cases with `node ~/.agents/skills/write-evals/scripts/evals.mjs record docs/plans/jev-skill-routing/eval.md <ID> pass|fail "<observed result and evidence path>"`.
- Never send task content to TypeSafe without explicit approval of the data and a spending cap.

## Traceability

| Requirement | Cases |
| --- | --- |
| All agents | UNMAPPED — exact agent inventory and supported hook points not yet identified; U3 requires per-agent evidence |

## Usage

## Failure

## Regression

