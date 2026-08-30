import { describe, it, expect } from "vitest";
import { evaluatePolicy, createEvaluator, capabilityKey } from "./evaluate";
import { PolicyConfigSchema, PolicyRequestSchema, ActionRiskSchema } from "./schemas";

const config = PolicyConfigSchema.parse({
  default: "require_approval",
  capabilities: {
    "filesystem.read": { decision: "allow" },
    "filesystem.write": { decision: "allow" },
    "filesystem.delete": { decision: "require_approval" },
    "web.search": { decision: "allow" },
    "email.send": { decision: "require_approval" },
    "git.commit": { decision: "require_approval" },
    "deployment.production": { decision: "require_approval" },
    "database.destructive": { decision: "deny" },
  },
});

describe("capabilityKey", () => {
  it("joins capability and action with a dot", () => {
    expect(capabilityKey("filesystem", "delete")).toBe("filesystem.delete");
  });
});

describe("policy evaluation — exact rules", () => {
  it("allows filesystem.read", () => {
    expect(
      evaluatePolicy(config, {
        actor: "cli",
        capability: "filesystem",
        action: "read",
        risk: "read",
      }),
    ).toBe("allow");
  });

  it("allows filesystem.write", () => {
    expect(
      evaluatePolicy(config, {
        actor: "cli",
        capability: "filesystem",
        action: "write",
        risk: "write",
      }),
    ).toBe("allow");
  });

  it("requires approval for filesystem.delete", () => {
    expect(
      evaluatePolicy(config, {
        actor: "cli",
        capability: "filesystem",
        action: "delete",
        risk: "destructive",
      }),
    ).toBe("require_approval");
  });

  it("allows web.search", () => {
    expect(
      evaluatePolicy(config, {
        actor: "agent",
        capability: "web",
        action: "search",
        risk: "read",
      }),
    ).toBe("allow");
  });

  it("requires approval for email.send", () => {
    expect(
      evaluatePolicy(config, {
        actor: "agent",
        capability: "email",
        action: "send",
        risk: "external",
      }),
    ).toBe("require_approval");
  });

  it("requires approval for git.commit", () => {
    expect(
      evaluatePolicy(config, {
        actor: "agent",
        capability: "git",
        action: "commit",
        risk: "write",
      }),
    ).toBe("require_approval");
  });

  it("requires approval for deployment.production", () => {
    expect(
      evaluatePolicy(config, {
        actor: "agent",
        capability: "deployment",
        action: "production",
        risk: "destructive",
      }),
    ).toBe("require_approval");
  });

  it("denies database.destructive", () => {
    expect(
      evaluatePolicy(config, {
        actor: "agent",
        capability: "database",
        action: "destructive",
        risk: "destructive",
      }),
    ).toBe("deny");
  });
});

describe("policy evaluation — unknown capability fallback", () => {
  it("falls back to default (require_approval) for unknown capability", () => {
    expect(
      evaluatePolicy(config, {
        actor: "agent",
        capability: "unknown",
        action: "something",
        risk: "external",
      }),
    ).toBe("require_approval");
  });

  it("returns deny when default is deny", () => {
    const denyConfig = PolicyConfigSchema.parse({
      default: "deny",
      capabilities: {},
    });
    expect(
      evaluatePolicy(denyConfig, {
        actor: "agent",
        capability: "mystery",
        action: "x",
        risk: "read",
      }),
    ).toBe("deny");
  });
});

describe("policy evaluation — risk representation", () => {
  it("action risk is a closed enum and accepts all four values", () => {
    const risks = ActionRiskSchema.options;
    expect(risks).toEqual(["read", "write", "destructive", "external"]);
  });

  it("risk does not by itself change the decision (capability rule wins)", () => {
    expect(
      evaluatePolicy(config, {
        actor: "cli",
        capability: "filesystem",
        action: "delete",
        risk: "external",
      }),
    ).toBe("require_approval");
  });
});

describe("policy schema validation", () => {
  it("rejects a decision outside the allowed set", () => {
    expect(() =>
      PolicyConfigSchema.parse({
        default: "allow",
        capabilities: { "x.y": { decision: "maybe" } },
      }),
    ).toThrowError(/decision/);
  });

  it("rejects an invalid action risk in a request", () => {
    expect(() =>
      PolicyRequestSchema.parse({
        actor: "a",
        capability: "x",
        action: "y",
        risk: "explode",
      }),
    ).toThrowError(/risk/);
  });
});

describe("createEvaluator", () => {
  it("closes over config and evaluates consistently", () => {
    const evaluator = createEvaluator(config);
    expect(
      evaluator.evaluate({
        actor: "cli",
        capability: "filesystem",
        action: "read",
        risk: "read",
      }),
    ).toBe("allow");
  });
});
