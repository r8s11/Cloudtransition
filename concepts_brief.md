# Phase 1 — Unified Agent Registry (read-only)

* **Author:** R8S
* **Date:** 2026-11-17

## Overview

The Command Center dashboard (`dashboard-app/`, FastAPI + Jinja2, one user, launchd on the Mac, reachable on loopback and Tailscale) shows only four hardcoded job-hunting agents. The workspace actually holds 34 agent definition files for 13 distinct agents, spread over six folders and two formats (`.md`, `.toml`), plus per-agent state in `workspace/agents/<slug>/`.

Phase 1 extends `dashboard-app/core/agents.py` so the dashboard discovers every agent definition, picks one copy to display by a fixed folder order, lists the other copies, and links each agent to its existing memory and outputs. It is read-only: no new storage, no execution, no edits to definitions, no new write endpoints. The goal is a window into the agents that already exist, not a second agent system.

Review note: the Goldfish synthesizer could not spawn sub-reviewers in this harness. It applied all seven lenses in one fresh-context pass over the repo. Findings are evidence-backed but not independently cross-checked.

## Analysis

### Blocking objections

1. **A YAML agent registry already exists.** `agentic-os/config/agentic-os.yaml` (`hub.agents`, from line 37) lists 8 agents with `memoryDir`, `outputDirs`, `coordinator`, `costClass` and `installed`. `agentic-os/packages/hub/src/types.ts` loads it. It maps `specialized-chief-of-staff` to `workspace/agents/chief-of-staff/memory`, which does not exist and does not match the filename stem. Without a decision, the dashboard and Mission Control will show different agent lists (13 found on disk versus 8 configured).
2. **"Preferred definition" describes what is displayed, not what runs.** Each tool loads its own copy relative to where it runs: `opencode run --agent` reads root `.opencode/agents`, Claude Code at the root reads `.claude/agents`, and `dashboard-app/.claude` only loads when Claude runs inside `dashboard-app/`. The UI must say "copy shown", and label each copy with the tool and folder that loads it.
3. **Fixed precedence currently shows a stale copy.** `personal-growth-mentor` has two versions. The `.claude` copies (Nov 17) add a "Your Identity & Memory" section that the `.opencode` copy (Nov 16) lacks. Precedence picks `.opencode`. A plain "conflict" flag would hide that the newest edit is not the one shown.

### Secondary risks

4. **A "USB unmounted" warning can never render.** The launchd plist keeps the server alive only while the USB path exists, and the venv, app and templates live on the drive. The only reachable case is "drive mounted, but a definition or state folder is missing". The no-`mkdir` rule still matters: creating `/Volumes/SANDISK USB` while the drive is absent makes macOS mount it as `SANDISK USB 1` later.
5. **`/api/file` cannot serve part of the detail view.** `ALLOWED_EXTENSIONS` (`app.py:1967`) excludes `.toml`, `.jsonl`, `.pdf` and `.docx`, so Codex definitions, `log.jsonl` and cv-adapter's PDF/DOCX outputs return 403.
6. **Agent memory is already readable over the tailnet.** `privacy_violation()` allows every agent definition, memory and output path, including mentor memory. The detail view adds no new exposure, but it makes that memory one tap away on any tailnet device.
7. **Sync can lose memory lines.** The parrot sync is whole-file, newer-file-wins `rsync --update`. If both machines append to `log.jsonl`, the older file's new lines are lost. The registry must not label displayed memory as authoritative.

### Codebase facts that refine the concept

* **Copies:** 34 definition files, 13 agents.
  * Duplicated: gmail-reader ×3, each of the four impeccable-* agents ×3, organizational-psychologist ×2, personal-growth-mentor ×6, resume-tailor ×2, specialized-chief-of-staff ×5.
  * Single copy: forge, scout, job-reader, cv-adapter.
* **Conflicts under the body-hash rule:** 2 of the 9 duplicated agents. `personal-growth-mentor` has really drifted. `impeccable-asset-producer` differs only because its `.codex` copy rewrites `.claude/skills/...` to `.Codex/skills/...` (4 places). The capital C works on the case-insensitive Mac drive and breaks on Linux parrot.
* **No definition has an `id` field.** Frontmatter `name` is a display name and sometimes differs from the filename stem: `Chief of Staff`, `Personal Growth Mentor`, and others.
* **Frontmatter differs by tool.** `.opencode` uses `description, mode, permissions, steps`. `.claude` uses `name, description, tools, model, …`. `.codex` TOML puts the instructions in `developer_instructions`. `tomllib` is in the standard library.
* **State folders:** 5 exist (forge, scout, job-reader, cv-adapter, personal-growth-mentor). Mentor has no `outputs/`. `workspace/agents/README.md` is a file, not an orphan agent. Today no state folder lacks a definition.
* **Interviews code stays separate.** `application_agents`, `scout_leads` and `base_cv_path` hardcode cv-adapter, job-reader and scout paths, not the roster, so they stay untouched.
* **Tests:** `tests/test_agents.py` (15 tests) patches the module-level `AGENT_DEFS` and `AGENT_STATE`. Turning `AGENT_DEFS` into a list of folders breaks that fixture.
* **The dashboard already runs agents.** The Run tab's `mentor-checkin` card launches `--agent personal-growth-mentor`. "No execution" means the registry adds none, not that the dashboard never runs agents.
* **Discovery runs on every `/` render** (`build_agents_view()`, around `app.py:1543`). Putting every agent's instructions into the page would add about 200 KB per load over Tailscale, so load the detail view on demand.

### Ideal Final Result

One pure function, `discover(workspace) -> list[Agent]`, reads folders that already exist. It writes nothing, needs no config file, and replaces the four-agent list. Every claim the UI makes ("found in X", "version A", "memory present") can be checked directly against the filesystem.

### Contradictions resolved

* **One preferred copy versus each tool loading its own:** use precedence only to choose which body is shown. For each copy, show which tool loads it.
* **Warn on missing USB versus the app living on the USB:** in-app warnings cover missing subfolders only. Drive-level outage shows outside the app, as an unreachable server or a 502 from `tailscale serve`.
* **No registry.yaml versus the hub YAML:** the filesystem is the inventory (what exists). `agentic-os.yaml` is the routing and policy layer (who coordinates whom, installed). The dashboard can read both and flag differences, with no new storage.
* **Showing memory versus not claiming it is authoritative:** show the path and modified time next to the memory, and note that parrot sync may overwrite it.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  * Discover `.md` and `.toml` definitions in root `.opencode/agents`, `.claude/agents` and `.codex/agents`, and in `dashboard-app/.claude/agents`, `.codex/agents` and `.github/agents`.
  * ID = filename stem.
  * Fixed precedence picks the displayed copy: root `.opencode` > `.claude` > `.codex` > `dashboard-app/.claude` > `dashboard-app/.codex` > `dashboard-app/.github`.
  * Group copies into versions by a hash of the normalized instruction body, showing copy count and newest modified time per version.
  * Label each copy with the tool and folder that loads it.
  * Link each agent to `workspace/agents/<slug>/` (`memory/index.md`, `memory/log.jsonl`, `outputs/`). Agents without these show "not initialized".
  * Agents tab lists all discovered agents. `ROSTER_ORDER` becomes display order only.
  * Warnings:
    * definition folder missing
    * frontmatter or TOML fails to parse
    * more than one version
    * state folder with no definition
  * Read-only detail view loaded on demand through the existing `/api/file` for `.md` content. Other file types are listed by path only.
  * Latest output shown as filename and modified time.
  * pytest coverage for discovery, duplicates and versions, missing files and folders, and deterministic selection.
* **Out-of-Scope Non-Goals:**
  * Execution, chat, model picker, new write endpoints
  * Authentication framework, or any claim of per-agent isolation
  * Merging, migrating or rewriting any definition
  * A new registry file, database or cache
  * Changes to the parrot sync
  * Widening the `/api/file` allowlist or privacy rules
  * Changes to the Interviews card helpers

## Alternatives Weighed

* **Merge duplicates into one canonical file.** Rejected by author: it breaks each tool's own loader and changes existing CLI workflows.
* **A new `registry.yaml` or `agents.json`.** Rejected by author: it duplicates `agentic-os.yaml` and goes stale after every sync.
* **Use frontmatter `name` as the ID.** Rejected in review: names contain spaces and differ between tools ("Chief of Staff" versus `specialized-chief-of-staff`).
* **Read an explicit `id` from metadata first.** Rejected in review: no file has one, so this code path would never run.
* **Pick the preferred copy by newest modified time.** Rejected in review: rsync moves modified times between machines, so the choice would not be deterministic.
* **A binary "conflict" flag.** Rejected in review: it hides which copy is newest. Version groups replace it.
* **A "USB unmounted" in-app warning.** Rejected in review: the server cannot run without the drive.
* **A new `GET /api/agents/{id}` endpoint.** Rejected in review: not needed if the detail view uses `/api/file` for `.md` and shows paths for the rest.
* **Put full instructions inside every agent card.** Rejected in review: it adds about 200 KB to every page load.
* **Add agent memory to the privacy rules now.** Deferred: it changes the Workspace map indexer and needs its own decision.

## Key Decisions & Staging for Next Steps

**Settled:**

* The dashboard is the first consumer.
* `.opencode` copies take precedence for display.
* `core/agents.py` is extended in place.
* The existing `workspace/agents/<slug>/` folders are the brain.
* The registry is read-only.
* CLI agents keep writing files directly.
* No isolation claims.
* No auth framework.
* The `X-Requested-With` check is not authentication.

**Open, to settle before `/egm-draft`:**

1. **Hub YAML:** is `agentic-os.yaml` `hub.agents` ignored, shown alongside the discovered list, or reconciled? Should the `chief-of-staff` path mismatch be flagged?
2. **Path differences:** is the `.claude/skills` → `.Codex/skills` rewrite an expected per-tool difference, a conflict, or a bug to report? It is also case-wrong on Linux.
3. **Stale copy:** should the older `.opencode` copy of `personal-growth-mentor` still be the one displayed, with the newer version shown in the version list?
4. **Exposure:** should mentor memory and chief-of-staff instructions be viewable from every tailnet device?
5. **Writers:** does parrot run any agent that writes `workspace/agents/*/memory/log.jsonl`? If not, record "Mac is the only writer".
6. **Unused folders:** should copies the root tools never load (`dashboard-app/.claude`, `.codex`, `.github`) be labelled "not loaded from workspace root"? Is the `.github` file without the `.agent.md` suffix a real definition?
7. **Output summary:** is the newest output's filename and time enough, especially for cv-adapter's PDF and DOCX files?

**Not checked in review:** `pages/agents.html` past line 50, the Mission Control UI, Copilot's file-suffix rules, and whether uvicorn survives an unmount.
