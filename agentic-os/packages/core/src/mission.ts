import { type Mission, type MissionStatus, type CreateMissionInput } from "./types.js";
import { MissionStatusSchema } from "./schemas.js";

// ── Legal transitions ───────────────────────────────────────────────────

const TRANSITION_MATRIX: Readonly<Record<MissionStatus, readonly MissionStatus[]>> = {
  draft: ["queued", "cancelled"],
  queued: ["running", "cancelled"],
  running: ["awaiting_approval", "paused", "failed", "completed"],
  awaiting_approval: ["queued", "cancelled"],
  paused: ["queued", "cancelled"],
  failed: ["queued", "cancelled"],
  completed: [],
  cancelled: [],
};

export function canTransition(from: MissionStatus, to: MissionStatus): boolean {
  const allowed = TRANSITION_MATRIX[from];
  if (!allowed) return false;
  return allowed.includes(to);
}

// ── createMission ────────────────────────────────────────────────────────

export function createMission(input: CreateMissionInput, clock: () => Date): Mission {
  const now = clock();
  return {
    id: input.id,
    title: input.title,
    description: input.description ?? undefined,
    status: "queued",
    priority: input.priority,
    acceptanceCriteria: [...input.acceptanceCriteria],
    createdAt: now.toISOString(),
    updatedAt: now.toISOString(),
  };
}

// ── transitionMission ────────────────────────────────────────────────────

export function transitionMission(
  mission: Mission,
  nextStatus: MissionStatus,
  clock: () => Date,
): Mission {
  if (!canTransition(mission.status, nextStatus)) {
    throw new Error(
      `cannot transition mission '${mission.id}' from '${mission.status}' to '${nextStatus}'`,
    );
  }

  const now = clock();
  const updated: Mission = {
    ...mission,
    status: nextStatus,
    updatedAt: now.toISOString(),
  };

  if (nextStatus === "running") {
    updated.startedAt = now.toISOString();
  }
  if (nextStatus === "completed") {
    updated.completedAt = now.toISOString();
  }

  return updated;
}

// ── validateMissionStatus ────────────────────────────────────────────────

export function validateMissionStatus(value: unknown): MissionStatus {
  return MissionStatusSchema.parse(value);
}

export { TRANSITION_MATRIX };
