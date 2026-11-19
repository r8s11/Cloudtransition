import { randomUUID } from "node:crypto";
import { mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { Database } from "@agentic-os/storage";
import type { Hono } from "hono";
import type { AgentRunRecord } from "@agentic-os/runtime";
import type {
  AgentRegistry,
  Hub,
  HubMessage,
  HubMessageInput,
  SessionView,
} from "@agentic-os/hub";
import { createApp } from "./index.js";

// Slice B tests run against a stub Hub implementing the frozen contract, so
// they never depend on packages/hub internals (or a real model/adapter).

const REGISTRY: AgentRegistry = {
  "specialized-chief-of-staff": {
    id: "specialized-chief-of-staff",
    name: "Chief of Staff",
    coordinator: null,
    memoryDir: "workspace/agents/chief-of-staff/memory",
    outputDirs: ["workspace/agents/chief-of-staff/outputs"],
    costClass: "free",
    installed: true,
  },
  forge: {
    id: "forge",
    name: "Forge",
    coordinator: "specialized-chief-of-staff",
    memoryDir: "workspace/agents/forge/memory",
    outputDirs: ["workspace/agents/forge/outputs"],
    costClass: "free",
    installed: true,
  },
  "job-reader": {
    id: "job-reader",
    name: "Job Reader",
    coordinator: "forge",
    memoryDir: "workspace/agents/job-reader/memory",
    outputDirs: ["workspace/agents/job-reader/outputs"],
    costClass: "free",
    installed: true,
  },
  "cv-adapter": {
    id: "cv-adapter",
    name: "CV Adapter",
    coordinator: "forge",
    memoryDir: "workspace/agents/cv-adapter/memory",
    outputDirs: ["workspace/agents/cv-adapter/outputs"],
    costClass: "free",
    installed: true,
  },
};

function httpError(status: number, message: string): Error {
  return Object.assign(new Error(message), { status });
}

interface StubTask {
  taskId: string;
  title: string;
  owner: string;
  status: string;
  runId: string | null;
  runStatus: string | null;
  blockedReason: string | null;
}
interface StubWaiting {
  id: string;
  missionId: string;
  kind: "approval" | "budget" | "blocker";
  title: string;
  detail: string;
  action: string;
  approvalId: string | null;
}
interface StubMission {
  id: string;
  title: string;
  status: string;
  priority: string;
  acceptanceCriteria: string[];
}
interface StubState {
  missions: Map<string, StubMission>;
  tasks: Map<string, StubTask[]>;
  messages: HubMessage[];
  waiting: StubWaiting[];
  usage: { calls: number; budget: number; inputTokens: number; outputTokens: number; costUsd: number };
  setRecommendation: (value: string) => void;
}
/** The frozen packages/hub public API, as far as the HTTP layer uses it. */
interface HubContract {
  readonly registry: AgentRegistry;
  readonly workspaceRoot: string;
  prepareApplication(input: { company: string; role: string; url: string }): Promise<{ missionId: string }>;
  start(missionId: string, idempotencyKey?: string): Promise<void>;
  pause(missionId: string): Promise<void>;
  resume(missionId: string): Promise<void>;
  stopAll(): Promise<{ terminated: number }>;
  ingest(message: HubMessageInput): { ok: boolean; reason?: string; id?: string };
  session(missionId: string): SessionView;
  messages(missionId: string): HubMessage[];
  listSessions(): { missionId: string; title: string; status: string }[];
  recover(): void;
  handleRunFinished(run: AgentRunRecord): void;
  resolveWaiting(missionId: string, waitingId: string, decision: "approve" | "deny"): Promise<void>;
}
interface StubHub {
  hub: HubContract;
  state: StubState;
}

function makeStubHub(workspaceRoot: string, tracker: Record<string, string>): StubHub {
  const missions = new Map<string, StubMission>();
  const tasks = new Map<string, StubTask[]>();
  const messages: HubMessage[] = [];
  const waiting: StubWaiting[] = [];
  const usage = { calls: 0, budget: 10, inputTokens: 0, outputTokens: 0, costUsd: 0 };
  let recommendation: string | null = null;

  function mission(id: string) {
    const found = missions.get(id);
    if (!found) throw httpError(404, `Mission ${id} not found`);
    return found;
  }

  const hub = {
    registry: REGISTRY,
    workspaceRoot,
    async prepareApplication(input: { company: string; role: string; url: string }) {
      const status = tracker[`${input.company}·${input.role}`];
      if (!status)
        throw httpError(400, `${input.company} · ${input.role} is not in the tracker`);
      if (status === "rejected" || status === "withdrawn")
        throw httpError(400, `Job is ${status}; closed jobs cannot be prepared`);
      const id = randomUUID();
      missions.set(id, {
        id,
        title: `Prepare an application — ${input.company} · ${input.role}`,
        status: "draft",
        priority: "medium",
        acceptanceCriteria: [
          "Job Reader output exists for this posting",
          "Tailored CV written from base-CV facts only",
          "Forge review cites both artifacts",
          "One Chief of Staff recommendation recorded",
        ],
      });
      tasks.set(id, [
        { taskId: "read-posting", title: "Read the posting", owner: "job-reader", status: "pending", runId: null, runStatus: null, blockedReason: null },
        { taskId: "tailor-cv", title: "Tailor the CV", owner: "cv-adapter", status: "pending", runId: null, runStatus: null, blockedReason: null },
        { taskId: "forge-review", title: "Review both artifacts", owner: "forge", status: "pending", runId: null, runStatus: null, blockedReason: null },
        { taskId: "recommend", title: "Record one recommendation", owner: "specialized-chief-of-staff", status: "pending", runId: null, runStatus: null, blockedReason: null },
      ]);
      messages.push({
        id: randomUUID(),
        missionId: id,
        taskId: null,
        inReplyTo: null,
        from: "roosevelt",
        to: "specialized-chief-of-staff",
        type: "assignment",
        objective: `Prepare one application for ${input.company} · ${input.role}`,
        doneWhen: "Tailored CV, review and recommendation recorded",
        inputRefs: [input.url],
        outputRefs: [],
        result: "",
        evidence: [],
        decisions: [],
        blockers: [],
        approvalNeeded: false,
        idempotencyKey: `prepare:${id}`,
        createdAt: new Date().toISOString(),
      });
      return { missionId: id };
    },
    async start(id: string) {
      const found = mission(id);
      found.status = "running";
      const next = tasks.get(id)?.find((t) => t.status === "pending");
      if (next) next.status = "in_progress";
    },
    async pause(id: string) {
      mission(id).status = "paused";
    },
    async resume(id: string) {
      mission(id).status = "running";
    },
    async stopAll() {
      return { terminated: 0 };
    },
    ingest(input: HubMessageInput) {
      const duplicate = messages.find((m) => m.idempotencyKey === input.idempotencyKey);
      if (duplicate) return { ok: true, id: duplicate.id };
      if (input.to === "*") return { ok: false, reason: "Broadcasts are not allowed" };
      for (const agent of [input.from, input.to]) {
        if (agent !== "roosevelt" && !REGISTRY[agent])
          return { ok: false, reason: `Unknown agent ${agent}` };
      }
      const stored: HubMessage = {
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
        createdAt: new Date().toISOString(),
      };
      messages.push(stored);
      return { ok: true, id: stored.id };
    },
    session(id: string): SessionView {
      const found = mission(id);
      const list = tasks.get(id) ?? [];
      const phase = list.find((t) => t.status === "in_progress") ?? null;
      return {
        mission: { id: found.id, title: found.title, status: found.status, priority: found.priority },
        objective: found.title,
        phase: phase
          ? { taskId: phase.taskId, title: phase.title, owner: phase.owner, status: phase.status }
          : null,
        criteria: found.acceptanceCriteria.map((text) => ({ text, done: false, evidence: [] })),
        handoffs: messages
          .filter((m) => m.missionId === id && m.type === "result")
          .map((m) => ({
            id: m.id,
            from: m.from,
            to: m.to,
            type: m.type,
            taskId: m.taskId,
            result: m.result,
            evidence: m.evidence,
            createdAt: m.createdAt,
          })),
        work: list.map((t) => ({ ...t })),
        waiting: waiting
          .filter((w) => w.missionId === id)
          .map(({ missionId: _missionId, ...rest }) => rest),
        usage: { ...usage },
        recommendation,
        counts: {
          running: list.filter((t) => t.status === "in_progress").length,
          blocked: list.filter((t) => t.status === "blocked").length,
          completed: list.filter((t) => t.status === "completed").length,
          pending: list.filter((t) => t.status === "pending").length,
        },
        audit: messages
          .filter((m) => m.missionId === id)
          .map((m) => ({
            id: m.id,
            from: m.from,
            to: m.to,
            type: m.type,
            taskId: m.taskId,
            result: m.result || m.objective,
            createdAt: m.createdAt,
          })),
      };
    },
    messages(id: string) {
      mission(id);
      return messages.filter((m) => m.missionId === id);
    },
    listSessions() {
      return [...missions.values()].map((m) => ({
        missionId: m.id,
        title: m.title,
        status: m.status,
      }));
    },
    async resolveWaiting(missionId: string, waitingId: string, decision: "approve" | "deny") {
      const found = mission(missionId);
      const index = waiting.findIndex((w) => w.id === waitingId && w.missionId === missionId);
      if (index < 0) throw httpError(404, `Waiting item ${waitingId} not found`);
      waiting.splice(index, 1);
      found.status = decision === "approve" ? "running" : "paused";
    },
    recover() {},
    handleRunFinished() {},
  };

  return { hub, state: { missions, tasks, messages, waiting, usage, setRecommendation: (v: string) => (recommendation = v) } };
}

describe("hub API — /api/hub routes against a stub Hub", () => {
  let db: Database;
  let root: string;
  let stub: StubHub;
  let app: Hono;

  beforeEach(() => {
    db = Database.memory();
    root = mkdtempSync(join(tmpdir(), "hub-api-"));
    stub = makeStubHub(root, {
      "Acme Health·Systems Administrator": "applied",
      "Closed Co·Engineer": "rejected",
    });
    app = createApp(db, { hub: stub.hub as unknown as Hub });
  });
  afterEach(() => {
    db.close();
    rmSync(root, { recursive: true, force: true });
  });

  const post = (path: string, body: unknown, headers: Record<string, string> = {}) =>
    app.request(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", Host: "localhost:8787", ...headers },
      body: JSON.stringify(body),
    });
  const get = (path: string, headers: Record<string, string> = {}) =>
    app.request(path, { headers: { Host: "localhost:8787", ...headers } });

  async function prepareAcme(): Promise<string> {
    const res = await post("/api/hub/missions/prepare-application", {
      company: "Acme Health",
      role: "Systems Administrator",
      url: "https://example.com/jobs/acme",
    });
    expect(res.status).toBe(201);
    return ((await res.json()) as { missionId: string }).missionId;
  }

  it("prepare-application creates a draft mission with four owned tasks", async () => {
    const missionId = await prepareAcme();
    expect(missionId).toBeTruthy();

    const list = (await (await get("/api/hub/missions")).json()) as { missionId: string; status: string }[];
    expect(list).toEqual([{ missionId, title: expect.any(String), status: "draft" }]);

    const view = (await (await get(`/api/hub/missions/${missionId}/session`)).json()) as SessionView;
    expect(view.mission.status).toBe("draft");
    expect(view.criteria).toHaveLength(4);
    const criteriaText = view.criteria.map((c) => c.text).join(" ");
    expect(criteriaText).toMatch(/Job Reader output/);
    expect(criteriaText).toMatch(/Tailored CV/);
    expect(criteriaText).toMatch(/recommendation/);
    expect(view.work.map((t) => t.taskId)).toEqual([
      "read-posting",
      "tailor-cv",
      "forge-review",
      "recommend",
    ]);
    expect(view.work.map((t) => t.owner)).toEqual([
      "job-reader",
      "cv-adapter",
      "forge",
      "specialized-chief-of-staff",
    ]);
    expect(view.usage.calls).toBe(0);

    const { messages } = (await (await get(`/api/hub/missions/${missionId}/messages`)).json()) as { messages: HubMessage[] };
    expect(messages).toHaveLength(1);
    expect(messages[0]).toMatchObject({
      type: "assignment",
      from: "roosevelt",
      to: "specialized-chief-of-staff",
    });
  });

  it("session view reports objective phase handoffs waiting usage and controls", async () => {
    const missionId = await prepareAcme();
    const { missions, tasks, messages, waiting, usage } = stub.state;
    missions.get(missionId)!.status = "running";
    const list = tasks.get(missionId)!;
    list[0]!.status = "completed";
    list[1]!.status = "blocked";
    list[1]!.blockedReason = "base CV missing";
    list[2]!.status = "in_progress";
    list[2]!.runId = "run-1";
    list[2]!.runStatus = "running";
    for (const [from, taskId, result, evidence] of [
      ["job-reader", "read-posting", "Extracted 9 responsibilities.", ["workspace/agents/job-reader/outputs/acme-health-systems-administrator.json"]],
      ["cv-adapter", "tailor-cv", "Rewrote headline and 7 bullets.", ["workspace/agents/cv-adapter/outputs/tailored-acme.md"]],
    ] as const) {
      messages.push({
        id: randomUUID(), missionId, taskId, inReplyTo: null, from, to: "forge", type: "result",
        objective: "", doneWhen: "", inputRefs: [], outputRefs: [], result, evidence: [...evidence],
        decisions: [], blockers: [], approvalNeeded: false, idempotencyKey: `run:${taskId}`,
        createdAt: new Date().toISOString(),
      });
    }
    waiting.push({
      id: "w-approval", missionId, kind: "approval",
      title: "Switch forge-review to Claude sonnet",
      detail: "Paid model. Nothing runs until you approve.",
      action: "approve", approvalId: "approval-1",
    });
    Object.assign(usage, { calls: 4, inputTokens: 41208, outputTokens: 2914, costUsd: 0 });

    const res = await get(`/api/hub/missions/${missionId}/session`);
    expect(res.status).toBe(200);
    const view = (await res.json()) as SessionView;
    expect(view.objective).toContain("Acme Health");
    expect(view.phase).toMatchObject({ taskId: "forge-review", owner: "forge" });
    expect(view.handoffs).toHaveLength(2);
    expect(view.handoffs[0]!.evidence[0]).toContain("job-reader/outputs/");
    expect(view.waiting).toEqual([
      { id: "w-approval", kind: "approval", title: expect.any(String), detail: expect.any(String), action: "approve", approvalId: "approval-1" },
    ]);
    expect(view.counts).toEqual({ running: 1, blocked: 1, completed: 1, pending: 1 });
    expect(view.usage).toMatchObject({ calls: 4, budget: 10, inputTokens: 41208, outputTokens: 2914, costUsd: 0 });
    expect(view.work.find((t) => t.taskId === "tailor-cv")!.blockedReason).toBe("base CV missing");
    expect(view.audit.length).toBeGreaterThanOrEqual(3);

    // Controls live in the Session tab markup/script served at /.
    const html = await (await get("/")).text();
    expect(html).toContain('id="sessionTab"');
    expect(html).toContain("Pause mission");
    expect(html).toContain("Stop all runs");
    expect(html).toContain("Approve");
    expect(html).toContain("Deny");
  });

  it("prepare rejects unknown and closed jobs", async () => {
    const unknown = await post("/api/hub/missions/prepare-application", {
      company: "Ghost Co", role: "Nobody", url: "https://example.com/x",
    });
    expect(unknown.status).toBe(400);
    expect(((await unknown.json()) as { error: string }).error).toMatch(/not in the tracker/);

    const closed = await post("/api/hub/missions/prepare-application", {
      company: "Closed Co", role: "Engineer", url: "https://example.com/y",
    });
    expect(closed.status).toBe(400);
    expect(((await closed.json()) as { error: string }).error).toMatch(/rejected/);

    expect(stub.state.missions.size).toBe(0);
    expect(stub.state.messages).toHaveLength(0);
    expect(await (await get("/api/hub/missions")).json()).toEqual([]);
  });

  it("stop and pause are safe no-ops when idle", async () => {
    const first = await post("/api/hub/stop-runs", {});
    expect(first.status).toBe(200);
    expect(await first.json()).toEqual({ terminated: 0 });
    const second = await post("/api/hub/stop-runs", {});
    expect(second.status).toBe(200);
    expect(await second.json()).toEqual({ terminated: 0 });

    const missionId = await prepareAcme();
    expect((await post(`/api/hub/missions/${missionId}/pause`, {})).status).toBe(200);
    expect((await post(`/api/hub/missions/${missionId}/pause`, {})).status).toBe(200);
    const view = (await (await get(`/api/hub/missions/${missionId}/session`)).json()) as SessionView;
    expect(view.mission.status).toBe("paused");
  });

  it("mailbox writes are loopback only and idempotent", async () => {
    const missionId = await prepareAcme();
    const message = {
      missionId, from: "job-reader", to: "forge", type: "note",
      result: "Reading the posting now.", idempotencyKey: "note-1",
    };
    const ok = await post(`/api/hub/missions/${missionId}/messages`, message);
    expect(ok.status).toBe(200);
    const okBody = (await ok.json()) as { ok: boolean; id: string };
    expect(okBody.ok).toBe(true);
    expect(okBody.id).toBeTruthy();

    const foreignHost = await post(`/api/hub/missions/${missionId}/messages`, { ...message, idempotencyKey: "note-2" }, { Host: "example.com" });
    expect(foreignHost.status).toBe(403);
    const foreignOrigin = await post(`/api/hub/missions/${missionId}/messages`, { ...message, idempotencyKey: "note-3" }, { Origin: "https://evil.example" });
    expect(foreignOrigin.status).toBe(403);
    expect(stub.state.messages.filter((m) => m.type === "note")).toHaveLength(1);

    const duplicate = await post(`/api/hub/missions/${missionId}/messages`, message);
    expect(duplicate.status).toBe(200);
    expect(((await duplicate.json()) as { id: string }).id).toBe(okBody.id);
    expect(stub.state.messages.filter((m) => m.type === "note")).toHaveLength(1);

    const broadcast = await post(`/api/hub/missions/${missionId}/messages`, { ...message, to: "*", idempotencyKey: "note-4" });
    expect(broadcast.status).toBe(400);
    expect(((await broadcast.json()) as { error: string }).error).toBeTruthy();
  });

  it("serves evidence files only inside registry output dirs", async () => {
    const outputs = join(root, "workspace/agents/job-reader/outputs");
    mkdirSync(outputs, { recursive: true });
    writeFileSync(join(outputs, "acme.json"), '{"ok":true}');
    writeFileSync(join(outputs, "notes.md"), "# Notes");
    writeFileSync(join(outputs, "cv.pdf"), "%PDF-1.4 test");
    writeFileSync(join(outputs, "blob.bin"), Buffer.from([0, 1, 2]));
    writeFileSync(join(root, "secret.txt"), "private");
    symlinkSync(join(root, "secret.txt"), join(outputs, "escape.txt"));

    const json = await get("/api/hub/file?path=workspace/agents/job-reader/outputs/acme.json");
    expect(json.status).toBe(200);
    expect(json.headers.get("content-type")).toContain("text/plain");
    expect(json.headers.get("content-security-policy")).toBe("sandbox allow-scripts");
    expect(await json.text()).toBe('{"ok":true}');

    const md = await get("/api/hub/file?path=workspace/agents/job-reader/outputs/notes.md");
    expect(md.headers.get("content-type")).toContain("text/plain");
    const pdf = await get("/api/hub/file?path=workspace/agents/job-reader/outputs/cv.pdf");
    expect(pdf.headers.get("content-type")).toBe("application/pdf");
    const bin = await get("/api/hub/file?path=workspace/agents/job-reader/outputs/blob.bin");
    expect(bin.headers.get("content-type")).toBe("application/octet-stream");
    expect(bin.headers.get("content-disposition")).toBe("attachment");

    for (const path of [
      "secret.txt",
      "workspace/agents/job-reader/outputs/../../../secret.txt",
      "workspace/agents/job-reader/memory/private.md",
      "workspace/agents/job-reader/outputs/escape.txt",
      "workspace/agents/job-reader/outputs/missing.json",
      "/etc/passwd",
      "",
    ]) {
      const res = await get(`/api/hub/file?path=${encodeURIComponent(path)}`);
      expect(res.status, path).toBe(404);
    }
  });

  it("exposes the registry, control routes and 404s for unknown missions", async () => {
    const agents = await get("/api/hub/agents");
    expect(agents.status).toBe(200);
    const registry = (await agents.json()) as AgentRegistry;
    expect(registry.forge).toMatchObject({ name: "Forge", coordinator: "specialized-chief-of-staff" });
    expect(registry["job-reader"]!.outputDirs).toEqual(["workspace/agents/job-reader/outputs"]);

    const missionId = await prepareAcme();
    expect((await post(`/api/hub/missions/${missionId}/start`, {})).status).toBe(200);
    expect(((await (await get(`/api/hub/missions/${missionId}/session`)).json()) as SessionView).mission.status).toBe("running");
    expect((await post(`/api/hub/missions/${missionId}/pause`, {})).status).toBe(200);
    expect((await post(`/api/hub/missions/${missionId}/resume`, {})).status).toBe(200);

    stub.state.waiting.push({
      id: "w-budget", missionId, kind: "budget", title: "Raise the model-call budget to 12",
      detail: "Remaining: recommend.", action: "12", approvalId: null,
    });
    const resolved = await post(`/api/hub/missions/${missionId}/waiting/w-budget/resolve`, { decision: "approve" });
    expect(resolved.status).toBe(200);
    expect(await resolved.json()).toEqual({ ok: true });
    const invalid = await post(`/api/hub/missions/${missionId}/waiting/w-budget/resolve`, { decision: "maybe" });
    expect(invalid.status).toBe(400);

    expect((await get("/api/hub/missions/ghost/session")).status).toBe(404);
    expect((await get("/api/hub/missions/ghost/messages")).status).toBe(404);
  });

  it("serves the Session tab in the dashboard HTML", async () => {
    const res = await get("/");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain('id="sessionTab"');
    expect(html).toContain('aria-controls="sessionWorkspace"');
    expect(html).toContain('id="sessionWorkspace"');
    expect(html).toContain('id="sessionPrepareForm"');
    expect(html).toContain("#session-prepare");
  });

  it("does not mount hub routes without a hub option", async () => {
    const plain = createApp(db);
    expect((await plain.request("/api/hub/missions")).status).toBe(404);
  });
});
