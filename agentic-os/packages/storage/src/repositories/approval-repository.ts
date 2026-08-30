import type { Database } from "../database.js";
import type {
  ApprovalRecord,
  CreateApprovalInput,
  ResolveApprovalInput,
} from "../types.js";
import { IsoStringSchema } from "@agentic-os/core";

/** Legal approval status transitions (resolved approvals are immutable). */
const APPROVAL_RESOLUTION: Readonly<
  Record<ApprovalRecord["status"], readonly ApprovalRecord["status"][]>
> = {
  pending: ["approved", "rejected"],
  approved: [], // terminal
  rejected: [], // terminal
};

/** Persistence contract for approval requests (first-class domain concept). */
export interface ApprovalRepository {
  create(input: CreateApprovalInput): Promise<ApprovalRecord>;
  getById(id: string): Promise<ApprovalRecord | null>;
  list(options?: { missionId?: string; status?: ApprovalRecord["status"] }): Promise<ApprovalRecord[]>;
  resolve(id: string, input: ResolveApprovalInput): Promise<ApprovalRecord>;
}

function rowToApproval(row: any): ApprovalRecord {
  return {
    id: row.id,
    missionId: row.mission_id,
    runId: row.run_id as string | null,
    capability: row.capability,
    action: row.action,
    reason: row.reason,
    risk: row.risk,
    status: row.status,
    createdAt: IsoStringSchema.parse(row.created_at),
    resolvedAt: row.resolved_at as string | null,
  };
}

export class SqliteApprovalRepository implements ApprovalRepository {
  constructor(private readonly db: Database) {}

  async create(input: CreateApprovalInput): Promise<ApprovalRecord> {
    const createdAt = new Date().toISOString();
    this.db
      .prepare(
        `INSERT INTO approval_requests
           (id, mission_id, run_id, capability, action, reason, risk, status, created_at, resolved_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, NULL)`,
      )
      .run(
        input.id,
        input.missionId,
        input.runId ?? null,
        input.capability,
        input.action,
        input.reason,
        input.risk,
        createdAt,
      );
    const created = await this.getById(input.id);
    if (!created) throw new Error(`Failed to load created approval '${input.id}'`);
    return created;
  }

  async getById(id: string): Promise<ApprovalRecord | null> {
    const row = this.db
      .prepare("SELECT * FROM approval_requests WHERE id = ?")
      .get(id) as any | undefined;
    return row ? rowToApproval(row) : null;
  }

  async list(options?: {
    missionId?: string;
    status?: ApprovalRecord["status"];
  }): Promise<ApprovalRecord[]> {
    const clauses: string[] = [];
    const params: any[] = [];
    if (options?.missionId) {
      clauses.push("mission_id = ?");
      params.push(options.missionId);
    }
    if (options?.status) {
      clauses.push("status = ?");
      params.push(options.status);
    }
    let sql = "SELECT * FROM approval_requests";
    if (clauses.length) sql += " WHERE " + clauses.join(" AND ");
    sql += " ORDER BY created_at ASC";
    const rows = this.db.prepare(sql).all(...params) as any[];
    return rows.map(rowToApproval);
  }

  async resolve(id: string, input: ResolveApprovalInput): Promise<ApprovalRecord> {
    const current = await this.getById(id);
    if (!current) throw new Error(`Approval '${id}' not found`);
    const allowed = APPROVAL_RESOLUTION[current.status];
    if (!allowed.includes(input.status)) {
      throw new Error(
        `cannot resolve approval '${id}' from '${current.status}' to '${input.status}'`,
      );
    }
    IsoStringSchema.parse(input.resolvedAt);
    this.db
      .prepare(
        "UPDATE approval_requests SET status = ?, resolved_at = ? WHERE id = ?",
      )
      .run(input.status, input.resolvedAt, id);
    const updated = await this.getById(id);
    if (!updated) throw new Error(`Failed to load resolved approval '${id}'`);
    return updated;
  }
}
