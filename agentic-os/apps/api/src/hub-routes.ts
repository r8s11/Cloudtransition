import { readFile, realpath, stat } from "node:fs/promises";
import { extname, join, sep } from "node:path";

import { Hono, type Context } from "hono";
import { z } from "zod";
import type { AgentRegistry, Hub, HubMessageInput } from "@agentic-os/hub";

// Type-only import keeps this slice runnable against a stub Hub before
// packages/hub lands. HubError is recognised structurally by its .status.
type HubErrorStatus = 400 | 403 | 404 | 409 | 503;
const HUB_ERROR_STATUSES = new Set<number>([400, 403, 404, 409, 503]);

function hubError(status: HubErrorStatus, message: string): Error {
  return Object.assign(new Error(message), { status });
}

const text = z.string().trim().min(1);
const prepareInput = z
  .object({ company: text, role: text, url: text })
  .strict();
const startInput = z
  .object({ idempotencyKey: text.optional() })
  .strict();
const decisionInput = z
  .object({ decision: z.enum(["approve", "deny"]) })
  .strict();
const messageInput = z
  .object({
    missionId: text,
    taskId: z.string().nullable().optional(),
    inReplyTo: z.string().nullable().optional(),
    from: text,
    to: text,
    type: z.enum(["assignment", "result", "note"]),
    objective: z.string().optional(),
    doneWhen: z.string().optional(),
    inputRefs: z.array(z.string()).optional(),
    outputRefs: z.array(z.string()).optional(),
    result: z.string().optional(),
    evidence: z.array(z.string()).optional(),
    decisions: z.array(z.string()).optional(),
    blockers: z.array(z.string()).optional(),
    approvalNeeded: z.boolean().optional(),
    idempotencyKey: text,
  })
  .strict();

async function jsonBody(c: Context): Promise<unknown> {
  const raw = await c.req.text();
  if (!raw.trim()) return {};
  try {
    return JSON.parse(raw);
  } catch {
    throw hubError(400, "Invalid JSON body");
  }
}

const LOOPBACK_HOST = /^(localhost|127\.0\.0\.1|\[::1\])(?::\d{1,5})?$/i;

/** Same rules as packages/hub assertLoopbackRequest; absent socket info (test
 * clients) passes, a present non-loopback address never does. */
function assertLoopback(req: {
  host?: string;
  origin?: string;
  remoteAddress?: string;
}): void {
  if (!LOOPBACK_HOST.test(req.host ?? ""))
    throw hubError(403, "Mailbox writes require a loopback Host");
  if (req.origin !== undefined) {
    let originHost: string;
    try {
      originHost = new URL(req.origin).host;
    } catch {
      throw hubError(403, "Mailbox writes require a loopback Origin");
    }
    if (!LOOPBACK_HOST.test(originHost))
      throw hubError(403, "Mailbox writes require a loopback Origin");
  }
  if (req.remoteAddress !== undefined) {
    const address = req.remoteAddress.replace(/^::ffff:/i, "");
    if (address !== "::1" && !/^127\./.test(address))
      throw hubError(403, "Mailbox writes require a loopback connection");
  }
}

const MAX_FILE_BYTES = 20 * 1024 * 1024;

/** Serve one evidence file, but only inside a registry output dir. */
async function readOutputFile(
  registry: AgentRegistry,
  workspaceRoot: string,
  path: string,
): Promise<{ body: Buffer; type: string | null }> {
  const notFound = () => hubError(404, "File not found");
  const parts = path.split("/");
  if (
    !path ||
    path.includes("\0") ||
    path.includes("\\") ||
    path.startsWith("/") ||
    parts.some((part) => !part || part.startsWith("."))
  )
    throw notFound();
  let target: string;
  try {
    target = await realpath(join(workspaceRoot, ...parts));
  } catch {
    throw notFound();
  }
  const bases = await Promise.all(
    Object.values(registry)
      .flatMap((entry) => entry.outputDirs)
      .map(async (dir) => {
        try {
          return await realpath(join(workspaceRoot, dir));
        } catch {
          return null;
        }
      }),
  );
  if (!bases.some((base) => base && target.startsWith(base + sep)))
    throw notFound();
  const info = await stat(target).catch(() => null);
  if (!info?.isFile() || info.size > MAX_FILE_BYTES) throw notFound();
  const extension = extname(target).toLowerCase();
  const type =
    extension === ".md" || extension === ".json"
      ? "text/plain; charset=utf-8"
      : extension === ".pdf"
        ? "application/pdf"
        : null;
  return { body: await readFile(target), type };
}

export function hubRoutes(hub: Hub): Hono {
  const routes = new Hono();

  routes.onError((error, c) => {
    if ("status" in error) {
      const status = error.status;
      if (typeof status === "number" && HUB_ERROR_STATUSES.has(status)) {
        // Validated against HUB_ERROR_STATUSES; Hono needs the literal union.
        const code = status as HubErrorStatus;
        return c.json({ error: error.message }, code);
      }
    }
    if (error instanceof z.ZodError)
      return c.json({ error: "Invalid request", issues: error.issues }, 400);
    return c.json({ error: "Hub request failed" }, 500);
  });

  routes.post("/missions/prepare-application", async (c) => {
    const input = prepareInput.parse(await jsonBody(c));
    return c.json(await hub.prepareApplication(input), 201);
  });

  routes.post("/missions/:id/start", async (c) => {
    const { idempotencyKey } = startInput.parse(await jsonBody(c));
    await hub.start(c.req.param("id"), idempotencyKey);
    return c.json({ ok: true });
  });

  routes.get("/missions", (c) => c.json(hub.listSessions()));

  routes.get("/missions/:id/session", (c) =>
    c.json(hub.session(c.req.param("id"))),
  );

  routes.get("/missions/:id/messages", (c) =>
    c.json({ messages: hub.messages(c.req.param("id")) }),
  );

  routes.post("/missions/:id/messages", async (c) => {
    // @hono/node-server exposes the socket address on env; Hono's Env type omits it.
    const env = c.env as { remoteAddress?: string } | undefined;
    assertLoopback({
      host: c.req.header("host"),
      origin: c.req.header("origin"),
      remoteAddress: env?.remoteAddress,
    });
    const input: HubMessageInput = messageInput.parse(await jsonBody(c));
    if (input.missionId !== c.req.param("id"))
      throw hubError(400, "missionId must match the mission in the path");
    const result = hub.ingest(input);
    if (!result.ok)
      return c.json({ error: result.reason ?? "Message rejected" }, 400);
    return c.json({ ok: true, id: result.id });
  });

  routes.post("/missions/:id/pause", async (c) => {
    await hub.pause(c.req.param("id"));
    return c.json({ ok: true });
  });

  routes.post("/missions/:id/resume", async (c) => {
    await hub.resume(c.req.param("id"));
    return c.json({ ok: true });
  });

  routes.post("/missions/:id/waiting/:wid/resolve", async (c) => {
    const { decision } = decisionInput.parse(await jsonBody(c));
    await hub.resolveWaiting(c.req.param("id"), c.req.param("wid"), decision);
    return c.json({ ok: true });
  });

  routes.post("/stop-runs", async (c) => c.json(await hub.stopAll()));

  routes.get("/agents", (c) => c.json(hub.registry));

  routes.get("/file", async (c) => {
    const file = await readOutputFile(
      hub.registry,
      hub.workspaceRoot,
      c.req.query("path") ?? "",
    );
    return new Response(new Uint8Array(file.body), {
      headers: {
        "Content-Type": file.type ?? "application/octet-stream",
        "Content-Security-Policy": "sandbox allow-scripts",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
        ...(file.type ? {} : { "Content-Disposition": "attachment" }),
      },
    });
  });

  return routes;
}
