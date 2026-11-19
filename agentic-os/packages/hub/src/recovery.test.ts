import { afterEach, describe, expect, it } from "vitest";
import { AgentRuntime } from "@agentic-os/runtime";
import { Hub } from "./orchestrator.js";
import { FREE_MODEL, makeSlice, runsFor, settle, waitFor, type Slice } from "./test-support.js";

describe("hub restart recovery", () => {
  let slice: Slice;
  let extraRuntime: AgentRuntime | null = null;
  afterEach(async () => {
    if (extraRuntime) await extraRuntime.shutdown();
    extraRuntime = null;
    await slice?.cleanup();
  });

  it("restart recovery separates results from processes", async () => {
    slice = makeSlice({ subscribe: false });
    const unsubscribe = slice.runtime.subscribe((run) => slice.hub.handleRunFinished(run));
    const { missionId } = await slice.prepare();
    await slice.hub.start(missionId);
    await waitFor(() => runsFor(slice.runtime, missionId)[0]?.status === "completed");
    expect(slice.hub.session(missionId).work.find((w) => w.taskId === "read-posting")!.status).toBe("completed");

    // The next task leases a long-running process; then the supervisor "dies".
    slice.setMode("sleep_long");
    slice.hub.handleRunFinished(runsFor(slice.runtime, missionId)[0]!);
    await waitFor(() => runsFor(slice.runtime, missionId).some((r) => r.taskId === "tailor-cv"));
    const liveRun = runsFor(slice.runtime, missionId).find((r) => r.taskId === "tailor-cv")!;
    unsubscribe();
    slice.db.prepare("DELETE FROM runtime_owner").run();
    extraRuntime = new AgentRuntime(slice.db, slice.adapters);
    const hub2 = new Hub(slice.db, extraRuntime, slice.service, slice.registry, {
      workspaceRoot: slice.workspace,
      freeModels: [FREE_MODEL],
      trackerLookup: async () => ({ status: "applied", jobUrl: "https://example.com/jobs/1" }),
    });
    await settle();

    expect(extraRuntime.getRun(liveRun.id)!.status).toBe("lost");
    const view = hub2.session(missionId);
    expect(view.work.find((w) => w.taskId === "tailor-cv")!.status).toBe("interrupted");
    expect(view.work.find((w) => w.taskId === "read-posting")!.status).toBe("completed");
    expect(view.mission.status).toBe("paused");
    expect(view.waiting.some((w) => w.kind === "blocker")).toBe(true);
    expect(runsFor(extraRuntime, missionId)).toHaveLength(2);
    const subscriptions = slice.db
      .prepare("SELECT kind FROM hub_subscriptions WHERE mission_id = ? ORDER BY kind")
      .all(missionId) as { kind: string }[];
    expect(subscriptions.map((s) => s.kind)).toEqual(["new_message", "run_completion"]);

    // Re-arm the subscription, resume explicitly, and accept the new handoff once.
    const unsubscribe2 = extraRuntime.subscribe((run) => hub2.handleRunFinished(run));
    slice.setMode("ok");
    await hub2.resume(missionId);
    await waitFor(() =>
      hub2.session(missionId).work.some((w) => w.taskId === "tailor-cv" && w.status === "completed"),
    );
    const newRun = runsFor(extraRuntime, missionId).find(
      (r) => r.taskId === "tailor-cv" && r.id !== liveRun.id,
    )!;
    hub2.handleRunFinished(newRun);
    hub2.handleRunFinished(newRun);
    expect(hub2.messages(missionId).filter((m) => m.idempotencyKey === `run:${newRun.id}`)).toHaveLength(1);
    expect(runsFor(extraRuntime, missionId).filter((r) => r.taskId === "tailor-cv")).toHaveLength(2);
    unsubscribe2();

    // Silence the orphaned child of the "dead" supervisor before cleanup.
    if (liveRun.pid) {
      try {
        process.kill(-liveRun.pid, "SIGKILL");
      } catch {
        /* already gone */
      }
    }
  });

  it("recover reprocesses a finished run without a result message exactly once", async () => {
    slice = makeSlice({ subscribe: false });
    const { missionId } = await slice.prepare();
    await slice.hub.start(missionId);
    await waitFor(() => runsFor(slice.runtime, missionId)[0]?.status === "completed");
    await settle();
    expect(slice.hub.session(missionId).work.find((w) => w.taskId === "read-posting")!.status).toBe("in_progress");
    expect(slice.hub.messages(missionId).filter((m) => m.type === "result")).toHaveLength(0);

    slice.hub.recover();
    await waitFor(() =>
      slice.hub.session(missionId).work.some((w) => w.taskId === "read-posting" && w.status === "completed"),
    );
    const run = runsFor(slice.runtime, missionId).find((r) => r.taskId === "read-posting")!;
    expect(slice.hub.messages(missionId).filter((m) => m.idempotencyKey === `run:${run.id}`)).toHaveLength(1);

    slice.hub.recover();
    await settle();
    expect(slice.hub.messages(missionId).filter((m) => m.idempotencyKey === `run:${run.id}`)).toHaveLength(1);
  });
});
