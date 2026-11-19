// Ownership and history guardrails: snapshot protected trees before a run,
// compare after, and keep evidence refs inside the workspace.

import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";
import type { AgentRegistry } from "./types.js";

export interface GuardEntry {
  path: string;
  size: number;
  mtimeMs: number;
}

function walk(dir: string, root: string, out: GuardEntry[]): void {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) walk(full, root, out);
    else if (entry.isFile()) {
      const stat = statSync(full);
      out.push({
        path: relative(root, full),
        size: stat.size,
        mtimeMs: stat.mtimeMs,
      });
    }
  }
}

/** Protected dirs: every agent memory plus output dirs the task owner does not own. */
export function protectedDirs(registry: AgentRegistry, owner: string): string[] {
  const dirs = new Set<string>();
  for (const agent of Object.values(registry)) {
    dirs.add(agent.memoryDir);
    if (agent.id !== owner) for (const dir of agent.outputDirs) dirs.add(dir);
  }
  return [...dirs];
}

/** Recursive (path, size, mtimeMs) list under every protected dir; missing dirs are empty. */
export function snapshotProtected(
  workspaceRoot: string,
  registry: AgentRegistry,
  owner: string,
): string {
  const entries: GuardEntry[] = [];
  for (const dir of protectedDirs(registry, owner)) {
    const full = join(workspaceRoot, dir);
    if (existsSync(full)) walk(full, workspaceRoot, entries);
  }
  entries.sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
  return JSON.stringify(entries);
}

/** Paths added, removed or modified between two snapshots. */
export function diffSnapshots(before: string | null, after: string): string[] {
  const parse = (raw: string | null): Map<string, GuardEntry> => {
    const map = new Map<string, GuardEntry>();
    if (!raw) return map;
    try {
      for (const entry of JSON.parse(raw) as GuardEntry[]) map.set(entry.path, entry);
    } catch {
      /* an unreadable snapshot guards nothing; treat as empty */
    }
    return map;
  };
  const old = parse(before);
  const current = parse(after);
  const changed: string[] = [];
  for (const [path, entry] of current) {
    const prior = old.get(path);
    if (!prior || prior.size !== entry.size || prior.mtimeMs !== entry.mtimeMs)
      changed.push(path);
  }
  for (const path of old.keys()) if (!current.has(path)) changed.push(path);
  return changed.sort();
}

export function gitHead(workspaceRoot: string): string | null {
  try {
    return (
      execFileSync("git", ["rev-parse", "HEAD"], {
        cwd: workspaceRoot,
        encoding: "utf8",
        timeout: 5000,
        stdio: ["ignore", "pipe", "pipe"],
      }).trim() || null
    );
  } catch {
    return null;
  }
}

/** Evidence must be a workspace-relative path that exists and stays inside the root. */
export function evidenceExists(workspaceRoot: string, ref: string): boolean {
  if (typeof ref !== "string" || !ref.trim() || ref.startsWith("/")) return false;
  const full = resolve(workspaceRoot, ref);
  if (full !== workspaceRoot && !full.startsWith(workspaceRoot + sep)) return false;
  return existsSync(full);
}
