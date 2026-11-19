# Brain

Personal OpenCode home base for phone chat and delegated work across `Cloudtransition`. The primary **Brain** agent handles this directory and uses the **workspace** subagent for parent/sibling projects.

No custom app or additional runtime is required. This uses the installed OpenCode V2 server, web UI/app, and Tailscale.

## Connect a phone

On this computer:

```sh
cd /home/r8s/code/Cloudtransition/bot
./start.sh
```

The command restricts OpenCode's shared background service to loopback (restarting it if its binding must change), exposes it through **tailnet-only HTTPS port 8443**, then prints a one-time pairing link and QR code. It leaves the existing HTTPS service on port 443 unchanged.

On the phone:

1. Connect Tailscale to the same tailnet.
2. Scan the QR code with the OpenCode app, or open the printed link in the browser. Links work once and expire after five minutes; authenticated sessions last 30 days.
3. Start a session in the `bot` location. New sessions use **Brain** automatically. An existing session keeps its stored agent selection.

Run `./start.sh` again for a fresh pairing link or after a reboot if the service is unavailable. Do not use `opencode pair --remote` or Tailscale Funnel for this setup; neither is needed for private tailnet access.

## Chat and delegate

Examples:

- “Update the Brain startup instructions.”
- “Inspect `dashboard-app` and propose the smallest fix.”
- “Delegate the `job-autofill` test failure to workspace.”

Brain handles home-base changes directly and delegates parent/sibling work to `workspace`. Attach the `workspace` reference when you want to point the client at the whole parent tree. Reading is allowed when task-relevant; edits outside `bot/`, shell commands, and unrecognized external actions require approval.

Project-specific instructions and checks still apply. In particular, `dashboard-app` has macOS-only service steps and `job-autofill` has a Python-helper test stage. These projects are delegated targets, not dependencies of Brain.

## Personalize

- `AGENTS.md`: standing behavior, routing, privacy, and safety rules.
- `.opencode/agents/brain.md`: primary assistant role.
- `.opencode/agents/workspace.md`: delegated workspace worker.
- `opencode.jsonc`: agent selection, scoped references, and permission rules.
- `tools/`: personal utilities. No weather provider or other external integration is configured yet.

## Verify

```sh
cd /home/r8s/code/Cloudtransition/bot
bash -n start.sh
opencode debug config
opencode debug agents
```

The repository root's `.gitignore` ignores `*.json`, so this configuration intentionally uses `opencode.jsonc`, which remains trackable.
