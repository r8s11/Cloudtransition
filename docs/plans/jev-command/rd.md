# Jev command requirements

> Make me a /jev on command. While it's on, send each message I type to Jev first, ask how hard the task is, and hand it to a Haiku, Sonnet or Opus helper agent to match. Log every pick.

> actually i meant to add codex models as well

Jev considers available models from both Anthropic (Claude) and OpenAI (Codex), chooses a family based on the task, then an appropriate available model tier. Discover availability for both companies rather than assume model names or account entitlements; do not exclude either family's models solely because they were not named in the original examples.

Assume this Omp interactive session, session-scoped opt-in, and `/jev off` for disabling. System and safety instructions continue to apply. Do not silently send credentials, attachments, or private content when unavailable or unapproved. Jev and helper calls may incur charges; exact test data and a spending cap need explicit authorization before live tests. Real-time cost limits and behavior when Jev, the selected model, or helper dispatch is unavailable need explicit failure reporting. Normal user messages sent while on are transmitted to TypeSafe and the selected helper provider. Logs should contain the pick and metadata, not message content or secrets.
