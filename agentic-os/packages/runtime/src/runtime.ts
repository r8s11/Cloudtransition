import { randomUUID } from "node:crypto";
import { execFile, execFileSync, type ChildProcess } from "node:child_process";
import { readdir, readFile, realpath } from "node:fs/promises";
import { basename, join } from "node:path";
import { promisify } from "node:util";
import { parsePlan } from "@agentic-os/core";
import {
  Database,
  SqliteRuntimeRepository,
  type AgentRunRecord,
  type AgentRunStatus,
  type ProjectRecord,
  type RunEventRecord,
  type RunUsageRecord,
} from "@agentic-os/storage";
import { defaultAdapters, type AgentAdapter } from "./adapters.js";

const exec = promisify(execFile);
const ACTIVE: Partial<Record<AgentRunStatus, true>> = {
  starting: true,
  running: true,
  interrupting: true,
  terminating: true,
};
const TERMINATE_GRACE_MS = 3000;
/** A usage report larger than this is not buffered: stdout is stored as it arrives. */
const REPORT_LIMIT = 8 * 1024 * 1024;
const SKILL_NAME = /^[a-z0-9][a-z0-9_-]{0,63}$/i;
const SKILL_LIMIT = 200;

export class RuntimeError extends Error {
  constructor(
    message: string,
    readonly status: 400 | 404 | 409 | 503,
  ) {
    super(message);
    this.name = "RuntimeError";
  }
}

export interface StartRunInput {
  projectId: string;
  adapterId: string;
  prompt: string;
  missionId?: string;
  planVersion?: number;
  taskId?: string;
  /** Must be one of the adapter's own `models` / `efforts` / `agents`. */
  model?: string;
  effort?: string;
  agent?: string;
}

export interface AdapterInfo {
  id: string;
  available: boolean;
  models: readonly string[];
  efforts: readonly string[];
}

export interface SkillInfo {
  name: string;
  description: string;
}

interface LiveRun {
  run: AgentRunRecord;
  child: ChildProcess;
  adapter: AgentAdapter;
  done: Promise<void>;
  timer?: NodeJS.Timeout;
}

function processStart(pid: number): string | null {
  try {
    return (
      execFileSync("ps", ["-p", String(pid), "-o", "lstart="], {
        encoding: "utf8",
        timeout: 5000,
        stdio: ["ignore", "pipe", "pipe"],
        env: { ...process.env, LC_ALL: "C" },
      }).trim() || null
    );
  } catch (error) {
    if (error instanceof Error && "status" in error && error.status === 1)
      return null;
    throw new RuntimeError(
      "Cannot establish supervisor process identity using ps",
      503,
    );
  }
}

async function repositoryRoot(path: string): Promise<string> {
  if (typeof path !== "string" || !path.trim())
    throw new RuntimeError("Repository path is required", 400);
  try {
    const cwd = await realpath(path);
    const env = { ...process.env };
    for (const key of [
      "GIT_DIR",
      "GIT_WORK_TREE",
      "GIT_COMMON_DIR",
      "GIT_INDEX_FILE",
    ])
      delete env[key];
    const result = await exec(
      "git",
      ["-C", cwd, "rev-parse", "--show-toplevel"],
      { env, timeout: 5000 },
    );
    return await realpath(result.stdout.trim());
  } catch {
    throw new RuntimeError(
      "Path must be an accessible local Git working repository",
      400,
    );
  }
}

/** One supervisor per database. Only live handles owned here can be signalled. */
export class AgentRuntime {
  private readonly store: SqliteRuntimeRepository;
  private readonly adapters = new Map<string, AgentAdapter>();
  private readonly live = new Map<string, LiveRun>();
  private readonly finishListeners = new Set<(run: AgentRunRecord) => void>();
  private readonly ownerId = randomUUID();
  private closing = false;
  private shutdownPromise?: Promise<void>;
  private storageError?: string;

  constructor(
    private readonly db: Database,
    adapters: AgentAdapter[] = defaultAdapters(),
  ) {
    if (process.platform === "win32")
      throw new RuntimeError(
        "Local agent supervision currently requires macOS or Linux",
        503,
      );
    this.store = new SqliteRuntimeRepository(db);
    for (const adapter of adapters) {
      if (!adapter.id || this.adapters.has(adapter.id))
        throw new RuntimeError("Adapter IDs must be nonempty and unique", 400);
      this.adapters.set(adapter.id, adapter);
    }
    const started = processStart(process.pid);
    if (!started)
      throw new RuntimeError("Cannot identify current supervisor process", 503);
    db.exec("PRAGMA busy_timeout = 5000");
    db.transaction(() => {
      const owner = db
        .prepare("SELECT * FROM runtime_owner WHERE slot = 1")
        .get() as
        | { owner_id: string; pid: number; started: string }
        | undefined;
      if (owner && processStart(owner.pid) === owner.started) {
        throw new RuntimeError(
          "Another agent supervisor already owns this database",
          409,
        );
      }
      db.prepare(
        "INSERT OR REPLACE INTO runtime_owner (slot, owner_id, pid, started) VALUES (1, ?, ?, ?)",
      ).run(this.ownerId, process.pid, started);
    });
    try {
      this.recover();
    } catch (error) {
      this.release();
      throw error;
    }
  }

  private healthy(): void {
    if (this.storageError)
      throw new RuntimeError(
        `Run persistence failed: ${this.storageError}`,
        503,
      );
    if (this.closing)
      throw new RuntimeError("Agent supervisor is shutting down", 503);
  }

  /** Lost ownership means lost observability, not proof the agent exited. Never kill recovered PIDs. */
  recover(): void {
    this.healthy();
    let offset = 0;
    for (;;) {
      const runs = this.store.listRuns({ active: true, limit: 1000, offset });
      if (!runs.length) break;
      for (const run of runs) {
        if (this.live.has(run.id)) {
          offset++;
          continue;
        }
        this.store.updateRun({
          ...run,
          status: "lost",
          endedAt: new Date().toISOString(),
          error:
            "Supervisor ownership was lost; process exit and surviving descendants are unknown",
        });
      }
    }
  }

  async registerProject(path: string, name?: string): Promise<ProjectRecord> {
    this.healthy();
    if (name !== undefined && (typeof name !== "string" || !name.trim()))
      throw new RuntimeError("Project name must be nonblank", 400);
    const root = await repositoryRoot(path);
    this.healthy();
    return this.store.registerProject({
      id: randomUUID(),
      path: root,
      name: name?.trim() ?? basename(root),
      createdAt: new Date().toISOString(),
    });
  }

  listProjects(): ProjectRecord[] {
    this.healthy();
    return this.store.listProjects();
  }
  listRuns(options?: {
    active?: boolean;
    projectId?: string;
    limit?: number;
    offset?: number;
  }): AgentRunRecord[] {
    this.healthy();
    return this.store.listRuns(options);
  }
  getRun(id: string): AgentRunRecord | null {
    this.healthy();
    return this.store.getRun(id);
  }
  events(id: string, after?: number, limit?: number): RunEventRecord[] {
    this.healthy();
    if (!this.store.getRun(id)) throw new RuntimeError("Run not found", 404);
    return this.store.listEvents(id, after, limit);
  }

  /** Durable-subscription seam: notified once per run when its terminal state
   * is persisted. Listeners never break the supervisor. Returns unsubscribe. */
  subscribe(listener: (run: AgentRunRecord) => void): () => void {
    this.finishListeners.add(listener);
    return () => this.finishListeners.delete(listener);
  }

  async detectAdapters(): Promise<AdapterInfo[]> {
    this.healthy();
    return Promise.all(
      [...this.adapters.values()].map(async (adapter) => ({
        id: adapter.id,
        available: await adapter.detect().catch(() => false),
        models: adapter.models ?? [],
        efforts: adapter.efforts ?? [],
      })),
    );
  }

  /** Skills in a registered repository's `.claude/skills`. Run one with the prompt `/<name>`. */
  async listSkills(projectId: string): Promise<SkillInfo[]> {
    this.healthy();
    const project = this.store.getProject(projectId);
    if (!project) throw new RuntimeError("Project not found", 404);
    const root = join(project.path, ".claude", "skills");
    let names: string[];
    try {
      names = (await readdir(root)).filter((name) => SKILL_NAME.test(name));
    } catch {
      return [];
    }
    const skills: SkillInfo[] = [];
    for (const name of names.sort()) {
      let text: string;
      try {
        text = (await readFile(join(root, name, "SKILL.md"), "utf8")).slice(0, 4096);
      } catch {
        continue; // not a skill folder
      }
      const description = /^description:\s*(.+)$/m.exec(text)?.[1] ?? "";
      skills.push({
        name,
        description: description.trim().replace(/^(["'])(.*)\1$/, "$2").slice(0, 200),
      });
      if (skills.length >= SKILL_LIMIT) break;
    }
    return skills;
  }

  /** Runs of the last `days` days grouped by prompt, most expensive first. */
  usage(days = 7): RunUsageRecord[] {
    this.healthy();
    if (!Number.isSafeInteger(days) || days < 1 || days > 90)
      throw new RuntimeError("days must be between 1 and 90", 400);
    return this.store.usageByPrompt(
      new Date(Date.now() - days * 86_400_000).toISOString(),
    );
  }

  private validateLink(input: StartRunInput): void {
    if (
      input.taskId !== undefined &&
      (!input.missionId || input.planVersion === undefined)
    ) {
      throw new RuntimeError(
        "Task linkage requires missionId and planVersion",
        400,
      );
    }
    if (
      input.planVersion !== undefined &&
      (!input.missionId ||
        !Number.isSafeInteger(input.planVersion) ||
        input.planVersion < 1)
    ) {
      throw new RuntimeError(
        "Plan linkage requires missionId and a positive planVersion",
        400,
      );
    }
    if (!input.missionId) return;
    if (
      !this.db
        .prepare("SELECT id FROM missions WHERE id = ?")
        .get(input.missionId)
    )
      throw new RuntimeError("Mission not found", 404);
    if (input.planVersion === undefined) return;
    const row = this.db
      .prepare(
        "SELECT plan_json FROM plans WHERE mission_id = ? AND version = ?",
      )
      .get(input.missionId, input.planVersion) as
      | { plan_json: string }
      | undefined;
    if (!row) throw new RuntimeError("Plan version not found", 404);
    if (
      input.taskId !== undefined &&
      !parsePlan(JSON.parse(row.plan_json)).tasks.some(
        (task) => task.id === input.taskId,
      )
    ) {
      throw new RuntimeError("Task not found in the specified Core plan", 400);
    }
  }

  async start(input: StartRunInput): Promise<AgentRunRecord> {
    this.healthy();
    if (
      typeof input.prompt !== "string" ||
      !input.prompt.trim() ||
      input.prompt.length > 65536
    )
      throw new RuntimeError("Prompt must contain 1–65536 characters", 400);
    const project = this.store.getProject(input.projectId);
    if (!project) throw new RuntimeError("Project not found", 404);
    const adapter = this.adapters.get(input.adapterId);
    if (!adapter) throw new RuntimeError("Unknown agent adapter", 400);
    for (const [option, allowed] of [
      ["model", adapter.models],
      ["effort", adapter.efforts],
      ["agent", adapter.agents],
    ] as const) {
      const value = input[option];
      if (value !== undefined && !allowed?.includes(value))
        throw new RuntimeError(
          `Agent ${adapter.id} does not offer ${option} '${String(value)}'`,
          400,
        );
    }
    const root = await repositoryRoot(project.path);
    this.healthy();
    if (root !== project.path)
      throw new RuntimeError("Registered repository root has changed", 409);
    this.validateLink(input);
    const run: AgentRunRecord = {
      id: randomUUID(),
      projectId: project.id,
      adapterId: adapter.id,
      prompt: input.prompt,
      status: "starting",
      createdAt: new Date().toISOString(),
      startedAt: null,
      endedAt: null,
      pid: null,
      ownerId: this.ownerId,
      missionId: input.missionId ?? null,
      planVersion: input.planVersion ?? null,
      taskId: input.taskId ?? null,
      exitCode: null,
      signal: null,
      error: null,
      model: input.model ?? null,
      effort: input.effort ?? null,
      inputTokens: null,
      outputTokens: null,
      costUsd: null,
    };
    this.store.createRun(run);
    let child: ChildProcess;
    try {
      child = adapter.start({
        cwd: project.path,
        prompt: input.prompt,
        model: input.model,
        effort: input.effort,
        agent: input.agent,
      });
    } catch (error) {
      run.status = "failed";
      run.error = error instanceof Error ? error.message : String(error);
      run.endedAt = new Date().toISOString();
      this.store.updateRun(run);
      return { ...run };
    }
    const ready = Promise.withResolvers<AgentRunRecord>();
    const completed = Promise.withResolvers<void>();
    const live: LiveRun = { run, child, adapter, done: completed.promise };
    this.live.set(run.id, live);
    const persist = (fn: () => void) => {
      try {
        fn();
      } catch (error) {
        this.storageError =
          error instanceof Error ? error.message : String(error);
        run.error = `Persistence failure: ${this.storageError}`;
        ready.reject(new RuntimeError(run.error, 503));
        try {
          adapter.terminate(child, true);
        } catch {
          /* close/error still owns completion */
        }
      }
    };
    child.once("spawn", () => {
      run.pid = child.pid ?? null;
      run.startedAt = new Date().toISOString();
      if (run.status === "starting") run.status = "running";
      persist(() => this.store.updateRun(run));
      ready.resolve({ ...run });
    });
    // An adapter that reports usage writes one report on exit. Hold its stdout until then, so
    // the stored output is the agent's answer and the report's numbers land on the run.
    let report: string[] | null = adapter.usage ? [] : null;
    let reportSize = 0;
    for (const kind of ["stdout", "stderr"] as const) {
      const stream = child[kind];
      stream?.setEncoding("utf8");
      stream?.on("data", (data: string) => {
        if (kind === "stdout" && report) {
          report.push(data);
          reportSize += data.length;
          if (reportSize <= REPORT_LIMIT) return;
          data = report.join("");
          report = null;
        }
        persist(() => this.store.appendEvent(run.id, kind, data));
      });
      stream?.on("error", (error: Error) => {
        run.error = `${kind}: ${error.message}`;
        try {
          adapter.terminate(child, true);
        } catch (failure) {
          run.error += `; ${failure instanceof Error ? failure.message : String(failure)}`;
        }
      });
    }
    child.on("error", (error) => {
      run.error = error.message;
      // Spawn errors also emit close. Completion waits for both output streams.
    });
    child.once("exit", () => {
      // A helper inheriting pipes must not keep an ended run alive indefinitely.
      // This is the still-owned process group, never a recovered PID.
      try {
        adapter.terminate(child, true);
      } catch (error) {
        run.error = error instanceof Error ? error.message : String(error);
      }
    });
    child.once("close", (code, signal) => {
      clearTimeout(live.timer);
      if (report?.length) {
        const raw = report.join("");
        let usage = null;
        try {
          usage = adapter.usage?.(raw) ?? null;
        } catch {
          /* not a report: keep the raw output */
        }
        if (usage) {
          run.inputTokens = usage.inputTokens;
          run.outputTokens = usage.outputTokens;
          run.costUsd = usage.costUsd;
        }
        const output = usage ? usage.result : raw;
        if (output)
          persist(() => this.store.appendEvent(run.id, "stdout", output));
      }
      run.exitCode = code;
      run.signal = signal;
      run.endedAt = new Date().toISOString();
      run.status = run.error
        ? "failed"
        : run.status === "terminating"
          ? "terminated"
          : run.status === "interrupting"
            ? "interrupted"
            : code === 0
              ? "completed"
              : "failed";
      persist(() => this.store.updateRun(run));
      this.live.delete(run.id);
      for (const listener of [...this.finishListeners]) {
        try {
          listener({ ...run });
        } catch {
          /* a subscriber failure must not lose the run's terminal state */
        }
      }
      ready.resolve({ ...run });
      completed.resolve();
    });
    return ready.promise;
  }

  private control(id: string, terminate: boolean): AgentRunRecord {
    const run = this.store.getRun(id);
    if (!run) throw new RuntimeError("Run not found", 404);
    if (!ACTIVE[run.status]) return run;
    const live = this.live.get(id);
    if (!live)
      throw new RuntimeError("Run is not owned by this supervisor", 409);
    if (!terminate && run.status === "terminating")
      throw new RuntimeError("Run is already terminating", 409);
    const status = terminate ? "terminating" : "interrupting";
    if (run.status === status) return run;
    try {
      if (terminate) live.adapter.terminate(live.child);
      else live.adapter.interrupt(live.child);
    } catch (error) {
      throw new RuntimeError(
        `Cannot signal agent: ${error instanceof Error ? error.message : String(error)}`,
        503,
      );
    }
    live.run.status = status;
    this.store.updateRun(live.run);
    if (terminate) {
      live.timer = setTimeout(() => {
        try {
          live.adapter.terminate(live.child, true);
        } catch (error) {
          live.run.error =
            error instanceof Error ? error.message : String(error);
        }
      }, TERMINATE_GRACE_MS);
    }
    return { ...live.run };
  }
  async interrupt(id: string): Promise<AgentRunRecord> {
    this.healthy();
    return this.control(id, false);
  }
  async terminate(id: string): Promise<AgentRunRecord> {
    this.healthy();
    return this.control(id, true);
  }

  private release(): void {
    this.db
      .prepare("DELETE FROM runtime_owner WHERE slot = 1 AND owner_id = ?")
      .run(this.ownerId);
  }

  shutdown(): Promise<void> {
    if (this.shutdownPromise) return this.shutdownPromise;
    this.closing = true;
    this.shutdownPromise = (async () => {
      const runs = [...this.live.values()];
      for (const live of runs) {
        try {
          this.control(live.run.id, true);
        } catch (error) {
          live.run.error =
            error instanceof Error ? error.message : String(error);
          live.adapter.terminate(live.child, true);
        }
      }
      await Promise.all(runs.map((live) => live.done));
      this.release();
      if (this.storageError)
        throw new RuntimeError(
          `Run persistence failed: ${this.storageError}`,
          503,
        );
    })();
    return this.shutdownPromise;
  }
}
