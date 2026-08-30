import type { Database } from "../database.js";
import type { MissionTransitionRecord, MissionStatus } from "../types.js";
import { IsoStringSchema } from "@agentic-os/core";

/** Persistence contract for mission transition (audit) history. */
export interface TransitionRepository {
  record(input: {
    missionId: string;
    fromStatus: MissionStatus;
    toStatus: MissionStatus;
    reason: string | null;
    createdAt: string;
  }): Promise<void>;
  listForMission(missionId: string): Promise<MissionTransitionRecord[]>;
}

export class SqliteTransitionRepository implements TransitionRepository {
  constructor(private readonly db: Database) {}

  async record(input: {
    missionId: string;
    fromStatus: MissionStatus;
    toStatus: MissionStatus;
    reason: string | null;
    createdAt: string;
  }): Promise<void> {
    IsoStringSchema.parse(input.createdAt);
    this.db
      .prepare(
        `INSERT INTO mission_transitions
           (mission_id, from_status, to_status, reason, created_at)
         VALUES (?, ?, ?, ?, ?)`,
      )
      .run(
        input.missionId,
        input.fromStatus,
        input.toStatus,
        input.reason ?? null,
        input.createdAt,
      );
  }

  async listForMission(missionId: string): Promise<MissionTransitionRecord[]> {
    const rows = this.db
      .prepare(
        "SELECT * FROM mission_transitions WHERE mission_id = ? ORDER BY id ASC",
      )
      .all(missionId) as any[];
    return rows.map((row) => ({
      id: row.id,
      missionId: row.mission_id,
      fromStatus: row.from_status as MissionStatus,
      toStatus: row.to_status as MissionStatus,
      reason: row.reason as string | null,
      createdAt: IsoStringSchema.parse(row.created_at),
    }));
  }
}
