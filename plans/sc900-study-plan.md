# SC-900 Certification Study Plan

> Microsoft Security, Compliance, and Identity Fundamentals — 4-week intensive

**Timeline:** 4 weeks (~28 days)
**Exam:** Week 4 (target: Saturday of week 4)
**Time Commitment:** 6-8 hours/week (~25-30 hours total)
**Goal:** Pass SC-900 exam (700/1000 minimum)
**Start Date:** 2026-04-27 (Monday)
**Target Exam Date:** 2026-05-23 (Saturday)

---

## Why SC-900

- **Fills a gap.** Rebuilds the security credential your Security+ CE used to provide (expired 2019).
- **Natural stepping stone.** Feeds directly into AZ-500 (your 2027-Q1 roadmap target) without redundant study.
- **NYC market fit.** Cloud + security is the highest-paying combo in the NYC tech market — this cert lets you start that conversation today instead of waiting until AZ-500.
- **Leverages AZ-900.** The Azure conceptual overlap with your existing Fundamentals knowledge cuts ~30% of the study load.
- **Low friction.** No hands-on Azure labs required to pass (unlike AZ-204). Mostly concepts and service awareness.

---

## Cost & Voucher Strategy

**List price:** $99 USD (proctored online via Pearson VUE)

**Free / discounted paths to check BEFORE scheduling:**

1. **Microsoft Cloud Skills Challenge** — Microsoft runs these ~2-3x per year (typically around Build, Ignite, and Reactor events). Complete the challenge within the timeframe → free exam voucher. Check <https://developer.microsoft.com/en-us/offers/30-days-to-learn-it> and Microsoft Reactor event pages.
2. **Microsoft Virtual Training Days** — Attending the free "Security, Compliance, and Identity Fundamentals" virtual training day has historically granted a free SC-900 voucher. Register at <https://www.microsoft.com/en-us/trainingdays>.
3. **Employer reimbursement** — If your current IT Support employer has a learning & development budget, SC-900 typically qualifies.

**Action item for Day 1:** Check Microsoft Virtual Training Days for an upcoming SC-900-themed session in the next 4 weeks. If one exists, pivot your study plan to align with its date.

---

## Exam Domains

The exam is scored across four skill areas. Official breakdown:

### 1. Concepts of Security, Compliance, and Identity (10-15%)

- Shared responsibility model
- Defense in depth
- Zero Trust methodology
- Encryption and hashing
- Compliance concepts (data residency, sovereignty, privacy)
- Identity as the primary security perimeter
- Authentication, authorization, identity providers
- Directory services and Active Directory
- Federation

### 2. Capabilities of Microsoft Entra (25-30%)

- Microsoft Entra ID (formerly Azure AD) — types, editions, tenants
- Identity types: users, service principals, managed identities, device identities
- External identities: B2B, B2C
- Hybrid identity: password hash sync, pass-through auth, federation
- Authentication methods: passwords, MFA, passwordless (Windows Hello, FIDO2, Authenticator)
- Conditional Access
- Entra ID roles (built-in) vs Azure RBAC — know the difference
- Identity Protection
- Entra ID Governance: entitlement management, access reviews, Privileged Identity Management (PIM)

### 3. Capabilities of Microsoft Security Solutions (35-40%)

**Largest domain — spend the most time here.**

- Azure DDoS Protection
- Azure Firewall
- Web Application Firewall (WAF)
- Network Security Groups (NSGs)
- Azure Bastion and JIT access
- Microsoft Defender for Cloud (CSPM, CWPP, secure score)
- Microsoft Sentinel (SIEM/SOAR basics)
- Microsoft Defender XDR suite:
  - Defender for Endpoint
  - Defender for Office 365
  - Defender for Identity
  - Defender for Cloud Apps
- Microsoft 365 Defender portal

### 4. Capabilities of Microsoft Compliance Solutions (20-25%)

- Service Trust Portal
- Microsoft Privacy Principles
- Microsoft Priva
- Microsoft Purview compliance portal
- Compliance Manager and compliance score
- Information Protection: sensitivity labels, data classification
- Data Loss Prevention (DLP)
- Records management and retention policies
- Insider Risk Management
- eDiscovery and audit
- Resource governance: Azure Policy, Blueprints, resource locks

---

## Week-by-Week Study Plan

### Week 1 — Foundations + Entra Basics (2026-04-27 → 2026-05-03)

**Goal:** Lock in Domain 1 (concepts) and the first half of Domain 2 (Entra ID basics).

| Day | Focus | Time |
|-----|-------|------|
| Mon | MS Learn: "Describe the concepts of security, compliance, and identity" — full module | 90 min |
| Tue | Zero Trust + shared responsibility deep-dive (read + YouTube: John Savill SC-900 Study Cram pt 1) | 60 min |
| Wed | Entra ID editions, tenants, identity types | 75 min |
| Thu | Authentication methods (MFA, passwordless, Windows Hello, FIDO2) | 75 min |
| Fri | Rest / light review — flashcards only | 20 min |
| Sat | Hands-on: create free Entra tenant, add a user, enable MFA | 90 min |
| Sun | Week 1 recap quiz (MeasureUp free demo or Whizlabs sample) | 45 min |

**Checkpoint:** Can you explain Zero Trust in 3 sentences? Can you name the 5 authentication methods Entra supports?

---

### Week 2 — Entra Deep Dive (2026-05-04 → 2026-05-10)

**Goal:** Finish Domain 2 — the second-highest-weighted area.

| Day | Focus | Time |
|-----|-------|------|
| Mon | Conditional Access — policies, signals, controls | 75 min |
| Tue | Entra ID roles vs Azure RBAC (this is a common trick question) | 60 min |
| Wed | Identity Protection: risky users, risky sign-ins, risk policies | 60 min |
| Thu | Entra Governance: PIM, access reviews, entitlement management | 75 min |
| Fri | External identities: B2B guest users vs B2C tenants | 45 min |
| Sat | Hands-on: configure a Conditional Access policy in your tenant | 90 min |
| Sun | Practice quiz — Entra domain only (aim for 75%+) | 60 min |

**Checkpoint:** Can you distinguish when you'd use Entra ID roles vs Azure RBAC? Can you describe what PIM does in one sentence?

---

### Week 3 — Security Solutions (2026-05-11 → 2026-05-17)

**Goal:** Nail Domain 3 — this is 35-40% of the exam. Everything else is secondary to this week.

| Day | Focus | Time |
|-----|-------|------|
| Mon | Azure network security: NSGs, Azure Firewall, DDoS, WAF, Bastion | 90 min |
| Tue | Microsoft Defender for Cloud — CSPM, secure score, regulatory compliance | 75 min |
| Wed | Microsoft Sentinel — SIEM vs SOAR, workbooks, playbooks (concepts only) | 60 min |
| Thu | Defender XDR suite — Endpoint, Office 365, Identity, Cloud Apps (know what each one protects) | 90 min |
| Fri | Microsoft 365 Defender portal navigation + incidents | 45 min |
| Sat | Full practice exam #1 (MeasureUp or ExamTopics) — review every wrong answer | 120 min |
| Sun | Rewatch John Savill SC-900 Study Cram (2-hour single-sit review) | 120 min |

**Checkpoint:** Can you match each Defender product to what it protects without looking? Can you explain the difference between Defender for Cloud and Microsoft Sentinel?

---

### Week 4 — Compliance + Exam (2026-05-18 → 2026-05-23)

**Goal:** Finish Domain 4 and do high-reps practice exams. Take the exam Saturday.

| Day | Focus | Time |
|-----|-------|------|
| Mon | Microsoft Purview: information protection, sensitivity labels, DLP | 90 min |
| Tue | Compliance Manager, Service Trust Portal, Priva | 60 min |
| Wed | eDiscovery, audit, insider risk management, records management | 75 min |
| Thu | Azure Policy, Blueprints, resource locks | 45 min |
| Fri | Full practice exam #2 — target 80%+; review weak spots only | 120 min |
| **Sat** | **EXAM DAY** — light review in morning, exam mid-day | — |
| Sun | Update LinkedIn + resume + `skills-inventory.yml` with the new cert | 30 min |

**Exam day reminders:**

- Online proctored: quiet room, clean desk, government ID, one monitor only, camera on the whole time
- Arrive 30 min early to handle check-in
- ~45 questions, 60 minutes, typically 700/1000 to pass
- Flag and skip anything you're unsure of; return after clearing the easy ones

---

## Primary Resources

**Free:**

- [Microsoft Learn SC-900 learning path](https://learn.microsoft.com/en-us/training/paths/describe-concepts-of-security-compliance-identity/) — authoritative source
- [John Savill's SC-900 Study Cram (YouTube)](https://www.youtube.com/watch?v=nzu7GtMRUm0) — the single most useful review video; rewatch Week 3 and morning of exam
- [Microsoft Virtual Training Days: SCI Fundamentals](https://www.microsoft.com/en-us/trainingdays) — free + often grants an exam voucher
- [ExamTopics SC-900 dumps](https://www.examtopics.com/exams/microsoft/sc-900/) — use for practice questions, but read community discussion (top-voted answer is often more accurate than the listed one)

**Low-cost (optional):**

- MeasureUp SC-900 practice exam (~$89) — official Microsoft practice partner; skip if budget is tight
- Whizlabs SC-900 ($15-20 on sale) — lower-quality questions but cheap high-volume practice

---

## Tracking

Update these as you progress:

- [ ] Day 1: Check Microsoft Virtual Training Days for free voucher opportunity
- [ ] Week 1 quiz: ___% (target 70%+)
- [ ] Week 2 quiz: ___% (target 75%+)
- [ ] Week 3 practice exam #1: ___% (target 70%+)
- [ ] Week 4 practice exam #2: ___% (target 80%+ before booking)
- [ ] Exam scheduled for: ___________
- [ ] Exam passed: ___________
- [ ] `skills-inventory.yml` updated
- [ ] LinkedIn badge added
- [ ] Resume updated (add to Certifications section)

---

## Notes

- **If you hit 80%+ on practice exam #2 early:** book the exam sooner and free up time for ST-02 (FastAPI) work.
- **If you're below 70% on practice exam #1 in Week 3:** slip the exam by one week rather than failing — a retake costs another $99 (unless you have a voucher).
- **Pairing with current studies:** SC-900 studying is mostly conceptual reading/videos, so it slots well around your Python Crash Course and SQLBolt work without conflict.
- **After SC-900:** the logical next low-cost cert is either AI-900 (same voucher pattern, complements AI-102 goal) or you skip fundamentals and go straight to AZ-204 prep per your existing ST-03 plan.
