import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createRequire } from "node:module";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createMission } from "@agentic-os/core";
import {
  Database,
  MIGRATIONS,
  SqliteMissionRepository,
  SqliteRuntimeRepository,
  type AgentRunRecord,
} from "./index.js";

const date = "2026-09-13T00:00:00.000Z";

describe("runtime persistence invariants", () => {
  let db: Database;
  let store: SqliteRuntimeRepository;
  let run: AgentRunRecord;
  beforeEach(() => {
    db = Database.memory();
    store = new SqliteRuntimeRepository(db);
    store.registerProject({
      id: "project",
      name: "Project",
      path: "/repo",
      createdAt: date,
    });
    run = {
      id: "run",
      projectId: "project",
      adapterId: "agent",
      prompt: "work",
      status: "starting",
      createdAt: date,
      startedAt: null,
      endedAt: null,
      error: null,
      pid: null,
      ownerId: "owner",
      missionId: null,
      planVersion: null,
      taskId: null,
      exitCode: null,
      signal: null,
      model: null,
      effort: null,
      inputTokens: null,
      outputTokens: null,
      costUsd: null,
    };
    store.createRun(run);
  });
  afterEach(() => db.close());
  it("rejects another owner's update without changing state or events", () => {
    expect(() =>
      store.updateRun({ ...run, ownerId: "impostor", status: "completed" }),
    ).toThrow();
    expect(store.getRun(run.id)?.status).toBe("starting");
    expect(store.listEvents(run.id).map((event) => event.data)).toEqual([
      "starting",
    ]);
  });
  it("rolls back the state when its event cannot be persisted", () => {
    db.exec(
      "CREATE TRIGGER reject_events BEFORE INSERT ON run_events BEGIN SELECT RAISE(ABORT, 'disk unavailable'); END",
    );
    expect(() => store.updateRun({ ...run, status: "running" })).toThrow(
      "disk unavailable",
    );
    expect(store.getRun(run.id)?.status).toBe("starting");
  });
  it("pages output without skipping or duplicating chunks and filters historical runs", () => {
    store.appendEvent(run.id, "stdout", "one");
    store.appendEvent(run.id, "stderr", "two");
    const first = store.listEvents(run.id, 0, 2);
    const second = store.listEvents(run.id, first[1]!.id, 2);
    expect([...first, ...second].map((event) => event.data)).toEqual([
      "starting",
      "one",
      "two",
    ]);
    expect(store.listRuns({ active: false })).toEqual([]);
    store.updateRun({
      ...run,
      status: "completed",
      endedAt: date,
      exitCode: 0,
    });
    expect(store.listRuns({ active: true })).toEqual([]);
    expect(store.listRuns({ active: false }).map((value) => value.id)).toEqual([
      "run",
    ]);
  });
  it("rejects dangling project and mission references", () => {
    expect(() =>
      store.createRun({ ...run, id: "other", projectId: "missing" }),
    ).toThrow();
    expect(() =>
      store.createRun({ ...run, id: "other", missionId: "missing" }),
    ).toThrow();
    expect(store.getRun("other")).toBeNull();
  });
});

it("upgrades an actual initial-schema database and preserves mission data on reopen", async () => {
  const directory = mkdtempSync(join(tmpdir(), "runtime-migration-"));
  const path = join(directory, "os.db");
  const ctor = createRequire(import.meta.url)("node:sqlite").DatabaseSync;
  const native = new ctor(path);
  const initial = MIGRATIONS[0]!;
  native.exec(initial.sql);
  native
    .prepare("INSERT INTO migrations(name,hash,applied_at) VALUES(?,?,?)")
    .run(initial.name, initial.hash, date);
  const old = new Database(native);
  await new SqliteMissionRepository(old).create(
    createMission(
      {
        id: "existing",
        title: "Preserved mission",
        priority: "low",
        acceptanceCriteria: ["persist"],
      },
      () => new Date(date),
    ),
  );
  old.close();
  try {
    const upgraded = Database.open(path);
    new SqliteRuntimeRepository(upgraded).registerProject({
      id: "project",
      name: "New project",
      path: "/repo",
      createdAt: date,
    });
    upgraded.close();
    const reopened = Database.open(path);
    expect(
      (await new SqliteMissionRepository(reopened).getById("existing"))?.title,
    ).toBe("Preserved mission");
    expect(
      new SqliteRuntimeRepository(reopened).getProject("project")?.path,
    ).toBe("/repo");
    reopened
      .prepare("UPDATE migrations SET hash = 'changed' WHERE name = ?")
      .run(initial.name);
    reopened.close();
    expect(() => Database.open(path)).toThrow(/changed/);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
