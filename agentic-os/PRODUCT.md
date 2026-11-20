# Agentic OS

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Roosevelt, a single operator at a personal workstation, supervising local missions and coding-agent processes.

## Product Purpose

Keep a mission pipeline moving through explicit decisions. Register local repositories, start coding-agent runs, inspect their output, and interrupt or terminate them deliberately.

## Operating Context

Local-only Mission Control dashboard, served by Hono at the loopback address. Desktop-first, also usable on a narrow mobile browser. The existing dark Control Room identity remains binding. Data refreshes every five seconds.

## Capabilities and Constraints

- Missions: board, creation, acceptance criteria, latest plan, transition history, legal status changes.
- Approvals: pending queue, approve and reject decisions.
- Runtime: register Git repositories, detect installed Claude/Codex CLIs, start runs, inspect ordered process output, interrupt and terminate.
- SQLite is authoritative. Existing HTTP and domain contracts remain unchanged.
- Runs do not automatically advance missions. Agent availability does not guarantee authentication.
- No scheduler, autonomous orchestration, provider SDK integration, or interactive terminal sessions.
- Local agents inherit the server user's credentials and permissions. Approval records are not an agent sandbox.

## Brand Commitments

Retain Mission Control naming and the existing dark Control Room palette, system typography, and restrained interactions. Refine rather than replace the identity.

## Evidence on Hand

`README.md`, `apps/api/www/index.html`, `apps/api/src/runtime-routes.ts`, and the existing Mission Control surface brief. Use live API data; do not invent activity, performance claims, or runtime capabilities.

## Product Principles

- Human control is explicit.
- Important decisions and process state are easy to scan.
- Preserve context while data refreshes.
- Distinguish mission workflow from process lifecycle.
