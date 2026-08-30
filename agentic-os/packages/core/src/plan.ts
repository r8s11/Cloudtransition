import { PlanSchema, PlanTaskSchema } from "./schemas";
import type { Plan, PlanTask } from "./types";

// ── parsePlan ────────────────────────────────────────────────────────────

export function parsePlan(input: unknown): Plan {
  return PlanSchema.parse(input);
}

// ── validatePlanTask ─────────────────────────────────────────────────────

export function validatePlanTask(input: unknown): PlanTask {
  return PlanTaskSchema.parse(input);
}

// ── plan builder helpers ─────────────────────────────────────────────────

export function createPlanTask(input: {
  id: string;
  title: string;
  description?: string;
  steps: readonly { kind: string }[];
  expectedResult: string;
  verificationCriteria: readonly string[];
}): PlanTask {
  return {
    id: input.id,
    title: input.title,
    description: input.description,
    steps: input.steps as PlanTask["steps"],
    expectedResult: input.expectedResult,
    verificationCriteria: [...input.verificationCriteria],
  };
}
