// Internal persistence for the hub_* tables (migration 004). Missions, plans and
// approvals are never written here: reads below are sync projections for the
// session view; every mutation of those tables goes through MissionService or
// the storage repositories.

import { randomUUID } from "node:crypto";
import { parsePlan, type Mission, type Plan } from "@agentic-os/core";
import type { Database } from "@agentic-os/storage";
import type { HubMessage } from "./types.js";

export interface SessionRow {
  mission_id: string;
  budget: number;
  max_depth: number;
  models_json: string;
  criteria_refs_json: string;
  recommendation: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskRow {
  mission_id: string;
  task_id: string;
  owner: string;
  status: "pending" | "in_progress" | "completed" | "blocked" | "interrupted";
  lease_key: string | null;
  run_id: string | null;
  blocked_reason: string | null;
  guard_snapshot: string | null;
  git_head: string | null;
  updated_at: string;
}

export interface WaitingRow {
  id: string;
  mission_id: string;
  kind: "approval" | "budget" | "blocker";
  title: string;
  detail: string;
  action: string;
  approval_id: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface AuditRow {
  id: number;
  mission_id: string;
  kind: string;
  detail: string;
  created_at: string;
}

export interface TaskPatch {
  status?: TaskRow["status"];
  lease_key?: string | null;
  run_id?: string | null;
  blocked_reason?: string | null;
  guard_snapshot?: string | null;
  git_head?: string | null;
}

function messageFromRow(row: Record<string, unknown>): HubMessage {
  return {
    id: row.id as string,
    missionId: row.mission_id as string,
    taskId: (row.task_id as string | null) ?? null,
    inReplyTo: (row.in_reply_to as string | null) ?? null,
    from: row.from_agent as string,
    to: row.to_agent as string,
    type: row.type as HubMessage["type"],
    objective: row.objective as string,
    doneWhen: row.done_when as string,
    inputRefs: JSON.parse(row.input_refs as string) as string[],
    outputRefs: JSON.parse(row.output_refs as string) as string[],
    result: row.result as string,
    evidence: JSON.parse(row.evidence as string) as string[],
    decisions: JSON.parse(row.decisions as string) as string[],
    blockers: JSON.parse(row.blockers as string) as string[],
    approvalNeeded: row.approval_needed === 1,
    idempotencyKey: row.idempotency_key as string,
    createdAt: row.created_at as string,
  };
}

export class HubStore {
  constructor(private readonly db: Database) {}

  createSession(
    missionId: string,
    budget: number,
    maxDepth: number,
    criteriaRefs: string[],
    now: string,
  ): void {
    this.db
      .prepare(
        `INSERT INTO hub_sessions (mission_id, budget, max_depth, models_json, criteria_refs_json, recommendation, created_at, updated_at)
         VALUES (?, ?, ?, '{}', ?, NULL, ?, ?)`,
      )
      .run(missionId, budget, maxDepth, JSON.stringify(criteriaRefs), now, now);
  }

  getSession(missionId: string): SessionRow | null {
    return (
      (this.db
        .prepare("SELECT * FROM hub_sessions WHERE mission_id = ?")
        .get(missionId) as SessionRow | undefined) ?? null
    );
  }

  listSessionMissionIds(): string[] {
    return (
      this.db
        .prepare("SELECT mission_id FROM hub_sessions ORDER BY created_at, mission_id")
        .all() as { mission_id: string }[]
    ).map((row) => row.mission_id);
  }

  setRecommendation(missionId: string, recommendation: string, now: string): void {
    this.db
      .prepare(
        "UPDATE hub_sessions SET recommendation = ?, updated_at = ? WHERE mission_id = ?",
      )
      .run(recommendation, now, missionId);
  }

  addBudget(missionId: string, delta: number, now: string): void {
    this.db
      .prepare(
        "UPDATE hub_sessions SET budget = budget + ?, updated_at = ? WHERE mission_id = ?",
      )
      .run(delta, now, missionId);
  }

  insertTask(missionId: string, taskId: string, owner: string, now: string): void {
    this.db
      .prepare(
        `INSERT INTO hub_tasks (mission_id, task_id, owner, status, updated_at)
         VALUES (?, ?, ?, 'pending', ?)`,
      )
      .run(missionId, taskId, owner, now);
  }

  getTask(missionId: string, taskId: string): TaskRow | null {
    return (
      (this.db
        .prepare("SELECT * FROM hub_tasks WHERE mission_id = ? AND task_id = ?")
        .get(missionId, taskId) as TaskRow | undefined) ?? null
    );
  }

  /** Insertion order is plan order. */
  listTasks(missionId: string): TaskRow[] {
    return this.db
      .prepare("SELECT * FROM hub_tasks WHERE mission_id = ? ORDER BY rowid")
      .all(missionId) as unknown as TaskRow[];
  }

  updateTask(missionId: string, taskId: string, patch: TaskPatch, now: string): void {
    const sets: string[] = ["updated_at = ?"];
    const args: (string | number | null)[] = [now];
    for (const [key, value] of Object.entries(patch)) {
      sets.push(`${key} = ?`);
      args.push(value ?? null);
    }
    args.push(missionId, taskId);
    this.db
      .prepare(
        `UPDATE hub_tasks SET ${sets.join(", ")} WHERE mission_id = ? AND task_id = ?`,
      )
      .run(...args);
  }

  insertMessage(message: HubMessage): void {
    this.db
      .prepare(
        `INSERT INTO hub_messages (id, mission_id, task_id, in_reply_to, from_agent, to_agent, type,
           objective, done_when, input_refs, output_refs, result, evidence, decisions, blockers,
           approval_needed, idempotency_key, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        message.id,
        message.missionId,
        message.taskId,
        message.inReplyTo,
        message.from,
        message.to,
        message.type,
        message.objective,
        message.doneWhen,
        JSON.stringify(message.inputRefs),
        JSON.stringify(message.outputRefs),
        message.result,
        JSON.stringify(message.evidence),
        JSON.stringify(message.decisions),
        JSON.stringify(message.blockers),
        message.approvalNeeded ? 1 : 0,
        message.idempotencyKey,
        message.createdAt,
      );
  }

  messageByKey(idempotencyKey: string): HubMessage | null {
    const row = this.db
      .prepare("SELECT * FROM hub_messages WHERE idempotency_key = ?")
      .get(idempotencyKey) as Record<string, unknown> | undefined;
    return row ? messageFromRow(row) : null;
  }

  listMessages(missionId: string): HubMessage[] {
    return (
      this.db
        .prepare(
          "SELECT * FROM hub_messages WHERE mission_id = ? ORDER BY created_at, id",
        )
        .all(missionId) as Record<string, unknown>[]
    ).map(messageFromRow);
  }

  addSubscription(missionId: string, kind: "run_completion" | "new_message", now: string): void {
    this.db
      .prepare(
        "INSERT OR IGNORE INTO hub_subscriptions (mission_id, kind, created_at) VALUES (?, ?, ?)",
      )
      .run(missionId, kind, now);
  }

  listSubscriptions(missionId: string): { kind: string; created_at: string }[] {
    return this.db
      .prepare("SELECT kind, created_at FROM hub_subscriptions WHERE mission_id = ?")
      .all(missionId) as { kind: string; created_at: string }[];
  }

  insertWaiting(
    waiting: Omit<WaitingRow, "created_at" | "resolved_at">,
    now: string,
  ): void {
    this.db
      .prepare(
        `INSERT INTO hub_waiting (id, mission_id, kind, title, detail, action, approval_id, created_at, resolved_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)`,
      )
      .run(
        waiting.id,
        waiting.mission_id,
        waiting.kind,
        waiting.title,
        waiting.detail,
        waiting.action,
        waiting.approval_id,
        now,
      );
  }

  getWaiting(id: string): WaitingRow | null {
    return (
      (this.db
        .prepare("SELECT * FROM hub_waiting WHERE id = ?")
        .get(id) as WaitingRow | undefined) ?? null
    );
  }

  listWaiting(missionId: string, unresolvedOnly = false): WaitingRow[] {
    return this.db
      .prepare(
        `SELECT * FROM hub_waiting WHERE mission_id = ?${unresolvedOnly ? " AND resolved_at IS NULL" : ""} ORDER BY created_at, id`,
      )
      .all(missionId) as unknown as WaitingRow[];
  }

  resolveWaiting(id: string, now: string): void {
    this.db
      .prepare("UPDATE hub_waiting SET resolved_at = ? WHERE id = ?")
      .run(now, id);
  }

  audit(missionId: string, kind: string, detail: string, now: string): void {
    this.db
      .prepare(
        "INSERT INTO hub_audit (mission_id, kind, detail, created_at) VALUES (?, ?, ?, ?)",
      )
      .run(missionId, kind, detail, now);
  }

  listAudit(missionId: string): AuditRow[] {
    return this.db
      .prepare("SELECT * FROM hub_audit WHERE mission_id = ? ORDER BY id")
      .all(missionId) as unknown as AuditRow[];
  }
}

/** Read-only mission projection for the sync session view. Writes go through MissionService. */
export function readMission(db: Database, missionId: string): Mission | null {
  const row = db
    .prepare("SELECT * FROM missions WHERE id = ?")
    .get(missionId) as Record<string, unknown> | undefined;
  if (!row) return null;
  const mission: Mission = {
    id: row.id as string,
    title: row.title as string,
    status: row.status as Mission["status"],
    priority: row.priority as Mission["priority"],
    acceptanceCriteria: JSON.parse(row.acceptance_criteria as string) as string[],
    createdAt: row.created_at as string,
    updatedAt: row.updated_at as string,
  };
  if (row.description != null) mission.description = row.description as string;
  if (row.started_at != null) mission.startedAt = row.started_at as string;
  if (row.completed_at != null) mission.completedAt = row.completed_at as string;
  return mission;
}

/** Read-only latest plan projection. Writes go through SqlitePlanRepository. */
export function readLatestPlan(
  db: Database,
  missionId: string,
): { version: number; plan: Plan } | null {
  const row = db
    .prepare(
      "SELECT version, plan_json FROM plans WHERE mission_id = ? ORDER BY version DESC LIMIT 1",
    )
    .get(missionId) as { version: number; plan_json: string } | undefined;
  if (!row) return null;
  return { version: row.version, plan: parsePlan(JSON.parse(row.plan_json)) };
}

export function newMessageId(): string {
  return randomUUID();
}
