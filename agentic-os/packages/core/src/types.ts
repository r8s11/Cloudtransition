// Core domain types for Agentic OS V1

export type MissionStatus =
  | "draft"
  | "queued"
  | "running"
  | "awaiting_approval"
  | "paused"
  | "failed"
  | "completed"
  | "cancelled";

export type TaskStatus = "pending" | "in_progress" | "completed" | "failed" | "cancelled";

export type VerificationStatus = "pending" | "passed" | "failed" | "inconclusive";

export type Priority = "critical" | "high" | "medium" | "low";

export type Capability = "memory" | "reasoning" | "tool_use" | "planning" | "execution";

export type PolicyOutcome = "allow" | "deny" | "review";

export type EventType =
  | "mission_created"
  | "mission_started"
  | "mission_completed"
  | "mission_cancelled"
  | "mission_failed"
  | "mission_paused"
  | "mission_resumed"
  | "task_started"
  | "task_completed"
  | "task_failed"
  | "approval_requested"
  | "approval_granted"
  | "approval_denied"
  | "verification_passed"
  | "verification_failed"
  | "tool_call_started"
  | "tool_call_completed"
  | "tool_call_failed";

// ── Mission ──────────────────────────────────────────────────────────────

export interface CreateMissionInput {
  id: string;
  title: string;
  description?: string;
  acceptanceCriteria: string[];
  priority: Priority;
}

export interface Mission {
  id: string;
  title: string;
  description?: string;
  status: MissionStatus;
  priority: Priority;
  acceptanceCriteria: string[];
  createdAt: string; // ISO-8601
  updatedAt: string; // ISO-8601
  startedAt?: string; // ISO-8601
  completedAt?: string; // ISO-8601
}

// ── Task ────────────────────────────────────────────────────────────────

export interface Task {
  id: string;
  title: string;
  status: TaskStatus;
  missionId: string;
  order: number;
}

// ── Plan ────────────────────────────────────────────────────────────────

export interface Plan {
  missionId: string;
  tasks: PlanTask[];
}

export interface PlanTask {
  id: string;
  title: string;
  description?: string;
  steps: PlanStep[];
  expectedResult: string;
  verificationCriteria: string[];
  owner?: string;
  dependsOn?: string[];
}

export type PlanStep =
  | ConnectorCallStep
  | MemoryWriteStep
  | ReasoningStep;

export interface ConnectorCallStep {
  kind: "connector_call";
  connector: string;
  action: string;
  expectedObservation: string;
}

export interface MemoryWriteStep {
  kind: "memory_write";
  partition: string;
  expectedObservation: string;
}

export interface ReasoningStep {
  kind: "reasoning";
  expectedObservation: string;
}

// ── Tool Call ───────────────────────────────────────────────────────────

export interface ToolCall {
  id: string;
  kind: string;
  status: "pending" | "running" | "completed" | "failed";
  startedAt?: string;
  completedAt?: string;
}

// ── Verification ────────────────────────────────────────────────────────

export interface Verification {
  id: string;
  status: VerificationStatus;
  criteria: string[];
  checkedAt?: string;
}

// ── Approval ────────────────────────────────────────────────────────────

export interface Approval {
  id: string;
  status: "pending" | "granted" | "denied";
  requestedAt?: string;
  decidedAt?: string;
}

// ── Event ──────────────────────────────────────────────────────────────

export interface Event {
  id: string;
  type: EventType;
  occurredAt: string; // ISO-8601
  data: Record<string, unknown>;
}
