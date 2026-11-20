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

// ── Hub config (Mission Control Hub) ────────────────────────────────────────

export const HubAgentSchema = z.object({
  name: z.string().min(1),
  /** Coordinating agent id, or null for a top-level coordinator. */
  coordinator: z.string().nullable(),
  memoryDir: z.string().min(1),
  /** Comma-separated workspace-relative output dirs the agent owns. */
  outputDirs: z.string().min(1),
  costClass: z.enum(["free", "paid"]),
  installed: z.boolean(),
});
export type HubAgent = z.infer<typeof HubAgentSchema>;

export const HubConfigSchema = z.object({
  budget: z.number().int().positive(),
  maxDepth: z.number().int().positive(),
  /** Comma-separated free OpenCode model ids. */
  freeModels: z.string().min(1),
  /** Trusted override of the opencode executable (verification harnesses). */
  opencodeExecutable: z.string().min(1).optional(),
  /** Workspace root for evidence refs and guard snapshots; default: parent of cwd. */
  workspaceRoot: z.string().min(1).optional(),
  /** Base URL of the tracker read API used by prepare; default Command Center. */
  trackerUrl: z.string().min(1).optional(),
  agents: z.record(z.string(), HubAgentSchema),
});
export type HubConfig = z.infer<typeof HubConfigSchema>;

// ── Root config ─────────────────────────────────────────────────────────────

export const AgenticOsConfigSchema = z.object({
  database: DatabaseConfigSchema,
  policy: PolicyConfigSchema,
  hub: HubConfigSchema.optional(),
});
export type AgenticOsConfig = z.infer<typeof AgenticOsConfigSchema>;

export function parseConfig(input: unknown): AgenticOsConfig {
  return AgenticOsConfigSchema.parse(input);
}
