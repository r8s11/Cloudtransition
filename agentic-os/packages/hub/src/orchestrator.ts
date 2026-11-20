// The mission orchestrator: code-routed leases, budget/depth/paid gates,
// handoff validation and the session view. Workers never post to the mailbox
// themselves; the orchestrator turns validated handoffs into messages.

import { randomUUID } from "node:crypto";
import { realpathSync } from "node:fs";
import { resolve } from "node:path";
import {
  canTransition,
  createMission,
  type MissionStatus,
  type PlanTask,
} from "@agentic-os/core";
import {
  SqliteMissionRepository,
  SqlitePlanRepository,
  type AgentRunRecord,
  type Database,
} from "@agentic-os/storage";
import type { AgentRuntime } from "@agentic-os/runtime";
import type { MissionService } from "../../../apps/api/src/mission-service.js";
import {
  ACTIVE_RUN_STATUSES,
  HubError,
  TERMINAL_RUN_STATUSES,
  type AgentRegistry,
  type Handoff,
  type HubMessage,
  type HubMessageInput,
  type HubOptions,
  type SessionView,
} from "./types.js";
import { HubStore, readLatestPlan, readMission } from "./store.js";
import { ingestMessage } from "./mailbox.js";
import { diffSnapshots, evidenceExists, gitHead, snapshotProtected } from "./guardrails.js";
import { recoverHub } from "./recovery.js";

const SLICE_TASKS = [
  { id: "read-posting", title: "Read the job posting", owner: "job-reader" },
  { id: "tailor-cv", title: "Tailor the CV", owner: "cv-adapter" },
  { id: "forge-review", title: "Forge review", owner: "forge" },
  { id: "recommend", title: "Recommend next step", owner: "specialized-chief-of-staff" },
] as const;

const ALL_STATUSES: MissionStatus[] = [
  "draft",
  "queued",
  "running",
  "awaiting_approval",
  "paused",
  "failed",
  "completed",
  "cancelled",
];

async function defaultTrackerLookup(
  company: string,
  role: string,
): Promise<{ status: string; jobUrl: string } | null> {
  const url = `http://127.0.0.1:8000/api/interviews/detail?company=${encodeURIComponent(company)}&role=${encodeURIComponent(role)}`;
  let response: Response;
  try {
    response = await fetch(url);
  } catch {
    throw new HubError("tracker unreachable on loopback", 503);
  }
  if (response.status === 404) return null;
  if (!response.ok) throw new HubError(`tracker lookup failed (${response.status})`, 503);
  const body = (await response.json()) as {
    status?: string;
    jobUrl?: string;
    job_url?: string;
  };
  if (!body.status) return null;
  return { status: body.status, jobUrl: body.jobUrl ?? body.job_url ?? "" };
}

/** Parse the LAST fenced ```handoff block. Throws on malformed JSON or shape. */
export function parseHandoff(stdout: string): Handoff | null {
  const matches = [...stdout.matchAll(/```handoff[^\n]*\n([\s\S]*?)```/g)];
  const last = matches[matches.length - 1];
  if (!last) return null;
  const raw = last[1]!.trim();
  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(raw) as Record<string, unknown>;
  } catch (error) {
    throw new Error(
      `handoff parse error: ${error instanceof Error ? error.message : String(error)}; first 200 chars: ${raw.slice(0, 200)}`,
    );
  }
  const strings = (value: unknown, field: string): string[] => {
    if (value === undefined) return [];
    if (!Array.isArray(value) || value.some((item) => typeof item !== "string"))
      throw new Error(`handoff parse error: ${field} must be an array of strings; first 200 chars: ${raw.slice(0, 200)}`);
    return value as string[];
  };
  if (typeof parsed.result !== "string")
    throw new Error(`handoff parse error: result must be a string; first 200 chars: ${raw.slice(0, 200)}`);
  return {
    result: parsed.result,
    evidence: strings(parsed.evidence, "evidence"),
    decisions: strings(parsed.decisions, "decisions"),
    blockers: strings(parsed.blockers, "blockers"),
    approvalNeeded: parsed.approval_needed === true,
    recommendedReceiver:
      typeof parsed.recommended_receiver === "string" ? parsed.recommended_receiver : null,
  };
}

export class Hub {
  readonly registry: AgentRegistry;
  readonly workspaceRoot: string;
  private readonly store: HubStore;
  private readonly clock: () => Date;
  private readonly budget: number;
  private readonly maxDepth: number;
  private readonly freeModels: string[];
  private readonly trackerLookup: NonNullable<HubOptions["trackerLookup"]>;
  private projectId: string | null = null;

  constructor(
    private readonly db: Database,
    private readonly runtime: AgentRuntime,
    private readonly service: MissionService,
    registry: AgentRegistry,
    opts: HubOptions = {},
  ) {
    this.registry = registry;
    this.workspaceRoot = realpathSync(resolve(opts.workspaceRoot ?? process.cwd()));
    this.clock = opts.clock ?? (() => new Date());
    this.budget = opts.budget ?? 10;
    this.maxDepth = opts.maxDepth ?? 3;
    this.freeModels = opts.freeModels?.length ? opts.freeModels : ["opencode/beam-free"];
    this.trackerLookup = opts.trackerLookup ?? defaultTrackerLookup;
    this.store = new HubStore(db);
    this.recover();
  }

  private now(): string {
    return this.clock().toISOString();
  }

  /** Sync callers (handleRunFinished, recover) detach async mission work; failures are audited. */
  private detach(missionId: string, work: Promise<unknown>): void {
    work.catch((error) => {
      try {
        this.store.audit(missionId, "error", String(error), this.now());
      } catch {
        /* database already closed during shutdown */
      }
    });
  }

  /** Walk the Core transition matrix hop by hop; never raw SQL on missions. */
  private async setStatus(missionId: string, target: MissionStatus): Promise<void> {
    const mission = readMission(this.db, missionId);
    if (!mission) throw new HubError("mission not found", 404);
    if (mission.status === target) return;
    const queue: MissionStatus[][] = [[mission.status]];
    const seen = new Set<MissionStatus>([mission.status]);
    let path: MissionStatus[] | null = null;
    while (queue.length && !path) {
      const current = queue.shift()!;
      for (const next of ALL_STATUSES) {
        if (seen.has(next) || !canTransition(current[current.length - 1]!, next)) continue;
        const extended = [...current, next];
        if (next === target) {
          path = extended;
          break;
        }
        seen.add(next);
        queue.push(extended);
      }
    }
    if (!path) throw new HubError(`mission cannot move from ${mission.status} to ${target}`, 409);
    for (const hop of path.slice(1)) await this.service.transition(missionId, hop, "hub");
  }

  private delegationDepth(agentId: string): number {
    let depth = 0;
    let current: string | null = agentId;
    const seen = new Set<string>();
    while (current) {
      if (seen.has(current)) throw new HubError("coordinator cycle in registry", 400);
      seen.add(current);
      current = this.registry[current]?.coordinator ?? null;
      if (current) depth += 1;
    }
    return depth;
  }

  async prepareApplication(input: {
    company: string;
    role: string;
    url: string;
  }): Promise<{ missionId: string }> {
    const company = input.company?.trim();
    const role = input.role?.trim();
    const url = input.url?.trim();
    if (!company || !role || !url)
      throw new HubError("company, role and url are required", 400);
    const tracked = await this.trackerLookup(company, role);
    if (!tracked) throw new HubError(`${company} — ${role} is not in tracker`, 400);
    if (tracked.status === "rejected" || tracked.status === "withdrawn")
      throw new HubError(`${company} — ${role} is ${tracked.status} in the tracker`, 400);
    for (const task of SLICE_TASKS)
      if (!this.registry[task.owner])
        throw new HubError(`agent '${task.owner}' is missing from the registry`, 400);
    const depth = Math.max(...SLICE_TASKS.map((task) => this.delegationDepth(task.owner)));
    if (depth > this.maxDepth)
      throw new HubError(`delegation depth ${depth} exceeds maxDepth ${this.maxDepth}`, 400);

    const missionId = randomUUID();
    const slug = `${company}-${role}`.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    const objective = `Prepare an application for ${company} — ${role}`;
    const criteria = [
      `Job Reader output exists at workspace/agents/job-reader/outputs/${slug}.json`,
      `Tailored CV exists at workspace/agents/cv-adapter/outputs/${slug}-cv.md`,
      "Forge review of the tailored CV is recorded with evidence",
      "Chief of Staff returns one recommendation",
    ];
    const expected = [
      `Posting analysis written to workspace/agents/job-reader/outputs/${slug}.json`,
      `Tailored CV written to workspace/agents/cv-adapter/outputs/${slug}-cv.md`,
      "Forge review recorded with evidence under workspace/agents/forge/outputs/",
      "One concise recommendation returned",
    ];
    const tasks: PlanTask[] = SLICE_TASKS.map((task, index) => ({
      id: task.id,
      title: task.title,
      description: objective,
      steps: [{ kind: "reasoning", expectedObservation: expected[index]! }],
      expectedResult: expected[index]!,
      verificationCriteria: [expected[index]!],
      owner: task.owner,
      dependsOn: index === 0 ? [] : [SLICE_TASKS[index - 1]!.id],
    }));

    // Initial state is draft (creation, not a transition); later moves use MissionService.
    const mission = {
      ...createMission(
        { id: missionId, title: objective, description: objective, acceptanceCriteria: criteria, priority: "medium" },
        this.clock,
      ),
      status: "draft" as MissionStatus,
    };
    await new SqliteMissionRepository(this.db).create(mission);
    await new SqlitePlanRepository(this.db).save(missionId, { missionId, tasks });

    const now = this.now();
    this.store.createSession(missionId, this.budget, this.maxDepth, SLICE_TASKS.map((t) => t.id), now);
    for (const task of SLICE_TASKS) this.store.insertTask(missionId, task.id, task.owner, now);
    this.store.addSubscription(missionId, "run_completion", now);
    this.store.addSubscription(missionId, "new_message", now);
    this.sendInternal({
      missionId,
      from: "roosevelt",
      to: "specialized-chief-of-staff",
      type: "assignment",
      objective,
      doneWhen: expected[3]!,
      inputRefs: [url],
      idempotencyKey: `prepare:${missionId}`,
    });
    return { missionId };
  }

  async start(missionId: string, idempotencyKey?: string): Promise<void> {
    if (!this.store.getSession(missionId)) throw new HubError("mission has no hub session", 404);
    const mission = readMission(this.db, missionId);
    if (!mission) throw new HubError("mission not found", 404);
    if (mission.status === "completed" || mission.status === "cancelled")
      throw new HubError(`mission is ${mission.status}`, 409);
    await this.setStatus(missionId, "running");
    await this.leaseNext(missionId, idempotencyKey);
  }

  async pause(missionId: string): Promise<void> {
    if (!this.store.getSession(missionId)) throw new HubError("mission has no hub session", 404);
    const mission = readMission(this.db, missionId);
    if (!mission) throw new HubError("mission not found", 404);
    if (mission.status === "running" || mission.status === "awaiting_approval")
      await this.setStatus(missionId, "paused");
  }

  async resume(missionId: string): Promise<void> {
    if (!this.store.getSession(missionId)) throw new HubError("mission has no hub session", 404);
    const mission = readMission(this.db, missionId);
    if (!mission) throw new HubError("mission not found", 404);
    if (mission.status === "completed" || mission.status === "cancelled")
      throw new HubError(`mission is ${mission.status}`, 409);
    await this.setStatus(missionId, "running");
    await this.leaseNext(missionId);
  }

  async stopAll(): Promise<{ terminated: number }> {
    const sessions = new Set(this.store.listSessionMissionIds());
    const active = this.runtime
      .listRuns({ active: true, limit: 1000 })
      .filter((run) => run.missionId && sessions.has(run.missionId));
    let terminated = 0;
    const missions = new Set<string>();
    for (const run of active) {
      try {
        await this.runtime.terminate(run.id);
        terminated += 1;
        missions.add(run.missionId!);
      } catch {
        /* not owned by this supervisor; recovery handles it */
      }
    }
    for (const missionId of missions) await this.pause(missionId);
    return { terminated };
  }

  ingest(message: HubMessageInput): { ok: boolean; reason?: string; id?: string } {
    return ingestMessage(this.db, this.store, this.registry, message, this.now());
  }

  /** Trusted orchestrator writes: routing rules guard external ingest, not code-routed assignments. */
  private sendInternal(input: HubMessageInput): HubMessage {
    const existing = this.store.messageByKey(input.idempotencyKey);
    if (existing) return existing;
    const message: HubMessage = {
      id: randomUUID(),
      missionId: input.missionId,
      taskId: input.taskId ?? null,
      inReplyTo: input.inReplyTo ?? null,
      from: input.from,
      to: input.to,
      type: input.type,
      objective: input.objective ?? "",
      doneWhen: input.doneWhen ?? "",
      inputRefs: input.inputRefs ?? [],
      outputRefs: input.outputRefs ?? [],
      result: input.result ?? "",
      evidence: input.evidence ?? [],
      decisions: input.decisions ?? [],
      blockers: input.blockers ?? [],
      approvalNeeded: input.approvalNeeded ?? false,
      idempotencyKey: input.idempotencyKey,
      createdAt: this.now(),
    };
    this.store.insertMessage(message);
    return message;
  }

  /** listRuns pages at 1000; gather every run for the mission. */
  private missionRuns(missionId: string): AgentRunRecord[] {
    const runs: AgentRunRecord[] = [];
    for (let offset = 0; offset < 100_000; offset += 1000) {
      const page = this.runtime.listRuns({ limit: 1000, offset });
      runs.push(...page.filter((run) => run.missionId === missionId));
      if (page.length < 1000) break;
    }
    return runs;
  }

  private stdoutOf(runId: string): { stdout: string; stderr: string } {
    let stdout = "";
    let stderr = "";
    let after = 0;
    for (;;) {
      const page = this.runtime.events(runId, after, 1000);
      for (const event of page) {
        if (event.kind === "stdout") stdout += event.data;
        else if (event.kind === "stderr") stderr += event.data;
        after = event.id;
      }
      if (page.length < 1000) break;
    }
    return { stdout, stderr };
  }

  private taskInputRefs(missionId: string, task: PlanTask): string[] {
    const deps = task.dependsOn ?? [];
    if (!deps.length)
      return this.store.messageByKey(`prepare:${missionId}`)?.inputRefs ?? [];
    const refs: string[] = [];
    for (const dep of deps) {
      const result = this.store
        .listMessages(missionId)
        .filter((message) => message.type === "result" && message.taskId === dep)
        .pop();
      if (result) refs.push(...result.evidence);
    }
    return refs;
  }

  private async ensureProject(): Promise<string> {
    if (this.projectId) return this.projectId;
    const existing = this.runtime.listProjects().find((p) => p.path === this.workspaceRoot);
    this.projectId =
      existing?.id ?? (await this.runtime.registerProject(this.workspaceRoot)).id;
    return this.projectId;
  }

  private async leaseNext(missionId: string, idempotencyKey?: string): Promise<void> {
    const mission = readMission(this.db, missionId);
    if (!mission || mission.status !== "running") return;
    const session = this.store.getSession(missionId)!;
    const latest = readLatestPlan(this.db, missionId);
    if (!latest) return;
    const rows = new Map(this.store.listTasks(missionId).map((row) => [row.task_id, row]));
    const candidate = latest.plan.tasks.find((task) => {
      const row = rows.get(task.id);
      return (
        row &&
        (row.status === "pending" || row.status === "interrupted" || row.status === "blocked") &&
        (task.dependsOn ?? []).every((dep) => rows.get(dep)?.status === "completed")
      );
    });
    if (!candidate) {
      await this.maybeComplete(missionId);
      return;
    }
    const runs = this.missionRuns(missionId);
    if (runs.length >= session.budget) {
      const remaining = [...rows.values()].filter((row) => row.status !== "completed");
      const unresolved = this.store.listWaiting(missionId, true);
      if (!unresolved.some((waiting) => waiting.kind === "budget")) {
        this.store.insertWaiting(
          {
            id: randomUUID(),
            mission_id: missionId,
            kind: "budget",
            title: `Raise the model-call budget to ${session.budget + remaining.length}`,
            detail: `Budget of ${session.budget} model calls exhausted. Remaining: ${remaining
              .map((row) => `${row.task_id} (${row.owner})`)
              .join(", ")}`,
            action: `approve to add ${remaining.length} model calls`,
            approval_id: null,
          },
          this.now(),
        );
      }
      await this.setStatus(missionId, "awaiting_approval");
      return;
    }
    await this.leaseTask(missionId, candidate, idempotencyKey);
  }

  private async leaseTask(
    missionId: string,
    task: PlanTask,
    idempotencyKey?: string,
  ): Promise<void> {
    const row = this.store.getTask(missionId, task.id)!;
    if (row.status === "in_progress" && row.run_id) {
      const run = this.runtime.getRun(row.run_id);
      if (run && ACTIVE_RUN_STATUSES[run.status]) throw new HubError("task already leased", 409);
    }
    const session = this.store.getSession(missionId)!;
    const mission = readMission(this.db, missionId)!;
    const owner = task.owner!;
    const models = JSON.parse(session.models_json) as Record<
      string,
      { adapter: string; model: string }
    >;
    const paid = models[owner];
    let adapterId = "opencode";
    let model: string | undefined = this.freeModels[0];
    if (paid) {
      const approval = await this.taskApproval(missionId, task.id);
      if (!approval || approval.status === "pending") {
        if (!approval) {
          const record = await this.service.createApproval({
            missionId,
            capability: "model",
            action: `paid model ${paid.adapter}:${paid.model} for ${owner} on ${task.id}`,
            reason: `Mission ${missionId} requests paid model ${paid.model} for role ${owner}`,
            risk: "paid model call",
          });
          this.store.insertWaiting(
            {
              id: randomUUID(),
              mission_id: missionId,
              kind: "approval",
              title: `Switch ${task.id} to ${paid.adapter} ${paid.model}`,
              detail: `task:${task.id}; role:${owner}; model:${paid.adapter}:${paid.model}`,
              action: "approve to start the paid run",
              approval_id: record.id,
            },
            this.now(),
          );
        }
        await this.setStatus(missionId, "awaiting_approval");
        return;
      }
      if (approval.status === "rejected") {
        this.blockTask(missionId, task.id, "paid model approval denied", "Approval denied", "Switch the model or resume after a new approval");
        await this.setStatus(missionId, "paused");
        return;
      }
      adapterId = paid.adapter;
      model = paid.model;
    }

    const objective = mission.description ?? mission.title;
    const inputRefs = this.taskInputRefs(missionId, task);
    const doneWhen = task.expectedResult;
    this.sendInternal({
      missionId,
      taskId: task.id,
      from: "specialized-chief-of-staff",
      to: "forge",
      type: "assignment",
      objective,
      doneWhen,
      inputRefs,
      idempotencyKey: `assign:${missionId}:forge`,
    });
    this.sendInternal({
      missionId,
      taskId: task.id,
      from: "forge",
      to: owner,
      type: "assignment",
      objective,
      doneWhen,
      inputRefs,
      idempotencyKey: `assign:${missionId}:${task.id}`,
    });

    const prompt = [
      `Objective: ${objective}`,
      "",
      `Task: ${task.title} (${task.id})`,
      `Done when: ${doneWhen}`,
      "",
      "Input refs (read these paths; no file bodies are inlined):",
      ...inputRefs.map((ref) => `- ${ref}`),
      "",
      'Finish with one fenced ```handoff JSON block: {"result": string, "evidence": string[], "decisions": string[], "blockers": string[], "approval_needed": boolean, "recommended_receiver": string}.',
    ].join("\n");

    const now = this.now();
    this.store.updateTask(
      missionId,
      task.id,
      {
        status: "in_progress",
        lease_key: idempotencyKey ?? `start:${missionId}:${task.id}`,
        blocked_reason: null,
        guard_snapshot: snapshotProtected(this.workspaceRoot, this.registry, owner),
        git_head: gitHead(this.workspaceRoot),
      },
      now,
    );
    const latest = readLatestPlan(this.db, missionId)!;
    try {
      const projectId = await this.ensureProject();
      const run = await this.runtime.start({
        projectId,
        adapterId,
        prompt,
        missionId,
        planVersion: latest.version,
        taskId: task.id,
        model,
        ...(adapterId === "opencode" ? { agent: owner } : {}),
      });
      this.store.updateTask(missionId, task.id, { run_id: run.id }, this.now());
      if (TERMINAL_RUN_STATUSES[run.status]) this.handleRunFinished(run);
    } catch (error) {
      // A lease must never strand a task in_progress without a run.
      const reason = error instanceof Error ? error.message : String(error);
      this.blockTask(missionId, task.id, reason, "Run could not start", "Fix the cause and resume");
      await this.setStatus(missionId, "paused");
    }
  }

  private async taskApproval(missionId: string, taskId: string) {
    const waiting = this.store
      .listWaiting(missionId)
      .filter((w) => w.kind === "approval" && w.detail.includes(`task:${taskId}`))
      .pop();
    if (!waiting?.approval_id) return null;
    const approvals = await this.service.listApprovals();
    return approvals.find((approval) => approval.id === waiting.approval_id) ?? null;
  }

  private blockTask(
    missionId: string,
    taskId: string,
    reason: string,
    waitingTitle: string,
    waitingAction: string,
    detail = reason,
  ): void {
    this.store.updateTask(missionId, taskId, { status: "blocked", blocked_reason: reason }, this.now());
    this.store.insertWaiting(
      {
        id: randomUUID(),
        mission_id: missionId,
        kind: "blocker",
        title: waitingTitle,
        detail,
        action: waitingAction,
        approval_id: null,
      },
      this.now(),
    );
  }

  private resultMessageFor(missionId: string, taskId: string): HubMessage | null {
    return (
      this.store
        .listMessages(missionId)
        .filter((message) => message.type === "result" && message.taskId === taskId)
        .pop() ?? null
    );
  }

  handleRunFinished(run: AgentRunRecord): void {
    if (!run.missionId || !run.taskId) return;
    const missionId = run.missionId;
    const taskId = run.taskId;
    const task = this.store.getTask(missionId, taskId);
    if (!task || task.status !== "in_progress" || task.run_id !== run.id) return;
    if (this.store.messageByKey(`run:${run.id}`)) return;
    const latest = readLatestPlan(this.db, missionId);
    const planTask = latest?.plan.tasks.find((item) => item.id === taskId);
    if (!planTask) return;
    const owner = task.owner;
    const coordinator = this.registry[owner]?.coordinator ?? "roosevelt";
    const assignment = this.store.messageByKey(`assign:${missionId}:${taskId}`);
    const { stdout, stderr } = this.stdoutOf(run.id);

    const storeResult = (fields: Partial<HubMessage>, blockers: string[]): void => {
      this.sendInternal({
        missionId,
        taskId,
        inReplyTo: assignment?.id ?? null,
        from: owner,
        to: coordinator,
        type: "result",
        objective: readMission(this.db, missionId)?.description ?? "",
        doneWhen: planTask.expectedResult,
        inputRefs: assignment?.inputRefs ?? [],
        outputRefs: fields.evidence ?? [],
        result: fields.result ?? "",
        evidence: fields.evidence ?? [],
        decisions: fields.decisions ?? [],
        blockers,
        approvalNeeded: fields.approvalNeeded ?? false,
        idempotencyKey: `run:${run.id}`,
      });
    };
    const blockAndPause = (reason: string, title: string, detail: string, action: string, fields: Partial<HubMessage>, blockers: string[]): void => {
      storeResult(fields, blockers);
      this.blockTask(missionId, taskId, reason, title, action, detail);
      this.detach(missionId, this.setStatus(missionId, "paused"));
    };

    if (run.status !== "completed") {
      const errorText = run.error ?? stderr.trim() ?? `run ${run.status}`;
      blockAndPause(
        errorText.slice(0, 500),
        `Worker ${owner} failed on ${taskId}`,
        errorText.slice(0, 500),
        "resume to retry or switch model",
        { result: errorText.slice(0, 500) },
        [errorText.slice(0, 500)],
      );
      return;
    }

    const foreign = diffSnapshots(
      task.guard_snapshot,
      snapshotProtected(this.workspaceRoot, this.registry, owner),
    );
    if (foreign.length) {
      blockAndPause(
        `foreign change: ${foreign[0]}`,
        "Ownership guardrail blocked the handoff",
        `Protected paths changed during ${owner}'s run: ${foreign.join(", ")}. Files are left in place for manual cleanup.`,
        "clean up and resume",
        { result: stdout },
        foreign.map((path) => `foreign change: ${path}`),
      );
      return;
    }
    const head = gitHead(this.workspaceRoot);
    if (task.git_head && head && head !== task.git_head) {
      blockAndPause(
        "git history changed during run",
        "git history changed during run",
        `HEAD moved from ${task.git_head} to ${head} during ${owner}'s run on ${taskId}. No approval is implied.`,
        "inspect the commit and resume",
        { result: stdout },
        ["git history changed during run"],
      );
      return;
    }

    let handoff: Handoff | null;
    try {
      handoff = parseHandoff(stdout);
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      blockAndPause(reason, `Malformed handoff from ${owner}`, reason, "resume to retry", { result: stdout }, [reason]);
      return;
    }
    if (!handoff) {
      blockAndPause(
        "no handoff block",
        `No handoff from ${owner}`,
        `Run completed without a handoff block; stdout is preserved in the mailbox result.`,
        "resume to retry",
        { result: stdout },
        ["no handoff block"],
      );
      return;
    }

    if (
      handoff.recommendedReceiver &&
      handoff.recommendedReceiver !== coordinator &&
      !this.hasRelationship(missionId, owner, handoff.recommendedReceiver)
    ) {
      this.store.audit(
        missionId,
        "ignored_recommendation",
        `recommended_receiver '${handoff.recommendedReceiver}' ignored: no task relationship`,
        this.now(),
      );
    }

    const missing = handoff.evidence.filter((ref) => !evidenceExists(this.workspaceRoot, ref));
    const problems = [
      ...missing.map((ref) => `missing evidence: ${ref}`),
      ...handoff.blockers,
      ...(handoff.result.trim() ? [] : ["empty result"]),
    ];
    if (problems.length) {
      blockAndPause(
        problems[0]!,
        `Validation failed for ${taskId}`,
        problems.join("; "),
        "resolve and resume",
        { result: handoff.result, evidence: handoff.evidence, decisions: handoff.decisions, approvalNeeded: handoff.approvalNeeded },
        problems,
      );
      return;
    }

    this.store.updateTask(missionId, taskId, { status: "completed", blocked_reason: null }, this.now());
    storeResult(
      { result: handoff.result, evidence: handoff.evidence, decisions: handoff.decisions, approvalNeeded: handoff.approvalNeeded },
      [],
    );
    if (taskId === "recommend") this.store.setRecommendation(missionId, handoff.result, this.now());
    this.detach(
      missionId,
      this.maybeComplete(missionId).then((done) =>
        done ? undefined : this.leaseNext(missionId),
      ),
    );
  }

  private hasRelationship(missionId: string, from: string, to: string): boolean {
    const registryTo = this.registry[to];
    if (!registryTo) return false;
    if (registryTo.coordinator === from || this.registry[from]?.coordinator === to) return true;
    const latest = readLatestPlan(this.db, missionId);
    if (!latest) return false;
    const fromTasks = latest.plan.tasks.filter((task) => task.owner === from);
    const toTasks = latest.plan.tasks.filter((task) => task.owner === to);
    return fromTasks.some((a) =>
      toTasks.some((b) => (a.dependsOn ?? []).includes(b.id) || (b.dependsOn ?? []).includes(a.id)),
    );
  }


  /** Completion only after every criterion's task carries validated evidence. */
  private async maybeComplete(missionId: string): Promise<boolean> {
    const mission = readMission(this.db, missionId);
    if (!mission || mission.status !== "running") return false;
    const rows = this.store.listTasks(missionId);
    if (!rows.length || !rows.every((row) => row.status === "completed")) return false;
    const session = this.store.getSession(missionId)!;
    const refs = JSON.parse(session.criteria_refs_json) as string[];
    for (let index = 0; index < mission.acceptanceCriteria.length; index += 1) {
      const result = this.resultMessageFor(missionId, refs[index] ?? "");
      if (
        !result ||
        !result.evidence.length ||
        !result.evidence.every((ref) => evidenceExists(this.workspaceRoot, ref))
      )
        return false;
    }
    if (!session.recommendation) return false;
    await this.setStatus(missionId, "completed");
    return true;
  }

  async resolveWaiting(
    missionId: string,
    waitingId: string,
    decision: "approve" | "deny",
  ): Promise<void> {
    const waiting = this.store.getWaiting(waitingId);
    if (!waiting || waiting.mission_id !== missionId)
      throw new HubError("waiting item not found", 404);
    if (waiting.resolved_at) throw new HubError("waiting item already resolved", 409);
    this.store.resolveWaiting(waitingId, this.now());
    if (waiting.kind === "approval") {
      if (!waiting.approval_id) throw new HubError("waiting item has no approval", 409);
      await this.service.resolveApproval(
        waiting.approval_id,
        decision === "approve" ? "approved" : "rejected",
      );
      if (decision === "approve") {
        await this.setStatus(missionId, "running");
        await this.leaseNext(missionId);
      } else {
        const taskId = /task:([^;]+)/.exec(waiting.detail)?.[1];
        if (taskId)
          this.store.updateTask(missionId, taskId, { status: "blocked", blocked_reason: "paid model approval denied" }, this.now());
        await this.setStatus(missionId, "paused");
      }
      return;
    }
    if (waiting.kind === "budget" && decision === "approve") {
      const add = Number.parseInt(/(\d+)/.exec(waiting.action)?.[1] ?? "0", 10);
      if (add > 0) this.store.addBudget(missionId, add, this.now());
      await this.setStatus(missionId, "running");
      await this.leaseNext(missionId);
      return;
    }
    if (waiting.kind === "blocker" && decision === "approve") {
      await this.setStatus(missionId, "running");
      await this.leaseNext(missionId);
    }
  }

  recover(): void {
    recoverHub(
      this.store,
      this.runtime,
      {
        processFinished: (run) => this.handleRunFinished(run),
        pauseMission: (missionId) => this.detach(missionId, this.pause(missionId)),
      },
      this.now(),
    );
  }

  session(missionId: string): SessionView {
    const session = this.store.getSession(missionId);
    if (!session) throw new HubError("mission has no hub session", 404);
    const mission = readMission(this.db, missionId);
    if (!mission) throw new HubError("mission not found", 404);
    const latest = readLatestPlan(this.db, missionId);
    const titleOf = (taskId: string) =>
      latest?.plan.tasks.find((task) => task.id === taskId)?.title ?? taskId;
    const rows = this.store.listTasks(missionId);
    const messages = this.store.listMessages(missionId);
    const runs = this.missionRuns(missionId);
    const runById = new Map(runs.map((run) => [run.id, run]));
    const refs = JSON.parse(session.criteria_refs_json) as string[];
    const phase = rows.find((row) => row.status === "in_progress") ?? null;
    const criteria = mission.acceptanceCriteria.map((text, index) => {
      const taskId = refs[index] ?? "";
      const row = rows.find((item) => item.task_id === taskId);
      const result = this.resultMessageFor(missionId, taskId);
      const evidence = result?.evidence ?? [];
      return {
        text,
        done:
          row?.status === "completed" &&
          evidence.length > 0 &&
          evidence.every((ref) => evidenceExists(this.workspaceRoot, ref)),
        evidence,
      };
    });
    return {
      mission: { id: mission.id, title: mission.title, status: mission.status, priority: mission.priority },
      objective: mission.description ?? mission.title,
      phase: phase
        ? { taskId: phase.task_id, title: titleOf(phase.task_id), owner: phase.owner, status: phase.status }
        : null,
      criteria,
      handoffs: messages
        .filter(
          (message) =>
            message.type === "result" &&
            rows.find((row) => row.task_id === message.taskId)?.status === "completed",
        )
        .map((message) => ({
          id: message.id,
          from: message.from,
          to: message.to,
          type: message.type,
          taskId: message.taskId,
          result: message.result,
          evidence: message.evidence,
          createdAt: message.createdAt,
        })),
      work: rows.map((row) => ({
        taskId: row.task_id,
        title: titleOf(row.task_id),
        owner: row.owner,
        status: row.status,
        runId: row.run_id,
        runStatus: row.run_id ? (runById.get(row.run_id)?.status ?? null) : null,
        blockedReason: row.blocked_reason,
      })),
      waiting: this.store.listWaiting(missionId, true).map((waiting) => ({
        id: waiting.id,
        kind: waiting.kind,
        title: waiting.title,
        detail: waiting.detail,
        action: waiting.action,
        approvalId: waiting.approval_id,
      })),
      usage: {
        calls: runs.length,
        budget: session.budget,
        inputTokens: runs.reduce((sum, run) => sum + (run.inputTokens ?? 0), 0),
        outputTokens: runs.reduce((sum, run) => sum + (run.outputTokens ?? 0), 0),
        costUsd: runs.reduce((sum, run) => sum + (run.costUsd ?? 0), 0),
      },
      recommendation: session.recommendation,
      counts: {
        running: rows.filter((row) => row.status === "in_progress").length,
        blocked: rows.filter((row) => row.status === "blocked").length,
        completed: rows.filter((row) => row.status === "completed").length,
        pending: rows.filter((row) => row.status === "pending" || row.status === "interrupted").length,
      },
      audit: messages.map((message) => ({
        id: message.id,
        from: message.from,
        to: message.to,
        type: message.type,
        taskId: message.taskId,
        result: message.result,
        createdAt: message.createdAt,
      })),
    };
  }

  messages(missionId: string): HubMessage[] {
    if (!this.store.getSession(missionId)) throw new HubError("mission has no hub session", 404);
    return this.store.listMessages(missionId);
  }

  listSessions(): { missionId: string; title: string; status: string }[] {
    return this.store
      .listSessionMissionIds()
      .map((missionId) => readMission(this.db, missionId))
      .filter((mission): mission is NonNullable<typeof mission> => mission !== null)
      .map((mission) => ({ missionId: mission.id, title: mission.title, status: mission.status }));
  }
}
