import { readFileSync } from "node:fs";

import {
  AgenticOsConfigSchema,
  type AgenticOsConfig,
} from "./schemas.js";

/**
 * Minimal, dependency-free YAML subset parser.
 *
 * Supports only what Phase 2 configuration needs:
 *   - 2-space-indented block mappings
 *   - scalar values (string, number, boolean, null)
 *   - unquoted and single/double-quoted strings
 *   - inline `{ decision: allow }` style single-level maps (used by capabilities)
 *
 * It intentionally does NOT implement the full YAML spec (flow sequences,
 * anchors, multi-line strings). Keeping it tiny avoids adding a YAML library
 * to the dependency tree for a configuration file that is fully expressible
 * in this subset. JSON is also accepted directly.
 */
export function parseYamlSubset(text: string): unknown {
  const lines = text.split(/\r?\n/);
  const root: Record<string, unknown> = {};
  // Stack of containers with their current indent level.
  type Frame = { indent: number; node: Record<string, unknown> };
  const stack: Frame[] = [{ indent: -1, node: root }];

  const inlineMap = (raw: string): Record<string, unknown> => {
    // e.g. `{ decision: allow }`
    const inner = raw.trim().replace(/^\{/, "").replace(/\}$/, "").trim();
    const out: Record<string, unknown> = {};
    if (!inner) return out;
    for (const part of inner.split(",")) {
      const sep = part.indexOf(":");
      if (sep === -1) continue;
      const key = part.slice(0, sep).trim();
      const val = part.slice(sep + 1).trim();
      out[key] = scalar(val);
    }
    return out;
  };

  const scalar = (raw: string): unknown => {
    const v = raw.trim();
    if (v === "" || v === "null" || v === "~") return null;
    if (v === "true") return true;
    if (v === "false") return false;
    if (/^-?\d+(\.\d+)?$/.test(v)) return Number(v);
    if (
      (v.startsWith('"') && v.endsWith('"')) ||
      (v.startsWith("'") && v.endsWith("'"))
    ) {
      return v.slice(1, -1);
    }
    return v;
  };

  for (const line of lines) {
    if (line.trim() === "" || line.trimStart().startsWith("#")) continue;
    const indent = line.length - line.trimStart().length;
    const trimmed = line.trim();

    // Pop frames deeper than or equal to current indent.
    while (stack.length > 1 && stack[stack.length - 1]!.indent >= indent) {
      stack.pop();
    }
    const parent = stack[stack.length - 1]!.node;

    const colon = trimmed.indexOf(":");
    if (colon === -1) continue;
    const key = trimmed.slice(0, colon).trim();
    const rest = trimmed.slice(colon + 1).trim();

    if (rest === "") {
      const child: Record<string, unknown> = {};
      parent[key] = child;
      stack.push({ indent, node: child });
    } else if (rest.startsWith("{")) {
      parent[key] = inlineMap(rest);
    } else {
      parent[key] = scalar(rest);
    }
  }

  return root;
}

/** Load and validate a config from a YAML or JSON file. */
export function loadConfigFile(path: string): AgenticOsConfig {
  const text = readFileSync(path, "utf8");
  const parsed =
    path.endsWith(".json") || path.endsWith(".jsonc")
      ? JSON.parse(text)
      : parseYamlSubset(text);
  return AgenticOsConfigSchema.parse(parsed);
}
