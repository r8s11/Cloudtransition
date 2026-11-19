# Agent registry and agent card runs

`core/agents.py` `discover_agents()` builds the Agents tab from files that already exist. It writes, creates, moves and deletes nothing. There is no registry file of its own.

## Sources

| What | Where | Role |
| --- | --- | --- |
| Definitions | the six folders below | Which agents exist and what their instructions say |
| Hub config | `agentic-os/config/agentic-os.yaml` → `hub.agents` | Coordinator, cost class, `installed`, configured memory/output folders |
| Brain | `workspace/agents/<id>/` (`memory/index.md`, `memory/log.jsonl`, `outputs/`) | What the agent has recorded and produced |

Terms used on the page:

- **Discovered**: at least one definition file exists.
- **Registered**: `agentic-os.yaml` lists the ID.
- **Loadable**: at least one copy sits where a CLI tool documents reading it.
- **Shown**: the one copy the dashboard displays. It is not proof of what ran, because each tool loads its own copy.

## Definition folders, in display precedence

The ID is the filename stem; for Copilot, `x.agent.md` becomes `x`. The first readable copy in this order is the one shown. Precedence is fixed: modification times move with the parrot rsync, so they would not give a stable choice. Copies whose instructions are identical after collapsing whitespace form one version; any other difference makes a separate version. Nothing is merged.

| Folder | Tool | Load status | Basis (checked 2026-11-17) |
| --- | --- | --- | --- |
| `.opencode/agents/*.md` | OpenCode | active | opencode.ai/docs/agents: `.opencode` folders are found from the working folder upward |
| `.claude/agents/*.md` | Claude Code | active | code.claude.com/docs/en/sub-agents: every `.claude/agents/` from the working folder up to the repo root is scanned; the closest copy wins |
| `.codex/agents/*.toml` | Codex | active | Codex custom agents: project `.codex/agents/*.toml` with required `name`, `description`, `developer_instructions`; the project must be trusted |
| `dashboard-app/.claude/agents/*.md` | Claude Code | scoped | Read only when Claude Code runs inside `dashboard-app/`; there it overrides a root copy of the same name |
| `dashboard-app/.codex/agents/*.toml` | Codex | unverified | A nested `.codex/agents/` is not documented |
| `dashboard-app/.github/agents/*.md` | GitHub Copilot | unverified | Copilot reads `.github/agents/*.agent.md` at the repository root. This folder is nested, and its file lacks the `.agent.md` suffix |

A copy is downgraded to **unverified** when it cannot be read, its TOML does not parse, or the TOML lacks a field Codex requires. Codex matches agents by their `name` field, not the filename.

## Inventory on 2026-11-17

There were 34 definition files for 13 agents. 8 of the agents are registered in the hub.

| ID | Copies | Versions | Brain | Notes |
| --- | --- | --- | --- | --- |
| forge, scout, job-reader, cv-adapter | 1 each (`.opencode`) | 1 | memory + outputs | Job-search team |
| gmail-reader | 3 | 1 | none | Not in hub |
| impeccable-asset-producer | 3 | 2 | none | `.codex` copy uses `.Codex/skills/` (capital C), which fails on Linux |
| impeccable-documenter, -finish-reviewer, -manual-edit-applier | 3 each | 1 | none | Not in hub |
| organizational-psychologist, resume-tailor | 2 each (`dashboard-app/` only) | 1 | none | Hub: `installed: false`; hub folders do not exist |
| personal-growth-mentor | 6 | 2 | memory, no outputs | The `.claude` copies (2026-11-17) add about 70 lines, including "Your Identity & Memory". The shown `.opencode` copy is older |
| specialized-chief-of-staff | 5 | 1 | none | Hub `memoryDir` is `workspace/agents/chief-of-staff/memory`. That does not match the ID, and the folder does not exist |

The page computes all of this live. These counts are a snapshot, not hardcoded values.

## Who writes agent memory

**Policy: the Mac is the single writer of `workspace/agents/*/memory/`.** Agent runs that write memory, including every dashboard run, happen on the Mac. The dashboard server only runs there. The policy was checked on 2026-11-17:

- parrot has no crontab and no user timers that run agents.
- parrot has no `opencode` and no `codex`.
- parrot's `workspace/agents/*/memory` files are equal to or older than the Mac's.

parrot **does** have `claude` (`~/.local/bin/claude`). A manual Claude Code session there, for example one using `personal-growth-mentor` (whose `.claude` copy has a memory section), could append to `log.jsonl`.

The sync is whole-file and newer-file-wins (`rsync --update`). If both machines append to the same `log.jsonl` between syncs, the older file's new lines are lost without notice. Until there is an explicit conflict strategy, keep agent runs that write memory on the Mac. Do not add a second writer, such as a dashboard memory API, before choosing either a single writer or per-machine log files. The page labels memory as "observed on this machine" for this reason.

## Exposure (existing, not changed by this feature)

- The dashboard has no authentication. It listens on loopback, and `tailscale serve` exposes it to tailnet devices. `X-Requested-With` blocks cross-site form posts; it does not authenticate.
- `/api/file` serves any workspace `.md/.txt/.yaml/.yml/.json/.csv/.html/.py` file that passes `privacy_violation()`. Agent definitions, memory (`index.md`) and outputs all pass. So mentor memory is readable from any tailnet device whether or not the page shows it.
- The page shows memory text inline only for `MEMORY_CONTENT_AGENTS` (the job-search team, which it showed before). Every other agent is metadata-only. That is a display choice, not access control. Restricting access means adding `workspace/agents/*/memory` to the privacy rules, which also affects the Workspace map indexer and needs its own review.
- This feature adds no endpoint and does not widen any allowlist.

## Register another agent

1. Add one definition where the tool you use will load it, for example `.opencode/agents/<id>.md` with `description:` frontmatter. The filename stem becomes the ID.
2. Optional: add a `hub.agents.<id>` entry in `agentic-os.yaml` with `memoryDir: workspace/agents/<id>/memory` and `outputDirs: workspace/agents/<id>/outputs`.
3. Optional: create `workspace/agents/<id>/memory/` when the agent first records something. Until then the page shows "No memory initialized".

No dashboard code changes. The page lists the agent on its next load.

## Running an agent from its card (Phase 2)

`AGENT_CARD_RUNNERS` in `core/config.py` maps an agent ID to an existing runner card. Today the only entry is `job-reader` → `job-reader`. The card embeds the same run grid as the Run and Interviews tabs. Starting a run goes through the existing `/api/skills/run`, `_resolve_run` and `_execute_run` (`routes/runs.py`), which provide the model check, input pattern, logging and output file. The Interviews tab's "Read posting" button still fills its own card.

**What a run records.** Each record appears in `/api/skills/runs` and in the start and finish events in `runs.log`:

- `agent`, `runner` (`opencode-agent`), `provider`, `model`
- `cwd` (the workspace root), `started`, `finished`, `status`, `exit_code`, `output` (`dashboard-app/runs/<id>.txt`), `log` (`runs.log`)
- `definition.path`: the copy the dashboard expects OpenCode to load (`.opencode/agents/<id>.md`)
- `definition.sha256`: the exact file bytes, hashed when the run is requested
- `definition.version`: the registry's hash of the normalized instructions
- `definition.check` and `definition.detail`: the outcome of the comparison below
- `definition.permissions`: the permission rules OpenCode resolved

**Expected copy versus loaded copy.** Just before launch, the worker does three things:

1. It hashes the file again. If the bytes changed since the request, it marks the run `mismatch` and does not launch it.
2. It runs `opencode debug agents --standalone` from the workspace root and compares OpenCode's resolved prompt for the agent with the expected copy.
3. If the card declares a `policy`, it evaluates OpenCode's resolved permission rules against each probe in that policy, using OpenCode's documented order: the last matching rule wins, and no match means `ask`.

The check **fails closed**: anything but `matched` stops the run before launch.

| check | Meaning |
| --- | --- |
| `matched` | The instructions match, and every policy probe has its expected effect. The run launches |
| `mismatch` | OpenCode resolved different instructions, or the file changed after the request |
| `missing` | OpenCode lists no agent with that ID |
| `policy` | A probe, such as `shell true` or editing memory, does not resolve to its required effect |
| `unverified` | `opencode debug agents` gave no readable answer |

This proves which instructions and permission rules OpenCode resolved. It does not prove which file OpenCode read. The detail says when the global `~/.config/opencode/agents/<id>.md` has the same text, because the two copies cannot then be told apart. It is a check made just before launch; it is not taken from inside the run.

**Working folder.** `opencode run` finds its project from `$PWD`, not from the process working folder. That project decides which agents load and which folder the relative permission paths are matched against. A probe in a fresh project failed with "Agent not found" until `PWD` was set. `_run_env()` therefore sets `PWD` to the workspace root for every CLI run and every check. Without it, a server started from `dashboard-app/` would pass its own folder on.

## Job Reader execution boundary (Phase 2.1 and 2.2)

`.opencode/agents/job-reader.md` uses OpenCode V2 `permissions`, which OpenCode 2.3.0 applies. V2 uses the action name `shell`, not `bash`. The rules start with a deny, and the last matching rule wins:

```yaml
- {action: "*",      resource: "*",                                         effect: deny}
- {action: read,     resource: "workspace/agents/job-reader/memory/*",      effect: allow}
- {action: webfetch, resource: "https://*",                                 effect: allow}
- {action: webfetch, resource: "http://*",                                  effect: allow}
- {action: edit,     resource: "workspace/agents/job-reader/staging/*",     effect: allow}
```

The opening `* * deny` covers more than files. It also covers:

- shell
- subagents
- skills
- web search
- MCP tools, such as `trail_*` from `opencode.json`
- questions
- `external_directory`
- glob and grep
- reads anywhere other than its memory

OpenCode matches absolute paths inside the project as relative paths, which a probe confirmed.

**Global copy (Phase 2.2).** OpenCode merges `~/.config/opencode/agents/job-reader.md` into every job-reader run, and uses that copy alone when OpenCode runs outside this project. The old global copy allowed edits anywhere under `job-reader/`, including by absolute path from any folder, and did not deny shell.

OpenCode's session database shows job-reader sessions only in this workspace and in the probe folders, never anywhere else. On 2026-11-17 the global copy was therefore made byte-identical to the project copy. The old file is saved at `~/.config/opencode/job-reader.md.pre-2026-11-17-hardening`, outside the agents folder so it does not load.

Outside this project the identical copy can only fetch pages. The workspace is an external directory there, and `* * deny` blocks it. `test_global_copy_matches_the_project_copy` fails if the two copies drift apart.

**Per-run staging (Phase 2.2).** The agent cannot write `outputs/` at all. For each run:

1. `api_skill_run` picks the run ID and puts the path `workspace/agents/job-reader/staging/<run id>/` into the prompt. The server creates that path; the user never supplies it.
2. `_stage_job_reading()` creates that folder empty, just before launch. It works only under an existing `workspace/agents/job-reader/` and fails if the folder already exists.
3. The agent writes `<job id>.json` there. Its OpenCode rules allow edits only under `staging/`, so overwriting another job's published output is denied, not merely detected afterwards.

One run per agent at a time means no other live run's staging folder exists while it runs.

**Publishing, timestamps and memory are the runner's job.** After the CLI exits, `_finish_job_reading()` does the following:

1. Validates `staging/<run id>/<job id>.json`. It must be a JSON object of at most 1 MB, with the strings `job_id`, `title`, `company` and `source_url`, the four string-list keys, and the requested job ID. Extra keys are allowed.
2. Builds the published file with `finalize_reading()`. Any `fetched_at` or `provenance` the model wrote is dropped. `fetched_at` becomes the CLI exit time from the server clock; the fetch happened between launch and exit. A `provenance` block records the run ID, `launched_at`, `exited_at`, `published_at`, provider, model and definition version.
3. Writes `outputs/<job id>.json` atomically (temp file, then `os.replace`) under `_FILE_WRITE_LOCK`. A rejected run never touches an existing published output.
4. Deletes this run's staging folder only. Other files the agent staged are listed in the check and never published.
5. Appends one event to `memory/log.jsonl`: `jd_read`, or `jd_read_failed` with the reason. The event carries the server-side `ts`, `fetched_at`, run ID, provider, model, definition version and `recorded_by: dashboard`. It adds a missing trailing newline first and never creates a missing memory folder.
6. Fails the run, with the reason in its output, when the staged file is missing or invalid, publishing fails or the event cannot be written.

`memory/index.md` is not updated by dashboard runs. The log is the record. A Job Reader started some other way, such as by Forge, can now write only to `staging/`, so nothing it produces is published unless the dashboard runner finalizes it.

**Which layer enforces what**

| Restriction | Enforced by | Evidence |
| --- | --- | --- |
| No shell commands | OpenCode (`* * deny`; the shell tool is removed) | Live probe: "No tool named shell"; `test_opencode_enforces_the_rules_in_a_live_run` |
| No writes outside `staging/`: published outputs, memory, other agents | OpenCode edit rules | Live probe: "Permission denied: edit"; another job's output was left unchanged |
| No paths outside the project | OpenCode `external_directory` (denied by `* *`) | Live probe: "Permission denied: external_directory" |
| No reads outside its memory | OpenCode read rules | Live run: reading another output was denied |
| Agent, prompt, input format, provider, free models | Dashboard (`SKILL_RUNNERS`, `api_skill_run`) | Existing tests |
| The instructions and rules in force are the hashed copy and the expected policy; fail closed | Dashboard (`_verify_opencode_agent`) | `test_agents_runner.py` |
| Output valid, model timestamps replaced, published atomically; one memory writer | Dashboard (`_finish_job_reading`, `finalize_reading`) | `test_agents_runner.py` |
| One task per agent | Dashboard (`api_skill_run`) | `test_one_agent_runs_one_task_at_a_time` |
| Overwriting another job's published output | OpenCode, which denies edits to `outputs/`; the runner publishes only the requested job ID | Live probe and tests |
| Writing junk into `staging/` (any name, up to OpenCode's limits) | **Not prevented**; contained. Only `<job id>.json` is read, at most 1 MB, and the folder is deleted afterwards | `test_extra_staged_files_are_ignored_and_removed` |
| Data the fetched page sends to the model, and what the model sends back to any URL it fetches | **Not prevented.** `webfetch` allows any http(s) URL, and the input pattern only checks the format | — |
| OpenCode itself (the process, its plugins, its network) | **Nothing.** It runs as your user with full filesystem and network access. The rules bind its tools, not the process | — |

**Permission rules versus OS sandboxing.** OpenCode rules are checks inside OpenCode's own tool layer. They hold only while every action goes through a tool that checks them and while OpenCode has no bug. OpenCode's docs warn that `shell` "runs with the host user's filesystem, process, and network authority". Its shell-command scanner guesses directories on a best-effort basis, so shell allowlists are not a boundary.

Any agent that needs shell later needs an OS boundary, not more rules. Options:

- a separate macOS user with no access to the workspace
- `sandbox-exec` with a profile that limits writes to one folder
- a container with only the agent's folder mounted, and outbound network limited

Job Reader needs no shell, so it gets none.

**Tests.**

- `tests/test_job_reader_permissions.py`:
  - The checked-in rules pass the card policy and deny 9 other operations: shell variants, memory and code edits, the agent's own definition, other agents' memory, web search, skills and MCP tools.
  - The old rules would have been refused.
  - OpenCode's resolved rules pass the policy, when OpenCode is installed.
  - Opt-in (`OPENCODE_LIVE_PROBE=1`, free model, about a minute): a throwaway project shows that shell, writes outside the allowed folder, memory edits and external paths leave no trace, while the allowed output write lands. It also fails if the probe agent never ran, so the denials cannot pass vacuously.
- `tests/test_agents_runner.py` covers fail-closed verification, policy refusal, output validation and the memory event.

**Concurrency and cost.**

- One run per card, as before.
- One run per agent across cards. Two cards for the same agent (for example `cv-base` and `cv-tailor`) cannot run at once, so the agent's memory has one writer inside the dashboard.
- No confirmation dialog or spending cap. Agent cards accept only models whose ID ends in `-free`, so no paid run can be selected. OpenCode reports no usage data that a cap could be measured against.

**No free-form message box.** A message would run with the agent's full rights and no output contract. It could overwrite a reading that the Interviews tab depends on. The card keeps the task form only.

## Skill registry (Phase 3, read-only)

`core/skills.py` and the page `GET /agents/skills` (linked from the Agents tab) list the skills OpenCode 2.3 registers for a run started at the workspace root. That is where every dashboard run starts, because `_run_env()` pins `PWD`. The page shows what each agent's OpenCode rules let its model load. It edits nothing and assigns nothing.

**Discovery** mirrors opencode.ai/docs/skills (checked 2026-11-17):

- **Sources, lowest precedence first:** `~/.claude/skills`, `.claude/skills`, `~/.agents/skills`, `.agents/skills`, `~/.config/opencode/skills`, `.opencode/skills`. For a duplicate ID, the later source is the one OpenCode loads.
- **File rules:**
  - A root-level `*.md` file is a skill named by its stem.
  - A file named exactly `SKILL.md` is a skill named by its folder, at most 6 folders down.
  - A folder holding `SKILL.md` is not searched further.
  - Hidden folders and `node_modules` are skipped.
- **`dashboard-app/` sources** are listed but marked as not registered, because they load only when OpenCode runs inside `dashboard-app/`.
- **Built-in and plugin skills** are registered first but cannot be enumerated from files. This includes the `superpowers` plugin. OpenCode's `GET /api/skill` returned an empty list even for a project with skills, so it cannot be used as the inventory.
- **Config warning:** the workspace `opencode.json` uses the V1 form `skills: {paths: [...]}`. OpenCode 2.x documents an array. Whether it registers `.claude/skills` a second time, at the highest precedence, is not verified; the page says so.

**Inventory on 2026-11-17:** 348 skills registered from 434 files. 320 are advertised to models; 28 are hidden by `disable-model-invocation`. 80 IDs have duplicates, 5 of them with different instructions. In those 5 cases OpenCode loads the later copy, for example `impeccable` from `~/.config/opencode/skills`. 7 nested `SKILL.md` files in `~/.agents/skills` are ignored by OpenCode, and 3 skills exist only in `dashboard-app/.agents/skills`. Scanning takes about 0.3 s, and asking OpenCode for agent rules takes about 4 s. That is why this is a separate page and not part of every page load.

**Access** comes only from OpenCode's own resolved rules (`opencode debug agents`), evaluated per skill ID with the last matching `skill` rule.

| Access | Meaning |
| --- | --- |
| Loadable | The rule is allow and the skill is advertised |
| Hidden | The rule is allow, but the skill is never advertised |
| Ask | Nobody can approve it during a dashboard run |
| Denied | The skill is hidden and loading is rejected |
| Approved | Loadable, with valid metadata and no conflicting copies |

"Approved" is the list a future picker could offer.

Today:

- Forge, Scout, CV Adapter and the other agents that keep OpenCode's default `allow * *` can load all 320 advertised skills. OpenCode denies one skill ID, `browser`, through a `deny skill browser` rule in every agent's resolved rules.
- Job Reader and Gmail Reader deny every skill.
- Claude- and Codex-only agents are not evaluated, because they load skills by their own rules.

**A skill grants nothing.** Loading a skill adds text to the conversation. The tools that text asks for still follow the agent's own rules. For example, Job Reader could not read a skill's supporting files even if it were allowed to load the skill. The registry offers no way to attach permissions to a skill.

**Can OpenCode enforce a skill allowlist for one run?** Findings from 2026-11-17, all made in throwaway projects:

| Mechanism | Finding |
| --- | --- |
| Agent `skill` rules (static, per definition) | Enforced for the model's `skill` tool. Live evidence from Phase 2.1: the model's attempt to load `using-superpowers` failed with "Permission denied: skill". The rules cannot change per run without editing the definition |
| `opencode run` flags | None for permissions or skills |
| Session permissions | `PATCH /api/session/{id}` accepts a permission ruleset, and `GET` returns it. A run can attach with `opencode run --session <id>`. **Not verified:** whether those rules apply to the model's `skill` tool, and whether they come before or after the agent's rules, which decides whether they can narrow or only widen. The live test failed with "Free usage limit reached" on every free OpenCode model, and paid models are out of scope |
| Explicit activation `POST /api/experimental/session/{id}/skill` | **Bypasses skill rules.** It loaded `beta` into a session whose agent denies every skill and whose session rules allowed only `alpha`. Anyone who can drive OpenCode's API can inject any registered skill |
| `@skill-id` in `opencode run` message text | Did not attach a skill. A posting URL containing `@name` does not load a skill in Job Reader runs |

**Conclusion: no per-run skill picker yet.** No verified mechanism restricts the skill tool for one execution. A dropdown would only look like a restriction.

**Proposed design, to build only after its check passes:**

1. **Ceiling.** An agent card declares `skills: [...]`, a static allowlist. At render time the picker offers only the intersection of that list with the registry's `approved` list for that agent.
2. **Per-run rules (option A).** The runner creates a session through `opencode api`, then patches its rules to `skill * deny` followed by `skill <id> allow` for each selected skill. It runs `opencode run --session <id>`, and before launch reads the session back and checks that the rules match the selection, failing closed otherwise.
   - **Enable only after** a live probe in a throwaway project, run against a working model, shows two things: an unselected skill is rejected while a selected one loads, and session rules cannot widen past the agent's ceiling.
   - **If session rules can widen:** the ceiling check in step 1 stays the only guard, and that must be stated on the card.
3. **Server-injected skills (option B), the fallback that is enforceable today.**
   - The agent keeps `skill * deny`, so the model can load nothing.
   - The runner adds the selected skills' bodies to the prompt, read from the registry's loaded copy. It records each skill ID and hash in the run record, as it does for definitions.
   - Only skills that need no supporting files qualify.
   - Trade-off: this assembles instructions outside OpenCode's loader, which Phase 2 avoided for definitions. Choosing it is your decision.
4. **Run record.** Selected skill IDs, their paths and body hashes, and the mechanism used (A or B).
5. **Never.** A skill never changes `edit`, `read`, `shell`, `webfetch` or any other rule. A selection that would need a wider permission is refused, not granted.

## Left for later phases

- An OS-level boundary (separate user, `sandbox-exec` or container) before any agent gets shell.
- A runtime that owns agent identity and enforces per-agent permissions itself.
- An access policy for memory content, and whether `/api/file` should keep serving it.
- A decision on drifted copies (`personal-growth-mentor`, `.Codex` paths) and on the unverified `dashboard-app/.codex` and `.github` folders.
- Reconciling hub paths: `chief-of-staff`, and hub folders for agents that never ran.
- A conflict strategy, such as per-machine logs, before any writer other than the Mac.
- Per-run skill selection: verify option A live (needs a working free model), or choose option B.
- Reconcile the 5 skill IDs with different instructions, and the V1 `skills` config entry.
