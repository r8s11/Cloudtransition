# Windows Sysadmin — STAR Stories
## Pre-Written Behavioral Answers from Real Experience

> Phone screens lean light on behaviorals — but expect 1-2. Know these cold so they roll naturally if asked. Each story is calibrated to ~60-90 seconds spoken aloud.

---

## STORY 1 — "Tell me about a project you led from scratch"
### Jira Service Management Build (Ventus Therapeutics)

**Situation:** When I joined Ventus as IT Specialist, the company had no formal IT ticketing system. Requests came through email, Slack, and hallway asks. Around 100+ users, no SLA tracking, no audit trail.

**Task:** Build IT support infrastructure from the ground up — a real ticketing system with workflows, SLAs, and a paper trail.

**Action:** I evaluated tooling and chose Jira Service Management. Designed the request types — hardware, software access, account changes, security exceptions. Built workflows with approval chains for sensitive requests. Set SLA targets aligned with how the business actually operated. Migrated existing ad-hoc requests, trained the team, and documented runbooks so the system could outlast me.

**Result:** It became the system of record for IT at Ventus. Users got a clear front door, IT got a tracked queue, leadership got reporting for the first time. It's the project I point to most when people ask what I've built.

**Why this story works for Windows Sysadmin role:** Demonstrates ownership, system-building, documentation, stakeholder management — all called out in the JD.

---

## STORY 2 — "Walk me through a complex technical project"
### OneView Windows 10 Upgrade (MGH/BWH Radiology)

**Situation:** Mass General and Brigham & Women's Radiology departments — 200+ clinical workstations across two hospital campuses needed the OneView Windows 10 migration. HIPAA-regulated, zero tolerance for clinical disruption, radiologists actively reading studies.

**Task:** Coordinate the OS migration without disrupting patient care or imaging workflows.

**Action:** Scheduled migrations around clinical hours and reading-room availability. Validated each workstation's clinical peripherals — PACS connectivity, dictation systems, dual-monitor configs — before and after upgrade. Coordinated handoff windows directly with radiologists and clinical staff. Built a rollback procedure for each migration so we could revert quickly if a clinical workflow broke.

**Result:** Migration completed across both campuses without a clinical disruption. The validation discipline became a model for similar migrations the team did afterward.

**Why this story works:** Shows you handle high-stakes production environments, change management, validation, communication with non-IT stakeholders.

---

## STORY 3 — "Tell me about a time you kept things running under pressure"
### Office Relocation Cutover (Ventus)

**Situation:** Ventus was relocating its full office. Research scientists, dev team, business operations — all needed to be productive Day 1 in the new space. No room for IT to be the bottleneck.

**Task:** Lead the IT infrastructure setup at the new location and cut over without losing data or productivity.

**Action:** Pre-staged all hardware before moving day. Cabled and validated the network in advance — switches, APs, firewalls. Tested AD and M365 connectivity from the new site. Set strict cutover windows so users had clear expectations. Walked the floor on Day 1 to catch issues fast.

**Result:** Zero unplanned downtime. Lab and dev teams resumed work the next morning as if nothing had moved.

**Why this story works:** Shows planning, risk management, hands-on infra work, and the calm execution that JD specifically calls for in incident response.

---

## STORY 4 — "When did you have to support a really demanding user / situation?"
### 24/7 Cross-Time-Zone Handovers (Peak Scientific)

**Situation:** Peak Scientific runs a 24/7 global operation. I was supporting 100+ employees in North America while coordinating with global IT teams in India and Europe — incidents can start in one zone and need resolution by another.

**Task:** Maintain SLA on tickets that crossed time zones without dropping context or disappointing the user.

**Action:** Built a clean handover ritual — at end of shift, every open ticket got a clear status summary in Zendesk: what's been tried, what's blocked on, what the next action is. I'd ping the receiving zone directly for high-priority items. Same in reverse when picking up from India in the morning.

**Result:** Maintained 95%+ SLA across 2 years. Recurring incident patterns I flagged led to infra fixes that reduced repeat tickets.

**Why this story works:** Shows operational discipline, written communication, ownership of SLA, working in a global team — all called out in JD.

---

## STORY 5 — "Tell me about a time you had to make something more secure"
### Onboarding/Offboarding Hardening (Jounce)

**Situation:** At Jounce, the user lifecycle wasn't fully tight — onboarding and offboarding had manual steps that occasionally got missed, especially around access reviews after offboarding.

**Task:** Tighten the user lifecycle so accounts and access weren't lingering after departures.

**Action:** Documented every system a departing user had to be removed from — AD, M365, Box, CyberArk SSO, FortiGate VPN, Cisco Meraki where relevant. Built a checklist that tied to HR's offboarding signal. Coordinated with HR on the timing so access was disabled at the same moment as their last day, not days later. Added a 30-day audit step to confirm cleanup.

**Result:** Lifecycle became repeatable and audit-ready. Cut down lingering access risk significantly.

**Why this story works:** Shows security mindset, IAM understanding, cross-team coordination — all called out in JD ("identity and access management," "system documentation").

---

## STORY 6 — "Describe a time you investigated and resolved a security alert"
### Cortex XDR Alert Triage (Jounce)

**Situation:** At Jounce, I monitored Cortex XDR alerts as part of daily endpoint security work. We'd see anything from low-signal noise to genuine indicators worth investigating.

**Task:** Triage alerts, escalate when needed, document outcomes.

**Action:** My triage flow: identify the endpoint and user; check the alert details against recent activity (legitimate process? known software?); pull supporting context from Defender or the endpoint itself; if uncertain, isolate the host before deeper investigation. For genuine concerns, I'd escalate to the security lead with a complete write-up — what fired, what I checked, what I recommend.

**Result:** Most alerts resolved as benign with documented reasoning. The genuine ones got cleaned up fast because the context was already gathered. Escalations went up with everything the security lead needed in one message.

**Why this story works:** Shows EDR fluency, triage discipline, written escalation — direct match for JD's incident response language.

---

## STORY 7 — "Tell me about a mistake you made"
### [Pick one — be honest, own it, don't be dramatic]

**Template — fill in your real one:**

**Situation:** [Real incident — production, not theoretical]

**Task:** [What I was trying to accomplish]

**Action:** [The mistake I made]

**Recovery:** [How I caught it / fixed it / what I changed afterward]

**Lesson:** [One-sentence: "Now I always [X] before [Y]"]

> **Coach's note:** Recruiters love this question — but they want a real, specific, owned mistake with a clean lesson. Don't pick something trivial ("I take on too much"). Pick something where you broke or almost broke something, caught it, fixed it, and learned. If you want to draft this together for next time, flag it.

**Possible candidates from your history (think about which one):**
- Any change-window slip where you had to roll back?
- A misread alert you initially dismissed?
- A user-permissions change with broader impact than expected?
- A backup/restore situation that taught you something?

---

## STORY 8 — "Tell me about a time you had to learn something new fast"
### GitHub Enterprise Rollout (Ventus)

**Situation:** Ventus's dev team didn't have a unified version control platform. They asked IT to evaluate options and lead a deployment. I had Git fundamentals but hadn't run a GitHub Enterprise rollout before.

**Task:** Get up to speed on GitHub Enterprise admin and stand up the platform for the dev team.

**Action:** Studied GitHub Enterprise docs, set up a sandbox environment to test SSO integration with our identity provider, mapped out org structure and team permissions, and ran a small pilot with 2-3 devs before broader rollout. Documented the admin handoff so I wasn't the single point of failure.

**Result:** Platform deployed cleanly, dev team adopted it, and we had a working version control + collaboration story for the first time.

**Why this story works:** Shows you can ramp on a new tool fast, work with technical users, and deliver — direct match for JD's "willingness to learn" criterion.

---

## How To Use These

**Phone screen reality check:** A 30-min recruiter call usually has time for **at most 1-2 behavioral questions**, often zero. They're looking for fit, logistics, and a sanity check that you can speak to your resume.

**If they ask one behavioral, default to:**
- Story 1 (JSM) for "project you led"
- Story 4 (Peak SLA) for "demanding situation"
- Story 7 (mistake) — the one question almost every recruiter asks

**If they ask zero, move on.** Save these for the hiring manager round, where you'll get 4-6 behavioral questions and can deploy them more freely.

---

_STAR stories — Windows Systems Administrator interview prep — April 2026_
