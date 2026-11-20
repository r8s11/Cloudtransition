# Second Brain research and workspace fit

Research date: 2026-10-28. Public sources were fetched without sending workspace contents. Repository documentation describes capabilities; community reports are anecdotes, not controlled benchmarks.

## Four source projects

| Project | Adopt here | Skip here and why |
| --- | --- | --- |
| [Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) | Plain Markdown, small catalogue, source citations, immutable original documents, explicit maintenance. | Automatically rewriting many synthesized pages on every ingestion. Existing workspace documents already carry authoritative state; duplicate summaries would drift. |
| [QMD](https://github.com/tobi/qmd) | Ranked retrieval, scoped collections, evidence-first command output. | Embeddings, GGUF model downloads and reranking by default. The requested deterministic path must work without inference, and the workspace already has graft for code. |
| [GBrain](https://github.com/garrytan/gbrain) | Provenance, explicit corrections, transparent unknowns, separation between local storage and provider access. | Always-on enrichment, another database/service and remote exposure. Those add permissions and costs without a demonstrated local retrieval need. |
| [Graphify](https://github.com/safishamsi/graphify) | Explicit links and distinguish extracted evidence from inference. | A second code graph. Graft already indexes this workspace; CodeGraph also exists but its installed launcher currently points to a missing module. Do not install a third index. |

## Current practice versus hype

An [October 5 practitioner report](https://medium.com/@christopherramm/i-stopped-taking-notes-claude-code-now-maintains-my-second-brain-4a74f7c3ab05) describes a linked Markdown wiki, immutable sources, provenance, and deliberate exclusion of a private inbox. Its scale and productivity claims are self-reported. Recent Reddit search results include [a cited Markdown vault](https://www.reddit.com/r/claudeskills/comments/1xb38m6/i_built_a_second_brain_for_claude_code_a_markdown/) and [a small Markdown memory setup](https://www.reddit.com/r/secondbrain/comments/1x6slhg/i_moved_my_chatgpt_memory_into_5_markdown_files/). Search excerpts alone do not verify their reliability. A [YouTube walkthrough](https://www.youtube.com/watch?v=1FiER-40zng) describes Markdown plus Python, but its April publication is outside the last-30-day window. Searches targeted Reddit, X, Hacker News and YouTube; no independently verified recent X/Hacker News performance evidence was obtained.

Useful common denominator: small maps, source links, deterministic operations, and human-approved corrections. Unsupported generalizations: a graph automatically eliminates hallucinations; all memory systems reduce total model bills; cache pings always save money; every skill benefits from an external routing model. Measure this workspace instead.

## Workspace findings and decisions

The workspace already has five department routers, an operational dashboard, a visual index, a mission runtime, and a Python memory domain model without persistent repository wiring. It lacks the guide's working deterministic memory save/retrieve command. Existing `routine.md` names weekly review and artifact-driven learning; use those rather than inventing a content-creator workflow.

Keep the existing documents in place. Add a local memory CLI, source catalogue, feedback/recommendation micro app, a zero-inference routine report and one explicitly invoked browser clipper. Reuse the Orizuru design tokens. Keep employer-private directories, agent settings, secrets and generated/vendor trees out of ingestion. Store sensitive operational data locally, and do not include it in external benchmark prompts.

## Model and cache cautions

Claude Code documentation was checked through Context7 against `/anthropics/claude-code`, including skill model metadata and usage output. The installed `claude --help` supports model selection, JSON output, `--max-budget-usd`, safe mode and read-only tool restriction. `claude auth status --json` reports an authenticated OAuth session. No `OPENROUTER_API_KEY` or `ANTHROPIC_API_KEY` is present in this process environment; this does not prove no key exists elsewhere. No keys were searched or disclosed.

Managed skills in this harness are not equivalent to Claude Code skill frontmatter. Do not claim a managed skill's prose changes its execution model. Deterministic commands need no model; choose a supported smaller model explicitly for any future synthesis. The Jev model was rejected by the account used by the local find tool during this run, so an automatic Jev router is not a dependable prerequisite.

Do not issue keepalive pings. Cache TTL, cache-read counts, same-session identity and actual rates must be known before estimating savings. API-equivalent costs are not subscription charges. Benchmark bytes or token approximations are not `/context` measurements.
