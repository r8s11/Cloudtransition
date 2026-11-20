---
feature: Jev on command and helper routing
status: draft
retired: 2026-11-16  # all cases were manual; trimmed by owner decision
rd: rd.md
---

# Evals: Jev on command and helper routing

An Omp session command enables opt-in Jev task-difficulty classification, chooses Claude or Codex based on the task, routes to a suitable available helper model, and logs the pick. No graphical UI is added.

## Build contract

- Implementation starts only after this eval is approved.
- Do not run live model tests before approval of the exact transmitted data and spend cap.
- Run `node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/jev-command/eval.md`; record manual evidence with the evals runner.

## Traceability

| Requirement | Cases |
| --- | --- |

## Usage

## Failure

## Regression

