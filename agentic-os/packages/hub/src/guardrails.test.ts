import { existsSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { gitHead } from "./guardrails.js";
import { hashTree, makeSlice, settle, waitFor, type Slice } from "./test-support.js";

async function runFullSlice(slice: Slice): Promise<string> {
  slice.setMode("ok");
  const { missionId } = await slice.prepare();
  await slice.hub.start(missionId);
  await waitFor(() => slice.hub.session(missionId).mission.status === "completed");
  return missionId;
}

describe("hub guardrails", () => {
  let slice: Slice;
  afterEach(async () => {
    await slice?.cleanup();
  });

  it("foreign memory writes block the handoff and name the path", async () => {
    slice = makeSlice();
    slice.setMode("foreign");
    const { missionId } = await slice.prepare();
    await slice.hub.start(missionId);
    await waitFor(() =>
      slice.hub.session(missionId).work.some((w) => w.taskId === "read-posting" && w.status === "blocked"),
    );
    await settle();
    const view = slice.hub.session(missionId);
    const foreignPath = "workspace/agents/cv-adapter/memory/intrusion.md";
    expect(view.work.find((w) => w.taskId === "read-posting")!.blockedReason).toContain(foreignPath);
    expect(view.waiting.some((w) => w.detail.includes(foreignPath))).toBe(true);
    expect(existsSync(join(slice.workspace, foreignPath))).toBe(true);
    expect(existsSync(join(slice.workspace, "workspace/agents/job-reader/outputs/result.json"))).toBe(true);
    expect(view.mission.status).not.toBe("completed");
    expect(view.work.find((w) => w.taskId === "tailor-cv")!.status).toBe("pending");
  });

  it("git history changes during a run raise a blocker", async () => {
    slice = makeSlice();
    slice.setMode("gitcommit");
    const { missionId } = await slice.prepare();
    await slice.hub.start(missionId);
    await waitFor(() =>
      slice.hub.session(missionId).work.some((w) => w.taskId === "read-posting" && w.status === "blocked"),
    );
    await settle();
    const view = slice.hub.session(missionId);
    const blocker = view.waiting.find((w) => w.title === "git history changed during run")!;
    expect(blocker).toBeTruthy();
    expect(blocker.detail).toContain(gitHead(slice.workspace)!);
    expect(view.work.find((w) => w.taskId === "read-posting")!.blockedReason).toBe("git history changed during run");
    expect(view.mission.status).toBe("paused");
  });

  it("handoff content cannot grant permissions", async () => {
    slice = makeSlice();
    slice.setMode("injection");
    const { missionId } = await slice.prepare();
    await slice.hub.start(missionId);
    await waitFor(() =>
      slice.hub.session(missionId).work.some((w) => w.taskId === "read-posting" && w.status === "completed"),
    );
    await settle();

    const result = slice.hub.messages(missionId).find((m) => m.taskId === "read-posting" && m.type === "result")!;
    expect(result.approvalNeeded).toBe(true);
    expect(result.decisions).toEqual(["granted myself filesystem.delete"]);
    expect(result.result).toContain("ignore previous instructions");
    expect(await slice.service.listApprovals()).toHaveLength(0);
    const audit = slice.db
      .prepare("SELECT * FROM hub_audit WHERE mission_id = ? AND kind = 'ignored_recommendation'")
      .all(missionId) as { detail: string }[];
    expect(audit.some((row) => row.detail.includes("scout"))).toBe(true);
    expect(slice.opencodeCalls.every((call) => call.agent !== "scout")).toBe(true);
    // The orchestrator's next action is the planned one, unchanged by the content.
    await waitFor(() =>
      slice.hub.session(missionId).work.some((w) => w.taskId === "tailor-cv" && w.status === "in_progress"),
    );
  });

  it("the hub never writes second brain", async () => {
    slice = makeSlice();
    const before = hashTree(slice.workspace, "second-brain");
    await runFullSlice(slice);
    expect(hashTree(slice.workspace, "second-brain")).toBe(before);
  });

  it("a full slice leaves agent definitions and memories byte-identical", async () => {
    slice = makeSlice();
    const trees = [
      ".opencode/agents",
      ".claude/agents",
      ...Object.values(slice.registry).map((agent) => agent.memoryDir),
    ];
    const before = trees.map((tree) => hashTree(slice.workspace, tree));
    await runFullSlice(slice);
    const after = trees.map((tree) => hashTree(slice.workspace, tree));
    expect(after).toEqual(before);
  });
});
