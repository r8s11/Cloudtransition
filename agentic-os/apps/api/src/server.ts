import { serve } from "@hono/node-server";
import { loadConfigFile } from "@agentic-os/config";
import { Database } from "@agentic-os/storage";

import { createApp } from "./index.js";

const DEFAULT_CONFIG = new URL("../../../config/agentic-os.yaml", import.meta.url);

function resolveConfigPath(explicit?: string): string {
  if (explicit) return explicit;
  return DEFAULT_CONFIG.pathname;
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

main(process.argv.slice(2)).catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
