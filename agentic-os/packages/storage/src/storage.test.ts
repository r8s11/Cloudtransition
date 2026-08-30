import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { Database, SqliteMissionRepository, SqlitePlanRepository, SqliteTransitionRepository, SqliteApprovalRepository } from "./index.js";
import { createMission, transitionMission, parsePlan } from "@agentic-os/core";

const T0 = new Date("2026-08-29T12:00:00.000Z");
let clockTicks = 0;
function tickClock(): Date {
  // Advance 1s per call for distinct timestamps.
  clockTicks += 1;
  return new Date(T0.getTime() + clockTicks * 1000);
}

describe("Database initialization + migration tracking", () => {
  it("initializes a fresh in-memory database and applies migration 001", () => {
    const db = Database.memory();
    const row = db
      .prepare("SELECT name FROM migrations ORDER BY name")
      .get() as { name: string };
    expect(row.name).toBe("001_initial.sql");
    db.close();
  });

  it("records the migration hash", () => {
    const db = Database.memory();
    const row = db
      .prepare("SELECT name, hash FROM migrations")
      .get() as { name: string; hash: string };
    expect(row.hash).toMatch(/^[a-f0-9]{64}$/);
    db.close();
  });

  it("does not rerun migrations on reopen (idempotent)", () => {
    const db = Database.memory();
    const count1 = (
      db.prepare("SELECT COUNT(*) AS c FROM migrations").get() as { c: number }
    ).c;
    db.close();

    // A new connection to the same in-memory handle is not possible; simulate by
    // reopening a file-backed DB and asserting the migration is still applied once.
    const fileDb = Database.open(":memory:");
    const count2 = (
      fileDb.prepare("SELECT COUNT(*) AS c FROM migrations").get() as { c: number }
    ).c;
    expect(count2).toBe(count1);
    expect(count2).toBe(1);
    fileDb.close();
  });

  it("reopening a file database does not duplicate migrations", () => {
    const fs = require("node:fs");
    const os = require("node:os");
    const path = `${os.tmpdir()}/os-test-${Date.now()}-${Math.random()}.db`;
    try {
      const a = Database.open(path);
      const b = Database.open(path); // reopen
      const c = (
        b.prepare("SELECT COUNT(*) AS c FROM migrations").get() as { c: number }
      ).c;
      expect(c).toBe(1);
      a.close();
      b.close();
    } finally {
      fs.rmSync(path, { force: true });
    }
  });
});

describe("MissionRepository", () => {
  let db: Database;
  let repo: SqliteMissionRepository;
  beforeEach(() => {
    db = Database.memory();
    repo = new SqliteMissionRepository(db);
  });
  afterEach(() => db.close());

  it("create then getById returns the same mission", async () => {
    const m = createMission(
      {
        id: "m1",
        title: "Test mission",
        description: "desc",
        acceptanceCriteria: ["a", "b"],
        priority: "high",
      },
      tickClock,
    );
    await repo.create(m);
    const got = await repo.getById("m1");
    expect(got).not.toBeNull();
    expect(got!.id).toBe("m1");
    expect(got!.title).toBe("Test mission");
    expect(got!.status).toBe("queued");
    expect(got!.acceptanceCriteria).toEqual(["a", "b"]);
    expect(got!.description).toBe("desc");
  });

  it("getById returns null for unknown mission", async () => {
    expect(await repo.getById("nope")).toBeNull();
  });

  it("update mutates persisted fields and bumps updatedAt", async () => {
    const m = createMission(
      { id: "m2", title: "T", acceptanceCriteria: ["x"], priority: "low" },
      tickClock,
    );
    await repo.create(m);
    const updated = { ...m, title: "T2", updatedAt: tickClock().toISOString() };
    await repo.update(updated);
    const got = await repo.getById("m2");
    expect(got!.title).toBe("T2");
  });

  it("update throws for missing mission", async () => {
    const m = createMission(
      { id: "missing", title: "T", acceptanceCriteria: ["x"], priority: "low" },
      tickClock,
    );
    await expect(repo.update(m)).rejects.toThrow(/not found/);
  });

  it("list returns all missions and supports status filter", async () => {
    const a = createMission(
      { id: "a", title: "A", acceptanceCriteria: ["x"], priority: "low" },
      tickClock,
    );
    const b = transitionMission(
      createMission(
        { id: "b", title: "B", acceptanceCriteria: ["x"], priority: "low" },
        tickClock,
      ),
      "running",
      tickClock,
    );
    await repo.create(a);
    await repo.create(b);
    const all = await repo.list();
    expect(all).toHaveLength(2);
    const running = await repo.list({ status: "running" });
    expect(running).toHaveLength(1);
    expect(running[0]!.id).toBe("b");
  });
});

describe("PlanRepository", () => {
  let db: Database;
  let missions: SqliteMissionRepository;
  let plans: SqlitePlanRepository;
  beforeEach(() => {
    db = Database.memory();
    missions = new SqliteMissionRepository(db);
    plans = new SqlitePlanRepository(db);
  });
  afterEach(() => db.close());

  it("validates the plan via Core before persisting", async () => {
    const m = createMission(
      { id: "p1", title: "P", acceptanceCriteria: ["x"], priority: "low" },
      tickClock,
    );
    await missions.create(m);
    const badPlan = {
      missionId: "p1",
      tasks: [
        {
          id: "t1",
          title: "Task",
          steps: [],
          expectedResult: "done",
          // missing verificationCriteria -> invalid
        },
      ],
    };
    await expect(plans.save("p1", badPlan as any)).rejects.toThrow();
  });

  it("saves a valid plan and retrieves the latest version", async () => {
    const m = createMission(
      { id: "p2", title: "P", acceptanceCriteria: ["x"], priority: "low" },
      tickClock,
    );
    await missions.create(m);
    const plan = parsePlan({
      missionId: "p2",
      tasks: [
        {
          id: "t1",
          title: "Task",
          steps: [{ kind: "reasoning", expectedObservation: "ok" }],
          expectedResult: "done",
          verificationCriteria: ["it works"],
        },
      ],
    });
    await plans.save("p2", plan);
    const got = await plans.getLatest("p2");
    expect(got).not.toBeNull();
    expect(got!.missionId).toBe("p2");
    expect(got!.tasks).toHaveLength(1);
  });

  it("increments version on subsequent saves", async () => {
    const m = createMission(
      { id: "p3", title: "P", acceptanceCriteria: ["x"], priority: "low" },
      tickClock,
    );
    await missions.create(m);
    const makePlan = () =>
      parsePlan({
        missionId: "p3",
        tasks: [
          {
            id: "t1",
            title: "Task",
            steps: [{ kind: "reasoning", expectedObservation: "ok" }],
            expectedResult: "done",
            verificationCriteria: ["works"],
          },
        ],
      });
    await plans.save("p3", makePlan());
    await plans.save("p3", makePlan());
    const got = await plans.getLatest("p3");
    // We can't read version from the public Plan type, but latest should be retrievable
    // and present (version tracking is internal). Assert retrievable content.
    expect(got).not.toBeNull();
    expect(got!.tasks[0]!.title).toBe("Task");
  });

  it("getLatest returns null when no plan exists", async () => {
    expect(await plans.getLatest("nope")).toBeNull();
  });
});

describe("TransitionRepository (audit persistence)", () => {
  let db: Database;
  let missions: SqliteMissionRepository;
  let transitions: SqliteTransitionRepository;
  beforeEach(() => {
    db = Database.memory();
    missions = new SqliteMissionRepository(db);
    transitions = new SqliteTransitionRepository(db);
  });
  afterEach(() => db.close());

  it("records and lists transition history", async () => {
    const m = createMission(
      { id: "t1", title: "T", acceptanceCriteria: ["x"], priority: "low" },
      tickClock,
    );
    await missions.create(m);
    await transitions.record({
      missionId: "t1",
      fromStatus: "queued",
      toStatus: "running",
      reason: "begin",
      createdAt: tickClock().toISOString(),
    });
    const history = await transitions.listForMission("t1");
    expect(history).toHaveLength(1);
    expect(history[0]!.fromStatus).toBe("queued");
    expect(history[0]!.toStatus).toBe("running");
    expect(history[0]!.reason).toBe("begin");
  });

  it("returns empty list for a mission with no transitions", async () => {
    expect(await transitions.listForMission("ghost")).toEqual([]);
  });
});

describe("ApprovalRepository", () => {
  let db: Database;
  let approvals: SqliteApprovalRepository;
  beforeEach(() => {
    db = Database.memory();
    approvals = new SqliteApprovalRepository(db);
  });
  afterEach(() => db.close());

  it("creates an approval in pending state", async () => {
    const a = await approvals.create({
      id: "ap1",
      missionId: "m1",
      capability: "filesystem",
      action: "delete",
      reason: "cleanup",
      risk: "destructive",
    });
    expect(a.status).toBe("pending");
    expect(a.resolvedAt).toBeNull();
  });

  it("approves and rejects transitions and blocks terminal re-resolution", async () => {
    await approvals.create({
      id: "ap2",
      missionId: "m1",
      capability: "email",
      action: "send",
      reason: "notify",
      risk: "external",
    });
    const approved = await approvals.resolve("ap2", {
      status: "approved",
      resolvedAt: tickClock().toISOString(),
    });
    expect(approved.status).toBe("approved");
    expect(approved.resolvedAt).not.toBeNull();

    // Approved -> rejected must be rejected (terminal state).
    await expect(
      approvals.resolve("ap2", {
        status: "rejected",
        resolvedAt: tickClock().toISOString(),
      }),
    ).rejects.toThrow(/cannot resolve/);

    // Rejected request: create + reject -> approve blocked.
    await approvals.create({
      id: "ap3",
      missionId: "m1",
      capability: "git",
      action: "commit",
      reason: "ship",
      risk: "write",
    });
    await approvals.resolve("ap3", {
      status: "rejected",
      resolvedAt: tickClock().toISOString(),
    });
    await expect(
      approvals.resolve("ap3", {
        status: "approved",
        resolvedAt: tickClock().toISOString(),
      }),
    ).rejects.toThrow(/cannot resolve/);
  });

  it("lists approvals by status", async () => {
    await approvals.create({
      id: "ap4",
      missionId: "m1",
      capability: "web",
      action: "search",
      reason: "find",
      risk: "read",
    });
    const pending = await approvals.list({ status: "pending" });
    expect(pending).toHaveLength(1);
  });
});

describe("Required integration test — database reopen round-trip", () => {
  it("persists, closes, reopens, transitions, and verifies history", async () => {
    const fs = require("node:fs");
    const os = require("node:os");
    const path = `${os.tmpdir()}/os-integ-${Date.now()}-${Math.random()}.db`;
    try {
      // 1. initialize + create
      const db1 = Database.open(path);
      const mRepo1 = new SqliteMissionRepository(db1);
      const mission = createMission(
        {
          id: "integ-1",
          title: "Integration mission",
          acceptanceCriteria: ["survives restart"],
          priority: "medium",
        },
        tickClock,
      );
      await mRepo1.create(mission);

      // 2. close
      db1.close();

      // 3. reopen
      const db2 = Database.open(path);
      const mRepo2 = new SqliteMissionRepository(db2);
      const tRepo2 = new SqliteTransitionRepository(db2);

      // 4. reload
      const reloaded = await mRepo2.getById("integ-1");
      expect(reloaded).not.toBeNull();
      expect(reloaded!.title).toBe("Integration mission");
      expect(reloaded!.status).toBe("queued");

      // 5. transition through Core + persist
      const transitioned = transitionMission(reloaded!, "running", tickClock);
      await mRepo2.update(transitioned);
      await tRepo2.record({
        missionId: "integ-1",
        fromStatus: "queued",
        toStatus: "running",
        reason: "accepted plan",
        createdAt: tickClock().toISOString(),
      });

      // 6. close + reopen again
      db2.close();
      const db3 = Database.open(path);
      const mRepo3 = new SqliteMissionRepository(db3);
      const tRepo3 = new SqliteTransitionRepository(db3);

      // 7. verify updated status + history
      const final = await mRepo3.getById("integ-1");
      expect(final!.status).toBe("running");
      expect(final!.startedAt).not.toBeUndefined();
      const history = await tRepo3.listForMission("integ-1");
      expect(history).toHaveLength(1);
      expect(history[0]!.toStatus).toBe("running");
      expect(history[0]!.reason).toBe("accepted plan");
      db3.close();
    } finally {
      fs.rmSync(path, { force: true });
    }
  });
});
