# Jane Street — IT Operations Engineer
## Interview Prep | Roosevelt Segura | April 2026

---

## Role Snapshot

**Position:** IT Operations Engineer (NYC, onsite)
**Team:** Global IT Operations — mixed Windows / Linux / macOS across multiple continents, supporting trading operations
**Stack you'd touch:** Desktop environments, network infra, application platforms, Windows domain (AD/GPO), monitoring, PowerShell/Bash automation
**Physical:** Occasional lifting up to 40 lbs; onsite NYC; flex for occasional evening/weekend hours

---

## Your 30-Second Pitch

> "I'm an IT Engineer with 7+ years supporting technically sophisticated users in finance-adjacent, biotech, and hospital environments. Most recently I delivered Tier 1/2 support to a 24/7 global org spanning North America, India, and Europe — hitting 95%+ SLA in Zendesk while building things that stuck: I stood up Jira Service Management from scratch at Ventus, rolled out GitHub Enterprise for the dev team, and centralized SQL Server for lab data. I'm strongest in Windows/AD, M365, and networking, comfortable across macOS and Linux, and I'm actively deepening my scripting and cloud chops. The Jane Street role hits exactly where I want to be — high-caliber users, mixed OS at global scale, and real ownership."

---

## Resume → Job Description Crosswalk

| What Jane Street Wants | Your Proof Point |
|---|---|
| Windows Desktop/Server in production | Co-managed M365 tenant for 100+ users at Ventus; Win Server admin across Foundation Medicine, MGH, Jounce |
| Active Directory, Group Policy, Windows admin sub-systems | AD/GPO daily across every role since 2019; user provisioning, OU structure, GPO troubleshooting |
| Build/configure Win + Linux + macOS laptops, desktops, servers | "Managed complete new-hire setups" at Peak Scientific; onboarded 15+/month at Foundation Medicine |
| Networking principles | Cisco Meraki at Jounce; FortiGate VPN troubleshooting; DNS/DHCP/VPN across all roles |
| Monitoring critical systems | Cortex XDR alert investigation at Jounce; Defender; SLA monitoring in Zendesk |
| Real-time troubleshooting + clear comms | 95%+ SLA at Peak; cross-time-zone handovers; HIPAA hospital users at MGH |
| PowerShell / Bash automation | AD user mgmt scripting, M365 admin via PowerShell; building Python + Bash now |
| Mixed OS environment | Windows 10/11 + Server, macOS, Linux — all on resume |
| Working with technically sophisticated users | MGH radiologists, Foundation Medicine lab staff, Ventus research scientists, biotech devs |
| Written docs + KB maintenance | SLA-driven ticketing process improvements; recommended infra changes that reduced repeat issues |
| Lift up to 40 lbs, onsite, occasional evenings/weekends | Army Reserve 12W (Carpentry & Masonry) — 8 years; 24/7 global support model at Peak |

---

## Top Stories (STAR-Ready)

### Story 1 — "Tell me about a project you led."
**Jira Service Management Build (Ventus Therapeutics)**
- **Situation:** No formal IT ticketing system existed; requests came via email, Slack, hallway.
- **Task:** Build IT support infrastructure from the ground up for 100+ users.
- **Action:** Designed request types, workflows, SLAs, and approval chains in Jira Service Management. Migrated existing ad-hoc tickets, trained the team, documented runbooks.
- **Result:** Became the system of record for IT. Tied directly to *"projects to optimize the way we work"* and *"elegant, scalable solutions during quieter periods."*

### Story 2 — "Walk me through a complex technical project."
**OneView Windows 10 Upgrade (MGH/BWH Radiology)**
- **Situation:** HIPAA-regulated hospital environment, 200+ clinical workstations, zero tolerance for clinical disruption.
- **Task:** Coordinate OS migration across two campuses (BWH + MGH).
- **Action:** Scheduled migrations around clinical hours, validated peripherals (PACS, dictation), coordinated with radiologists, executed rollback plan.
- **Result:** Migration completed without disrupting patient care workflows.

### Story 3 — "When did you have to keep things running under pressure?"
**Office Relocation IT Setup (Ventus)**
- **Situation:** Full office move; research operations couldn't lose data continuity.
- **Task:** Lead IT infrastructure setup at the new site.
- **Action:** Pre-staged hardware, cabled network, validated AD/M365 connectivity before users arrived, set cutover windows.
- **Result:** **Zero unplanned downtime.** Lab and dev teams resumed work the next morning.

### Backup Stories
- **GitHub Enterprise rollout (Ventus)** — introduced modern version control for the dev team.
- **SQL Server centralization (Ventus)** — built infra from scratch for lab data accessibility.
- **Foundation Medicine major incident response** — executed business continuity procedures during platform outage.
- **Peak Scientific recurring-ticket analysis** — identified pattern, recommended infra fix, repeat tickets dropped.

---

## The PowerShell Question (likely)

Be honest, then pivot to growth:

> "My day-to-day scripting has leaned more toward Python and Bash recently — I'm working through AZ-204 — but I've used PowerShell for the standard admin work: AD user provisioning with `Get-ADUser` / `Set-ADUser`, bulk M365 license assignments via MSOnline and Graph modules, exporting mailbox stats, restarting services on remote machines with `Invoke-Command`. I'd be excited to go deeper here — the automation focus is one of the things drawing me to this role."

**Cmdlets to have on the tip of your tongue:**
- `Get-ADUser -Filter * -Properties LastLogonDate`
- `Add-ADGroupMember -Identity "GroupName" -Members user1, user2`
- `Get-MailboxStatistics -Identity user@domain.com`
- `Test-NetConnection -ComputerName server -Port 443`
- `Import-Csv users.csv | ForEach-Object { New-ADUser ... }`
- `Invoke-Command -ComputerName SRV01 -ScriptBlock { Get-Service }`

---

## Likely Behavioral Questions

| Question | Your Angle |
|---|---|
| "Tell me about a mistake you made." | JD explicitly calls out *humility to acknowledge mistakes*. Have one ready — short, owned, what you fixed, what you do differently now. |
| "How would you troubleshoot a senior user with a VPN problem?" | Listen first. One clarifying question. Isolate layer (network vs. account vs. endpoint). Communicate ETA in writing. Follow up after resolution. |
| "How do you handle a user smarter than you on their domain?" | Lean on MGH/biotech experience. Respect their expertise, own the IT layer, ask good questions, don't fake it. |
| "Why Jane Street?" | Mixed OS at global scale; real infrastructure, not just tickets; high-caliber users; immediate feedback loop; growth path into deeper automation and scripting. |
| "What's your weakness?" | Honest answer + active fix. (e.g., "Deeper PowerShell — actively working it; here's what I've used it for.") |
| "Tell me about a time you disagreed with a teammate." | Pick a real one. Frame around evidence, listening, and the outcome. |

---

## Technical Topics to Refresh (5-min skim)

- **Active Directory:** OUs, security vs. distribution groups, FSMO roles (Schema Master, Domain Naming, RID, PDC, Infrastructure), `dcdiag`, `repadmin`, replication basics
- **Group Policy:** GPO precedence (Local → Site → Domain → OU), `gpresult /h`, `gpupdate /force`, loopback processing
- **DNS:** A vs. CNAME vs. MX vs. TXT/SPF/DKIM, forward vs. reverse lookup, `nslookup` / `Resolve-DnsName`
- **DHCP:** scope, lease, reservation, options (3 = gateway, 6 = DNS, 66/67 = boot)
- **Networking:** OSI layers, TCP vs. UDP, common ports (22, 53, 80, 389, 443, 445, 636, 3389, 5985/5986)
- **Imaging:** PXE boot, MDT, Autopilot for Windows, Munki/Jamf for macOS basics
- **Linux basics:** `systemctl`, `journalctl`, `ssh`, `top`/`htop`, file permissions, `grep`/`awk`/`sed`
- **macOS basics:** MDM, profiles, FileVault, Terminal commands

---

## Smart Questions to Ask Them

1. "What does a great first 90 days look like for this role?"
2. "How is work split between reactive support and proactive automation / project work?"
3. "What's the on-call and after-hours rhythm for the NYC team?"
4. "What automation tooling is the team standardizing on right now?"
5. "How does IT Ops interact with the trading desks day-to-day?"
6. "What's the biggest open project the team would want this hire to take on?"

---

## Last-Minute Reminders

- **Lead with curiosity, not credentials.** JD values humility + clarifying questions explicitly.
- **Trading floor = high stakes, calm voice.** Lean on Army + 24/7 support background.
- **Don't oversell PowerShell. Don't undersell, either.** You've done real admin scripting.
- **You're onsite, NYC, lifting equipment.** Confirm enthusiasm for in-person work early.
- **Mirror their language.** "Mixed environment," "trading operations," "elegant, scalable solutions."
- **Bring a notepad.** Write down their names. Reference them by name in follow-up.
- **Thank-you email same day.** One specific thing you discussed + one thing you're excited about.

---

_Prep doc — Jane Street IT Operations Engineer — April 2026_
