// Restart recovery: separate accepted results from merely exited processes.
// Never restarts a run; the caller re-arms subscriptions by subscribing again.

import type { AgentRunRecord, AgentRuntime } from "@agentic-os/runtime";
import { TERMINAL_RUN_STATUSES } from "./types.js";
import type { HubStore } from "./store.js";

export interface RecoveryHooks {
  processFinished(run: AgentRunRecord): void;
  pauseMission(missionId: string): void;
}

export function recoverHub(
  store: HubStore,
  runtime: AgentRuntime,
  hooks: RecoveryHooks,
  now: string,
): void {
  for (const missionId of store.listSessionMissionIds()) {
    for (const task of store.listTasks(missionId)) {
      if (task.status !== "in_progress" || !task.run_id) continue;
      const run = runtime.getRun(task.run_id);
      if (!run || !TERMINAL_RUN_STATUSES[run.status]) continue;
      if (store.messageByKey(`run:${run.id}`)) continue;
      if (run.status === "completed") {
        hooks.processFinished(run);
        continue;
      }
      store.updateTask(
        missionId,
        task.task_id,
        { status: "interrupted", blocked_reason: `run ${run.status} during restart` },
        now,
      );
      store.insertWaiting(
        {
          id: `recover:${run.id}`,
          mission_id: missionId,
          kind: "blocker",
          title: `Run for ${task.task_id} was ${run.status}`,
          detail: `The run ended ${run.status} while the supervisor was down; the task is interrupted, not completed.`,
          action: "resume to retry",
          approval_id: null,
        },
        now,
      );
      hooks.pauseMission(missionId);
    }
  }
}
