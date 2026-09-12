import { readFileSync } from "node:fs";

import { Hono } from "hono";
import { MissionStatusSchema, type MissionStatus, type Priority } from "@agentic-os/core";
import type { Database } from "@agentic-os/storage";

import { openMissionService, type MissionService } from "./mission-service.js";

const DASHBOARD_HTML = readFileSync(
  new URL("../www/index.html", import.meta.url),
  "utf-8",
);

const PRIORITIES: readonly Priority[] = ["critical", "high", "medium", "low"];

export interface CreateAppOptions {
  clock?: () => Date;
  /** Test seam — lets callers inject a MissionService bound to the same db. */
  service?: MissionService;
}

export function createApp(db: Database, options: CreateAppOptions = {}): Hono {
  const service = options.service ?? openMissionService(db, options.clock);
  const app = new Hono();

  app.onError((err, c) => {
    return c.json({ error: err instanceof Error ? err.message : String(err) }, 500);
  });

  // ── Dashboard ──────────────────────────────────────────────────────────
  app.get("/", (c) => c.html(DASHBOARD_HTML));

  // ── Missions ───────────────────────────────────────────────────────────
  app.get("/api/missions", async (c) => {
    const statusParam = c.req.query("status");
    let status: MissionStatus | undefined;
    if (statusParam) {
      const parsed = MissionStatusSchema.safeParse(statusParam);
      if (!parsed.success) {
        return c.json({ error: `invalid status '${statusParam}'` }, 400);
      }
      status = parsed.data;
    }
    return c.json(await service.list(status));
  });

  app.post("/api/missions", async (c) => {
    const body = await c.req.json().catch(() => null);
    if (!body) return c.json({ error: "invalid JSON body" }, 400);
    const title = typeof body.title === "string" ? body.title.trim() : "";
    const acceptanceCriteria = Array.isArray(body.acceptanceCriteria)
      ? body.acceptanceCriteria.filter((x: unknown): x is string => typeof x === "string")
      : [];
    if (!title) return c.json({ error: "title is required" }, 400);
    if (acceptanceCriteria.length === 0) {
      return c.json({ error: "acceptanceCriteria must be a non-empty array of strings" }, 400);
    }
    const priorityRaw = body.priority ?? "medium";
    const priority: Priority = PRIORITIES.includes(priorityRaw) ? priorityRaw : "medium";
    const mission = await service.create({
      title,
      description: typeof body.description === "string" ? body.description : undefined,
      priority,
      acceptanceCriteria,
    });
    return c.json(mission, 201);
  });

  app.get("/api/missions/:id", async (c) => {
    const mission = await service.get(c.req.param("id"));
    if (!mission) return c.json({ error: "mission not found" }, 404);
    return c.json(mission);
  });

  app.get("/api/missions/:id/plan", async (c) => {
    const id = c.req.param("id");
    const mission = await service.get(id);
    if (!mission) return c.json({ error: "mission not found" }, 404);
    return c.json(await service.getLatestPlan(id));
  });

  app.get("/api/missions/:id/history", async (c) => {
    const id = c.req.param("id");
    const mission = await service.get(id);
    if (!mission) return c.json({ error: "mission not found" }, 404);
    return c.json(await service.history(id));
  });

  app.post("/api/missions/:id/transition", async (c) => {
    const id = c.req.param("id");
    const body = await c.req.json().catch(() => null);
    if (!body) return c.json({ error: "invalid JSON body" }, 400);
    const parsed = MissionStatusSchema.safeParse(body.to);
    if (!parsed.success) {
      return c.json({ error: `invalid status '${String(body.to)}'` }, 400);
    }
    try {
      const mission = await service.transition(
        id,
        parsed.data,
        typeof body.reason === "string" ? body.reason : undefined,
      );
      return c.json(mission);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("not found")) return c.json({ error: msg }, 404);
      return c.json({ error: msg }, 400);
    }
  });

  // ── Approvals ──────────────────────────────────────────────────────────
  app.get("/api/approvals", async (c) => {
    const statusParam = c.req.query("status");
    const status =
      statusParam === "pending" || statusParam === "approved" || statusParam === "rejected"
        ? statusParam
        : undefined;
    return c.json(await service.listApprovals(status));
  });

  app.post("/api/approvals", async (c) => {
    const body = await c.req.json().catch(() => null);
    if (!body) return c.json({ error: "invalid JSON body" }, 400);
    const missionId = typeof body.missionId === "string" ? body.missionId : "";
    if (!missionId) return c.json({ error: "missionId is required" }, 400);
    const approval = await service.createApproval({
      missionId,
      capability: String(body.capability ?? ""),
      action: String(body.action ?? ""),
      reason: String(body.reason ?? ""),
      risk: String(body.risk ?? ""),
      runId: typeof body.runId === "string" ? body.runId : undefined,
    });
    return c.json(approval, 201);
  });

  app.post("/api/approvals/:id/resolve", async (c) => {
    const id = c.req.param("id");
    const body = await c.req.json().catch(() => null);
    if (!body) return c.json({ error: "invalid JSON body" }, 400);
    if (body.status !== "approved" && body.status !== "rejected") {
      return c.json({ error: `invalid resolution '${String(body.status)}'` }, 400);
    }
    try {
      const approval = await service.resolveApproval(id, body.status);
      return c.json(approval);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("not found")) return c.json({ error: msg }, 404);
      return c.json({ error: msg }, 400);
    }
  });

  // ── Transition matrix (for the dashboard's transition dropdown) ────────
  app.get("/api/transitions", (c) => c.json(service.transitionMatrix()));

  return app;
}
