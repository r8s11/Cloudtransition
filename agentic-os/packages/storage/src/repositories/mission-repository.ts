import type { Database } from "../database.js";
import type { Mission, MissionListOptions, MissionStatus } from "../types.js";
import { IsoStringSchema } from "@agentic-os/core";

/** Persistence contract for missions. No raw SQL escapes this package. */
export interface MissionRepository {
  create(mission: Mission): Promise<void>;
  getById(id: string): Promise<Mission | null>;
  update(mission: Mission): Promise<void>;
  list(options?: MissionListOptions): Promise<Mission[]>;
}

function rowToMission(row: any): Mission {
  const createdAt = IsoStringSchema.parse(row.created_at);
  const updatedAt = IsoStringSchema.parse(row.updated_at);
  const mission: Mission = {
    id: row.id,
    title: row.title,
    status: row.status as MissionStatus,
    priority: row.priority,
    acceptanceCriteria: JSON.parse(row.acceptance_criteria) as string[],
    createdAt,
    updatedAt,
  };
  if (row.description !== null && row.description !== undefined) {
    mission.description = row.description;
  }
  if (row.started_at !== null && row.started_at !== undefined) {
    mission.startedAt = IsoStringSchema.parse(row.started_at);
  }
  if (row.completed_at !== null && row.completed_at !== undefined) {
    mission.completedAt = IsoStringSchema.parse(row.completed_at);
  }
  return mission;
}

export class SqliteMissionRepository implements MissionRepository {
  constructor(private readonly db: Database) {}

  async create(mission: Mission): Promise<void> {
    // Validate timestamps at the persistence boundary.
    IsoStringSchema.parse(mission.createdAt);
    IsoStringSchema.parse(mission.updatedAt);
    this.db
      .prepare(
        `INSERT INTO missions
           (id, title, description, status, priority, acceptance_criteria, created_at, updated_at, started_at, completed_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        mission.id,
        mission.title,
        mission.description ?? null,
        mission.status,
        mission.priority,
        JSON.stringify(mission.acceptanceCriteria),
        mission.createdAt,
        mission.updatedAt,
        mission.startedAt ?? null,
        mission.completedAt ?? null,
      );
  }

  async getById(id: string): Promise<Mission | null> {
    const row = this.db
      .prepare("SELECT * FROM missions WHERE id = ?")
      .get(id) as any | undefined;
    return row ? rowToMission(row) : null;
  }

  async update(mission: Mission): Promise<void> {
    IsoStringSchema.parse(mission.updatedAt);
    const result = this.db
      .prepare(
        `UPDATE missions SET
           title = ?, description = ?, status = ?, priority = ?,
           acceptance_criteria = ?, updated_at = ?, started_at = ?, completed_at = ?
         WHERE id = ?`,
      )
      .run(
        mission.title,
        mission.description ?? null,
        mission.status,
        mission.priority,
        JSON.stringify(mission.acceptanceCriteria),
        mission.updatedAt,
        mission.startedAt ?? null,
        mission.completedAt ?? null,
        mission.id,
      );
    if (result.changes === 0) {
      throw new Error(`Mission '${mission.id}' not found`);
    }
  }

  async list(options?: MissionListOptions): Promise<Mission[]> {
    const clauses: string[] = [];
    const params: unknown[] = [];
    if (options?.status) {
      clauses.push("status = ?");
      params.push(options.status);
    }
    let sql = "SELECT * FROM missions";
    if (clauses.length) sql += " WHERE " + clauses.join(" AND ");
    sql += " ORDER BY created_at ASC";
    if (typeof options?.limit === "number") {
      sql += " LIMIT ?";
      params.push(options.limit);
      if (typeof options?.offset === "number") {
        sql += " OFFSET ?";
        params.push(options.offset);
      }
    }
    const rows = this.db.prepare(sql).all(...(params as any[])) as any[];
    return rows.map(rowToMission);
  }
}
