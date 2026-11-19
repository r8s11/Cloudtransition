import { afterEach, describe, expect, it } from "vitest";
import { rmSync } from "node:fs";
import { join } from "node:path";
import { defaultRegistry, FREE_MODEL, makeSlice, runsFor, settle, waitFor, type Slice } from "./test-support.js";

describe("hub orchestrator", () => {
  let slice: Slice;
  afterEach(async () => {
    await slice?.cleanup();
  });

  it("start leases the first task and writes assignments", async () => {
    slice = makeSlice();
    const { missionId } = await slice.prepare();
    expect((await slice.service.get(missionId))!.status).toBe("draft");
    expect(runsFor(slice.runtime, missionId)).toHaveLength(0);

    await slice.hub.start(missionId);
    await waitFor(() => runsFor(slice.runtime, missionId).length === 1);
    const run = runsFor(slice.runtime, missionId)[0]!;
    expect(run.adapterId).toBe("opencode");
    expect(run.model).toBe(FREE_MODEL);
    expect(slice.opencodeCalls[0]!.agent).toBe("job-reader");
    expect(run.prompt).toContain("Prepare an application for Acme Health — Systems Administrator");
    expect(run.prompt).toContain("Posting analysis written to workspace/agents/job-reader/outputs/");
    expect(run.prompt).toContain("https://example.com/jobs/1");
    expect(run.prompt).not.toContain("durable knowledge");
    expect(run.prompt).not.toContain("private memory");

    const messages = slice.hub.messages(missionId);
    const cosToForge = messages.find((m) => m.from === "specialized-chief-of-staff" && m.to === "forge")!;
    const forgeToWorker = messages.find((m) => m.from === "forge" && m.to === "job-reader")!;
    for (const assignment of [cosToForge, forgeToWorker]) {
      expect(assignment.type).toBe("assignment");
      expect(assignment.missionId).toBe(missionId);
      expect(assignment.taskId).toBe("read-posting");
      expect(assignment.objective).toContain("Acme Health");
      expect(assignment.doneWhen).toBeTruthy();
      expect(assignment.inputRefs).toContain("https://example.com/jobs/1");
    }
    const lease = slice.db
      .prepare("SELECT lease_key FROM hub_tasks WHERE mission_id = ? AND task_id = 'read-posting'")
      .get(missionId) as { lease_key: string };
    expect(lease.lease_key).toBe(`start:${missionId}:read-posting`);
    await waitFor(() => slice.hub.session(missionId).mission.status === "running");
  });

  it("completion requires validated acceptance criteria", async () => {
    slice = makeSlice();
    const { missionId } = await slice.prepare();
    await slice.hub.start(missionId);
    await waitFor(() =>
      slice.hub.session(missionId).work.some((w) => w.taskId === "forge-review" && w.status === "completed"),
    );
    await settle();
    expect(slice.hub.session(missionId).mission.status).toBe("running");

    await waitFor(() => slice.hub.session(missionId).mission.status === "completed");
    const view = slice.hub.session(missionId);
    expect(view.counts.completed).toBe(4);
    expect(view.criteria.every((c) => c.done)).toBe(true);
    expect(view.recommendation).toContain("done specialized-chief-of-staff");
    expect(view.handoffs).toHaveLength(4);

    const runs = runsFor(slice.runtime, missionId).sort((a, b) => a.createdAt.localeCompare(b.createdAt));
    const tailor = runs.find((r) => r.taskId === "tailor-cv")!;
    const forge = runs.find((r) => r.taskId === "forge-review")!;
    expect(forge.createdAt >= tailor.endedAt!).toBe(true);
    const recommend = slice.hub.messages(missionId).find((m) => m.taskId === "recommend" && m.type === "result")!;
    expect(view.recommendation).toBe(recommend.result);
  });

  it("budget and depth stop the mission before the next call", async () => {
    slice = makeSlice({ budget: 1 });
    const { missionId } = await slice.prepare();
    await slice.hub.start(missionId);
    await waitFor(() => slice.hub.session(missionId).mission.status === "awaiting_approval");
    expect(runsFor(slice.runtime, missionId)).toHaveLength(1);
    expect(slice.opencodeCalls).toHaveLength(1);
    expect(slice.hub.session(missionId).waiting.some((w) => w.kind === "budget")).toBe(true);
    await slice.cleanup();

    const deep = defaultRegistry();
    deep["scout"]!.coordinator = "lead";
    deep["job-reader"]!.coordinator = "scout";
    deep["lead"] = { ...deep["forge"]!, id: "lead", name: "Lead", coordinator: "forge" };
    slice = makeSlice({ registry: deep });
    await expect(slice.prepare()).rejects.toMatchObject({ status: 400 });
  });

  it("a paid model waits for approval", async () => {
    slice = makeSlice();
    const { missionId } = await slice.prepare();
    slice.db
      .prepare("UPDATE hub_sessions SET models_json = ? WHERE mission_id = ?")
      .run(JSON.stringify({ forge: { adapter: "claude", model: "sonnet" } }), missionId);
    await slice.hub.start(missionId);
    await waitFor(() => slice.hub.session(missionId).waiting.some((w) => w.kind === "approval"));
    await settle();
    expect(slice.hub.session(missionId).mission.status).toBe("awaiting_approval");
    expect(runsFor(slice.runtime, missionId)).toHaveLength(2);
    const approvals = await slice.service.listApprovals("pending");
    expect(approvals).toHaveLength(1);
    expect(approvals[0]!.action).toContain("forge");
    expect(approvals[0]!.action).toContain("sonnet");
    expect(approvals[0]!.reason).toContain(missionId);

    const waiting = slice.hub.session(missionId).waiting.find((w) => w.kind === "approval")!;
    await slice.hub.resolveWaiting(missionId, waiting.id, "deny");
    await waitFor(() => slice.hub.session(missionId).mission.status === "paused");
    expect(slice.hub.session(missionId).work.find((w) => w.taskId === "forge-review")!.status).toBe("blocked");

    const second = await slice.prepare();
    slice.db
      .prepare("UPDATE hub_sessions SET models_json = ? WHERE mission_id = ?")
      .run(JSON.stringify({ forge: { adapter: "claude", model: "sonnet" } }), second.missionId);
    await slice.hub.start(second.missionId);
    await waitFor(() => slice.hub.session(second.missionId).waiting.some((w) => w.kind === "approval"));
    const approvalWaiting = slice.hub.session(second.missionId).waiting.find((w) => w.kind === "approval")!;
    await slice.hub.resolveWaiting(second.missionId, approvalWaiting.id, "approve");
    await waitFor(() => runsFor(slice.runtime, second.missionId).some((r) => r.adapterId === "claude"));
    const paidRun = runsFor(slice.runtime, second.missionId).find((r) => r.adapterId === "claude")!;
    expect(paidRun.model).toBe("sonnet");
    expect(slice.claudeCalls[0]!.model).toBe("sonnet");
    await waitFor(() => slice.hub.session(second.missionId).mission.status === "completed");
    expect(slice.hub.session(second.missionId).usage.costUsd).toBeGreaterThanOrEqual(0.42);
  });

  it("provider failure blocks the task and waits", async () => {
    slice = makeSlice();
    slice.setMode("fail");
    const { missionId } = await slice.prepare();
    await slice.hub.start(missionId);
    await waitFor(() =>
      slice.hub.session(missionId).work.some((w) => w.taskId === "read-posting" && w.status === "blocked"),
    );
    await settle();
    const view = slice.hub.session(missionId);
    expect(view.work.find((w) => w.taskId === "read-posting")!.blockedReason).toContain("provider connection error");
    expect(view.mission.status).toBe("paused");
    expect(view.waiting.some((w) => w.kind === "blocker" && w.action.includes("retry"))).toBe(true);

    slice.setMode("ok");
    await slice.hub.resume(missionId);
    await waitFor(() =>
      slice.hub.session(missionId).work.some((w) => w.taskId === "read-posting" && w.status === "completed"),
    );
    expect(runsFor(slice.runtime, missionId)).toHaveLength(2);
  });

  it("an exit without a handoff never completes a task", async () => {
    slice = makeSlice();
    slice.setMode("prose");
    const { missionId } = await slice.prepare();
    await slice.hub.start(missionId);
    await waitFor(() =>
      slice.hub.session(missionId).work.some((w) => w.taskId === "read-posting" && w.status === "blocked"),
    );
    await settle();
    const view = slice.hub.session(missionId);
    const work = view.work.find((w) => w.taskId === "read-posting")!;
    expect(work.status).toBe("blocked");
    expect(work.blockedReason).toBe("no handoff block");
    expect(view.mission.status).toBe("paused");
    expect(view.mission.status).not.toBe("completed");
    expect(view.waiting.some((w) => w.title.includes("job-reader"))).toBe(true);
    const result = slice.hub.messages(missionId).find((m) => m.type === "result")!;
    expect(result.result).toContain("I reviewed the posting");
    expect(result.blockers).toContain("no handoff block");
  });

  it("missing evidence blocks validation", async () => {
    slice = makeSlice();
    slice.setMode("missing");
    const { missionId } = await slice.prepare();
    await slice.hub.start(missionId);
    await waitFor(() =>
      slice.hub.session(missionId).work.some((w) => w.taskId === "read-posting" && w.status === "blocked"),
    );
    await settle();
    const view = slice.hub.session(missionId);
    const missingRef = "workspace/agents/job-reader/outputs/does-not-exist.json";
    expect(view.work.find((w) => w.taskId === "read-posting")!.blockedReason).toContain(missingRef);
    const result = slice.hub.messages(missionId).find((m) => m.type === "result")!;
    expect(result.blockers.some((b) => b.includes(missingRef))).toBe(true);
    expect(view.mission.status).toBe("paused");
    expect(view.work.find((w) => w.taskId === "tailor-cv")!.status).toBe("pending");
  });

  it("a leased task starts once", async () => {
    slice = makeSlice();
    slice.setMode("sleep");
    const { missionId } = await slice.prepare();
    await slice.hub.start(missionId);
    await slice.hub.start(missionId);
    expect(runsFor(slice.runtime, missionId)).toHaveLength(1);
    await waitFor(() =>
      slice.hub.session(missionId).work.some((w) => w.taskId === "read-posting" && w.status === "completed"),
    );
    const run = runsFor(slice.runtime, missionId).find((r) => r.taskId === "read-posting")!;
    slice.hub.handleRunFinished(run);
    slice.hub.handleRunFinished(run);
    expect(slice.hub.messages(missionId).filter((m) => m.idempotencyKey === `run:${run.id}`)).toHaveLength(1);
  });

  it("an exhausted budget names what remains", async () => {
    slice = makeSlice({ budget: 1 });
    const { missionId } = await slice.prepare();
    await slice.hub.start(missionId);
    await waitFor(() => slice.hub.session(missionId).waiting.some((w) => w.kind === "budget"));
    const waiting = slice.hub.session(missionId).waiting.find((w) => w.kind === "budget")!;
    expect(waiting.detail).toContain("tailor-cv (cv-adapter)");
    expect(waiting.detail).toContain("forge-review (forge)");
    expect(waiting.detail).toContain("recommend (specialized-chief-of-staff)");
    expect(runsFor(slice.runtime, missionId)).toHaveLength(1);

    await slice.hub.resolveWaiting(missionId, waiting.id, "approve");
    await waitFor(() => runsFor(slice.runtime, missionId).length === 2);
    expect(slice.hub.session(missionId).usage.budget).toBe(4);
    expect(slice.hub.session(missionId).mission.status).toBe("running");
  });

  it("a failed run start blocks the task instead of stranding the lease", async () => {
    slice = makeSlice();
    const { missionId } = await slice.prepare();
    // Without a git root the runtime cannot register the project: start must
    // block the task and pause, never leave it in_progress with no run.
    rmSync(join(slice.workspace, ".git"), { recursive: true, force: true });
    await slice.hub.start(missionId);
    await waitFor(() => slice.hub.session(missionId).mission.status === "paused");
    const view = slice.hub.session(missionId);
    expect(view.work.find((w) => w.taskId === "read-posting")!.status).toBe("blocked");
    expect(view.waiting.some((w) => w.title === "Run could not start")).toBe(true);
    expect(runsFor(slice.runtime, missionId)).toHaveLength(0);
  });
});
