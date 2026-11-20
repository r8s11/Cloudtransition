import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { Hono } from "hono";
import { z } from "zod";
import { Database } from "@agentic-os/storage";
import { AgentRuntime, CommandAgentAdapter } from "@agentic-os/runtime";
import { createApp } from "./index.js";

describe("runtime HTTP boundaries", () => {
  let directory: string;
  let db: Database;
  let runtime: AgentRuntime;
  let app: Hono;
  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), "runtime-api-"));
    execFileSync("git", ["init", "--quiet", directory]);
    db = Database.memory();
    runtime = new AgentRuntime(db, [
      new CommandAgentAdapter("node", process.execPath, () => [
        "-e",
        "console.log('output');console.error('diagnostic')",
      ]),
    ]);
    app = createApp(db, { runtime, artifactsDir: join(directory, "artifacts") });
  });
  afterEach(async () => {
    await runtime.shutdown();
    db.close();
    rmSync(directory, { recursive: true, force: true });
  });
  function post(
    url: string,
    body: unknown,
    headers: Record<string, string> = {},
  ) {
    return app.request(`http://localhost${url}`, {
      method: "POST",
      headers: {
        host: "localhost",
        "content-type": "application/json",
        ...headers,
      },
      body: JSON.stringify(body),
    });
  }
  function get(url: string, headers: Record<string, string> = {}) {
    return app.request(`http://localhost${url}`, {
      headers: { host: "localhost", ...headers },
    });
  }
  it("registers and executes a project through HTTP with durable output", async () => {
    const registered = await post(
      "/api/projects",
      { path: directory },
      { origin: "http://localhost" },
    );
    expect(registered.status).toBe(201);
    const project = z.object({ id: z.string() }).parse(await registered.json());
    const started = await post("/api/runs", {
      projectId: project.id,
      adapterId: "node",
      prompt: "test",
    });
    expect(started.status).toBe(201);
    const run = z.object({ id: z.string() }).parse(await started.json());
    await expect
      .poll(
        async () =>
          z
            .object({ status: z.string() })
            .parse(await (await get(`/api/runs/${run.id}`)).json()).status,
      )
      .toBe("completed");
    const events = await (await get(`/api/runs/${run.id}/events`)).json();
    expect(events).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ kind: "stdout", data: "output\n" }),
        expect.objectContaining({ kind: "stderr", data: "diagnostic\n" }),
      ]),
    );
    expect(await (await get("/api/runs?active=true")).json()).toEqual([]);
    expect(await (await get("/api/runs?active=false")).json()).toEqual([
      expect.objectContaining({ id: run.id }),
    ]);
    expect(
      await (await get(`/api/runs/${run.id}/events?after=10001`)).json(),
    ).toEqual([]);
  });
  it("blocks hostile browser access on reads and writes without blocking same-origin use", async () => {
    expect((await get("/api/runs", { host: "attacker.example" })).status).toBe(
      403,
    );
    expect(
      (await get("/api/projects", { origin: "https://attacker.example" }))
        .status,
    ).toBe(403);
    expect(
      (
        await post(
          "/api/projects",
          { path: directory },
          { origin: "https://attacker.example" },
        )
      ).status,
    ).toBe(403);
    expect(
      (
        await post(
          "/api/projects",
          { path: directory },
          { "content-type": "text/plain" },
        )
      ).status,
    ).toBe(415);
    expect(
      (await get("/api/runs", { origin: "http://localhost" })).status,
    ).toBe(200);
  });
  it("rejects malformed linkage and pagination rather than trusting casts", async () => {
    const project = await runtime.registerProject(directory);
    expect(
      (
        await post("/api/runs", {
          projectId: project.id,
          adapterId: "node",
          prompt: "test",
          missionId: {},
        })
      ).status,
    ).toBe(400);
    expect(
      (
        await post("/api/runs", {
          projectId: project.id,
          adapterId: "node",
          prompt: "test",
          taskId: 3,
        })
      ).status,
    ).toBe(400);
    expect(
      (
        await post("/api/runs", {
          projectId: project.id,
          adapterId: "node",
          prompt: "test",
          planVersion: "1",
        })
      ).status,
    ).toBe(400);
    expect((await get("/api/runs?limit=0")).status).toBe(400);
    expect((await get("/api/runs?limit=1001")).status).toBe(400);
    expect((await get("/api/runs?offset=1.5")).status).toBe(400);
    expect((await get("/api/runs?active=")).status).toBe(400);
    expect((await get("/api/runs/missing/events")).status).toBe(404);
    expect(runtime.listRuns()).toEqual([]);
  });
  it("lists artifacts newest first and serves them sandboxed, never outside the folder", async () => {
    expect(await (await get("/api/artifacts")).json()).toEqual([]);
    const artifacts = join(directory, "artifacts");
    mkdirSync(join(artifacts, "reports"), { recursive: true });
    writeFileSync(join(artifacts, "reports", "week.html"), "<h1>Week</h1>");
    writeFileSync(join(artifacts, ".hidden.md"), "hidden");
    writeFileSync(join(directory, "outside.md"), "outside secret");
    symlinkSync(join(directory, "outside.md"), join(artifacts, "link.md"));
    const listed = z
      .array(z.object({ path: z.string(), size: z.number(), modifiedAt: z.string() }))
      .parse(await (await get("/api/artifacts")).json());
    expect(listed.map((a) => a.path)).toEqual(["reports/week.html"]);
    const page = await get("/api/artifacts/file?path=reports/week.html");
    expect(page.status).toBe(200);
    expect(await page.text()).toBe("<h1>Week</h1>");
    expect(page.headers.get("content-security-policy")).toBe("sandbox allow-scripts");
    expect(page.headers.get("x-content-type-options")).toBe("nosniff");
    for (const path of ["../outside.md", "link.md", ".hidden.md", "reports/../../outside.md", "/etc/hosts", "missing.md", ""])
      expect(
        (await get(`/api/artifacts/file?path=${encodeURIComponent(path)}`)).status,
        path,
      ).toBe(404);
    expect(
      (await get("/api/artifacts", { origin: "https://attacker.example" })).status,
    ).toBe(403);
  });
  it("exposes skills, launch options and usage, and rejects options outside the allowlist", async () => {
    const registered = await post("/api/projects", { path: directory });
    const project = z.object({ id: z.string() }).parse(await registered.json());
    mkdirSync(join(directory, ".claude", "skills", "tidy"), { recursive: true });
    writeFileSync(join(directory, ".claude", "skills", "tidy", "SKILL.md"), "description: Tidy up\n");
    expect(await (await get(`/api/projects/${project.id}/skills`)).json()).toEqual([
      { name: "tidy", description: "Tidy up" },
    ]);
    expect((await get("/api/projects/missing/skills")).status).toBe(404);
    expect(await (await get("/api/agents")).json()).toEqual([
      { id: "node", available: true, models: [], efforts: [] },
    ]);
    expect(
      (await post("/api/runs", { projectId: project.id, adapterId: "node", prompt: "/tidy", model: "opus" })).status,
    ).toBe(400);
    expect(await (await get("/api/usage?days=7")).json()).toEqual([]);
    expect((await get("/api/usage?days=0")).status).toBe(400);
  });
});
