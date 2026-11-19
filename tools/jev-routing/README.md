# Jev routing

Omp extension (`extension.mjs`), native optional-skill adapters, and shared Choice/logging core (`core.mjs`). Specs: [command](../../docs/plans/jev-command/rd.md), [skill routing](../../docs/plans/jev-skill-routing/rd.md).

## Commands (session-scoped, default off)

| Command | Effect |
| --- | --- |
| `/jev on` | Each ordinary typed message goes to Jev 1.14 (`jev-1.14.0`) first: skill Choice (with None), difficulty Choice, then helper-model Choice over all authenticated Anthropic and OpenAI chat models. A helper session on the picked model runs the task. |
| `/jev skills on` | Skill routing only: Jev picks a skill (or None); its `SKILL.md` is injected and your message goes to the main agent. |
| `/jev off`, `/jev status` | Disable and cancel queued work; show status and spend. |

Enabling asks for a classifier cap and a helper reported-usage cap, then a data-transmission confirmation. Resets to off on session switch, branch and shutdown.

## Behaviour and limits

- Catalogues over 254 candidates are split into several Choices, each with `None`; group winners go to a fresh Choice (a tournament). Group probabilities are never compared directly; an early elimination can drop a globally better candidate.
- Jev/helper/logging failures are shown and logged; the message is **not** forwarded to the main agent and no fallback model runs. Attachments and secret-like text are refused before any request.
- Helper sessions inherit the parent's system prompt, cannot delegate, and every helper tool call needs approval through the parent UI. The helper cap is checked between requests; one in-flight request can exceed it.
- Picks log: `~/.local/state/jev-routing/picks.jsonl` (mode 0600): id, outcome, difficulty, model, skill, token counts, costs. No message text or keys.
- Native optional-skill adapters exist for Claude Code, Codex, OpenCode V2, Gemini CLI, and pi. They are **not globally installed**. All five, plus Omp, have observed real-runtime traces against local providers; Codex and Gemini were observed in disposable profiles after the owner trusted the hook and workspace natively, so a real install still needs its own `/hooks` review or folder trust. Hermes and cursor-agent are unsupported. See [runtime inventory](../../docs/plans/jev-skill-routing/eval-evidence/runtime-inventory.md). “All agents” is not a verified installation claim.

## Native optional-skill adapters (review before installing)

| Runtime | Entry / supported hook |
| --- | --- |
| Claude Code | `node /absolute/path/prompt-hook.mjs claude`, synchronous `UserPromptSubmit` command hook; `hookSpecificOutput.additionalContext` |
| Codex | `node /absolute/path/prompt-hook.mjs codex`, synchronous `UserPromptSubmit` hook in `hooks.json`; human `/hooks` review/trust is required |
| Gemini CLI | `node /absolute/path/prompt-hook.mjs gemini`, synchronous `BeforeAgent` command hook; native workspace trust is required |
| OpenCode V2 | Local plugin directory `opencode/` (`index.ts`, host-provided `@opencode/plugin`), `ctx.session.hook("prompt", ...)` |
| pi | Explicit `pi -e /absolute/path/pi.mjs`; native `input` transform |

These adapters load only Jev's optional selection. Required skills, native tools, permissions and higher-priority instructions are not removed or rewritten. OpenCode uses the native `{location,data}` skill catalogue, stable IDs (display names may collide), and native embedded content, including `skill://` entries. Bodies are injected only after the answer; only names/descriptions are sent to Jev. A native catalogue change fails closed.

Non-Omp adapters default off. Without `JEV_SKILL_APPROVAL`, they disclose that routing is off and preserve native operation. Enabling requires a **reviewed, explicit approval** of exact task text, catalogue metadata, TypeSafe destination/key use, and total spending cap. Do not repurpose an old approval or create `approved:true` on a user's behalf. `JEV_SKILL_CATALOGUE` points to a JSON array of the native eligible `{name,description,filePath}` catalogue for Claude/Codex/Gemini/pi; OpenCode obtains its catalogue from the host.

`JEV_SKILL_APPROVAL` points to a private JSON file with `approved:true`, allowed `runtimes`, future ISO `expires`, exact `taskHashes`, `catalogueHash`, and positive `maxUSD`. Use exported `taskHash(text)` / `catalogueHash(skills)` from `agents.mjs` to prepare the **locally reviewed** payload, never to infer consent. The destination is fixed to `api.typesafe.ai`, model `jev-1.14.0`. The API key is read only after authorization. Attachments need separate approval; secret-like task/catalogue data is refused.

The approval's `.usage.json` ledger is shared across hook processes, reserves cost **before each request**, retains unknown-usage reservations on failure, and enforces the total cap across invocations. `.lock` refuses concurrent access rather than racing the cap; a crash-held lock requires explicit local inspection, not an automatic retry. `.picks.jsonl` contains only metadata. Keep the approval and sidecars in a private state directory, not the repository. Native trust and these data/spend approvals are separate gates.

`agent-fixture.mjs` is **local-test-only**, not an installation hook. It refuses non-loopback origins and uses a fixture credential. `runtime-agents.mjs` redirects each native model endpoint to localhost and isolates configuration; it never bypasses native trust and exits 2 if any requested runtime is blocked. `JEV_CODEX_PROFILE` and `JEV_GEMINI_PROFILE` may point to explicitly human-trusted temporary native profiles; their trust is preserved. Initial evidence contains request ordering; current fixture output additionally records server response-finish timestamps.

The saved historical benchmark approval is consumed. [Authorization provenance](../../docs/plans/jev-skill-routing/eval-evidence/authorization-source.json) traces the original interactive response and pre-request labels. `benchmark-report.mjs` re-reports those ten real tasks offline; it cannot authorize or issue a new request.

## Tests

```sh
export TMPDIR='/Volumes/SANDISK USB/work/omp-test-tmp'
node --test tools/jev-routing/core.test.mjs tools/jev-routing/extension.test.mjs tools/jev-routing/agents.test.mjs
bun tools/jev-routing/runtime-acceptance.mjs       # narrow U2 + mandatory-skill sequence, local providers
bun tools/jev-routing/runtime-agents.mjs claude pi opencode             # add codex gemini with JEV_CODEX_PROFILE / JEV_GEMINI_PROFILE set to human-trusted profiles
bun tools/jev-routing/runtime-agents.mjs claude pi opencode --disabled
node tools/jev-routing/benchmark-report.mjs        # offline, no requests
bun tools/jev-routing/runtime-matrix.mjs           # complete existing Omp command scenarios
bun tools/jev-routing/runtime-skills.mjs           # complete existing Omp skill scenarios
```
