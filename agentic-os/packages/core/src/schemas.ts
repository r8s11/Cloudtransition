import { z } from "zod";

// ── Mission status ───────────────────────────────────────────────────────

export const MissionStatusSchema = z.enum([
  "draft",
  "queued",
  "running",
  "awaiting_approval",
  "paused",
  "failed",
  "completed",
  "cancelled",
]);

// ── Task status ──────────────────────────────────────────────────────────

export const TaskStatusSchema = z.enum([
  "pending",
  "in_progress",
  "completed",
  "failed",
  "cancelled",
]);

// ── Verification status ──────────────────────────────────────────────────

export const VerificationStatusSchema = z.enum([
  "pending",
  "passed",
  "failed",
  "inconclusive",
]);

// ── Priority ─────────────────────────────────────────────────────────────

export const PrioritySchema = z.enum(["critical", "high", "medium", "low"]);

// ── Capability ───────────────────────────────────────────────────────────

export const CapabilitySchema = z.enum([
  "memory",
  "reasoning",
  "tool_use",
  "planning",
  "execution",
]);

// ── Policy outcome ──────────────────────────────────────────────────────

export const PolicyOutcomeSchema = z.enum(["allow", "deny", "review"]);

// ── Event type ──────────────────────────────────────────────────────────

export const EventTypeSchema = z.enum([
  "mission_created",
  "mission_started",
  "mission_completed",
  "mission_cancelled",
  "mission_failed",
  "mission_paused",
  "mission_resumed",
  "task_started",
  "task_completed",
  "task_failed",
  "approval_requested",
  "approval_granted",
  "approval_denied",
  "verification_passed",
  "verification_failed",
  "tool_call_started",
  "tool_call_completed",
  "tool_call_failed",
]);

// ── Timestamp helpers ───────────────────────────────────────────────────

export const IsoStringSchema = z.string().datetime({ offset: true });

// ── Plan step schemas ────────────────────────────────────────────────────

export const ConnectorCallStepSchema = z.object({
  kind: z.literal("connector_call"),
  connector: z.string().min(1),
  action: z.string().min(1),
  expectedObservation: z.string().min(1),
});

export const MemoryWriteStepSchema = z.object({
  kind: z.literal("memory_write"),
  partition: z.string().min(1),
  expectedObservation: z.string().min(1),
});

export const ReasoningStepSchema = z.object({
  kind: z.literal("reasoning"),
  expectedObservation: z.string().min(1),
});

export const PlanStepSchema = z.union([
  ConnectorCallStepSchema,
  MemoryWriteStepSchema,
  ReasoningStepSchema,
]);

// ── Plan task schema ─────────────────────────────────────────────────────

export const PlanTaskSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  description: z.string().optional(),
  steps: z.array(PlanStepSchema),
  expectedResult: z.string().min(1),
  verificationCriteria: z.array(z.string().min(1)).min(1, "At least one verification criterion is required"),
  /** Hub routing: the agent that owns this task. Optional for pre-hub plans. */
  owner: z.string().min(1).optional(),
  /** Hub routing: task ids that must complete before this one may start. */
  dependsOn: z.array(z.string().min(1)).optional(),
});

// ── Plan schema ──────────────────────────────────────────────────────────

export const PlanSchema = z.object({
  missionId: z.string().min(1),
  tasks: z.array(PlanTaskSchema).min(1, "A plan must have at least one task"),
});

// ── CreateMissionInput schema ────────────────────────────────────────────

export const CreateMissionInputSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  description: z.string().optional(),
  acceptanceCriteria: z.array(z.string().min(1)).min(1, "Acceptance criteria must be non-empty"),
  priority: PrioritySchema,
});

// ── Parse helpers ────────────────────────────────────────────────────────

export function parseMissionStatus(value: unknown) {
  return MissionStatusSchema.parse(value);
}
