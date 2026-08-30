import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import {
  parseYamlSubset,
  loadConfigFile,
  AgenticOsConfigSchema,
  PolicyDecisionSchema,
} from "./index.js";

const here = dirname(fileURLToPath(import.meta.url));
const defaultConfigPath = join(here, "..", "..", "..", "config", "agentic-os.yaml");

describe("parseYamlSubset", () => {
  it("parses nested mappings and inline maps", () => {
    const text = `
database:
  provider: sqlite
  path: .agentic-os/os.db

policy:
  default: require_approval
  capabilities:
    filesystem.read:
      decision: allow
    database.destructive:
      decision: deny
`;
    const parsed = parseYamlSubset(text) as Record<string, any>;
    expect(parsed["database"]["provider"]).toBe("sqlite");
    expect(parsed["database"]["path"]).toBe(".agentic-os/os.db");
    expect(parsed["policy"]["default"]).toBe("require_approval");
    expect(parsed["policy"]["capabilities"]["filesystem.read"]["decision"]).toBe("allow");
    expect(parsed["policy"]["capabilities"]["database.destructive"]["decision"]).toBe("deny");
  });
});

describe("loadConfigFile", () => {
  it("loads and validates the shipped default config", () => {
    const config = loadConfigFile(defaultConfigPath);
    expect(config.database.provider).toBe("sqlite");
    expect(config.policy.default).toBe("require_approval");
    expect(
      config.policy.capabilities["filesystem.read"]?.decision,
    ).toBe("allow");
    expect(
      config.policy.capabilities["database.destructive"]?.decision,
    ).toBe("deny");
  });

  it("rejects an invalid decision value", () => {
    const bad = {
      database: { provider: "sqlite", path: "x.db" },
      policy: { default: "allow", capabilities: { "a.b": { decision: "maybe" } } },
    };
    expect(() => AgenticOsConfigSchema.parse(bad)).toThrow();
  });

  it("policy decision enum allows only the three outcomes", () => {
    expect(PolicyDecisionSchema.options).toEqual([
      "allow",
      "deny",
      "require_approval",
    ]);
  });
});

describe("default config file sanity", () => {
  it("default config file exists and is non-empty", () => {
    const content = readFileSync(defaultConfigPath, "utf8");
    expect(content.trim().length).toBeGreaterThan(0);
  });
});
