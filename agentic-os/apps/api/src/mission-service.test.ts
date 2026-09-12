import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { Database } from "@agentic-os/storage";
import { openMissionService, MissionService } from "./mission-service.js";

const T0 = new Date("2026-08-29T12:00:00.000Z");
let ticks = 0;
function tickClock(): Date {
  ticks += 1;
  return new Date(T0.getTime() + ticks * 1000);
}

describe("MissionService", () => {
  let db: Database;
  let svc: MissionService;
  beforeEach(() => {
    ticks = 0;
    db = Database.memory();
    svc = openMissionService(db, tickClock);
  });
  afterEach(() => db.close());

  it("creates a mission and persists it (starts queued)", async () => {
    const m = await svc.create({
      title: "Improve event search",
      description: "Add searchable event filtering",
      acceptanceCriteria: ["Users can search events by title"],
      priority: "high",
    });
    expect(m.status).toBe("queued");
    expect(m.id).toBeTruthy();
    const got = await svc.get(m.id);
    expect(got?.title).toBe("Improve event search");
  });

  it("lists missions, optionally filtered by status", async () => {
    await svc.create({ title: "A", acceptanceCriteria: ["x"], priority: "low" });
    const b = await svc.create({ title: "B", acceptanceCriteria: ["x"], priority: "low" });
    await svc.transition(b.id, "running", "kickoff");
    const all = await svc.list();
    expect(all).toHaveLength(2);
    const running = await svc.list("running");
    expect(running).toHaveLength(1);
    expect(running[0]!.id).toBe(b.id);
  });

  it("returns null for an unknown mission", async () => {
    expect(await svc.get("ghost")).toBeNull();
  });

  it("getLatestPlan returns null when no plan exists", async () => {
    const m = await svc.create({ title: "P", acceptanceCriteria: ["x"], priority: "low" });
    expect(await svc.getLatestPlan(m.id)).toBeNull();
  });

  it("transitions a mission through Core, records history, and exposes the matrix", async () => {
    const m = await svc.create({ title: "T", acceptanceCriteria: ["x"], priority: "low" });
    const updated = await svc.transition(m.id, "running", "Plan accepted");
    expect(updated.status).toBe("running");
    const history = await svc.history(m.id);
    expect(history).toHaveLength(1);
    expect(history[0]!.toStatus).toBe("running");
    expect(history[0]!.reason).toBe("Plan accepted");
    expect(svc.transitionMatrix().queued).toEqual(expect.arrayContaining(["running", "cancelled"]));
    expect(svc.transitionMatrix().completed).toEqual([]);
  });

  it("rejects illegal transitions without mutating persistence", async () => {
    const m = await svc.create({ title: "Illegal", acceptanceCriteria: ["x"], priority: "low" });
    await expect(svc.transition(m.id, "completed")).rejects.toThrow(/cannot transition/);
    const got = await svc.get(m.id);
    expect(got!.status).toBe("queued");
    expect(await svc.history(m.id)).toHaveLength(0);
  });

  it("throws on transition of an unknown mission", async () => {
    await expect(svc.transition("ghost", "running")).rejects.toThrow(/not found/);
  });

  it("creates, lists, and resolves approvals; blocks terminal re-resolution", async () => {
    const m = await svc.create({ title: "Approve me", acceptanceCriteria: ["x"], priority: "high" });
    const a = await svc.createApproval({
      missionId: m.id,
      capability: "filesystem",
      action: "delete",
      reason: "cleanup tmp",
      risk: "destructive",
    });
    expect(a.status).toBe("pending");
    const pending = await svc.listApprovals("pending");
    expect(pending).toHaveLength(1);
    const resolved = await svc.resolveApproval(a.id, "approved");
    expect(resolved.status).toBe("approved");
    await expect(svc.resolveApproval(a.id, "rejected")).rejects.toThrow(/cannot resolve/);
  });
});
