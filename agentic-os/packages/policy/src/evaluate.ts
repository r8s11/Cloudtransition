import { PolicyConfigSchema } from "./schemas";
import type { PolicyConfig, PolicyDecision, PolicyRequest } from "./schemas";
import type { PolicyEvaluator } from "./types";

/**
 * Build the capability key used to look up a rule.
 *
 * Rules are keyed as `"capability.action"` (e.g. `"filesystem.delete"`).
 * If no exact `capability.action` rule exists, we fall back to a
 * `"capability.*"` wildcard rule (e.g. `"email.*"`), then to the configured
 * default decision.
 */
export function capabilityKey(capability: string, action: string): string {
  return `${capability}.${action}`;
}

/**
 * Evaluate a policy request against a configuration.
 *
 * Resolution order:
 *   1. exact `capability.action` rule
 *   2. wildcard `capability.*` rule
 *   3. configured `default` decision
 *
 * The default decision (typically `require_approval`) is the safe fallback for
 * unknown capabilities — nothing is silently allowed.
 */
export function evaluatePolicy(config: PolicyConfig, request: PolicyRequest): PolicyDecision {
  const parsed = PolicyConfigSchema.parse(config);
  const exact = capabilityKey(request.capability, request.action);

  const exactRule = parsed.capabilities[exact];
  if (exactRule) return exactRule.decision;

  const wildcard = `${request.capability}.*`;
  const wildcardRule = parsed.capabilities[wildcard];
  if (wildcardRule) return wildcardRule.decision;

  return parsed.default;
}

/** Factory that closes over a configuration to produce a {@link PolicyEvaluator}. */
export function createEvaluator(config: PolicyConfig): PolicyEvaluator {
  return {
    evaluate(request: PolicyRequest): PolicyDecision {
      return evaluatePolicy(config, request);
    },
  };
}
