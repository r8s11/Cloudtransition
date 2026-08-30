import { z } from "zod";

// ── Database config ─────────────────────────────────────────────────────────

export const DatabaseConfigSchema = z.object({
  provider: z.literal("sqlite"),
  path: z.string().min(1),
});
export type DatabaseConfig = z.infer<typeof DatabaseConfigSchema>;

// ── Policy config ───────────────────────────────────────────────────────────

export const PolicyDecisionSchema = z.enum(["allow", "deny", "require_approval"]);
export type PolicyDecision = z.infer<typeof PolicyDecisionSchema>;

export const CapabilityRuleSchema = z.object({
  decision: PolicyDecisionSchema,
});
export type CapabilityRule = z.infer<typeof CapabilityRuleSchema>;

export const PolicyConfigSchema = z.object({
  default: PolicyDecisionSchema,
  capabilities: z.record(z.string(), CapabilityRuleSchema),
});
export type PolicyConfig = z.infer<typeof PolicyConfigSchema>;

// ── Root config ─────────────────────────────────────────────────────────────

export const AgenticOsConfigSchema = z.object({
  database: DatabaseConfigSchema,
  policy: PolicyConfigSchema,
});
export type AgenticOsConfig = z.infer<typeof AgenticOsConfigSchema>;

export function parseConfig(input: unknown): AgenticOsConfig {
  return AgenticOsConfigSchema.parse(input);
}
