import type { Database } from "../database.js";
import type { Plan } from "../types.js";
import { parsePlan } from "@agentic-os/core";

/** A stored plan row. */
export interface PlanRecord {
  id: number;
  missionId: string;
  version: number;
  plan: Plan;
  createdAt: string;
}

/** Persistence contract for plans. Plans stay denormalized JSON in Phase 2. */
export interface PlanRepository {
  save(missionId: string, plan: Plan): Promise<void>;
  getLatest(missionId: string): Promise<Plan | null>;
}

export class SqlitePlanRepository implements PlanRepository {
  constructor(private readonly db: Database) {}

  /** Validate via Core schema, then persist as the next version. */
  async save(missionId: string, plan: Plan): Promise<void> {
    // Core validation: throws on invalid plan (e.g. missing verificationCriteria).
    const validated = parsePlan(plan);
    if (validated.missionId !== missionId) {
      throw new Error(
        `Plan missionId '${validated.missionId}' does not match '${missionId}'`,
      );
    }

    const versionRow = this.db
      .prepare("SELECT COALESCE(MAX(version), 0) AS max_version FROM plans WHERE mission_id = ?")
      .get(missionId) as { max_version: number } | undefined;
    const nextVersion = (versionRow?.max_version ?? 0) + 1;

    this.db
      .prepare(
        `INSERT INTO plans (mission_id, version, plan_json, created_at)
         VALUES (?, ?, ?, ?)`,
      )
      .run(
        missionId,
        nextVersion,
        JSON.stringify(validated),
        new Date().toISOString(),
      );
  }

  async getLatest(missionId: string): Promise<Plan | null> {
    const row = this.db
      .prepare(
        "SELECT * FROM plans WHERE mission_id = ? ORDER BY version DESC LIMIT 1",
      )
      .get(missionId) as any | undefined;
    if (!row) return null;
    const parsed = JSON.parse(row.plan_json) as unknown;
    // Re-validate on read so stored data can never desync from the schema.
    return parsePlan(parsed);
  }
}
