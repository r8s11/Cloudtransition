// Mailbox: loopback boundary, coordinator routing, idempotent delivery.
// Message content is untrusted data; it never grants permissions.

import { randomUUID } from "node:crypto";
import type { Database } from "@agentic-os/storage";
import { HubError, type AgentRegistry, type HubMessage, type HubMessageInput } from "./types.js";
import { HubStore, readLatestPlan } from "./store.js";

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);

function loopbackHost(value: string): boolean {
  let host = value.trim().toLowerCase();
  if (host.startsWith("[")) host = host.slice(1, host.indexOf("]"));
  else if (host.includes(":") && host.split(":").length === 2) host = host.split(":")[0]!;
  return LOOPBACK_HOSTS.has(host);
}

function loopbackAddress(value: string): boolean {
  const addr = value.trim().toLowerCase();
  return (
    addr === "127.0.0.1" ||
    addr === "::1" ||
    addr === "::ffff:127.0.0.1" ||
    addr.startsWith("127.")
  );
}

/** Mailbox writes are loopback-only: host, origin (when present) and peer address. */
export function assertLoopbackRequest(req: {
  host?: string;
  origin?: string;
  remoteAddress?: string;
}): void {
  if (!req.host || !loopbackHost(req.host))
    throw new HubError("mailbox writes are loopback-only", 403);
  if (req.origin) {
    let originHost: string;
    try {
      originHost = new URL(req.origin).hostname;
    } catch {
      throw new HubError("mailbox writes are loopback-only", 403);
    }
    if (!LOOPBACK_HOSTS.has(originHost.toLowerCase()))
      throw new HubError("mailbox writes are loopback-only", 403);
  }
  if (req.remoteAddress && !loopbackAddress(req.remoteAddress))
    throw new HubError("mailbox writes are loopback-only", 403);
}

function refusal(
  store: HubStore,
  input: HubMessageInput,
  reason: string,
  now: string,
): { ok: false; reason: string } {
  store.audit(
    input.missionId,
    "refused",
    `${input.from} -> ${input.to} (${input.type}): ${reason}`,
    now,
  );
  return { ok: false, reason };
}

/** Explicit task relationship: one task dependsOn the other, across the two owners. */
function taskRelationship(
  db: Database,
  missionId: string,
  from: string,
  to: string,
): boolean {
  const latest = readLatestPlan(db, missionId);
  if (!latest) return false;
  const tasks = latest.plan.tasks;
  const fromTasks = tasks.filter((task) => task.owner === from);
  const toTasks = tasks.filter((task) => task.owner === to);
  return fromTasks.some((a) =>
    toTasks.some(
      (b) => (a.dependsOn ?? []).includes(b.id) || (b.dependsOn ?? []).includes(a.id),
    ),
  );
}

/** Route one external message. Refusals are audited and store nothing. */
export function ingestMessage(
  db: Database,
  store: HubStore,
  registry: AgentRegistry,
  input: HubMessageInput,
  now: string,
): { ok: boolean; reason?: string; id?: string } {
  const existing = store.messageByKey(input.idempotencyKey);
  if (existing) return { ok: true, id: existing.id };

  if (!store.getSession(input.missionId))
    return refusal(store, input, "mission has no hub session", now);
  if (input.to === "*") return refusal(store, input, "broadcast messages are not allowed", now);
  const fromKnown = input.from === "roosevelt" || Boolean(registry[input.from]);
  if (!fromKnown) return refusal(store, input, `unknown agent '${input.from}'`, now);
  if (!registry[input.to]) return refusal(store, input, `unknown agent '${input.to}'`, now);

  const coordinatorOfTo = registry[input.to]!.coordinator;
  const coordinatorOfFrom = registry[input.from]?.coordinator ?? null;
  if (input.type === "assignment") {
    if (input.from !== "roosevelt" && coordinatorOfTo !== input.from)
      return refusal(store, input, "assignments flow coordinator to subordinate or roosevelt to any", now);
  } else if (input.type === "result") {
    const ownsTask = store.listTasks(input.missionId).some((task) => task.owner === input.from);
    if (coordinatorOfFrom !== input.to || !ownsTask)
      return refusal(store, input, "results flow from a task owner to its coordinator", now);
  } else {
    const related =
      input.from === "roosevelt" ||
      coordinatorOfTo === input.from ||
      coordinatorOfFrom === input.to ||
      taskRelationship(db, input.missionId, input.from, input.to);
    if (!related)
      return refusal(store, input, "no explicit task relationship between these agents", now);
  }

  const message: HubMessage = {
    id: randomUUID(),
    missionId: input.missionId,
    taskId: input.taskId ?? null,
    inReplyTo: input.inReplyTo ?? null,
    from: input.from,
    to: input.to,
    type: input.type,
    objective: input.objective ?? "",
    doneWhen: input.doneWhen ?? "",
    inputRefs: input.inputRefs ?? [],
    outputRefs: input.outputRefs ?? [],
    result: input.result ?? "",
    evidence: input.evidence ?? [],
    decisions: input.decisions ?? [],
    blockers: input.blockers ?? [],
    // Stored as data only: content never creates approvals or grants capabilities.
    approvalNeeded: input.approvalNeeded ?? false,
    idempotencyKey: input.idempotencyKey,
    createdAt: now,
  };
  store.insertMessage(message);
  return { ok: true, id: message.id };
}
