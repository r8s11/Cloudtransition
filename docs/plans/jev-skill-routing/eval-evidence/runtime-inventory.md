# U3 / R3 — Runtime inventory, 2026-11-13

Installed versions were read with `--version`. Runtime experiments used synthetic text, fixture credentials, isolated native configuration, and localhost Jev/model endpoints only. No global agent configuration or provider approval was changed. Codex hook trust and Gemini folder trust were granted by the owner on 2026-11-13 for the two disposable profiles named below only.

| Runtime | Installed version | Native integration and observed status |
| --- | --- | --- |
| Omp | 18.19.0 | Existing `input` extension + exact-model SDK helpers. `../../jev-command/eval-evidence/acceptance-runtime.json`: easy/medium/hard dispatch and required-skill read sequence, including optional choice and None. |
| Claude Code | 2.1.322 | New synchronous `UserPromptSubmit` adapter. `native-claude-pi.json`: 1 Jev call, then selected optional body in 1 native model request, final local answer. |
| Codex | 0.166.0 | New synchronous `UserPromptSubmit` adapter. A fresh isolated profile skips the untrusted hook (0 Jev calls; retained in `native-codex-opencode.json`). After the owner approved it, the exact hook was trusted through the native `/hooks` review in the disposable profile. `native-all-2026-11-13.json`: 1 Jev call, then selected optional body in 1 native model request. |
| OpenCode | 2.2.7 | New V2 `session.prompt` plugin. `native-opencode.json`: 1 Jev call, then selected optional body in native model input; 2 local model requests including auxiliary work. Uses native `{location,data}`, unique skill IDs and embedded bodies; late-added builtins are included rather than omitted. |
| Gemini CLI | 0.51.0 | New `BeforeAgent` adapter. An untrusted fixture workspace exits 55 with 0 calls (retained in `native-gemini.json`). After the owner approved it, only the disposable workspace was trusted through the native folder-trust dialog. `native-all-2026-11-13.json`: 1 Jev call, then selected optional body in 1 native model request. No `--skip-trust` or trust environment override was used. |
| pi | 1.5.0 | New native asynchronous `input` transform, not inferred from Omp compatibility. `native-claude-pi.json`: 1 Jev call, selected body in 1 model request, final local answer. |
| Hermes | not runnable | Launcher targets `/Users/roosevelt/.hermes/hermes-agent/venv/bin/python`; executable prerequisite is absent. No integration or runnable-runtime coverage claimed. |
| cursor-agent | 2026.09.10-fd3934a | Unsupported by this integration: documented `beforeSubmitPrompt` can allow/deny but cannot add context; `sessionStart` adds initial context only, not a routed body for each later prompt. No fabricated per-turn injection hook. |

U3's “all agents” scope is **not marked complete** merely because unsupported runtimes are listed. Omp, Claude Code, Codex, Gemini CLI, OpenCode and pi have actual ordered routing observations (`native-all-2026-11-13.json`, one run of all five native runtimes). Hermes is not runnable and cursor-agent has no per-prompt context hook; both stay unsupported and uncovered. The new adapters are repository source only, not global installations. `native-disabled-2026-11-13.json` observes all five native runtimes answering from the local model with zero Jev calls and no selected body when routing is off.

`native-codex-opencode.json` retains the earlier diagnostic attempt: its Codex entry is the fresh-profile trust block; its OpenCode failure preceded the catalogue/envelope/ID fixes and is superseded by `native-opencode.json`. Failures were retained, not relabelled. Current fixture versions record both request and response-finish times; earlier JSON ordering timestamps denote request arrival.

## Exact native trust boundaries

- Codex: isolated `CODEX_HOME=/Volumes/SANDISK USB/work/omp-test-tmp/jev-codex-native-trust`. `hooks.json` names `'/Users/roosevelt/.bun/bin/bun' '/Volumes/SANDISK USB/work/Cloudtransition/tools/jev-routing/agent-fixture.mjs' codex` (UserPromptSubmit, 60s). On 2026-11-13 the owner approved trusting that exact definition; it was reviewed and trusted in Codex's own `/hooks` screen, which showed the same command and source file. Trust is a hash recorded in that profile's `config.toml` only; `~/.codex` has no entry. No synthetic trust hashes or bypass flags.
- Gemini: `/Volumes/SANDISK USB/work/omp-test-tmp/jev-gemini-native-trust/{workspace,state}`. On 2026-11-13 the owner approved trusting only that workspace; option 1 “Trust folder (workspace)” was chosen in Gemini's own dialog and no task was submitted. Trust is recorded in `state/.gemini/trustedFolders.json` only; `~/.gemini` has no entry.
- These native trust decisions do not authorize TypeSafe data transfer or spending, and do not carry over to a real installation: any real profile needs its own `/hooks` review or folder trust. All experiments stayed local.

Hook contracts: [Claude](https://code.claude.com/docs/en/hooks), [Codex native trust](https://developers.openai.com/codex/hooks), [OpenCode V2](https://opencode.ai/docs/build/plugins/server/), [Gemini](https://geminicli.com/docs/hooks/reference/), [Cursor prompt hook](https://cursor.com/docs/hooks#beforesubmitprompt).
