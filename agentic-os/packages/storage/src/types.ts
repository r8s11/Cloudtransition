// Persistence-layer types for the storage package.
//
// These describe the *stored* shape plus repository input/output contracts.
// Domain objects (Mission, Plan) are imported from @agentic-os/core and are
// the runtime source of truth; the storage package never redefines them.

import type { Mission, Plan, MissionStatus } from "@agentic-os/core";

export type { Mission, Plan, MissionStatus };

/** Options for listing missions from the repository. */
export interface MissionListOptions {
  status?: MissionStatus;
  limit?: number;
  offset?: number;
}

/** A single persisted mission status change (audit record). */
export interface MissionTransitionRecord {
  id: number;
  missionId: string;
  fromStatus: MissionStatus;
  toStatus: MissionStatus;
  reason: string | null;
  createdAt: string; // ISO-8601
}

/** Stored approval request, matching the schema in 001_initial.sql. */
export interface ApprovalRecord {
  id: string;
  missionId: string;
  runId: string | null;
  capability: string;
  action: string;
  reason: string;
  risk: string; // ActionRisk as string
  status: "pending" | "approved" | "rejected";
  createdAt: string; // ISO-8601
  resolvedAt: string | null;
}

/** Input for creating an approval request (storage does not generate IDs/decisions). */
export interface CreateApprovalInput {
  id: string;
  missionId: string;
  runId?: string;
  capability: string;
  action: string;
  reason: string;
  risk: string;
}

/** Input for resolving (approve/reject) an approval request. */
export interface ResolveApprovalInput {
  status: "approved" | "rejected";
  resolvedAt: string; // ISO-8601
}

// ── Agent runtime (migration 002/003) ──────────────────────────────────────

export type AgentRunStatus =
  | "starting"
  | "running"
  | "interrupting"
  | "terminating"
  | "completed"
  | "failed"
  | "interrupted"
  | "terminated"
  | "lost";

/** A registered Git repository root. */
export interface ProjectRecord {
  id: string;
  name: string;
  path: string;
  createdAt: string;
}

/** One supervised agent process, as persisted in agent_runs. */
export interface AgentRunRecord {
  id: string;
  projectId: string;
  adapterId: string;
  prompt: string;
  status: AgentRunStatus;
  createdAt: string;
  startedAt: string | null;
  endedAt: string | null;
  error: string | null;
  pid: number | null;
  ownerId: string;
  missionId: string | null;
  planVersion: number | null;
  taskId: string | null;
  exitCode: number | null;
  signal: string | null;
  model: string | null;
  effort: string | null;
  inputTokens: number | null;
  outputTokens: number | null;
  costUsd: number | null;
}

/** Ordered capture chunk or lifecycle state for a run. */
export interface RunEventRecord {
  id: number;
  runId: string;
  kind: "state" | "stdout" | "stderr";
  data: string;
  createdAt: string;
}

export interface RunListOptions {
  active?: boolean;
  projectId?: string;
  limit?: number;
  offset?: number;
}

/** Usage grouped by prompt and adapter for the dashboard ledger. */
export interface RunUsageRecord {
  prompt: string;
  adapterId: string;
  runs: number;
  meteredRuns: number;
  inputTokens: number;
  outputTokens: number;
  costUsd: number;
  lastRunAt: string;
}
