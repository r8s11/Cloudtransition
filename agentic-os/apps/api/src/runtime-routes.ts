import { Hono, type Context } from "hono";
import { z } from "zod";
import { RuntimeError, type AgentRuntime } from "@agentic-os/runtime";
import { listArtifacts, readArtifact } from "./artifacts.js";

const text = z.string().trim().min(1);
const projectInput = z.object({ path: text, name: text.optional() }).strict();
const runInput = z
  .object({
    projectId: text,
    adapterId: text,
    prompt: z
      .string()
      .min(1)
      .max(65536)
      .refine((value) => value.trim().length > 0),
    missionId: text.optional(),
    planVersion: z.number().int().positive().safe().optional(),
    taskId: text.optional(),
    model: text.optional(),
    effort: text.optional(),
  })
  .strict();

function pageNumber(
  value: string | undefined,
  fallback: number,
  min: number,
  max = Number.MAX_SAFE_INTEGER,
): number {
  if (value === undefined) return fallback;
  if (!/^\d+$/.test(value))
    throw new RuntimeError("Pagination values must be integers", 400);
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number < min || number > max)
    throw new RuntimeError("Pagination value out of range", 400);
  return number;
}

async function body(c: Context): Promise<unknown> {
  try {
    return await c.req.json();
  } catch {
    throw new RuntimeError("Invalid JSON body", 400);
  }
}

export function runtimeRoutes(runtime: AgentRuntime, artifactsDir?: string): Hono {
  const routes = new Hono();
  routes.onError((error, c) => {
    if (error instanceof RuntimeError)
      return c.json({ error: error.message }, error.status);
    if (error instanceof z.ZodError)
      return c.json({ error: "Invalid request", issues: error.issues }, 400);
    return c.json({ error: "Runtime request failed" }, 500);
  });
  routes.use("*", async (c, next) => {
    const url = new URL(c.req.url);
    const host = c.req.header("Host") ?? url.host;
    if (
      !/^(localhost|127\.0\.0\.1|\[::1\])(?::\d{1,5})?$/i.test(host) ||
      host.toLowerCase() !== url.host.toLowerCase()
    ) {
      return c.json({ error: "Runtime API requires a loopback Host" }, 403);
    }
    const origin = c.req.header("Origin");
    if (
      (origin !== undefined && origin !== url.origin) ||
      c.req.header("Sec-Fetch-Site") === "cross-site"
    ) {
      return c.json({ error: "Cross-origin runtime access is forbidden" }, 403);
    }
    if (
      c.req.method === "POST" &&
      c.req.header("Content-Type")?.split(";")[0]?.trim().toLowerCase() !==
        "application/json"
    ) {
      return c.json({ error: "application/json is required" }, 415);
    }
    await next();
  });
  routes.get("/projects", (c) => c.json(runtime.listProjects()));
  routes.post("/projects", async (c) => {
    const input = projectInput.parse(await body(c));
    return c.json(await runtime.registerProject(input.path, input.name), 201);
  });
  routes.get("/projects/:id/skills", async (c) =>
    c.json(await runtime.listSkills(c.req.param("id"))),
  );
  routes.get("/agents", async (c) => c.json(await runtime.detectAdapters()));
  routes.get("/usage", (c) =>
    c.json(runtime.usage(pageNumber(c.req.query("days"), 7, 1, 90))),
  );
  routes.get("/artifacts", async (c) =>
    c.json(artifactsDir ? await listArtifacts(artifactsDir) : []),
  );
  routes.get("/artifacts/file", async (c) => {
    const file = artifactsDir
      ? await readArtifact(artifactsDir, c.req.query("path") ?? "")
      : null;
    if (!file) throw new RuntimeError("Artifact not found", 404);
    return new Response(new Uint8Array(file.body), { headers: file.headers });
  });
  routes.get("/runs", (c) => {
    const active = c.req.query("active");
    if (active !== undefined && active !== "true" && active !== "false")
      throw new RuntimeError("active must be true or false", 400);
    const projectId = c.req.query("projectId");
    return c.json(
      runtime.listRuns({
        active: active === undefined ? undefined : active === "true",
        projectId: projectId === undefined ? undefined : text.parse(projectId),
        limit: pageNumber(c.req.query("limit"), 100, 1, 1000),
        offset: pageNumber(c.req.query("offset"), 0, 0),
      }),
    );
  });
  routes.post("/runs", async (c) =>
    c.json(await runtime.start(runInput.parse(await body(c))), 201),
  );
  routes.get("/runs/:id", (c) => {
    const run = runtime.getRun(c.req.param("id"));
    if (!run) throw new RuntimeError("Run not found", 404);
    return c.json(run);
  });
  routes.get("/runs/:id/events", (c) =>
    c.json(
      runtime.events(
        c.req.param("id"),
        pageNumber(c.req.query("after"), 0, 0),
        pageNumber(c.req.query("limit"), 100, 1, 1000),
      ),
    ),
  );
  routes.post("/runs/:id/interrupt", async (c) => {
    z.object({})
      .strict()
      .parse(await body(c));
    return c.json(await runtime.interrupt(c.req.param("id")));
  });
  routes.post("/runs/:id/terminate", async (c) => {
    z.object({})
      .strict()
      .parse(await body(c));
    return c.json(await runtime.terminate(c.req.param("id")));
  });
  return routes;
}
