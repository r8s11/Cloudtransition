import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { Database } from "@agentic-os/storage";
import { createApp } from "./index.js";

describe("createApp — Mission Control HTTP API", () => {
  let db: Database;
  let app: ReturnType<typeof createApp>;
  beforeEach(() => {
    db = Database.memory();
    app = createApp(db);
  });
  afterEach(() => db.close());

  async function post(path: string, body: unknown) {
    return app.request(path, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  it("serves the dashboard HTML at /", async () => {
    const res = await app.request("/");
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toContain("text/html");
    const html = await res.text();
    expect(html).toContain("Mission Control");
  });

  it("starts with an empty mission list", async () => {
    const res = await app.request("/api/missions");
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual([]);
  });

  it("creates a mission and lists it", async () => {
    const res = await post("/api/missions", {
      title: "Improve event search",
      description: "Add searchable event filtering",
      priority: "high",
      acceptanceCriteria: ["Users can search events by title"],
    });
    expect(res.status).toBe(201);
    const m = (await res.json()) as { title: string; status: string };
    expect(m.title).toBe("Improve event search");
    expect(m.status).toBe("queued");

    const list = (await (await app.request("/api/missions")).json()) as unknown[];
    expect(list).toHaveLength(1);
  });

  it("rejects a create with missing title or acceptance criteria", async () => {
    expect((await post("/api/missions", { acceptanceCriteria: [] })).status).toBe(400);
    expect(
      (await post("/api/missions", { title: "X", acceptanceCriteria: [] })).status,
    ).toBe(400);
  });

  it("returns 404 for an unknown mission", async () => {
    expect((await app.request("/api/missions/ghost")).status).toBe(404);
  });

  it("transitions legally, and rejects illegal transitions without mutation", async () => {
    const created = (await (await post("/api/missions", {
      title: "Transitionable",
      acceptanceCriteria: ["x"],
      priority: "low",
    })).json()) as { id: string };

    const ok = await post(`/api/missions/${created.id}/transition`, { to: "running", reason: "go" });
    expect(ok.status).toBe(200);
    expect((await ok.json() as { status: string }).status).toBe("running");

    const bad = await post(`/api/missions/${created.id}/transition`, { to: "queued" });
    expect(bad.status).toBe(400);

    const history = (await (await app.request(`/api/missions/${created.id}/history`)).json()) as { toStatus: string }[];
    expect(history).toHaveLength(1);
    expect(history[0]!.toStatus).toBe("running");

    const miss = await post("/api/missions/ghost/transition", { to: "running" });
    expect(miss.status).toBe(404);
  });

  it("returns null plan for a mission without one", async () => {
    const created = (await (await post("/api/missions", {
      title: "Planned",
      acceptanceCriteria: ["x"],
      priority: "low",
    })).json()) as { id: string };
    const planRes = await app.request(`/api/missions/${created.id}/plan`);
    expect(planRes.status).toBe(200);
    expect(await planRes.json()).toBeNull();
  });

  it("creates and resolves approvals; blocks terminal re-resolution; 404s unknown", async () => {
    const created = (await (await post("/api/missions", {
      title: "Approve",
      acceptanceCriteria: ["x"],
      priority: "high",
    })).json()) as { id: string };

    const makeRes = await post("/api/approvals", {
      missionId: created.id,
      capability: "filesystem",
      action: "delete",
      reason: "cleanup",
      risk: "destructive",
    });
    expect(makeRes.status).toBe(201);
    const approval = (await makeRes.json()) as { id: string; status: string };

    const pending = (await (await app.request("/api/approvals?status=pending")).json()) as unknown[];
    expect(pending).toHaveLength(1);

    const approved = await post(`/api/approvals/${approval.id}/resolve`, { status: "approved" });
    expect(approved.status).toBe(200);
    expect((await approved.json() as { status: string }).status).toBe("approved");

    const again = await post(`/api/approvals/${approval.id}/resolve`, { status: "rejected" });
    expect(again.status).toBe(400);

    expect(
      (await post("/api/approvals/ghost/resolve", { status: "approved" })).status,
    ).toBe(404);
  });

  it("rejects invalid approval creation or resolution bodies", async () => {
    expect((await post("/api/approvals", { capability: "x" })).status).toBe(400);
    expect(
      (await post("/api/approvals/whatever/resolve", { status: "banana" })).status,
    ).toBe(400);
  });

  it("exposes the Core transition matrix", async () => {
    const matrix = (await (await app.request("/api/transitions")).json()) as Record<string, string[]>;
    expect(matrix.queued).toEqual(expect.arrayContaining(["running", "cancelled"]));
    expect(matrix.completed).toEqual([]);
  });
});
