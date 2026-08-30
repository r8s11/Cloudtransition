import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { Database, SqliteMissionRepository, SqlitePlanRepository, SqliteTransitionRepository } from "@agentic-os/storage";
import { MissionCli } from "./mission-cli.js";
import { formatMissionLine, formatMissionDetail } from "./format.js";
import { createMission, transitionMission } from "@agentic-os/core";

const T0 = new Date("2026-08-29T12:00:00.000Z");
let n = 0;
function clock(): Date {
  n += 1;
  return new Date(T0.getTime() + n * 1000);
}

describe("MissionCli — create / list / show / transition", () => {
  let db: Database;
  let cli: MissionCli;
  beforeEach(() => {
    db = Database.memory();
    cli = new MissionCli(
      new SqliteMissionRepository(db),
      new SqlitePlanRepository(db),
      new SqliteTransitionRepository(db),
      clock,
    );
  });
  afterEach(() => db.close());

  it("creates a mission and persists it (starts queued)", async () => {
    const m = await cli.create({
      id: "c1",
      title: "Improve event search",
      description: "Add searchable event filtering",
      acceptanceCriteria: ["Users can search events by title"],
      priority: "high",
    });
    expect(m.status).toBe("queued");
    const got = await cli.get("c1");
    expect(got).not.toBeNull();
    expect(got!.title).toBe("Improve event search");
  });

  it("lists missions", async () => {
    await cli.create({
      id: "l1",
      title: "A",
      acceptanceCriteria: ["x"],
      priority: "low",
    });
    await cli.create({
      id: "l2",
      title: "B",
      acceptanceCriteria: ["x"],
      priority: "low",
    });
    const all = await cli.list();
    expect(all).toHaveLength(2);
  });

  it("shows a mission (getById)", async () => {
    await cli.create({
      id: "s1",
      title: "Shown",
      acceptanceCriteria: ["x"],
      priority: "medium",
    });
    const got = await cli.get("s1");
    expect(got!.title).toBe("Shown");
  });

  it("transitions a mission through Core and records history", async () => {
    await cli.create({
      id: "tr1",
      title: "Transitionable",
      acceptanceCriteria: ["x"],
      priority: "low",
    });
    const updated = await cli.transition("tr1", "running", "Plan accepted");
    expect(updated.status).toBe("running");
    const history = await cli.history("tr1");
    expect(history).toHaveLength(1);
    expect(history[0]!.toStatus).toBe("running");
    expect(history[0]!.reason).toBe("Plan accepted");
  });

  it("rejects illegal transitions without mutating persistence", async () => {
    await cli.create({
      id: "il1",
      title: "Illegal",
      acceptanceCriteria: ["x"],
      priority: "low",
    });
    // queued -> completed is illegal in the Core matrix.
    await expect(cli.transition("il1", "completed")).rejects.toThrow(
      /cannot transition/,
    );
    const got = await cli.get("il1");
    expect(got!.status).toBe("queued"); // unchanged
    const history = await cli.history("il1");
    expect(history).toHaveLength(0); // no audit written
  });

  it("transition on unknown mission throws", async () => {
    await expect(cli.transition("ghost", "running")).rejects.toThrow(/not found/);
  });
});

describe("format helpers", () => {
  it("formatMissionLine includes id, status, title", () => {
    const m = createMission(
      { id: "f1", title: "F", acceptanceCriteria: ["x"], priority: "low" },
      clock,
    );
    const line = formatMissionLine(m);
    expect(line).toContain("f1");
    expect(line).toContain("queued");
    expect(line).toContain("F");
  });

  it("formatMissionDetail lists acceptance criteria", () => {
    const m = createMission(
      {
        id: "f2",
        title: "F2",
        description: "d",
        acceptanceCriteria: ["first", "second"],
        priority: "low",
      },
      clock,
    );
    const detail = formatMissionDetail(m);
    expect(detail).toContain("first");
    expect(detail).toContain("second");
    expect(detail).toContain("d");
  });

  it("formatMissionDetail reflects transitioned status", () => {
    const m = transitionMission(
      createMission(
        { id: "f3", title: "F3", acceptanceCriteria: ["x"], priority: "low" },
        clock,
      ),
      "running",
      clock,
    );
    expect(formatMissionDetail(m)).toContain("running");
  });
});
