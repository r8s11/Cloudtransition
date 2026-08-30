import { randomUUID } from "node:crypto";

import {
  createMission,
  transitionMission,
  canTransition,
  type Mission,
  type MissionStatus,
  type CreateMissionInput,
} from "@agentic-os/core";
import {
  Database,
  SqliteMissionRepository,
  SqlitePlanRepository,
  SqliteTransitionRepository,
  type MissionRepository,
  type PlanRepository,
  type TransitionRepository,
} from "@agentic-os/storage";

/**
 * Orchestrates mission commands using the Core domain (authoritative for rules)
 * and the storage package (authoritative for persistence). The CLI never
 * re-implements transition logic or writes SQL.
 */
export class MissionCli {
  constructor(
    private readonly missionRepo: MissionRepository,
    private readonly planRepo: PlanRepository,
    private readonly transitionRepo: TransitionRepository,
    private readonly clock: () => Date = () => new Date(),
  ) {}

  /** Create a mission via Core, then persist it. */
  async create(input: CreateMissionInput): Promise<Mission> {
    const mission = createMission(input, this.clock);
    await this.missionRepo.create(mission);
    return mission;
  }

  async get(id: string): Promise<Mission | null> {
    return this.missionRepo.getById(id);
  }

  async list(status?: MissionStatus): Promise<Mission[]> {
    return this.missionRepo.list(status ? { status } : undefined);
  }

  /**
   * Transition a mission. Core validates the transition and produces the
   * updated mission; the CLI persists it and records the audit entry. If Core
   * rejects the transition, nothing is persisted.
   */
  async transition(
    id: string,
    nextStatus: MissionStatus,
    reason?: string,
  ): Promise<Mission> {
    const current = await this.missionRepo.getById(id);
    if (!current) {
      throw new Error(`Mission '${id}' not found`);
    }
    if (!canTransition(current.status, nextStatus)) {
      throw new Error(
        `cannot transition mission '${id}' from '${current.status}' to '${nextStatus}'`,
      );
    }

    const updated = transitionMission(current, nextStatus, this.clock);
    await this.missionRepo.update(updated);
    await this.transitionRepo.record({
      missionId: id,
      fromStatus: current.status,
      toStatus: nextStatus,
      reason: reason ?? null,
      createdAt: this.clock().toISOString(),
    });
    return updated;
  }

  async getLatestPlan(id: string) {
    return this.planRepo.getLatest(id);
  }

  async history(id: string) {
    return this.transitionRepo.listForMission(id);
  }
}

/** Open a CLI bound to a SQLite database file (applies migrations). */
export function openMissionCli(
  dbPath: string,
  clock: () => Date = () => new Date(),
): MissionCli {
  const db = Database.open(dbPath);
  return new MissionCli(
    new SqliteMissionRepository(db),
    new SqlitePlanRepository(db),
    new SqliteTransitionRepository(db),
    clock,
  );
}

export { randomUUID };
