import { z } from "zod";

// ── Policy decision ────────────────────────────────────────────────────────

/** Result of evaluating a policy request. */
export const PolicyDecisionSchema = z.enum(["allow", "deny", "require_approval"]);
export type PolicyDecision = z.infer<typeof PolicyDecisionSchema>;

// ── Action risk ──────────────────────────────────────────────────────────────

/** Risk classification of an action. */
export const ActionRiskSchema = z.enum(["read", "write", "destructive", "external"]);
export type ActionRisk = z.infer<typeof ActionRiskSchema>;

// ── Capability rule ──────────────────────────────────────────────────────────

/** A single capability rule stored in configuration. */
export const CapabilityRuleSchema = z.object({
  decision: PolicyDecisionSchema,
});
export type CapabilityRule = z.infer<typeof CapabilityRuleSchema>;

// ── Policy request ───────────────────────────────────────────────────────────

/** Context passed to the policy evaluator. */
export const PolicyRequestSchema = z.object({
  actor: z.string().min(1),
  capability: z.string().min(1),
  action: z.string().min(1),
  risk: ActionRiskSchema,
  resource: z.string().optional(),
});
export type PolicyRequest = z.infer<typeof PolicyRequestSchema>;

// ── Policy configuration ─────────────────────────────────────────────────────

export const PolicyConfigSchema = z.object({
  /** Decision applied when no explicit rule matches a capability. */
  default: PolicyDecisionSchema,
  /** Map of "capability.action" capability keys to their decisions. */
  capabilities: z.record(z.string(), CapabilityRuleSchema),
});
export type PolicyConfig = z.infer<typeof PolicyConfigSchema>;

export function parsePolicyConfig(input: unknown): PolicyConfig {
  return PolicyConfigSchema.parse(input);
}
