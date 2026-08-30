import { describe, it, expect } from "vitest";
import { parsePlan } from "@agentic-os/core";

// ── Test 5: parsePlan rejects a task missing verification criteria ─────

describe("parsePlan — validation", () => {
  it("rejects a task missing verification criteria", () => {
    const input = {
      missionId: "m1",
      tasks: [
        {
          id: "t1",
          title: "Bad task",
          steps: [],
          expectedResult: "Do something",
          // verificationCriteria is missing — should be caught by Zod
        },
      ],
    };

    expect(() => parsePlan(input)).toThrow();
  });

  it("rejects a task with empty verification criteria array", () => {
    const input = {
      missionId: "m2",
      tasks: [
        {
          id: "t2",
          title: "Empty criteria",
          steps: [{ kind: "reasoning", expectedObservation: "observed" }],
          expectedResult: "Do something",
          verificationCriteria: [],
        },
      ],
    };

    expect(() => parsePlan(input)).toThrow();
  });

  it("rejects a plan with no tasks", () => {
    const input = {
      missionId: "m3",
      tasks: [],
    };

    expect(() => parsePlan(input)).toThrowError(/at least one task/i);
  });

  it("rejects a missionId that is empty", () => {
    const input = {
      missionId: "",
      tasks: [
        {
          id: "t3",
          title: "Task",
          steps: [],
          expectedResult: "Result",
          verificationCriteria: ["c1"],
        },
      ],
    };

    expect(() => parsePlan(input)).toThrowError(/missionId/i);
  });
});

// ── Test 6: parsePlan rejects a step missing expected observation ──────

describe("parsePlan — step validation", () => {
  it("rejects a connector_call step missing expectedObservation", () => {
    const input = {
      missionId: "m4",
      tasks: [
        {
          id: "t4",
          title: "Task with bad step",
          steps: [
            {
              kind: "connector_call",
              connector: "github",
              action: "list_issues",
              // expectedObservation missing
            } as never,
          ],
          expectedResult: "List issues",
          verificationCriteria: ["issues listed"],
        },
      ],
    };

    expect(() => parsePlan(input)).toThrowError(/expectedObservation/i);
  });

  it("rejects a memory_write step missing expectedObservation", () => {
    const input = {
      missionId: "m5",
      tasks: [
        {
          id: "t5",
          title: "Task with bad memory step",
          steps: [
            {
              kind: "memory_write",
              partition: "work",
              // expectedObservation missing
            } as never,
          ],
          expectedResult: "Write memory",
          verificationCriteria: ["memory written"],
        },
      ],
    };

    expect(() => parsePlan(input)).toThrowError(/expectedObservation/i);
  });

  it("rejects a reasoning step missing expectedObservation", () => {
    const input = {
      missionId: "m6",
      tasks: [
        {
          id: "t6",
          title: "Task with bad reasoning step",
          steps: [
            {
              kind: "reasoning",
              // expectedObservation missing
            } as never,
          ],
          expectedResult: "Reason",
          verificationCriteria: ["reasoning done"],
        },
      ],
    };

    expect(() => parsePlan(input)).toThrowError(/expectedObservation/i);
  });
});

// ── Test 7: parsePlan accepts one valid connector_call step ───────────

describe("parsePlan — valid input", () => {
  it("accepts a plan with one valid connector_call step", () => {
    const plan = parsePlan({
      missionId: "m7",
      tasks: [
        {
          id: "t7",
          title: "Gather issues",
          description: "Fetch open issues from GitHub",
          steps: [
            {
              kind: "connector_call",
              connector: "github",
              action: "list_issues",
              expectedObservation: "A list of open issues with titles and labels",
            },
          ],
          expectedResult: "A list of open issues",
          verificationCriteria: ["issues returned", "at least one issue found"],
        },
      ],
    });

    expect(plan.missionId).toBe("m7");
    expect(plan.tasks).toHaveLength(1);
    const task = plan.tasks[0]!;
    expect(task.id).toBe("t7");
    expect(task.steps).toHaveLength(1);
    const step0 = task.steps[0]!;
    if (step0.kind !== "connector_call") {
      throw new Error("expected connector_call step");
    }
    expect(step0.connector).toBe("github");
    expect(step0.action).toBe("list_issues");
    expect(step0.expectedObservation).toBe(
      "A list of open issues with titles and labels",
    );
    expect(task.verificationCriteria).toEqual([
      "issues returned",
      "at least one issue found",
    ]);
  });

  it("accepts a plan with a memory_write step", () => {
    const plan = parsePlan({
      missionId: "m8",
      tasks: [
        {
          id: "t8",
          title: "Write to memory",
          steps: [
            {
              kind: "memory_write",
              partition: "personal",
              expectedObservation: "Memory entry created in personal partition",
            },
          ],
          expectedResult: "Memory written",
          verificationCriteria: ["memory entry exists"],
        },
      ],
    });

    const task = plan.tasks[0]!;
    const step0 = task.steps[0]!;
    if (step0.kind !== "memory_write") {
      throw new Error("expected memory_write step");
    }
    expect(step0.kind).toBe("memory_write");
    expect(step0.partition).toBe("personal");
  });

  it("accepts a plan with a reasoning step", () => {
    const plan = parsePlan({
      missionId: "m9",
      tasks: [
        {
          id: "t9",
          title: "Reason about data",
          steps: [
            {
              kind: "reasoning",
              expectedObservation: "A reasoned conclusion based on the data",
            },
          ],
          expectedResult: "Conclusion reached",
          verificationCriteria: ["conclusion is non-empty"],
        },
      ],
    });

    const task = plan.tasks[0]!;
    const step0 = task.steps[0]!;
    if (step0.kind !== "reasoning") {
      throw new Error("expected reasoning step");
    }
    expect(step0.kind).toBe("reasoning");
    expect(step0.expectedObservation).toBe(
      "A reasoned conclusion based on the data",
    );
  });

  it("accepts a multi-task plan", () => {
    const plan = parsePlan({
      missionId: "m10",
      tasks: [
        {
          id: "t10a",
          title: "First task",
          steps: [
            {
              kind: "reasoning",
              expectedObservation: "first result",
            },
          ],
          expectedResult: "First result",
          verificationCriteria: ["first verified"],
        },
        {
          id: "t10b",
          title: "Second task",
          steps: [
            {
              kind: "connector_call",
              connector: "slack",
              action: "send_message",
              expectedObservation: "Message delivered",
            },
          ],
          expectedResult: "Message sent",
          verificationCriteria: ["message delivered"],
        },
      ],
    });

    expect(plan.tasks).toHaveLength(2);
    expect(plan.tasks[0]!.id).toBe("t10a");
    expect(plan.tasks[1]!.id).toBe("t10b");
  });

  it("preserves step order", () => {
    const plan = parsePlan({
      missionId: "m11",
      tasks: [
        {
          id: "t11",
          title: "Ordered steps",
          steps: [
            { kind: "reasoning", expectedObservation: "step 1" },
            { kind: "connector_call", connector: "api", action: "fetch", expectedObservation: "step 2" },
            { kind: "memory_write", partition: "work", expectedObservation: "step 3" },
          ],
          expectedResult: "All done",
          verificationCriteria: ["all steps executed"],
        },
      ],
    });

    expect(plan.tasks[0]!.steps).toHaveLength(3);
    const steps = plan.tasks[0]!.steps;
    expect(steps[0]!.kind).toBe("reasoning");
    if (steps[1]!.kind !== "connector_call") throw new Error("expected connector_call");
    expect(steps[1]!.kind).toBe("connector_call");
    if (steps[2]!.kind !== "memory_write") throw new Error("expected memory_write");
    expect(steps[2]!.kind).toBe("memory_write");
  });
});
