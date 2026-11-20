import { readdir, readFile, realpath, stat } from "node:fs/promises";
import { extname, join, sep } from "node:path";

export interface ArtifactRecord {
  /** POSIX path relative to the artifacts folder. */
  path: string;
  size: number;
  modifiedAt: string;
}

const MAX_DEPTH = 4;
const MAX_FILES = 200;
const MAX_BYTES = 20 * 1024 * 1024;
const TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".svg": "image/svg+xml",
  ".md": "text/plain; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".log": "text/plain; charset=utf-8",
  ".csv": "text/plain; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".pdf": "application/pdf",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
};
/** Agent-made pages get an opaque origin: their scripts run but cannot call this API. */
const ACTIVE = new Set([".html", ".svg"]);

/** Files under `root`, newest first. Dot files, symbolic links and deep trees are skipped. */
export async function listArtifacts(root: string): Promise<ArtifactRecord[]> {
  const found: ArtifactRecord[] = [];
  async function walk(directory: string, prefix: string, depth: number) {
    let entries;
    try {
      entries = await readdir(directory, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (entry.name.startsWith(".")) continue;
      const path = prefix ? `${prefix}/${entry.name}` : entry.name;
      if (entry.isDirectory()) {
        if (depth < MAX_DEPTH) await walk(join(directory, entry.name), path, depth + 1);
      } else if (entry.isFile()) {
        const info = await stat(join(directory, entry.name)).catch(() => null);
        if (info)
          found.push({ path, size: info.size, modifiedAt: info.mtime.toISOString() });
      }
    }
  }
  await walk(root, "", 1);
  return found
    .sort((a, b) => b.modifiedAt.localeCompare(a.modifiedAt) || a.path.localeCompare(b.path))
    .slice(0, MAX_FILES);
}

/** One artifact by its listed path, or null when the path leaves the folder or is not a file. */
export async function readArtifact(
  root: string,
  path: string,
): Promise<{ body: Buffer; headers: Record<string, string> } | null> {
  const parts = path.split("/");
  if (!path || path.includes("\0") || path.includes("\\") || parts.some((part) => !part || part.startsWith(".")))
    return null;
  try {
    const base = await realpath(root);
    const target = await realpath(join(base, ...parts));
    if (!target.startsWith(base + sep)) return null;
    const info = await stat(target);
    if (!info.isFile() || info.size > MAX_BYTES) return null;
    const extension = extname(target).toLowerCase();
    const type = TYPES[extension];
    return {
      body: await readFile(target),
      headers: {
        "Content-Type": type ?? "application/octet-stream",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
        ...(type ? {} : { "Content-Disposition": "attachment" }),
        ...(ACTIVE.has(extension)
          ? { "Content-Security-Policy": "sandbox allow-scripts" }
          : {}),
      },
    };
  } catch {
    return null;
  }
}
