import { randomUUID } from "node:crypto";

import {
  createMission,
  transitionMission,
  canTransition,
  type Mission,
  type MissionStatus,
  type Priority,
  type CreateMissionInput,
} from "@agentic-os/core";
import {
  type MissionRepository,
  type PlanRepository,
  type TransitionRepository,
  type ApprovalRepository,
  type CreateApprovalInput,
  type ApprovalRecord,
  type MissionTransitionRecord,
  type Database,
  SqliteMissionRepository,
  SqlitePlanRepository,
  SqliteTransitionRepository,
  SqliteApprovalRepository,
} from "@agentic-os/storage";

const ALL_STATUSES: readonly MissionStatus[] = [
  "draft",
  "queued",
  "running",
  "awaiting_approval",
  "paused",
  "failed",
  "completed",
  "cancelled",
];

export interface CreateMissionPayload {
  title: string;
  description?: string;
  priority?: Priority;
  acceptanceCriteria: string[];
  id?: string;
}

export interface CreateApprovalPayload {
  missionId: string;
  capability: string;
  action: string;
  reason: string;
  risk: string;
  runId?: string;
  id?: string;
}

/**
 * The only component the HTTP layer talks to. Composes Core for rules and
 * storage for persistence — never re-implements transitions or writes SQL.
 */
export class MissionService {
  constructor(
    private readonly missions: MissionRepository,
    private readonly plans: PlanRepository,
    private readonly transitions: TransitionRepository,
    private readonly approvals: ApprovalRepository,
    private readonly clock: () => Date = () => new Date(),
  ) {}

  list(status?: MissionStatus): Promise<Mission[]> {
    return this.missions.list(status ? { status } : undefined);
  }

  get(id: string): Promise<Mission | null> {
    return this.missions.getById(id);
  }

  getLatestPlan(id: string) {
    return this.plans.getLatest(id);
  }

  history(id: string): Promise<MissionTransitionRecord[]> {
    return this.transitions.listForMission(id);
  }

  async create(input: CreateMissionPayload): Promise<Mission> {
    const missionInput: CreateMissionInput = {
      id: input.id ?? randomUUID(),
      title: input.title,
      description: input.description,
      acceptanceCriteria: input.acceptanceCriteria,
      priority: input.priority ?? "medium",
    };
    const mission = createMission(missionInput, this.clock);
    await this.missions.create(mission);
    return mission;
  }

  async transition(id: string, to: MissionStatus, reason?: string): Promise<Mission> {
    const current = await this.missions.getById(id);
    if (!current) {
      throw new Error(`Mission '${id}' not found`);
    }
    if (!canTransition(current.status, to)) {
      throw new Error(
        `cannot transition mission '${id}' from '${current.status}' to '${to}'`,
      );
    }
    const updated = transitionMission(current, to, this.clock);
    await this.missions.update(updated);
    await this.transitions.record({
      missionId: id,
      fromStatus: current.status,
      toStatus: to,
      reason: reason ?? null,
      createdAt: this.clock().toISOString(),
    });
    return updated;
  }

  listApprovals(status?: ApprovalRecord["status"]): Promise<ApprovalRecord[]> {
    return this.approvals.list(status ? { status } : undefined);
  }

  async createApproval(input: CreateApprovalPayload): Promise<ApprovalRecord> {
    const record: CreateApprovalInput = {
      id: input.id ?? randomUUID(),
      missionId: input.missionId,
      runId: input.runId,
      capability: input.capability,
      action: input.action,
      reason: input.reason,
      risk: input.risk,
    };
    return this.approvals.create(record);
  }

  async resolveApproval(id: string, status: "approved" | "rejected"): Promise<ApprovalRecord> {
    return this.approvals.resolve(id, {
      status,
      resolvedAt: this.clock().toISOString(),
    });
  }

  transitionMatrix(): Record<MissionStatus, MissionStatus[]> {
    const out = {} as Record<MissionStatus, MissionStatus[]>;
    for (const from of ALL_STATUSES) {
      out[from] = ALL_STATUSES.filter((to) => canTransition(from, to));
    }
    return out;
  }
}

/** Open a MissionService bound to a SQLite database. */
export function openMissionService(db: Database, clock: () => Date = () => new Date()): MissionService {
  return new MissionService(
    new SqliteMissionRepository(db),
    new SqlitePlanRepository(db),
    new SqliteTransitionRepository(db),
    new SqliteApprovalRepository(db),
    clock,
  );
}
