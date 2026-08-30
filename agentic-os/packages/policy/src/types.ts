import type { PolicyDecision, PolicyRequest, PolicyConfig } from "./schemas";

export type {
  PolicyDecision,
  ActionRisk,
  PolicyRequest,
  PolicyConfig,
  CapabilityRule,
} from "./schemas";

/**
 * The policy engine evaluates a {@link PolicyRequest} against a
 * {@link PolicyConfig} and returns one of three decisions.
 *
 * The result is intentionally narrow so that callers (CLI, API, runtime) have
 * a single place to branch on permission outcomes.
 */
export interface PolicyEvaluator {
  evaluate(request: PolicyRequest): PolicyDecision;
}
