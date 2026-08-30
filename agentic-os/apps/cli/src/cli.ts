#!/usr/bin/env node
import { randomUUID } from "node:crypto";
import { existsSync } from "node:fs";

import {
  MissionStatusSchema,
  type MissionStatus,
  type CreateMissionInput,
} from "@agentic-os/core";
import { loadConfigFile } from "@agentic-os/config";
import { MissionCli, openMissionCli } from "./mission-cli.js";
import { formatMissionLine, formatMissionDetail } from "./format.js";

const DEFAULT_CONFIG = new URL("../../config/agentic-os.yaml", import.meta.url);

interface CliContext {
  dbPath: string;
  cli: MissionCli;
}

function resolveConfigPath(explicit?: string): string {
  if (explicit) return explicit;
  const candidate = DEFAULT_CONFIG.pathname;
  if (existsSync(candidate)) return candidate;
  // Fallback to the documented default location.
  return new URL("../../config/agentic-os.yaml", import.meta.url).pathname;
}

function bootstrap(explicitConfig?: string): CliContext {
  const configPath = resolveConfigPath(explicitConfig);
  const config = loadConfigFile(configPath);
  const cli = openMissionCli(config.database.path);
  return { dbPath: config.database.path, cli };
}

function parseAcceptance(flags: string[]): string[] {
  // Supports repeated --acceptance "..." or --acceptance=...
  const out: string[] = [];
  for (let i = 0; i < flags.length; i++) {
    const f = flags[i]!;
    if (f === "--acceptance" || f.startsWith("--acceptance=")) {
      const value = f.startsWith("--acceptance=")
        ? f.slice("--acceptance=".length)
        : flags[++i];
      if (value) out.push(value);
    }
  }
  return out;
}

function getFlag(flags: string[], name: string): string | undefined {
  for (let i = 0; i < flags.length; i++) {
    const f = flags[i]!;
    if (f === name) return flags[i + 1];
    if (f.startsWith(`${name}=`)) return f.slice(name.length + 1);
  }
  return undefined;
}

async function main(argv: string[]): Promise<number> {
  const [command, ...rest] = argv;
  if (!command) {
    console.error("Usage: agent-os mission <create|list|show|transition> ...");
    return 2;
  }

  if (command !== "mission") {
    console.error(`Unknown command: ${command} (expected 'mission')`);
    return 2;
  }

  const sub = rest[0];
  const args = rest.slice(1);

  if (!sub) {
    console.error("Usage: agent-os mission <create|list|show|transition>");
    return 2;
  }

  const { cli } = bootstrap(getFlag(args, "--config"));

  switch (sub) {
    case "create": {
      const title = getFlag(args, "--title");
      const objective = getFlag(args, "--objective");
      const priority = getFlag(args, "--priority") ?? "medium";
      const acceptance = parseAcceptance(args);
      if (!title) {
        console.error("mission create requires --title");
        return 2;
      }
      if (acceptance.length === 0) {
        console.error("mission create requires at least one --acceptance");
        return 2;
      }
      const input: CreateMissionInput = {
        id: randomUUID(),
        title,
        description: objective,
        acceptanceCriteria: acceptance,
        priority: priority as CreateMissionInput["priority"],
      };
      const mission = await cli.create(input);
      console.log(`Created mission ${mission.id}`);
      console.log(formatMissionDetail(mission));
      return 0;
    }

    case "list": {
      const statusFlag = getFlag(args, "--status");
      const status = statusFlag
        ? (MissionStatusSchema.parse(statusFlag) as MissionStatus)
        : undefined;
      const missions = await cli.list(status);
      if (missions.length === 0) {
        console.log("No missions.");
        return 0;
      }
      for (const m of missions) console.log(formatMissionLine(m));
      return 0;
    }

    case "show": {
      const id = args[0];
      if (!id) {
        console.error("mission show requires <id>");
        return 2;
      }
      const mission = await cli.get(id);
      if (!mission) {
        console.error(`Mission '${id}' not found`);
        return 1;
      }
      console.log(formatMissionDetail(mission));
      const plan = await cli.getLatestPlan(id);
      if (plan) {
        console.log(`\nLatest Plan (${plan.tasks.length} task(s)):`);
        for (const t of plan.tasks) console.log(`  - [${t.title}]`);
      }
      const history = await cli.history(id);
      if (history.length) {
        console.log(`\nTransition History (${history.length}):`);
        for (const h of history) {
          console.log(
            `  ${h.fromStatus} -> ${h.toStatus} @ ${h.createdAt}${h.reason ? ` (${h.reason})` : ""}`,
          );
        }
      }
      return 0;
    }

    case "transition": {
      const id = args[0];
      const next = args[1];
      if (!id || !next) {
        console.error("mission transition requires <id> <status>");
        return 2;
      }
      const status = MissionStatusSchema.parse(next) as MissionStatus;
      const reason = getFlag(args, "--reason");
      try {
        const updated = await cli.transition(id, status, reason);
        console.log(`Transitioned ${updated.id} -> ${updated.status}`);
      } catch (err) {
        console.error((err as Error).message);
        return 1;
      }
      return 0;
    }

    default:
      console.error(`Unknown mission subcommand: ${sub}`);
      return 2;
  }
}

// Only run when invoked as the entrypoint (not when imported by tests).
const invokedDirectly =
  process.argv[1] !== undefined &&
  import.meta.url === `file://${process.argv[1]}`;

if (invokedDirectly) {
  main(process.argv.slice(2))
    .then((code) => process.exit(code))
    .catch((err) => {
      console.error(err instanceof Error ? err.message : String(err));
      process.exit(1);
    });
}

export { main };
