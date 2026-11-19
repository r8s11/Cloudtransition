# Pomodoro Timer for Orca

A Pomodoro focus timer in Orca's right sidebar. It runs focus sessions, short breaks and long breaks, and sends a desktop notification when each one ends.

## Use

- Open the **Pomodoro** panel (lightning icon) in the right sidebar. It has **Start/Pause**, **Skip** and **Reset** buttons.
- Command palette:
  - **Pomodoro: Start or Pause**
  - **Pomodoro: Skip to Next Phase**
  - **Pomodoro: Reset Current Phase**
- Settings → Plugins → Pomodoro Timer sets the focus, short-break and long-break lengths (25, 5 and 15 minutes by default) and how many focus sessions come before a long break (4). It can also start the next phase automatically (off by default).

Only a focus session that runs to the end counts toward the long break and **today** total. Skipping a focus session goes to a break without counting it. A long break starts the cycle again.

## How it works

| File | Role |
| --- | --- |
| `src/timer.ts` | Pure state machine: start, pause, reset, advance and reconcile. It takes `now` as an argument and never reads the clock. |
| `src/worker.ts` | Owns the timer. It keeps state in plugin storage, sets a wake-up for the end of the phase and sends the notification. It also answers panel requests and palette commands. |
| `src/panel.tsx` | Components panel. It draws what the worker reports. The countdown is a `RelativeTime` that Orca keeps current, so the panel does not poll. |
| `src/protocol.ts` | Panel and worker request and event types. |

Timer state is stored, not held in memory, so the worker can restart without losing a session. Orca stops idle workers, and saving a file also restarts the worker. When the worker starts, and on every request or command, it first finishes any phase that ended while it was stopped. An open panel also asks once, just after the phase ends. If the worker is stopped while no panel is open, the **done** notification may arrive late: it arrives the next time the worker runs.

## Access it asks for

`trusted-worker` (its own Node process), `storage:own`, `settings:own`, `notifications:show`. It makes no network requests and cannot read terminals or workspaces.

## Develop

```bash
orca plugin test .            # unit tests for timer, worker and panel
orca plugin check .           # renders the panel when idle, running and paused
orca plugin dev watch . --check --shot .orca/shots
```

Orca 1.4.247 does not ship the `orca.d.ts` files that `orca plugin types` copies, so `.orca/types` cannot be written and `tsc` or editor type checks report missing `orca` modules. `orca plugin test` and `orca plugin check` run normally.
