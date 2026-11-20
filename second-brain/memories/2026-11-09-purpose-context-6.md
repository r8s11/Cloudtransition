# Purpose & context**

> **Purpose & context** Roosevelt is a contractor working at a client site on a large-scale laptop deployment and refresh project. The primary goal is deploying Lenovo Windows 11 laptops to end users by end of summer, with success defined as apps installed and OneDrive restored per device. The broader engagement also involves building credibility, establishing good working relationships, and potentially formalizing IT Asset Management (ITAM) practices at the client. Key stakeholders include a...

_Saved: 2026-11-09T19:47:19Z_

**Purpose & context**

Roosevelt is a contractor working at a client site on a large-scale laptop deployment and refresh project. The primary goal is deploying Lenovo Windows 11 laptops to end users by end of summer, with success defined as apps installed and OneDrive restored per device. The broader engagement also involves building credibility, establishing good working relationships, and potentially formalizing IT Asset Management (ITAM) practices at the client.

Key stakeholders include a client IT manager who is the primary counterpart — Roosevelt has navigated this relationship carefully, working to align rather than bypass the IT manager, and has expressed some concern about the IT manager's follow-through and pace of progress. The project involves coordination with business owners and IT stakeholders across multiple domains.

Roosevelt is a newcomer to this client environment, which shapes a preference for relationship-building approaches over direct confrontation, and for politically careful moves (e.g., co-owning proposals, establishing rapport before raising friction).

---

**Current state**

The deployment project is underway with a ramp-up from a slow start toward a significantly higher weekly throughput needed to hit the end-of-summer target. Key active concerns include:

- **Project momentum**: A stalled period with insufficient meetings and follow-through from the IT manager has been a friction point; Roosevelt has been working to surface this diplomatically using data and structured questions rather than direct criticism
- **Tracker visibility**: Roosevelt lacked visibility into the client IT manager's Excel tracking sheet — this may be an ongoing gap
- **Credential handling**: The current practice of collecting user passwords during setup was flagged as uncomfortable; Temporary Access Pass (TAP) via Entra was identified as the preferred alternative to raise once rapport is established
- **ITAM proposal**: A one-pager was drafted to propose formal IT Asset Management to management, framed around the refresh work already generating clean asset data, with the IT manager positioned as co-sponsor

---

**On the horizon**

- Raising the TAP/password issue verbally once sufficient rapport with the IT manager exists
- Accelerating deployment throughput toward the pace required to hit the end-of-summer deadline
- Potentially formalizing the ITAM proposal through the IT manager
- Completing laptop triage and inventory for older Dell devices being repurposed or retired
- Possible consolidation of discovery and checklist materials into portable reference formats

---

**Key learnings & principles**

- **Data creates urgency better than confrontation**: Letting throughput math surface the problem (devices remaining vs. weeks left vs. required pace) is more effective than direct criticism of the IT manager
- **Align before proposing**: Co-owning initiatives with the IT manager rather than going around them is both politically safer and more likely to succeed
- **Post-meeting written recaps** serve as both factual records and gentle accountability tools
- **Reframe counterparts as fellow victims of bureaucracy** rather than its source when trying to restore momentum without damaging relationships
- **ITAM pitch language**: Speak to management in cost, risk/security, and compliance terms; avoid leading with tool spend; use a phased crawl-walk-run ask
- **Scope USMT as a gap-filler only**: OneDrive KFM handles the majority of migration needs; USMT is for what KFM doesn't cover (PSTs, local-only folders, app data)
- **ESP configuration and pre-provisioning** are the highest-leverage variables for improving Autopilot deployment throughput

---

**Approach & patterns**

- Prefers diplomatically effective strategies over direct confrontation; works through relationships and systems
- Values concise, direct, technically grounded communication with scannable structure
- Favors practical, portable reference formats (checklists, one-pagers, markdown files) over abstract advice
- Approaches sensitive workplace dynamics (e.g., raising process concerns, making proposals) carefully — sequencing rapport before raising friction, verbal before written
- Uses structured discovery questions to build situational awareness early in an engagement rather than assuming environment details
- Tends toward organized, phased approaches (crawl-walk-run) when proposing new initiatives

---

**Tools & resources**

- **Deployment**: Microsoft Autopilot, Intune, SCCM/MDT, Entra ID (including hybrid join and Temporary Access Pass), Enrollment Status Page (ESP), white glove/pre-provisioning mode
- **Migration**: OneDrive Known Folder Move (KFM), USMT (as gap-filler), Files On-Demand
- **Imaging/provisioning**: Windows ICD, provisioning packages (.ppkg)
- **Hardware**: Lenovo laptops (primary refresh), Dell laptops (triage/inventory/repurpose)
- **Asset management**: Dell TechDirect (bulk warranty lookup), ServiceNow (ITSM/ITAM), Excel (client tracker)
- **Reference materials**: Discovery question framework, deployment-phase checklists (KFM, USMT, ICD, Autopilot), ITAM one-pager draft
