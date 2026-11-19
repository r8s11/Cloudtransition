import { afterEach, describe, expect, it } from "vitest";
import { SqlitePlanRepository } from "@agentic-os/storage";
import { assertLoopbackRequest, HubError } from "./index.js";
import { makeSlice, runsFor, settle, waitFor, type Slice } from "./test-support.js";

describe("hub mailbox", () => {
  let slice: Slice;
  afterEach(async () => {
    await slice?.cleanup();
  });

  it("a validated handoff completes its task", async () => {
    slice = makeSlice();
    const { missionId } = await slice.prepare();
    await slice.hub.start(missionId);
    await waitFor(() =>
      slice.hub.session(missionId).work.some((w) => w.taskId === "read-posting" && w.status === "completed"),
    );
    await settle();

    const messages = slice.hub.messages(missionId);
    const assignment = messages.find((m) => m.idempotencyKey === `assign:${missionId}:read-posting`)!;
    const result = messages.find((m) => m.idempotencyKey.startsWith("run:"))!;
    expect(result.type).toBe("result");
    expect(result.from).toBe("job-reader");
    expect(result.to).toBe("forge");
    expect(result.taskId).toBe("read-posting");
    expect(result.inReplyTo).toBe(assignment.id);
    expect(result.objective).toContain("Acme Health");
    expect(result.doneWhen).toBeTruthy();
    expect(result.inputRefs).toContain("https://example.com/jobs/1");
    expect(result.evidence).toEqual(["workspace/agents/job-reader/outputs/result.json"]);
    expect(result.decisions).toEqual([]);
    expect(result.blockers).toEqual([]);
    expect(result.approvalNeeded).toBe(false);
    expect(result.result).toContain("done job-reader");

    const view = slice.hub.session(missionId);
    expect(view.mission.status).toBe("running");
    expect(view.usage.inputTokens).toBeGreaterThanOrEqual(100);
    expect(view.usage.outputTokens).toBeGreaterThanOrEqual(50);
    expect(view.handoffs.some((h) => h.taskId === "read-posting")).toBe(true);
  });

  it("duplicate keys store once", async () => {
    slice = makeSlice();
    const { missionId } = await slice.prepare();
    await slice.hub.start(missionId, "start-key-1");
    await slice.hub.start(missionId, "start-key-1");
    expect(runsFor(slice.runtime, missionId)).toHaveLength(1);
    await waitFor(() =>
      slice.hub.session(missionId).work.some((w) => w.taskId === "read-posting" && w.status === "completed"),
    );

    const input = {
      missionId,
      taskId: "read-posting",
      from: "job-reader",
      to: "forge",
      type: "result" as const,
      result: "duplicate delivery",
      idempotencyKey: "dup-1",
    };
    const first = slice.hub.ingest(input);
    const second = slice.hub.ingest(input);
    expect(first.ok).toBe(true);
    expect(second.ok).toBe(true);
    expect(second.id).toBe(first.id);
    expect(slice.hub.messages(missionId).filter((m) => m.idempotencyKey === "dup-1")).toHaveLength(1);
  });

  it("messages need an explicit task relationship", async () => {
    slice = makeSlice();
    // A mission whose two specialist tasks declare no dependsOn relationship.
    const mission = await slice.service.create({ title: "routing", acceptanceCriteria: ["x"] });
    const missionId = mission.id;
    const task = (id: string, owner: string) => ({
      id,
      title: id,
      steps: [{ kind: "reasoning" as const, expectedObservation: "out" }],
      expectedResult: "out",
      verificationCriteria: ["out"],
      owner,
    });
    await new SqlitePlanRepository(slice.db).save(missionId, {
      missionId,
      tasks: [task("read-posting", "job-reader"), task("tailor-cv", "cv-adapter")],
    });
    const now = new Date().toISOString();
    slice.db
      .prepare(
        "INSERT INTO hub_sessions (mission_id, budget, max_depth, models_json, criteria_refs_json, created_at, updated_at) VALUES (?, 10, 3, '{}', '[]', ?, ?)",
      )
      .run(missionId, now, now);
    for (const [id, owner] of [["read-posting", "job-reader"], ["tailor-cv", "cv-adapter"]])
      slice.db
        .prepare("INSERT INTO hub_tasks (mission_id, task_id, owner, status, updated_at) VALUES (?, ?, ?, 'pending', ?)")
        .run(missionId, id, owner, now);
    const before = slice.hub.messages(missionId).length;

    const sibling = slice.hub.ingest({
      missionId, from: "job-reader", to: "cv-adapter", type: "note", result: "hi", idempotencyKey: "r1",
    });
    const broadcast = slice.hub.ingest({
      missionId, from: "job-reader", to: "*", type: "note", result: "hi", idempotencyKey: "r2",
    });
    const outsider = slice.hub.ingest({
      missionId, from: "job-reader", to: "scout", type: "note", result: "hi", idempotencyKey: "r3",
    });
    const unknown = slice.hub.ingest({
      missionId, from: "job-reader", to: "nobody", type: "note", result: "hi", idempotencyKey: "r4",
    });
    for (const refused of [sibling, broadcast, outsider, unknown]) {
      expect(refused.ok).toBe(false);
      expect(refused.reason).toBeTruthy();
    }
    expect(slice.hub.messages(missionId)).toHaveLength(before);
    const refusals = slice.db
      .prepare("SELECT * FROM hub_audit WHERE mission_id = ? AND kind = 'refused'")
      .all(missionId) as { detail: string }[];
    expect(refusals).toHaveLength(4);

    const coordinator = slice.hub.ingest({
      missionId, from: "job-reader", to: "forge", type: "note", result: "status", idempotencyKey: "r5",
    });
    expect(coordinator.ok).toBe(true);
  });

  it("mailbox writes are loopback only", () => {
    const allowed = [
      { host: "localhost:8787", remoteAddress: "127.0.0.1" },
      { host: "127.0.0.1:8787" },
      { host: "[::1]:8787", remoteAddress: "::1" },
      { host: "localhost", origin: "http://localhost:8787" },
    ];
    for (const req of allowed) expect(() => assertLoopbackRequest(req)).not.toThrow();

    const refused = [
      { host: "example.com" },
      { host: "localhost:8787", origin: "https://evil.example.com" },
      { host: "localhost", remoteAddress: "100.64.0.5" },
      { host: "localhost", origin: "not a url" },
      {},
    ];
    for (const req of refused) {
      try {
        assertLoopbackRequest(req);
        expect.unreachable("expected a 403");
      } catch (error) {
        expect(error).toBeInstanceOf(HubError);
        expect((error as HubError).status).toBe(403);
      }
    }
  });

  it("a malformed handoff is reported, not swallowed", async () => {
    slice = makeSlice();
    slice.setMode("badjson");
    const { missionId } = await slice.prepare();
    await slice.hub.start(missionId);
    await waitFor(() =>
      slice.hub.session(missionId).work.some((w) => w.taskId === "read-posting" && w.status === "blocked"),
    );
    await settle();

    const view = slice.hub.session(missionId);
    const work = view.work.find((w) => w.taskId === "read-posting")!;
    expect(work.blockedReason).toContain("parse error");
    expect(work.blockedReason).toContain("{not valid json");
    expect(view.mission.status).toBe("paused");
    expect(view.waiting.some((w) => w.kind === "blocker")).toBe(true);
    const result = slice.hub.messages(missionId).find((m) => m.type === "result")!;
    expect(result.blockers.length).toBeGreaterThan(0);
    expect(result.result).toContain("{not valid json");
  });
});
