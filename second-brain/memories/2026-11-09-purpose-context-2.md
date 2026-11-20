# Purpose & context**

> **Purpose & context** Roosevelt is building **SalsaSegura.com**, a salsa dance community platform with both web and mobile components. The platform serves multiple stakeholders: event promoters who submit events, and community members who browse and engage with them. The broader goal is to become a trusted hub for the salsa community, which influences product decisions (e.g., protecting the platform's reputation with event organizers when adding social features). Key dependencies and archit...

_Saved: 2026-11-09T19:47:19Z_

**Purpose & context**

Roosevelt is building **SalsaSegura.com**, a salsa dance community platform with both web and mobile components. The platform serves multiple stakeholders: event promoters who submit events, and community members who browse and engage with them. The broader goal is to become a trusted hub for the salsa community, which influences product decisions (e.g., protecting the platform's reputation with event organizers when adding social features).

Key dependencies and architecture: the project is backed by **Supabase** (auth, database with RLS, real-time subscriptions, storage) and follows a **structured weekly learning roadmap** with time estimates per feature. A parallel mobile app is planned using React Native with Expo, sharing the Supabase backend with the web app.

---

**Current state**

Roosevelt is actively building out SalsaSegura.com on a phased roadmap. Completed or in-progress milestones include authentication (Week 5), a moderation dashboard (Week 6), RSVP functionality (Week 18), and Favorites (Week 19).

The most recently planned feature is a two-phase matching system:
- **Phase A – "Discover Mode" (Weeks 19–20):** Event swiping
- **Phase B – "Dance Connect" (Weeks 27–34):** People matching, broken into four sub-phases: match profiles, swipe/match logic, realtime chat, and a safety/moderation layer

A formal `MATCHING_FEATURE_GUIDE.md` has been produced documenting the full plan, annotated SQL schema with RLS policies, legal/community trust checklists, success metrics, and roadmap timing.

---

**On the horizon**

- Launching the mobile app (React Native + Expo) with shared Supabase infrastructure
- Executing Phases A and B of the matching feature per the documented roadmap
- Phase B safety and moderation layer (non-negotiable pre-launch requirement)
- Mobile-specific features to explore: push notifications, offline support, image caching, location-based filtering, real-time event updates

---

**Key learnings & principles**

- **Community trust over feature breadth:** Dating functionality is framed as an opt-in intent tag, not the primary feature framing, to protect relationships with event organizers
- **Event-anchored matching as core differentiator:** Match visibility is scoped to users sharing an RSVP to the same event; matches expire 48 hours after the event ends
- **Safety is non-negotiable:** The moderation/safety layer must be complete before any Phase B launch
- **Shared infrastructure reduces duplication:** Reusing the Supabase client, TypeScript types, and data-fetching hooks across web and mobile is a core architectural principle

---

**Approach & patterns**

- Follows a **structured weekly roadmap** with explicit time estimates and feature sequencing
- Produces **formal markdown documentation** (matching existing project doc style) as features are planned
- Prefers **phased implementation** with clear sub-phases and dependency mapping before building
- Clarifies scope early (e.g., confirming both event swiping and people matching before designing the system)

---

**Tools & resources**

- **Backend:** Supabase (auth, Postgres with RLS, real-time, storage)
- **Web:** Existing web app (framework not specified)
- **Mobile:** React Native with Expo; `@howljs/calendar-kit` (day/week views), `react-native-calendars` (month view)
- **Shared layer:** Monorepo-style structure (`/shared`, `/web`, `/mobile`); reusable `useSupabaseEvents` hook with real-time subscriptions
- **Language:** TypeScript
