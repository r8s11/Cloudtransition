# Jane Street — IT Operations Engineer (NYC, onsite)

**Interview prep, mapped to your resume.** Last updated: 2026-04-27.

---

## 1. Who is Jane Street and why does this role matter?

Jane Street is a quantitative proprietary trading firm. They trade their own capital across global markets — equities, ETFs, options, crypto, futures — and are one of the largest market makers in the world. Headquartered at One Manhattan West (NYC), with offices in London, Hong Kong, Amsterdam, and Singapore.

Things that matter for IT Ops:

- **Technology IS the business.** When trading systems are down, the firm loses money by the second. IT Ops sits one layer below the engineers who run the trading platform — your job is to keep the people who keep the markets moving fully operational.
- **Mixed Windows / Linux / macOS environment** with a strong Linux culture (most quant/dev work is done on Linux; OCaml is their dominant programming language). Trading desks run Windows; engineers and researchers lean Linux/macOS.
- **Sophisticated users.** You'll be supporting traders, quant researchers, and software engineers — people who can read a stack trace and won't tolerate hand-waving. The JD literally says "patient listening, comfort with asking clarifying questions, and the humility to acknowledge mistakes." Take that line seriously — they screen for it.
- **Culture is famously collegial, low-ego, and intellectually honest.** They want curiosity, not bravado. Don't oversell. Admit what you don't know, then describe how you'd figure it out.
- **Onsite, NYC.** No hybrid wiggle room for this role. Confirm you're good with daily commute / 40 lb lifts / occasional evenings and weekends.

---

## 2. JD-to-resume mapping (your strongest evidence)

| What they want | Your strongest proof |
|---|---|
| Tier 1/2 support for sophisticated users | Peak Scientific — Tier 1/2 to 100+ users in a 24/7 global model (NA / India / Europe), 95%+ SLA |
| Build/configure Windows/Linux/macOS laptops, desktops, servers | Jounce (full lifecycle, VM creation), Ventus (M365 tenant, SQL Server stand-up), Foundation Medicine (laptop config + onboarding 15+/mo) |
| Windows domain / AD / Group Policy | Listed under Infrastructure; you've used it across MGH, Jounce, Ventus, Peak |
| Networking principles | Cisco Meraki and FortiGate hands-on at Jounce; VPN troubleshooting at Foundation Medicine |
| Real-time troubleshooting + empathy | "Played during major incidents, executing business continuity procedures" at Foundation Medicine |
| Documentation / KB maintenance | Built Jira Service Management from scratch at Ventus — workflows, SLAs (this implies KB and process docs) |
| Evening/weekend flexibility | Already worked 24/7 global support model at Peak |
| 40 lb physical lifts | Army Reserve, deployed Kuwait, S&R training — frame as "I've done physical work in worse conditions; not a concern" |
| Bonus: Linux / macOS familiarity | Listed (basic Linux, macOS support at Jounce/Peak); be honest about depth |
| Bonus: PowerShell / Bash scripting | Currently building Python/Docker/CI/CD; this is your weakest spot — see Section 5 |

**Headline pitch (use in recruiter screen and "tell me about yourself"):**

> "I'm an IT engineer with 7+ years supporting distributed technical environments. Most recently I've been delivering Tier 1/2 support to a 24/7 globally distributed organization across North America, India, and Europe — handling cross-time-zone handoffs, M365 administration, and infrastructure troubleshooting at scale. Across my career I've built things from the ground up — Jira Service Management at Ventus, GitHub Enterprise for a dev team, centralized SQL infrastructure for lab researchers — not just used what was already there. I'm AWS Cloud Practitioner and AZ-900 certified, and I'm building deeper Azure and automation skills now. The Jane Street role caught my attention because the user base is exactly the kind of technically sophisticated environment I do my best work in, and I want to be where the technology is the business."

---

## 3. The honest gaps — and how to handle them

Don't pretend these don't exist. Jane Street will sniff out an overclaim instantly.

### Gap 1: PowerShell scripting depth
The JD calls PowerShell out specifically as a quiet-period automation tool.

**How to handle:** "I've used PowerShell for ad-hoc admin tasks — pulling AD users, M365 license audits, basic mailbox queries — but I haven't written production-grade automation in it. I'm comfortable with the language and I'd ramp fast; my Python is stronger and the patterns transfer." Then prep a couple of PowerShell snippets you *do* know (see Section 5).

### Gap 2: Linux depth
JD lists Linux as a bonus, but in a Jane Street environment Linux is everywhere.

**How to handle:** "Linux experience has been at the user-support level — package issues, network troubleshooting, basic shell. For deeper administration — systemd, package management at scale, kernel-level issues — I've not been the primary admin." Then mention you've been working through it on your AZ-204 path and it's a skill you're actively building.

### Gap 3: Tenure pattern
You have several 1–2 year stints. This is the same pattern that's been hurting you in screens.

**How to handle:** Have a clean, short narrative ready. Don't get defensive. Example:
> "Two of my shorter roles were contracts — Foundation Medicine and Jounce. The startup roles ended for business reasons outside my control. Peak has been my longest stretch and is where I've most clearly demonstrated the kind of long-term ownership I want to bring here."

### Gap 4: "10+ years" claim
Your memory file flags this — make sure your resume v2 (2026-04-it-engineer.md) says "7+ years" consistently. It does. Good.

---

## 4. Behavioral questions — STAR answers pre-built from your experience

Use these as a base. Practice them out loud until they're natural — *not* memorized.

### Q: Tell me about a time you helped a frustrated, technically sophisticated user.

**S** — At Peak Scientific, a senior R&D engineer in our UK office had a recurring VPN drop that was killing his ability to access lab data; he'd opened three tickets and was visibly frustrated by the time it hit me.
**T** — I needed to actually fix this, not just close another ticket, and rebuild trust.
**A** — First I called him instead of replying in Zendesk — listened to his full account without interrupting, asked clarifying questions about timing and what apps were open during drops. I reproduced the issue with him on a screen-share, captured logs, and looped in our network engineer in India. We traced it to a FortiGate session-timeout misconfiguration affecting a specific traffic pattern. I documented the fix in our KB and proactively pinged a list of users likely affected.
**R** — Issue closed in 48 hours after weeks of churn. The engineer emailed my manager. More importantly, I caught three more reports of the same root cause before they became tickets.

### Q: Tell me about a time you made a mistake.

**S** — At Ventus, when we relocated offices, I'd done the AD/DHCP cutover plan but I missed verifying that one of the lab printers had a static reservation rather than DHCP.
**T** — Day one, the lab team came in and printing was down for the most-used device.
**A** — I owned it immediately — went to the lab, told the team it was my miss, fixed the reservation in under 20 minutes, and stayed late that day to walk through every other lab device manually. I added a printer-and-device pre-cutover checklist to the runbook so the next person wouldn't repeat it.
**R** — Zero further outages from the move. The runbook checklist became the standard process for all subsequent infra changes there.

(This one is gold for Jane Street — they specifically said "humility to acknowledge mistakes.")

### Q: Tell me about building or improving a system.

**S** — At Ventus Therapeutics, IT support was happening over email and Slack DMs with no system, no SLAs, and no record of recurring issues.
**T** — I owned getting us off ad-hoc and onto a real platform.
**A** — I evaluated options, chose Jira Service Management, designed the request types, workflows, SLAs, and routing. I migrated historical email threads into tickets, trained the team on the new intake, and set up weekly reporting on ticket categories.
**R** — Within a quarter we had clear visibility into the top recurring issues, and three of them turned into permanent infrastructure fixes (printer driver standardization, VPN config, and a SharePoint permission template). We went from "everyone DMs Roosevelt" to a real service desk.

### Q: Tell me about handling a high-pressure incident.

**S** — At Foundation Medicine, a major outage hit during a workday — a HIPAA-regulated lab environment, so downtime had compliance implications, not just productivity ones.
**T** — Execute business-continuity procedures and keep lab staff functional while the senior engineers chased the root cause.
**A** — I worked the front-line: communicated status to lab leads, set up offline workstations on the documented BCP path, kept a running log of who was affected and what we'd done for them. I didn't try to be a hero on the root cause — I stayed in my lane and made sure no one was stuck waiting.
**R** — Lab operations stayed running through the incident. Post-mortem singled out the BCP execution as the reason the impact was contained.

### Q: Tell me about a time you collaborated across time zones.

(Peak Scientific NA/India/Europe is your strongest material here — pick a specific incident handover and walk through how you wrote up the state of an open ticket so the next region could pick it up cleanly.)

### Q: Tell me about working in a team where you weren't the strongest technical person.

**S** — At MGH, on the OneView Windows 10 upgrade for Radiology, the senior engineers were running the migration tooling and architecture; I was one of the more junior people on the project.
**T** — Be useful without slowing them down.
**A** — I owned the user-side: pre-migration outreach, scheduling, post-migration validation, and a running list of edge cases I sent to the seniors weekly. I asked questions in writing where I could, in person when I needed to learn faster.
**R** — 200+ workstations migrated across BWH and MGH on schedule, and I came out of the project understanding the imaging and deployment pipelines well enough to support them independently afterward.

### Q: Why Jane Street?

> "Two reasons. First, the user base — supporting people who write the trading systems, who can read a log, who'll push back if I'm wrong, that's the environment I do my best work in. Second, the technology depth. Most of the places I've worked, IT was a cost center. Here, IT Operations is part of how the firm makes money. That changes everything about how seriously the work is taken, and I want to be in that kind of environment."

### Q: Why are you leaving your current role?

(If you're at Peak still — frame around scope and growth: "Peak has been a strong run; I've reached the natural ceiling of the role and the next step there isn't where I want to grow." If you're at Two Sigma, frame around scope/seat fit, and be careful — don't bash them; the quant world is small.)

---

## 5. Technical topics to drill — with quick refresher prompts

Spend a few hours on each over the next week. The goal is *fluency*, not memorization.

### Active Directory & Group Policy
- AD structure: forest → domain → OU → object
- FSMO roles (5 of them): Schema Master, Domain Naming Master, RID, PDC Emulator, Infrastructure Master
- Group types: Security vs Distribution; Scope: Domain Local, Global, Universal
- GPO precedence (LSDOU): Local → Site → Domain → OU; closer to user wins
- `gpresult /h report.html`, `gpupdate /force`
- AGDLP / AGUDLP for permissioning
- Common interview Q: "User can't log in — walk me through troubleshooting." Answer = check account locked/disabled, password expiry, replication health (`repadmin /replsummary`), DNS, Kerberos time skew (>5 min), site/subnet, GPO blocking.

### Windows desktop/server
- Boot process at a high level (POST → MBR/UEFI → bootmgr → winload → kernel → services → logon)
- Event Viewer: System / Application / Security logs and what each tells you
- Services / scheduled tasks
- Imaging concepts (MDT, SCCM, Intune autopilot — be honest you've used Intune)
- Print server troubleshooting (drivers, queues, spooler service)

### Networking
- OSI layers — be able to walk the stack: L1 cable → L2 MAC/switch → L3 IP/router → L4 TCP/UDP → L7 app
- TCP three-way handshake, common ports (53 DNS, 80/443 HTTP/S, 25/587/465 SMTP, 110/143/993/995, 389/636 LDAP, 88 Kerberos, 3389 RDP, 22 SSH, 445 SMB)
- DNS resolution path: client cache → hosts file → resolver → root → TLD → authoritative
- DHCP DORA: Discover, Offer, Request, Acknowledge
- Subnetting basics — be able to do /24 vs /16 vs /22 quickly
- VPN concepts: split tunnel vs full tunnel, common failure modes
- Tools: `ping`, `tracert`/`traceroute`, `nslookup`/`dig`, `netstat`, `ipconfig /all`, Wireshark basics

### Linux fundamentals (this is where they may push you)
- File permissions (`chmod`, `chown`, octal vs symbolic, sticky bit, setuid)
- Common dirs: `/etc`, `/var/log`, `/usr/bin`, `/home`
- Process inspection: `ps aux`, `top`/`htop`, `lsof`, `kill -9`
- systemd: `systemctl status/start/stop/enable`, `journalctl -u <service>`
- Networking: `ip addr`, `ip route`, `ss -tlnp`, `/etc/resolv.conf`
- Package management: `apt`, `yum`/`dnf`
- Logs: `tail -f /var/log/syslog`, `grep`, `awk`, `sed` basics

### macOS support
- MDM concepts (Jamf is industry standard; you've used Intune which is comparable)
- FileVault, Gatekeeper, XProtect
- `defaults write` for prefs, Console.app for logs
- Common issues: keychain, certificates, profile installs

### PowerShell — be ready to read and write basic scripts
Have these patterns at your fingertips:
```powershell
# Get all AD users in an OU
Get-ADUser -SearchBase "OU=Users,DC=corp,DC=local" -Filter * -Properties LastLogonDate

# Find disabled accounts
Search-ADAccount -AccountDisabled | Select Name, DistinguishedName

# M365 license report
Get-MgUser -All | Select DisplayName, UserPrincipalName, AssignedLicenses

# Loop with error handling
foreach ($user in $users) {
    try { Set-ADUser -Identity $user -Department "IT" }
    catch { Write-Warning "Failed for $user : $_" }
}

# Pipeline: filter then act
Get-Service | Where-Object {$_.Status -eq "Stopped" -and $_.StartType -eq "Automatic"} | Start-Service
```

### Bash — same idea
```bash
# Find large files
find /var/log -type f -size +100M -exec ls -lh {} \;

# Tail and grep live logs
tail -f /var/log/syslog | grep -i error

# Loop over hosts
for host in host1 host2 host3; do
  ssh "$host" "uptime"
done

# Check disk usage
df -h | awk '$5+0 > 80 {print $0}'
```

### Troubleshooting framework (tell them this is how you think)

When they give you a scenario, walk it like this *out loud*:

1. **Clarify** — "What exactly is the user seeing? When did it start? Is it just them or a group? What changed recently?"
2. **Reproduce** — Can I see it myself? Same machine, same network, same account?
3. **Isolate** — Local vs network vs identity vs application? OSI layer by layer.
4. **Check the obvious** — Logs (Event Viewer / journalctl), recent changes (patches, GPO), simple things (disk space, DNS, time sync).
5. **Hypothesize and test cheaply** — One change at a time. Document each.
6. **Fix + verify + document** — Fix isn't done until the user confirms and the KB has the entry.

Saying this framework explicitly is a green flag for Jane Street. They're hiring for *how you think*, not what you know.

---

## 6. Likely scenario / "walk me through" questions

Practice these out loud:

1. **"A trader walks up and says her workstation is frozen mid-trade. What do you do?"** Triage: is it just the screen or the whole machine? Don't reboot — could orphan an open position; loop in trading desk lead first; identify what app is hung; capture state for the trader's records; restore minimum viable working environment fast.

2. **"User in our London office can't reach a SharePoint site. NYC users can. Walk me through it."** Identity (is the user provisioned?) → DNS (resolving the same IP from London?) → network path (proxy / VPN / geo-routing) → SharePoint permissions (regional groups?) → recent changes.

3. **"Half of one office can't print. Walk me through it."** Print server vs printer vs network segment? Spooler service? Driver push via GPO? VLAN / subnet correlation.

4. **"You're on call at 2 AM, alert says a domain controller is down. What's your first 10 minutes?"** Confirm alert isn't a false positive (ping, RDP, console), check secondary DCs are healthy and authenticating, page senior if AD-wide impact, document everything in the incident channel.

5. **"User says their Mac is slow. What do you ask?"** Slow at what — boot, login, app launch, network? When did it start? Activity Monitor / `top`? Recent updates? Disk space? FileVault re-encrypting? Background processes?

6. **"Write a script that finds every M365 user who hasn't logged in for 90 days."** PowerShell with `Get-MgAuditLogSignIn` or `Get-AzureADUser` + `LastSignInDateTime`. If they let you pseudocode, do that and explain the logic.

7. **"You roll out a GPO and 50 users can't log in. What do you do?"** Roll back first, diagnose second. Use `gpresult`, check the GPO scope, look at what setting changed (loopback processing? security filtering? WMI filter?). Always have a rollback plan.

---

## 7. Smart questions to ask them

Pick 3–5. The best questions show you've thought about the *work*, not the perks.

- "What does a typical week look like for someone in this seat — what's the rough split between break-fix tickets, project work, and automation/scripting?"
- "When something breaks during market hours, what's the escalation path between IT Ops and the platform / SRE teams?"
- "How does the team decide what to automate? Is it bottom-up from whoever spots the pattern, or is there a planning process?"
- "What's the on-call model? How often does it actually fire?"
- "What does success look like for this role at the 6-month and 12-month mark?"
- "What separates someone who's good in this role from someone who's great?"
- "What's the team's relationship with the trading floor? How embedded are you with the desks?"
- "How does the team handle knowledge sharing — KBs, runbooks, mentoring?"
- "What's the most interesting problem your team has solved in the last six months?"

Save the comp/benefits questions for the recruiter, not the team.

---

## 8. Brain teasers / problem-solving (Jane Street is famous for this)

Even for ops roles, expect at least one logic / probability / estimation question. They're testing how you reason out loud, not whether you nail the answer.

**The rules:**
- Talk through your thinking. Silence is a fail.
- Restate the question in your own words first.
- Pick a starting point — wrong is fine, frozen is not.
- If you get stuck, narrate what's blocking you and ask a clarifying question.
- They'll often nudge — take the nudge gracefully.

**Examples to get warmed up on:**
- "Estimate the number of laptops Jane Street replaces per year." (Fermi estimation — headcount × refresh cycle, plus break/repair rate.)
- "You have 12 coins, one is heavier. With a balance, find it in 3 weighings." (Classic — group of 4 vs 4, etc.)
- "What's the probability of getting at least one 6 in four rolls of a die?" (1 - (5/6)^4 ≈ 51.8%)
- "How would you design monitoring for a system you've never seen before?" (Open-ended — what failure modes matter, what signals catch them, what's the alert threshold and who responds.)

You don't need to be a math whiz. You need to be calm and audible.

---

## 9. Logistics and the day-of

- **Onsite at One Manhattan West.** Confirm address, floor, and contact name in the confirmation email. Plan to arrive 15 min early; the building has security. Photo ID required.
- **Dress:** Business casual — Jane Street is not suit-formal. Slacks and a button-down are fine. No jeans on the first onsite.
- **Bring:** Printed copies of resume (3+), notepad and pen, a list of your prepared questions, water.
- **Phone interviews / virtual rounds:** Test camera/mic an hour ahead. Wired headphones. Quiet, well-lit room. Tab open with your resume and this prep doc.
- **Food:** They often feed you onsite — accept it; sharing a meal is part of the assessment of fit.
- **Energy management:** Onsite loops are usually 4–6 hours. Eat real food beforehand. Bathroom break between rounds is fine and expected.

---

## 10. Final 24-hour checklist

- [ ] Re-read the JD twice.
- [ ] Re-read your resume v2 (`it-engineer/resume-2026-04-it-engineer.md`) — you should be able to talk to every line without notes.
- [ ] Practice the headline pitch out loud 3+ times, on camera.
- [ ] Run through 5 STAR stories cold. Time them — each should land in 2–3 minutes.
- [ ] PowerShell + Bash quick-reference review (Section 5).
- [ ] AD/GPO + networking cheat sheet review (Section 5).
- [ ] Pick your 5 questions to ask.
- [ ] Lay out clothes, charge devices, set out commute plan.
- [ ] Sleep. Coffee in the morning, not the night before.

---

**One last thing.** Jane Street's culture rewards intellectual honesty. If you don't know something, the answer is "I haven't worked with that directly — here's how I'd approach learning it" — never bluffing. The interviewers have seen every flavor of bluff and they will catch it. The candidates who get hired are the ones who are calm, curious, accurate about their own skill level, and obviously good with people. That's you on a good day. Show up as that.

Good luck. You've got real material to work with.
