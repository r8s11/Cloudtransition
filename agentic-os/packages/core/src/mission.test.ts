import { describe, it, expect } from "vitest";
import {
  createMission,
  transitionMission,
  canTransition,
  type Mission,
  type MissionStatus,
} from "@agentic-os/core";

// ── Fixed clock for deterministic tests ────────────────────────────────

function fixedClock(date: Date): () => Date {
  return () => date;
}

const T0 = new Date("2026-08-29T12:00:00.000Z");
const clock = fixedClock(T0);

// ── Test 1: createMission produces queued status, ISO timestamps, and copied acceptance criteria ──

describe("createMission", () => {
  it("creates a mission with queued status and ISO timestamps", () => {
    const mission = createMission(
      {
        id: "mission-1",
        title: "Deploy the API",
        acceptanceCriteria: ["API responds on port 8080", "Health endpoint returns 200"],
        priority: "high",
      },
      clock,
    );

    expect(mission.status).toBe("queued");
    expect(mission.id).toBe("mission-1");
    expect(mission.title).toBe("Deploy the API");
    expect(mission.priority).toBe("high");
    expect(mission.acceptanceCriteria).toEqual([
      "API responds on port 8080",
      "Health endpoint returns 200",
    ]);
    expect(mission.createdAt).toBe("2026-08-29T12:00:00.000Z");
    expect(mission.updatedAt).toBe("2026-08-29T12:00:00.000Z");
    expect(mission.startedAt).toBeUndefined();
    expect(mission.completedAt).toBeUndefined();
  });

  it("copies acceptance criteria (not a reference)", () => {
    const criteria = ["criteria one", "criteria two"];
    const mission = createMission(
      {
        id: "m2",
        title: "Test copy",
        acceptanceCriteria: criteria,
        priority: "medium",
      },
      clock,
    );

    criteria.push("should not appear");
    expect(mission.acceptanceCriteria).not.toContain("should not appear");
  });

  it("respects optional description", () => {
    const mission = createMission(
      {
        id: "m3",
        title: "With description",
        description: "A detailed description",
        acceptanceCriteria: ["one"],
        priority: "low",
      },
      clock,
    );

    expect(mission.description).toBe("A detailed description");
  });

  it("omits description when not provided", () => {
    const mission = createMission(
      {
        id: "m4",
        title: "No description",
        acceptanceCriteria: ["one"],
        priority: "low",
      },
      clock,
    );

    expect(mission.description).toBeUndefined();
  });
});

// ── Test 2: Legal transitions succeed ───────────────────────────────────

describe("transitionMission — legal transitions", () => {
  it("createMission returns queued status (direct from draft)", () => {
    const m = createMission(
      {
        id: "mt1",
        title: "Test",
        acceptanceCriteria: ["one"],
        priority: "medium",
      },
      clock,
    );
    // createMission starts at queued; this is the implicit draft→queued transition
    expect(m.status).toBe("queued");
    expect(m.createdAt).toBe("2026-08-29T12:00:00.000Z");
  });

  it("queued → running succeeds", () => {
    const m = createMission(
      {
        id: "mt2",
        title: "Test",
        acceptanceCriteria: ["one"],
        priority: "medium",
      },
      clock,
    );
    const result = transitionMission(m, "running", clock);
    expect(result.status).toBe("running");
    expect(result.startedAt).toBe("2026-08-29T12:00:00.000Z");
  });

  it("running → completed succeeds", () => {
    const m = createMission(
      {
        id: "mt3",
        title: "Test",
        acceptanceCriteria: ["one"],
        priority: "medium",
      },
      clock,
    );
    const running = transitionMission(m, "running", clock);
    const result = transitionMission(running, "completed", clock);
    expect(result.status).toBe("completed");
    expect(result.completedAt).toBe("2026-08-29T12:00:00.000Z");
  });

  it("running → awaiting_approval succeeds", () => {
    const m = createMission(
      {
        id: "mt4",
        title: "Test",
        acceptanceCriteria: ["one"],
        priority: "medium",
      },
      clock,
    );
    const running = transitionMission(m, "running", clock);
    const result = transitionMission(running, "awaiting_approval", clock);
    expect(result.status).toBe("awaiting_approval");
  });

  it("running → paused succeeds", () => {
    const m = createMission(
      {
        id: "mt5",
        title: "Test",
        acceptanceCriteria: ["one"],
        priority: "medium",
      },
      clock,
    );
    const running = transitionMission(m, "running", clock);
    const result = transitionMission(running, "paused", clock);
    expect(result.status).toBe("paused");
  });

  it("running → failed succeeds", () => {
    const m = createMission(
      {
        id: "mt6",
        title: "Test",
        acceptanceCriteria: ["one"],
        priority: "medium",
      },
      clock,
    );
    const running = transitionMission(m, "running", clock);
    const result = transitionMission(running, "failed", clock);
    expect(result.status).toBe("failed");
  });

  it("awaiting_approval → queued succeeds", () => {
    const m = createMission(
      {
        id: "mt7",
        title: "Test",
        acceptanceCriteria: ["one"],
        priority: "medium",
      },
      clock,
    );
    const running = transitionMission(m, "running", clock);
    const awaiting = transitionMission(running, "awaiting_approval", clock);
    const result = transitionMission(awaiting, "queued", clock);
    expect(result.status).toBe("queued");
  });

  it("paused → queued succeeds", () => {
    const m = createMission(
      {
        id: "mt8",
        title: "Test",
        acceptanceCriteria: ["one"],
        priority: "medium",
      },
      clock,
    );
    const running = transitionMission(m, "running", clock);
    const paused = transitionMission(running, "paused", clock);
    const result = transitionMission(paused, "queued", clock);
    expect(result.status).toBe("queued");
  });

  it("failed → queued succeeds", () => {
    const m = createMission(
      {
        id: "mt9",
        title: "Test",
        acceptanceCriteria: ["one"],
        priority: "medium",
      },
      clock,
    );
    const running = transitionMission(m, "running", clock);
    const failed = transitionMission(running, "failed", clock);
    const result = transitionMission(failed, "queued", clock);
    expect(result.status).toBe("queued");
  });

  it("queued → cancelled succeeds", () => {
    const m = createMission(
      {
        id: "mt10",
        title: "Test",
        acceptanceCriteria: ["one"],
        priority: "medium",
      },
      clock,
    );
    const result = transitionMission(m, "cancelled", clock);
    expect(result.status).toBe("cancelled");
  });

  it("draft → queued succeeds (manual draft mission)", () => {
    // Manually construct a draft mission to test the draft→queued transition
    const draftMission: Mission = {
      id: "mt11",
      title: "Draft test",
      description: undefined,
      status: "draft",
      priority: "medium",
      acceptanceCriteria: ["one"],
      createdAt: "2026-08-29T12:00:00.000Z",
      updatedAt: "2026-08-29T12:00:00.000Z",
    };
    const result = transitionMission(draftMission, "queued", clock);
    expect(result.status).toBe("queued");
  });

  it("draft → cancelled succeeds (manual draft mission)", () => {
    const draftMission: Mission = {
      id: "mt12",
      title: "Draft cancel test",
      description: undefined,
      status: "draft",
      priority: "medium",
      acceptanceCriteria: ["one"],
      createdAt: "2026-08-29T12:00:00.000Z",
      updatedAt: "2026-08-29T12:00:00.000Z",
    };
    const result = transitionMission(draftMission, "cancelled", clock);
    expect(result.status).toBe("cancelled");
  });
});

// ── Test 3: completed → running is rejected with "cannot transition" ──

describe("transitionMission — illegal transitions", () => {
  it("completed → running is rejected", () => {
    const m = createMission(
      {
        id: "illegal1",
        title: "Test",
        acceptanceCriteria: ["one"],
        priority: "medium",
      },
      clock,
    );
    const running = transitionMission(m, "running", clock);
    const completed = transitionMission(running, "completed", clock);

    expect(() => transitionMission(completed, "running", clock)).toThrowError(
      /cannot transition/,
    );
  });

  it("cancelled → running is rejected", () => {
    const m = createMission(
      {
        id: "illegal2",
        title: "Test",
        acceptanceCriteria: ["one"],
        priority: "medium",
      },
      clock,
    );
    const cancelled = transitionMission(m, "cancelled", clock);

    expect(() => transitionMission(cancelled, "running", clock)).toThrowError(
      /cannot transition/,
    );
  });

  it("completed → queued is rejected", () => {
    const m = createMission(
      {
        id: "illegal3",
        title: "Test",
        acceptanceCriteria: ["one"],
        priority: "medium",
      },
      clock,
    );
    const running = transitionMission(m, "running", clock);
    const completed = transitionMission(running, "completed", clock);

    expect(() => transitionMission(completed, "queued", clock)).toThrowError(
      /cannot transition/,
    );
  });

  it("running → draft is rejected", () => {
    const m = createMission(
      {
        id: "illegal4",
        title: "Test",
        acceptanceCriteria: ["one"],
        priority: "medium",
      },
      clock,
    );
    const running = transitionMission(m, "running", clock);

    expect(() => transitionMission(running, "draft", clock)).toThrowError(
      /cannot transition/,
    );
  });

  it("pending → running is rejected (pending not a valid status)", () => {
    // createMission always produces "queued", so "pending" isn't reachable
    // But validate via canTransition
    expect(canTransition("pending" as MissionStatus, "running")).toBe(false);
  });
});

// ── Test 4: canTransition utility ───────────────────────────────────────

describe("canTransition", () => {
  it("returns true for legal transitions", () => {
    expect(canTransition("draft", "queued")).toBe(true);
    expect(canTransition("queued", "running")).toBe(true);
    expect(canTransition("running", "completed")).toBe(true);
    expect(canTransition("running", "awaiting_approval")).toBe(true);
    expect(canTransition("running", "paused")).toBe(true);
    expect(canTransition("running", "failed")).toBe(true);
    expect(canTransition("awaiting_approval", "queued")).toBe(true);
    expect(canTransition("paused", "queued")).toBe(true);
    expect(canTransition("failed", "queued")).toBe(true);
    expect(canTransition("queued", "cancelled")).toBe(true);
  });

  it("returns false for illegal transitions", () => {
    expect(canTransition("completed", "running")).toBe(false);
    expect(canTransition("cancelled", "running")).toBe(false);
    expect(canTransition("completed", "queued")).toBe(false);
    expect(canTransition("running", "draft")).toBe(false);
    expect(canTransition("queued", "completed")).toBe(false);
    expect(canTransition("completed", "completed")).toBe(false);
  });
});
