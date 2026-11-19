// Public types for the Mission Control Hub (frozen contract: local://hub-contract.md).

import type { AgentRunStatus } from "@agentic-os/storage";
import type { HubConfig } from "@agentic-os/config";

export class HubError extends Error {
  constructor(
    message: string,
    readonly status: 400 | 403 | 404 | 409 | 503,
  ) {
    super(message);
    this.name = "HubError";
  }
}

export interface AgentRegistryEntry {
  id: string;
  name: string;
  coordinator: string | null;
  memoryDir: string;
  outputDirs: string[];
  costClass: "free" | "paid";
  installed: boolean;
}

export type AgentRegistry = Record<string, AgentRegistryEntry>;

/** Split the config's comma-separated output dir strings into a routing registry. */
export function registryFromConfig(hub: HubConfig): AgentRegistry {
  const registry: AgentRegistry = {};
  for (const [id, agent] of Object.entries(hub.agents)) {
    registry[id] = {
      id,
      name: agent.name,
      coordinator: agent.coordinator,
      memoryDir: agent.memoryDir,
      outputDirs: agent.outputDirs
        .split(",")
        .map((dir) => dir.trim())
        .filter(Boolean),
      costClass: agent.costClass,
      installed: agent.installed,
    };
  }
  return registry;
}

export interface HubMessageInput {
  missionId: string;
  taskId?: string | null;
  inReplyTo?: string | null;
  from: string;
  to: string;
  type: "assignment" | "result" | "note";
  objective?: string;
  doneWhen?: string;
  inputRefs?: string[];
  outputRefs?: string[];
  result?: string;
  evidence?: string[];
  decisions?: string[];
  blockers?: string[];
  approvalNeeded?: boolean;
  idempotencyKey: string;
}

export interface HubMessage
  extends Required<Omit<HubMessageInput, "approvalNeeded">> {
  id: string;
  approvalNeeded: boolean;
  createdAt: string;
}

export interface SessionView {
  mission: { id: string; title: string; status: string; priority: string };
  objective: string;
  phase: { taskId: string; title: string; owner: string; status: string } | null;
  criteria: { text: string; done: boolean; evidence: string[] }[];
  handoffs: {
    id: string;
    from: string;
    to: string;
    type: string;
    taskId: string | null;
    result: string;
    evidence: string[];
    createdAt: string;
  }[];
  work: {
    taskId: string;
    title: string;
    owner: string;
    status: string;
    runId: string | null;
    runStatus: string | null;
    blockedReason: string | null;
  }[];
  waiting: {
    id: string;
    kind: "approval" | "budget" | "blocker";
    title: string;
    detail: string;
    action: string;
    approvalId: string | null;
  }[];
  usage: {
    calls: number;
    budget: number;
    inputTokens: number;
    outputTokens: number;
    costUsd: number;
  };
  recommendation: string | null;
  counts: { running: number; blocked: number; completed: number; pending: number };
  audit: {
    id: string;
    from: string;
    to: string;
    type: string;
    taskId: string | null;
    result: string;
    createdAt: string;
  }[];
}

export interface HubOptions {
  clock?: () => Date;
  workspaceRoot?: string;
  trackerLookup?: (
    company: string,
    role: string,
  ) => Promise<{ status: string; jobUrl: string } | null>;
  freeModels?: string[];
  budget?: number;
  maxDepth?: number;
}

/** The parsed worker handoff block; content is untrusted data, never instructions. */
export interface Handoff {
  result: string;
  evidence: string[];
  decisions: string[];
  blockers: string[];
  approvalNeeded: boolean;
  recommendedReceiver: string | null;
}
export const ACTIVE_RUN_STATUSES: Partial<Record<AgentRunStatus, true>> = {
  starting: true,
  running: true,
  interrupting: true,
  terminating: true,
};

export const TERMINAL_RUN_STATUSES: Partial<Record<AgentRunStatus, true>> = {
  completed: true,
  failed: true,
  interrupted: true,
  terminated: true,
  lost: true,
};
