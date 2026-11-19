import { IsoStringSchema } from "@agentic-os/core";
import type { SQLInputValue } from "node:sqlite";
import type { Database } from "../database.js";
import type {
  AgentRunRecord,
  ProjectRecord,
  RunEventRecord,
  RunListOptions,
  RunUsageRecord,
} from "../types.js";

const RUN_COLUMNS = `id, project_id AS projectId, adapter_id AS adapterId, prompt, status,
  created_at AS createdAt, started_at AS startedAt, ended_at AS endedAt, error, pid,
  owner_id AS ownerId, mission_id AS missionId, plan_version AS planVersion,
  task_id AS taskId, exit_code AS exitCode, signal, model, effort,
  input_tokens AS inputTokens, output_tokens AS outputTokens, cost_usd AS costUsd`;
const ACTIVE_STATUSES = "('starting','running','interrupting','terminating')";

function integer(
  value: number,
  minimum: number,
  maximum = Number.MAX_SAFE_INTEGER,
): number {
  if (!Number.isSafeInteger(value) || value < minimum || value > maximum)
    throw new Error("Invalid pagination value");
  return value;
}

export class SqliteRuntimeRepository {
  constructor(private readonly db: Database) {}

  registerProject(project: ProjectRecord): ProjectRecord {
    IsoStringSchema.parse(project.createdAt);
    this.db
      .prepare(
        `INSERT INTO projects (id, name, path, created_at) VALUES (?, ?, ?, ?)
      ON CONFLICT(path) DO NOTHING`,
      )
      .run(project.id, project.name, project.path, project.createdAt);
    return this.db
      .prepare(
        "SELECT id, name, path, created_at AS createdAt FROM projects WHERE path = ?",
      )
      .get(project.path) as unknown as ProjectRecord;
  }

  getProject(id: string): ProjectRecord | null {
    return (
      (this.db
        .prepare(
          "SELECT id, name, path, created_at AS createdAt FROM projects WHERE id = ?",
        )
        .get(id) as unknown as ProjectRecord | undefined) ?? null
    );
  }

  listProjects(): ProjectRecord[] {
    return this.db
      .prepare(
        "SELECT id, name, path, created_at AS createdAt FROM projects ORDER BY created_at, id",
      )
      .all() as unknown as ProjectRecord[];
  }

  createRun(run: AgentRunRecord): void {
    IsoStringSchema.parse(run.createdAt);
    this.db.transaction(() => {
      this.db
        .prepare(
          `INSERT INTO agent_runs
        (id, project_id, adapter_id, prompt, status, created_at, started_at, ended_at,
         error, pid, owner_id, mission_id, plan_version, task_id, exit_code, signal,
         model, effort)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        )
        .run(
          run.id,
          run.projectId,
          run.adapterId,
          run.prompt,
          run.status,
          run.createdAt,
          run.startedAt,
          run.endedAt,
          run.error,
          run.pid,
          run.ownerId,
          run.missionId,
          run.planVersion,
          run.taskId,
          run.exitCode,
          run.signal,
          run.model ?? null,
          run.effort ?? null,
        );
      this.appendEvent(run.id, "state", run.status);
    });
  }

  getRun(id: string): AgentRunRecord | null {
    return (
      (this.db
        .prepare(`SELECT ${RUN_COLUMNS} FROM agent_runs WHERE id = ?`)
        .get(id) as unknown as AgentRunRecord | undefined) ?? null
    );
  }

  listRuns(options: RunListOptions = {}): AgentRunRecord[] {
    const where: string[] = [];
    const args: SQLInputValue[] = [];
    if (options.active !== undefined)
      where.push(
        `status ${options.active ? "IN" : "NOT IN"} ${ACTIVE_STATUSES}`,
      );
    if (options.projectId !== undefined) {
      where.push("project_id = ?");
      args.push(options.projectId);
    }
    const limit = integer(options.limit ?? 100, 1, 1000);
    const offset = integer(options.offset ?? 0, 0);
    return this.db
      .prepare(
        `SELECT ${RUN_COLUMNS} FROM agent_runs
      ${where.length ? `WHERE ${where.join(" AND ")}` : ""}
      ORDER BY created_at DESC, id LIMIT ? OFFSET ?`,
      )
      .all(...args, limit, offset) as unknown as AgentRunRecord[];
  }

  updateRun(run: AgentRunRecord): void {
    if (run.startedAt !== null) IsoStringSchema.parse(run.startedAt);
    if (run.endedAt !== null) IsoStringSchema.parse(run.endedAt);
    this.db.transaction(() => {
      const previous = this.getRun(run.id);
      if (!previous) throw new Error("Run not found");
      const result = this.db
        .prepare(
          `UPDATE agent_runs SET
        status = ?, started_at = ?, ended_at = ?, error = ?, pid = ?, exit_code = ?, signal = ?,
        input_tokens = ?, output_tokens = ?, cost_usd = ?
        WHERE id = ? AND owner_id = ?`,
        )
        .run(
          run.status,
          run.startedAt,
          run.endedAt,
          run.error,
          run.pid,
          run.exitCode,
          run.signal,
          run.inputTokens ?? null,
          run.outputTokens ?? null,
          run.costUsd ?? null,
          run.id,
          run.ownerId,
        );
      if (Number(result.changes) !== 1) throw new Error("Run owner mismatch");
      if (previous.status !== run.status)
        this.appendEvent(run.id, "state", run.status);
    });
  }

  /** Runs created at or after `since`, grouped by prompt and adapter, most expensive first. */
  usageByPrompt(since: string, limit = 50): RunUsageRecord[] {
    IsoStringSchema.parse(since);
    return this.db
      .prepare(
        `SELECT prompt, adapter_id AS adapterId, COUNT(*) AS runs,
        COUNT(cost_usd) AS meteredRuns,
        COALESCE(SUM(input_tokens), 0) AS inputTokens,
        COALESCE(SUM(output_tokens), 0) AS outputTokens,
        COALESCE(SUM(cost_usd), 0) AS costUsd, MAX(created_at) AS lastRunAt
      FROM agent_runs WHERE created_at >= ?
      GROUP BY prompt, adapter_id
      ORDER BY costUsd DESC, inputTokens + outputTokens DESC, lastRunAt DESC, prompt
      LIMIT ?`,
      )
      .all(since, integer(limit, 1, 200)) as unknown as RunUsageRecord[];
  }

  appendEvent(runId: string, kind: RunEventRecord["kind"], data: string): void {
    this.db
      .prepare(
        "INSERT INTO run_events (run_id, kind, data, created_at) VALUES (?, ?, ?, ?)",
      )
      .run(runId, kind, data, new Date().toISOString());
  }

  listEvents(runId: string, after = 0, limit = 100): RunEventRecord[] {
    return this.db
      .prepare(
        `SELECT id, run_id AS runId, kind, data, created_at AS createdAt
      FROM run_events WHERE run_id = ? AND id > ? ORDER BY id LIMIT ?`,
      )
      .all(
        runId,
        integer(after, 0),
        integer(limit, 1, 1000),
      ) as unknown as RunEventRecord[];
  }
}
