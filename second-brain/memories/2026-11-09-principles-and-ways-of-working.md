# principles and ways of working

> --- name: principles-and-ways-of-working description: Product principles behind SalsaSegura and how features get planned and built sources: [backfill] aliases: [] --- ## Principles - [stated] Community trust over feature breadth: dating functionality is framed as an opt-in intent tag, not the primary feature framing, to protect relationships with event organizers - [stated] Event-anchored matching is the core differentiator — match visibility is scoped to users sharing an RSVP to the same e...

_Saved: 2026-11-09T19:47:21Z_

---
name: principles-and-ways-of-working
description: Product principles behind SalsaSegura and how features get planned and built
sources: [backfill]
aliases: []
---

## Principles

- [stated] Community trust over feature breadth: dating functionality is framed as an opt-in intent tag, not the primary feature framing, to protect relationships with event organizers
- [stated] Event-anchored matching is the core differentiator — match visibility is scoped to users sharing an RSVP to the same event, and matches expire 48 hours after the event ends
- [stated] Safety is non-negotiable: the moderation/safety layer must be complete before any Phase B launch
- [stated] Shared infrastructure reduces duplication — reusing the Supabase client, TypeScript types, and data-fetching hooks across web and mobile is a core architectural principle

## Ways of working

- [stated] Works from a structured weekly roadmap with explicit time estimates and deliberate feature sequencing
- [stated] Produces formal markdown documentation matching existing project doc style as features are planned
- [stated] Prefers phased implementation with clear sub-phases and dependency mapping before building
- [stated] Clarifies scope early — e.g. confirming both event swiping and people matching were in scope before designing the matching system
