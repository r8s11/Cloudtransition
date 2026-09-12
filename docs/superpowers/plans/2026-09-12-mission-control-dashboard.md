# Agentic OS Mission Control Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local, live, widget-based mission control dashboard to `agentic-os` — a Hono HTTP server over `apps/api` serving a static command-center page that can view and act on missions and approvals.

**Architecture:** `apps/api/src/mission-service.ts` becomes the only component the HTTP layer talks to, composing the existing Core + storage repositories exactly like `MissionCli` does. `apps/api/src/index.ts` exposes `createApp(db)` — a pure Hono app (testable without a port) — and `apps/api/src/server.ts` bootstraps it against the config's SQLite path on `localhost:8787`. The dashboard is a single dependency-free `apps/api/www/index.html` served at `/`.

**Tech Stack:** TypeScript (NodeNext ESM), Hono `^4.7.0`, `@hono/node-server` `^1.14.0`, `node:sqlite`, Vitest. Node >= 22.17 (workspace already requires it; local Node is v26.8.1).

**Spec:** `docs/superpowers/specs/2026-09-12-agentic-os-mission-control-dashboard-design.md`

## Global Constraints

- All new code lives in `apps/api` only. **No changes** to `packages/core`, `packages/storage`, `packages/policy`, or `packages/config`.
- Never re-implement transition rules or SQL in the API/frontend — always call Core functions and storage repositories.
- Local only: no external network calls, no AI/provider logic, no auth (localhost server).
- Error responses are JSON `{ error: string }` with the appropriate HTTP status.
- Existing suite must stay green: `npm test`, `npm run check`, `npm run build` from `agentic-os/`.
- Follow the repo's TS style: `import type` for types, `.js` extensions on relative TS imports, strict mode (tsconfig already sets `noUnusedLocals`/`noUnusedParameters`).
- Node executes `.ts` directly via type stripping (the CLI already runs `node apps/cli/src/cli.ts`); add `"type": "module"` to `apps/api/package.json` and run the server with `node src/server.ts`.

---

### Task 1: Workspace setup — deps, install, api scripts

**Files:**
- Modify: `apps/api/package.json`
- Verify: `package-lock.json`, `node_modules`

**Interfaces:**
- Consumes: nothing new (base workspace state).
- Produces: `apps/api/package.json` declaring workspace deps `@agentic-os/core`, `@agentic-os/storage`, `@agentic-os/config` plus existing `hono` + `@hono/node-server`; `type: "module"`; scripts `test`, `dev`, `start`. `node_modules` populated so `hono` resolves (currently not installed).

- [ ] **Step 1: Update `apps/api/package.json`**

Current content:

```json
{
  "name": "@agentic-os/api",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "test": "vitest run"
  },
  "dependencies": {
    "hono": "^4.7.0",
    "@hono/node-server": "^1.14.0"
  },
  "devDependencies": {
    "typescript": "^5.8.0",
    "vitest": "^2.1.0",
    "@types/node": "^22.0.0"
  }
}
```

Replace with (mirrors the `"type": "module"` + workspace-dep pattern already used by `packages/storage/package.json`):

```json
{
  "name": "@agentic-os/api",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "main": "./src/index.ts",
  "types": "./src/index.ts",
  "scripts": {
    "test": "vitest run",
    "dev": "node src/server.ts",
    "start": "node src/server.ts"
  },
  "dependencies": {
    "@agentic-os/core": "*",
    "@agentic-os/storage": "*",
    "@agentic-os/config": "*",
    "hono": "^4.7.0",
    "@hono/node-server": "^1.14.0"
  },
  "devDependencies": {
    "typescript": "^5.8.0",
    "vitest": "^2.1.0",
    "@types/node": "^22.0.0"
  }
}
```

- [ ] **Step 2: Install workspace dependencies**

Run (from `agentic-os/`):

```bash
npm install
```

Expected: resolves `hono`, `@hono/node-server`, and the workspace packages. Confirm with:

```bash
ls node_modules/hono/package.json
```

- [ ] **Step 3: Verify the baseline still passes**

Run (from `agentic-os/`):

```bash
npm test
```

Expected: all existing tests pass.

- [ ] **Step 4: Commit**

```bash
git add apps/api/package.json package-lock.json
git commit -m "chore(api): Wire workspace deps and scripts for mission control"
```

Note: if `package-lock.json` gains no staged changes (e.g. lock already current), add only `apps/api/package.json`.

---

### Task 2: `MissionService` facade + unit tests

**Files:**
- Create: `apps/api/src/mission-service.ts`
- Test: `apps/api/src/mission-service.test.ts`

**Interfaces:**
- Consumes:
  - `@agentic-os/core`: `createMission`, `transitionMission`, `canTransition`, `MissionStatusSchema`, and types `Mission`, `MissionStatus`, `Priority`, `CreateMissionInput`.
  - `@agentic-os/storage`: `Database`, `SqliteMissionRepository`, `SqlitePlanRepository`, `SqliteTransitionRepository`, `SqliteApprovalRepository`, and types `MissionRepository`, `PlanRepository`, `TransitionRepository`, `ApprovalRepository`, `CreateApprovalInput`, `ApprovalRecord`, `MissionTransitionRecord`.
- Produces:
  - `interface CreateMissionPayload { title: string; description?: string; priority?: Priority; acceptanceCriteria: string[]; id?: string }`
  - `interface CreateApprovalPayload { missionId: string; capability: string; action: string; reason: string; risk: string; runId?: string; id?: string }`
  - `class MissionService` with:
    - `list(status?: MissionStatus): Promise<Mission[]>`
    - `get(id: string): Promise<Mission | null>`
    - `getLatestPlan(id: string): Promise<Plan | null>` (Plan re-exported from storage)
    - `history(id: string): Promise<MissionTransitionRecord[]>`
    - `async create(input: CreateMissionPayload): Promise<Mission>`
    - `async transition(id: string, to: MissionStatus, reason?: string): Promise<Mission>`
    - `listApprovals(status?: ApprovalRecord["status"]): Promise<ApprovalRecord[]>`
    - `async createApproval(input: CreateApprovalPayload): Promise<ApprovalRecord>`
    - `async resolveApproval(id: string, status: "approved" | "rejected"): Promise<ApprovalRecord>`
    - `transitionMatrix(): Record<MissionStatus, MissionStatus[]>`
  - `function openMissionService(db: Database, clock?: () => Date): MissionService`

- [ ] **Step 1: Write the failing test**

Create `apps/api/src/mission-service.test.ts`:

```ts
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `agentic-os/`):

```bash
npx vitest run apps/api/src/mission-service.test.ts
```

Expected: FAIL — module `./mission-service.js` cannot be resolved.

- [ ] **Step 3: Write the implementation**

Create `apps/api/src/mission-service.ts`:

```ts
import { randomUUID } from "node:crypto";

import {
  createMission,
  transitionMission,
  canTransition,
  type Mission,
  type MissionStatus,
  type Priority,
  type CreateMissionInput,
} from "@agentic-os/core";
import {
  type MissionRepository,
  type PlanRepository,
  type TransitionRepository,
  type ApprovalRepository,
  type CreateApprovalInput,
  type ApprovalRecord,
  type MissionTransitionRecord,
  type Database,
  SqliteMissionRepository,
  SqlitePlanRepository,
  SqliteTransitionRepository,
  SqliteApprovalRepository,
} from "@agentic-os/storage";

const ALL_STATUSES: readonly MissionStatus[] = [
  "draft",
  "queued",
  "running",
  "awaiting_approval",
  "paused",
  "failed",
  "completed",
  "cancelled",
];

export interface CreateMissionPayload {
  title: string;
  description?: string;
  priority?: Priority;
  acceptanceCriteria: string[];
  id?: string;
}

export interface CreateApprovalPayload {
  missionId: string;
  capability: string;
  action: string;
  reason: string;
  risk: string;
  runId?: string;
  id?: string;
}

/**
 * The only component the HTTP layer talks to. Composes Core for rules and
 * storage for persistence — never re-implements transitions or writes SQL.
 */
export class MissionService {
  constructor(
    private readonly missions: MissionRepository,
    private readonly plans: PlanRepository,
    private readonly transitions: TransitionRepository,
    private readonly approvals: ApprovalRepository,
    private readonly clock: () => Date = () => new Date(),
  ) {}

  list(status?: MissionStatus): Promise<Mission[]> {
    return this.missions.list(status ? { status } : undefined);
  }

  get(id: string): Promise<Mission | null> {
    return this.missions.getById(id);
  }

  getLatestPlan(id: string) {
    return this.plans.getLatest(id);
  }

  history(id: string): Promise<MissionTransitionRecord[]> {
    return this.transitions.listForMission(id);
  }

  async create(input: CreateMissionPayload): Promise<Mission> {
    const missionInput: CreateMissionInput = {
      id: input.id ?? randomUUID(),
      title: input.title,
      description: input.description,
      acceptanceCriteria: input.acceptanceCriteria,
      priority: input.priority ?? "medium",
    };
    const mission = createMission(missionInput, this.clock);
    await this.missions.create(mission);
    return mission;
  }

  async transition(id: string, to: MissionStatus, reason?: string): Promise<Mission> {
    const current = await this.missions.getById(id);
    if (!current) {
      throw new Error(`Mission '${id}' not found`);
    }
    if (!canTransition(current.status, to)) {
      throw new Error(
        `cannot transition mission '${id}' from '${current.status}' to '${to}'`,
      );
    }
    const updated = transitionMission(current, to, this.clock);
    await this.missions.update(updated);
    await this.transitions.record({
      missionId: id,
      fromStatus: current.status,
      toStatus: to,
      reason: reason ?? null,
      createdAt: this.clock().toISOString(),
    });
    return updated;
  }

  listApprovals(status?: ApprovalRecord["status"]): Promise<ApprovalRecord[]> {
    return this.approvals.list(status ? { status } : undefined);
  }

  async createApproval(input: CreateApprovalPayload): Promise<ApprovalRecord> {
    const record: CreateApprovalInput = {
      id: input.id ?? randomUUID(),
      missionId: input.missionId,
      runId: input.runId,
      capability: input.capability,
      action: input.action,
      reason: input.reason,
      risk: input.risk,
    };
    return this.approvals.create(record);
  }

  async resolveApproval(id: string, status: "approved" | "rejected"): Promise<ApprovalRecord> {
    return this.approvals.resolve(id, {
      status,
      resolvedAt: this.clock().toISOString(),
    });
  }

  transitionMatrix(): Record<MissionStatus, MissionStatus[]> {
    const out = {} as Record<MissionStatus, MissionStatus[]>;
    for (const from of ALL_STATUSES) {
      out[from] = ALL_STATUSES.filter((to) => canTransition(from, to));
    }
    return out;
  }
}

/** Open a MissionService bound to a SQLite database. */
export function openMissionService(db: Database, clock: () => Date = () => new Date()): MissionService {
  return new MissionService(
    new SqliteMissionRepository(db),
    new SqlitePlanRepository(db),
    new SqliteTransitionRepository(db),
    new SqliteApprovalRepository(db),
    clock,
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `agentic-os/`):

```bash
npx vitest run apps/api/src/mission-service.test.ts
```

Expected: PASS.

- [ ] **Step 5: Run the full suite + typecheck**

Run (from `agentic-os/`):

```bash
npm test
npx tsc -b
```

Expected: all green, no type errors.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/mission-service.ts apps/api/src/mission-service.test.ts
git commit -m "feat(api): add MissionService facade over Core + storage"
```

---

### Task 3: `createApp` Hono routes + the dashboard

**Files:**
- Create: `apps/api/src/index.ts`
- Create: `apps/api/www/index.html`
- Test: `apps/api/src/index.test.ts`

**Interfaces:**
- Consumes: `openMissionService`/`MissionService` from `./mission-service.js` (Task 2), `Database` from `@agentic-os/storage`, `MissionStatusSchema` + `MissionStatus` from `@agentic-os/core`, `Hono` from `hono`.
- Produces:
  - `function createApp(db: Database, opts?: { clock?: () => Date; service?: MissionService }): Hono`
  - HTTP contract (from the spec):
    - `GET /` → `www/index.html` (text/html)
    - `GET /api/missions?status=` → `Mission[]`
    - `GET /api/missions/:id` → `Mission` | 404
    - `GET /api/missions/:id/plan` → `Plan` | `null` | 404
    - `GET /api/missions/:id/history` → `MissionTransitionRecord[]` | 404
    - `POST /api/missions` `{title, description?, priority?, acceptanceCriteria: string[], id?}` → `Mission` (201) | 400
    - `POST /api/missions/:id/transition` `{to: MissionStatus, reason?}` → `Mission` | 400/404
    - `GET /api/approvals?status=` → `ApprovalRecord[]`
    - `POST /api/approvals` `{missionId, capability, action, reason, risk, runId?}` → `ApprovalRecord` (201) | 400
    - `POST /api/approvals/:id/resolve` `{status: "approved"|"rejected"}` → `ApprovalRecord` | 400/404
    - `GET /api/transitions` → `Record<MissionStatus, MissionStatus[]>` (Core matrix for the UI transition dropdown)

- [ ] **Step 1: Write the failing test**

Create `apps/api/src/index.test.ts`:

```ts
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { Database } from "@agentic-os/storage";
import { openMissionService } from "./mission-service.js";
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
    const m = await res.json();
    expect(m.title).toBe("Improve event search");
    expect(m.status).toBe("queued");

    const list = await (await app.request("/api/missions")).json();
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
    const created = await (await post("/api/missions", {
      title: "Transitionable",
      acceptanceCriteria: ["x"],
      priority: "low",
    })).json();

    const ok = await post(`/api/missions/${created.id}/transition`, { to: "running", reason: "go" });
    expect(ok.status).toBe(200);
    expect((await ok.json()).status).toBe("running");

    const bad = await post(`/api/missions/${created.id}/transition`, { to: "completed" });
    expect(bad.status).toBe(400);

    const history = await (await app.request(`/api/missions/${created.id}/history`)).json();
    expect(history).toHaveLength(1);
    expect(history[0].toStatus).toBe("running");

    const miss = await post("/api/missions/ghost/transition", { to: "running" });
    expect(miss.status).toBe(404);
  });

  it("returns null plan for a mission without one", async () => {
    const created = await (await post("/api/missions", {
      title: "Planned",
      acceptanceCriteria: ["x"],
      priority: "low",
    })).json();
    const planRes = await app.request(`/api/missions/${created.id}/plan`);
    expect(planRes.status).toBe(200);
    expect(await planRes.json()).toBeNull();
  });

  it("creates and resolves approvals; blocks terminal re-resolution; 404s unknown", async () => {
    const created = await (await post("/api/missions", {
      title: "Approve",
      acceptanceCriteria: ["x"],
      priority: "high",
    })).json();

    const makeRes = await post("/api/approvals", {
      missionId: created.id,
      capability: "filesystem",
      action: "delete",
      reason: "cleanup",
      risk: "destructive",
    });
    expect(makeRes.status).toBe(201);
    const approval = await makeRes.json();

    const pending = await (await app.request("/api/approvals?status=pending")).json();
    expect(pending).toHaveLength(1);

    const approved = await post(`/api/approvals/${approval.id}/resolve`, { status: "approved" });
    expect(approved.status).toBe(200);
    expect((await approved.json()).status).toBe("approved");

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
    const matrix = await (await app.request("/api/transitions")).json();
    expect(matrix.queued).toEqual(expect.arrayContaining(["running", "cancelled"]));
    expect(matrix.completed).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `agentic-os/`):

```bash
npx vitest run apps/api/src/index.test.ts
```

Expected: FAIL — `./index.js` cannot be resolved.

- [ ] **Step 3a: Write the app — `apps/api/src/index.ts`**

```ts
import { readFileSync } from "node:fs";

import { Hono } from "hono";
import type { Context } from "hono";
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

export type { Context };
```

- [ ] **Step 3b: Write the dashboard — `apps/api/www/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Mission Control</title>
<style>
  :root {
    --bg: #0b0e14;
    --panel: #131722;
    --panel2: #1b2130;
    --border: #232838;
    --text: #e6e9ef;
    --muted: #8b93a7;
    --accent: #7c9eff;
    --accent2: #63e6be;
    --danger: #ff6b6b;
    --warn: #ffa94d;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: radial-gradient(1200px 600px at 20% -10%, #16203a 0%, var(--bg) 55%);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif;
    min-height: 100vh;
  }
  header {
    padding: 1.75rem 1.5rem 0.75rem;
    display: flex;
    align-items: baseline;
    gap: 0.9rem;
    flex-wrap: wrap;
  }
  header h1 {
    margin: 0;
    font-size: 1.5rem;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }
  header .sub {
    color: var(--muted);
    font-size: 0.82rem;
  }
  #errorStrip {
    display: none;
    margin: 0.5rem 1.5rem;
    padding: 0.6rem 0.9rem;
    border: 1px solid var(--danger);
    background: rgba(255, 107, 107, 0.08);
    color: var(--danger);
    border-radius: 8px;
    font-size: 0.85rem;
  }
  #errorStrip.show { display: block; }
  main {
    display: grid;
    grid-template-columns: 1fr 400px;
    gap: 1.25rem;
    padding: 0.5rem 1.5rem 3rem;
    align-items: start;
  }
  @media (max-width: 980px) {
    main { grid-template-columns: 1fr; }
  }
  .lane-column { display: flex; flex-direction: column; gap: 1.25rem; }
  .panel {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.1rem 1.25rem;
  }
  .panel h2 {
    margin: 0 0 0.9rem;
    font-size: 0.95rem;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: var(--accent2);
  }
  .board {
    display: flex;
    gap: 0.9rem;
    overflow-x: auto;
    padding-bottom: 0.5rem;
  }
  .lane {
    flex: 0 0 210px;
    background: var(--panel2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.7rem;
  }
  .lane header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 0.25rem 0.6rem;
  }
  .lane h3 {
    margin: 0;
    font-size: 0.74rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .lane .count {
    font-size: 0.74rem;
    color: var(--muted);
    background: #10141f;
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 0.05rem 0.5rem;
  }
  .mission-card {
    background: #10141f;
    border: 1px solid var(--border);
    border-radius: 9px;
    padding: 0.7rem;
    margin-bottom: 0.55rem;
    cursor: pointer;
    transition: border-color 0.15s ease, transform 0.15s ease;
  }
  .mission-card:hover { border-color: var(--accent); transform: translateY(-1px); }
  .mission-card.selected { border-color: var(--accent2); }
  .mission-card .title {
    font-size: 0.86rem;
    font-weight: 600;
    margin-bottom: 0.45rem;
  }
  .mission-card .meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.72rem;
    color: var(--muted);
  }
  .pri {
    font-size: 0.62rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    border-radius: 999px;
    padding: 0.1rem 0.5rem;
    border: 1px solid var(--border);
  }
  .pri.critical { color: var(--danger); border-color: var(--danger); }
  .pri.high { color: var(--warn); border-color: var(--warn); }
  .pri.medium { color: var(--accent); border-color: var(--accent); }
  .pri.low { color: var(--muted); }
  .empty {
    color: var(--muted);
    font-size: 0.78rem;
    padding: 0.5rem 0.25rem;
    text-align: center;
  }
  .approval {
    border: 1px solid var(--border);
    border-radius: 9px;
    padding: 0.7rem;
    margin-bottom: 0.6rem;
    background: #10141f;
  }
  .approval .action {
    font-size: 0.86rem;
    font-weight: 600;
    margin-bottom: 0.3rem;
  }
  .approval .action code {
    color: var(--accent);
    font-size: 0.8rem;
  }
  .approval .detail {
    font-size: 0.78rem;
    color: var(--muted);
    line-height: 1.45;
    margin-bottom: 0.55rem;
  }
  .approval .row {
    display: flex;
    gap: 0.45rem;
  }
  .btn {
    flex: 1;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text);
    border-radius: 7px;
    padding: 0.42rem 0.6rem;
    font-size: 0.78rem;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .btn.approve { border-color: var(--accent2); color: var(--accent2); }
  .btn.approve:hover { background: rgba(99, 230, 190, 0.12); }
  .btn.reject { border-color: var(--danger); color: var(--danger); }
  .btn.reject:hover { background: rgba(255, 107, 107, 0.1); }
  .btn.primary {
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    border: none;
    color: #0b0e14;
    font-weight: 700;
  }
  .btn.primary:hover { opacity: 0.9; }
  .btn.primary:disabled { opacity: 0.5; cursor: not-allowed; }
  .field { margin-bottom: 0.8rem; }
  .field label {
    display: block;
    font-size: 0.74rem;
    color: var(--muted);
    margin-bottom: 0.3rem;
  }
  .field input,
  .field select,
  .field textarea {
    width: 100%;
    background: #10141f;
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    padding: 0.5rem 0.65rem;
    font-size: 0.84rem;
    font-family: inherit;
    resize: vertical;
  }
  .field input:focus,
  .field select:focus,
  .field textarea:focus {
    outline: none;
    border-color: var(--accent);
  }
  .detail-line {
    font-size: 0.8rem;
    color: var(--muted);
    margin-bottom: 0.35rem;
  }
  .detail-line b { color: var(--text); font-weight: 600; }
  .criteria-list {
    list-style: none;
    margin: 0.4rem 0 0;
    padding: 0;
  }
  .criteria-list li {
    font-size: 0.8rem;
    color: var(--muted);
    padding: 0.25rem 0;
    border-bottom: 1px dashed var(--border);
  }
  .timeline { list-style: none; margin: 0.6rem 0 0; padding: 0; }
  .timeline li {
    position: relative;
    padding-left: 1.2rem;
    font-size: 0.78rem;
    color: var(--muted);
    padding-bottom: 0.5rem;
  }
  .timeline li::before {
    content: "";
    position: absolute;
    left: 0.3rem;
    top: 0.34rem;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--accent);
  }
  .timeline li .arrow { color: var(--accent2); }
  .hidden { display: none; }
  .section-h {
    font-size: 0.82rem;
    color: var(--muted);
    margin: 0.8rem 0 0.4rem;
    font-weight: 600;
  }
</style>
</head>
<body>
  <header>
    <h1>Mission Control</h1>
    <span class="sub" id="clockLine"></span>
  </header>
  <div id="errorStrip"></div>

  <main>
    <div class="lane-column">
      <section class="panel">
        <h2>Mission Board</h2>
        <div class="board" id="board"></div>
      </section>
    </div>

    <div class="lane-column">
      <section class="panel">
        <h2>Approvals Queue</h2>
        <div id="approvals"></div>
      </section>

      <section class="panel" id="detailPanel">
        <h2>Mission Detail</h2>
        <div id="detail"></div>
        <div id="detailEmpty" class="empty">Select a mission card to inspect it.</div>
        <div id="transitionForm" class="hidden"></div>
      </section>

      <section class="panel">
        <h2>New Mission</h2>
        <form id="newMissionForm">
          <div class="field">
            <label for="nmTitle">Title *</label>
            <input id="nmTitle" type="text" placeholder="e.g. Improve event search" required />
          </div>
          <div class="field">
            <label for="nmDescription">Description</label>
            <textarea id="nmDescription" rows="2" placeholder="Objective (optional)"></textarea>
          </div>
          <div class="field">
            <label for="nmPriority">Priority</label>
            <select id="nmPriority">
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium" selected>Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
          <div class="field">
            <label for="nmCriteria">Acceptance criteria (one per line) *</label>
            <textarea id="nmCriteria" rows="3" placeholder="Users can search events by title&#10;Results paginate"></textarea>
          </div>
          <button type="submit" class="btn primary" id="nmSubmit">Create Mission</button>
        </form>
      </section>
    </div>
  </main>

  <script>
    const LANES = ["queued", "running", "awaiting_approval", "paused", "failed", "completed", "cancelled"];
    const LANE_COLORS = {
      queued: "var(--muted)", running: "var(--accent)",
      awaiting_approval: "var(--warn)", paused: "var(--muted)",
      failed: "var(--danger)", completed: "var(--accent2)", cancelled: "var(--muted)",
    };

    let missions = [];
    let approvals = [];
    let matrix = {};
    let selectedId = null;

    const $ = (id) => document.getElementById(id);

    function esc(s) {
      return String(s ?? "").replace(/[&<>"']/g, (c) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
      }[c]));
    }

    function showError(msg) {
      const strip = $("errorStrip");
      strip.textContent = msg;
      strip.classList.add("show");
    }
    function clearError() { $("errorStrip").classList.remove("show"); }

    async function api(path, opts = {}) {
      const res = await fetch(path, {
        headers: { "content-type": "application/json" },
        ...opts,
      });
      if (!res.ok) {
        let msg = `HTTP ${res.status}`;
        try { msg = (await res.json()).error || msg; } catch { /* keep default */ }
        throw new Error(msg);
      }
      return res.json();
    }

    async function refresh() {
      try {
        const [ms, as, mx] = await Promise.all([
          api("/api/missions"),
          api("/api/approvals"),
          api("/api/transitions"),
        ]);
        missions = ms;
        approvals = as;
        matrix = mx;
        clearError();
      } catch (err) {
        showError(err.message);
      }
      renderBoard();
      renderApprovals();
      if (selectedId) renderDetail(selectedId);
    }

    function renderBoard() {
      const board = $("board");
      board.innerHTML = "";
      for (const lane of LANES) {
        const col = document.createElement("div");
        col.className = "lane";
        const laneMissions = missions.filter((m) => m.status === lane);
        const head = document.createElement("header");
        head.innerHTML = `<h3 style="color:${LANE_COLORS[lane]}">${lane.replace("_", " ")}</h3><span class="count">${laneMissions.length}</span>`;
        col.appendChild(head);
        if (laneMissions.length === 0) {
          const empty = document.createElement("div");
          empty.className = "empty";
          empty.textContent = "—";
          col.appendChild(empty);
        } else {
          for (const m of laneMissions) {
            const card = document.createElement("div");
            card.className = "mission-card" + (m.id === selectedId ? " selected" : "");
            card.innerHTML = `
              <div class="title">${esc(m.title)}</div>
              <div class="meta"><span class="pri ${esc(m.priority)}">${esc(m.priority)}</span><span>${new Date(m.createdAt).toLocaleDateString()}</span></div>`;
            card.addEventListener("click", () => { selectedId = m.id; renderDetail(m.id); renderBoard(); });
            col.appendChild(card);
          }
        }
        board.appendChild(col);
      }
    }

    function renderApprovals() {
      const wrap = $("approvals");
      wrap.innerHTML = "";
      const pending = approvals.filter((a) => a.status === "pending");
      if (pending.length === 0) {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = "All clear — no pending approvals.";
        wrap.appendChild(empty);
        return;
      }
      for (const a of pending) {
        const card = document.createElement("div");
        card.className = "approval";
        card.innerHTML = `
          <div class="action">${esc(a.capability)} <code>${esc(a.action)}</code></div>
          <div class="detail">${esc(a.reason)}<br />risk: ${esc(a.risk)} · mission: <span class="mono">${esc(a.missionId)}</span></div>
          <div class="row">
            <button class="btn approve">Approve</button>
            <button class="btn reject">Reject</button>
          </div>`;
        const approveBtn = card.querySelector(".approve");
        const rejectBtn = card.querySelector(".reject");
        const action = (status) => async () => {
          try {
            await api(`/api/approvals/${a.id}/resolve`, {
              method: "POST",
              body: JSON.stringify({ status }),
            });
            await refresh();
          } catch (err) { showError(err.message); }
        };
        approveBtn.addEventListener("click", action("approved"));
        rejectBtn.addEventListener("click", action("rejected"));
        wrap.appendChild(card);
      }
    }

    async function renderDetail(id) {
      $("detailEmpty").classList.add("hidden");
      const detail = $("detail");
      const tform = $("transitionForm");
      let m;
      try {
        m = await api(`/api/missions/${id}`);
      } catch (err) {
        showError(err.message);
        return;
      }
      selectedId = id;
      const plan = await api(`/api/missions/${id}/plan`);
      const history = await api(`/api/missions/${id}/history`);

      detail.innerHTML = `
        <div class="detail-line"><b>${esc(m.title)}</b></div>
        <div class="detail-line">id: ${esc(m.id)} · status: <b>${esc(m.status)}</b> · priority: <span class="pri ${esc(m.priority)}">${esc(m.priority)}</span></div>
        ${m.description ? `<div class="detail-line">${esc(m.description)}</div>` : ""}
        <div class="section-h">Acceptance criteria</div>
        <ul class="criteria-list">${m.acceptanceCriteria.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>
        <div class="section-h">Latest plan${plan ? ` (${plan.tasks.length} task(s))` : ""}</div>
        ${plan ? `<ul class="criteria-list">${plan.tasks.map((t) => `<li>${esc(t.title)}</li>`).join("")}</ul>` : `<div class="empty">No plan yet.</div>`}
        <div class="section-h">Transition history</div>
        ${history.length
          ? `<ul class="timeline">${history.map((h) => `<li><span class="arrow">${esc(h.fromStatus)} → ${esc(h.toStatus)}</span> · ${new Date(h.createdAt).toLocaleString()}${h.reason ? ` — ${esc(h.reason)}` : ""}</li>`).join("")}</ul>`
          : `<div class="empty">No transitions yet.</div>`}`;

      const legal = (matrix[m.status] || []).filter((s) => s !== m.status);
      if (legal.length === 0) {
        tform.classList.add("hidden");
        tform.innerHTML = "";
      } else {
        tform.classList.remove("hidden");
        tform.innerHTML = `
          <div class="section-h">Transition mission</div>
          <div class="field">
            <label for="tfStatus">Next status</label>
            <select id="tfStatus">${legal.map((s) => `<option value="${esc(s)}">${esc(s)}</option>`).join("")}</select>
          </div>
          <div class="field">
            <label for="tfReason">Reason (optional)</label>
            <input id="tfReason" type="text" placeholder="e.g. Plan accepted" />
          </div>
          <button class="btn primary" id="tfSubmit">Transition</button>`;
        $("tfSubmit").addEventListener("click", async () => {
          try {
            await api(`/api/missions/${id}/transition`, {
              method: "POST",
              body: JSON.stringify({ to: $("tfStatus").value, reason: $("tfReason").value || undefined }),
            });
            await refresh();
          } catch (err) { showError(err.message); }
        });
      }
    }

    function updateClockLine() {
      $("clockLine").textContent = new Date().toLocaleString();
    }

    $("newMissionForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      const criteria = $("nmCriteria").value.split("\n").map((s) => s.trim()).filter(Boolean);
      if (criteria.length === 0) { showError("Add at least one acceptance criterion"); return; }
      const submit = $("nmSubmit");
      submit.disabled = true;
      submit.textContent = "Creating…";
      try {
        await api("/api/missions", {
          method: "POST",
          body: JSON.stringify({
            title: $("nmTitle").value,
            description: $("nmDescription").value || undefined,
            priority: $("nmPriority").value,
            acceptanceCriteria: criteria,
          }),
        });
        e.target.reset();
        await refresh();
      } catch (err) { showError(err.message); }
      submit.disabled = false;
      submit.textContent = "Create Mission";
    });

    refresh();
    updateClockLine();
    setInterval(updateClockLine, 1000);
    setInterval(refresh, 5000);
  </script>
</body>
</html>
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `agentic-os/`):

```bash
npx vitest run apps/api/src/index.test.ts
```

Expected: PASS (all 10 cases).

- [ ] **Step 5: Typecheck + lint the workspace**

Run (from `agentic-os/`):

```bash
npx tsc -b
npm run lint
```

Expected: no type errors. Note: `npm run lint` targets `packages/**` and `apps/**`; if ESLint reports pre-existing unrelated issues in the new files (e.g. `Context` unused export in `index.ts`), remove the `export type { Context }` line and its import if it trips `noUnusedLocals`/lint. Re-run until clean.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/index.ts apps/api/src/index.test.ts apps/api/www/index.html
git commit -m "feat(api): serve mission control dashboard + HTTP API"
```

---

### Task 4: `server.ts` bootstrap + smoke test

**Files:**
- Create: `apps/api/src/server.ts`

**Interfaces:**
- Consumes: `loadConfigFile` from `@agentic-os/config`, `Database` from `@agentic-os/storage`, `createApp` from `./index.js` (Task 3).
- Produces: `node src/server.ts` boots a server on `localhost:8787` (or `$PORT`) reading `config/agentic-os.yaml`.

- [ ] **Step 1: Write `apps/api/src/server.ts`**

```ts
import { existsSync } from "node:fs";

import { serve } from "@hono/node-server";
import { loadConfigFile } from "@agentic-os/config";
import { Database } from "@agentic-os/storage";

import { createApp } from "./index.js";

const DEFAULT_CONFIG = new URL("../../config/agentic-os.yaml", import.meta.url);

function resolveConfigPath(explicit?: string): string {
  if (explicit) return explicit;
  const candidate = DEFAULT_CONFIG.pathname;
  return existsSync(candidate) ? candidate : DEFAULT_CONFIG.pathname;
}

async function main(argv: string[]): Promise<void> {
  const configPath = argv[0] ?? resolveConfigPath();
  const config = loadConfigFile(configPath);
  const db = Database.open(config.database.path);
  const app = createApp(db);

  const port = Number(process.env.PORT ?? 8787);
  serve({ fetch: app.fetch, port }, (info) => {
    console.log(`Mission Control running at http://localhost:${info.port}`);
  });

  const shutdown = () => {
    try { db.close(); } catch { /* already closed */ }
    process.exit(0);
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

if (process.argv[1] !== undefined && import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv.slice(2)).catch((err) => {
    console.error(err instanceof Error ? err.message : String(err));
    process.exit(1);
  });
}
```

- [ ] **Step 2: Verify `@hono/node-server` exports `serve`**

Run (from `agentic-os/`):

```bash
node -e "import('@hono/node-server').then(m => console.log(typeof m.serve))"
```

Expected: `function`.

- [ ] **Step 3: Typecheck**

Run (from `agentic-os/`):

```bash
npx tsc -b
```

Expected: no errors.

- [ ] **Step 4: Manual smoke test**

Run (from `agentic-os/`):

```bash
node apps/api/src/server.ts &
sleep 1.5
curl -s http://localhost:8787/ | head -5
curl -s http://localhost:8787/api/missions
curl -s -X POST http://localhost:8787/api/missions \
  -H "content-type: application/json" \
  -d '{"title":"Smoke","priority":"high","acceptanceCriteria":["reachable"]}'
curl -s http://localhost:8787/api/missions
kill %1
```

Expected:
- `/` returns the dashboard HTML (`<!doctype html>`…`Mission Control`).
- `/api/missions` returns `[]` (or prior missions on the existing db).
- create returns `201` JSON; list shows the new mission.
- The background job terminates via `kill %1`.

- [ ] **Step 5: Update the API section of the README**

In `agentic-os/README.md`, after the CLI examples (end of the `### apps/cli` section, before `## packages/memory/python`), add:

```markdown
### apps/api

Mission Control HTTP server + dashboard (read/write).

```bash
# seed a mission via the CLI, then open the dashboard
node apps/api/src/server.ts
# → http://localhost:8787  (PORT env var overrides)
```

Endpoints under `/api/`: `GET/POST /api/missions`, `GET /api/missions/:id`,
`GET /api/missions/:id/plan`, `GET /api/missions/:id/history`,
`POST /api/missions/:id/transition`, `GET/POST /api/approvals`,
`POST /api/approvals/:id/resolve`, `GET /api/transitions`.
All writes go through the same Core validation as the CLI. Dashboard widgets:
mission board (status lanes), approvals queue (approve/reject), mission detail
(plan + history + transition control), new-mission form. Autorefreshes every 5s.
```

- [ ] **Step 6: Run full suite + build**

Run (from `agentic-os/`):

```bash
npm test
npm run check
npm run build
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/server.ts agentic-os/README.md
git commit -m "feat(api): boot mission control server + document dashboard"
```

---

## Self-Review

**Spec coverage:**
- `apps/api` becomes a real Hono server — Task 1 (deps) + Task 4 (boot). ✅
- `MissionService` facade over Core + storage, never re-implements rules/SQL — Task 2. ✅
- Static `www/index.html` served at `/` with no frontend build step — Task 3. ✅
- Mission board lanes, approvals queue with approve/reject, mission detail with plan + history + transition control, new mission form — Task 3 (dashboard). ✅
- Legal-next-status `<select>` derived from Core's matrix, exposed via API — `GET /api/transitions` (Task 3) + `transitionMatrix()` (Task 2). ✅
- 5s polling, error strip, plan/history fetched only on selection — Task 3 dashboard. ✅
- All writes through Core validation; 400/404 error shape `{ error }` — Task 3. ✅
- Non-goals respected: no AI/model calls, no drag-reflow grid, no demo calendar/email widgets, no auth. ✅
- Testing via `Database.memory()` + `app.request()`, no ports — Task 2/3 tests. ✅

**Placeholder scan:** Every code step contains literal implementation; no TBD/TODO/`write tests` placeholders; runnable test commands with expected results per step.

**Type consistency:** `openMissionService`, `MissionService` constructor order (missions, plans, transitions, approvals, clock) matches its call site; `getLatestPlan` returns through storage's `Plan` type; `history` returns `MissionTransitionRecord[]`; `transitionMatrix(): Record<MissionStatus, MissionStatus[]>` matches `GET /api/transitions`; `CreateMissionPayload`/`CreateApprovalPayload` names used consistently in tests and impl. `apps/api/www/index.html` relative path resolves from `apps/api/src/index.ts` (`../www/index.html`). ✅