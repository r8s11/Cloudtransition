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
