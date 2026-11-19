# Dashboard, agentic-os and second brain wiring

> How the Command Center, Mission Control (agentic-os) and the second brain connect since 2026-11-12

_Saved: 2026-11-13T02:03:54Z_

Wired on 2026-11-12. Sources: dashboard-app/CLAUDE.md (Data sources: Connected systems on Today, Mission Control tab, Projects tab), agentic-os/README.md (apps/api), agentic-os/launchd/com.cloudtransition.mission-control.plist, .opencode/agents/scout.md.

- Mission Control: the agentic-os API runs always-on at 127.0.0.1:8787 under the LaunchAgent com.cloudtransition.mission-control, started from agentic-os/ because the database path .agentic-os/os.db is relative to the working directory. Starting it from apps/api/ opens a different, empty database.
- Dashboard to agentic-os: Today has a Mission Control row (open missions, pending approvals, active runs; Offline when the API does not answer). The Mission Control tab is a GET-only proxy: it reads, POSTs return 405 on purpose. Create missions, resolve approvals and start runs at http://localhost:8787 on the Mac.
- agentic-os to workspace: this workspace is registered in agentic-os as project Cloudtransition, so its launch form lists the workspace skills. Agents started there read AGENTS.md, which points them at second-brain/brain.py.
- Dashboard to second brain: Today has a Second brain row (sources, memories and catalogue time, read from second-brain/catalogue.md) that jumps to the Ask field. Answer cites link to /workspace-file/<path>. Run and Today have Reindex brain and Refresh map (visual-second-brain/refresh-index.py) as no-model tools.
- Projects: the Projects tab and Overview read live work from the project sections of TASKS.md (playbook, DevOps, Bogatyr lanes). The parked apps list stays in dashboard-app/app.py.
- Scout: OpenCode's built-in Web Search asks a one-time consent form. A non-interactive run cannot answer it and exits 1 after a finished scan. Scout's definition now denies the websearch action, which removes the tool. To use built-in web search, answer the form once in interactive opencode and remove the deny rule.
