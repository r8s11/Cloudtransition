import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { z } from "zod";
import { serve } from "@hono/node-server";
import { loadConfigFile } from "@agentic-os/config";
import { Database } from "@agentic-os/storage";
import { AgentRuntime, defaultAdapters, opencodeAdapter } from "@agentic-os/runtime";
import { Hub, registryFromConfig } from "@agentic-os/hub";

import { createApp } from "./index.js";
import { openMissionService } from "./mission-service.js";
const DEFAULT_CONFIG = new URL(
  "../../../config/agentic-os.yaml",
  import.meta.url,
);

function resolveConfigPath(explicit?: string): string {
  if (explicit) return explicit;
  // fileURLToPath decodes %20 etc.; URL.pathname would leave "SANDISK%20USB".
  return fileURLToPath(DEFAULT_CONFIG);
}

const trackerResponse = z.object({
  row: z.object({ status: z.string(), url: z.string().optional() }).optional(),
});

async function main(argv: string[]): Promise<void> {
  const configPath =
    argv[0] ?? process.env.AGENTIC_OS_CONFIG ?? resolveConfigPath();
  const config = loadConfigFile(configPath);
  const db = Database.open(config.database.path);
  const hubConfig = config.hub;
  const freeModels = hubConfig
    ? hubConfig.freeModels.split(",").map((m) => m.trim()).filter(Boolean)
    : [];
  const adapters = hubConfig
    ? [
        ...defaultAdapters(),
        opencodeAdapter({
          executable: hubConfig.opencodeExecutable,
          models: freeModels,
          agents: Object.entries(hubConfig.agents)
            .filter(([, agent]) => agent.installed)
            .map(([id]) => id),
        }),
      ]
    : undefined;
  let runtime: AgentRuntime;
  try {
    runtime = new AgentRuntime(db, adapters);
  } catch (error) {
    db.close();
    throw error;
  }
  const service = openMissionService(db);
  let hub: Hub | undefined;
  if (hubConfig) {
    const trackerBase = hubConfig.trackerUrl ?? "http://127.0.0.1:8000";
    const instance = new Hub(db, runtime, service, registryFromConfig(hubConfig), {
      workspaceRoot: hubConfig.workspaceRoot ?? resolve(process.cwd(), ".."),
      budget: hubConfig.budget,
      maxDepth: hubConfig.maxDepth,
      freeModels,
      trackerLookup: async (company, role) => {
        const res = await fetch(
          `${trackerBase}/api/interviews/detail?company=${encodeURIComponent(company)}&role=${encodeURIComponent(role)}`,
        );
        if (!res.ok) return null;
        const parsed = trackerResponse.safeParse(await res.json());
        if (!parsed.success || !parsed.data.row) return null;
        return { status: parsed.data.row.status, jobUrl: parsed.data.row.url ?? "" };
      },
    });
    instance.recover();
    runtime.subscribe((run) => instance.handleRunFinished(run));
    hub = instance;
  }
  const app = createApp(db, { service, runtime, hub });

  const port = Number(process.env.PORT ?? 8787);
  const server = serve(
    { fetch: app.fetch, port, hostname: "127.0.0.1" },
    (info) => {
      console.log(`Mission Control running at http://localhost:${info.port}`);
    },
  );

  let stopping = false;
  const shutdown = async () => {
    if (stopping) return;
    stopping = true;
    const closed = Promise.withResolvers<void>();
    server.close(() => closed.resolve());
    let exitCode = 0;
    try {
      await runtime.shutdown();
      await closed.promise;
    } catch (error) {
      console.error(error instanceof Error ? error.message : String(error));
      exitCode = 1;
    } finally {
      db.close();
    }
    process.exit(exitCode);
  };
  process.on("SIGINT", () => {
    void shutdown();
  });
  process.on("SIGTERM", () => {
    void shutdown();
  });
}

main(process.argv.slice(2)).catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
