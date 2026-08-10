# AZ-104 Study Plan — Direction Track (Linux + Python + Bicep)

_Created 2026-05-24. Companion to `plans/job-search-plan-2026-05.md` (income track). This is the cloud-infra/automation lane you said you actually want — done as cert prep so it counts twice._

## Why this cert, this way

AZ-104 is the **hinge**: it overlaps the endpoint/identity world you know (Entra) and the cloud-native/DevOps world you want (compute, containers, IaC, Linux VMs), and it's the prerequisite into AZ-400 (DevOps Expert). See `project_cert_direction_2026` memory for the full reasoning.

**The rule that makes this dual-purpose:** every lab is done on a **Linux VM**, driven by **Azure CLI + Python**, and deployed with **Bicep** — never click-ops in the portal except to *verify*. That way:
- You scratch the Linux + Python itch you came in with.
- You build the automation muscle the cloud lane hires for.
- Your AZ-104 answers in Tier-2 SysAdmin interviews come from your hands, not a textbook.

## Pace & target

- **~6–8 hrs/week**, on the protected study mornings (Tue/Wed/Thu) from the job-search calendar. Job search owns the afternoons.
- **~10 weeks → target exam ≈ first week of August 2026.** You already hold AZ-900 (concepts) + AWS CCP, so the bottleneck is hands-on, not theory. Adjust if a job lands and eats time — the cert waits, the paycheck doesn't.
- Official skills outline (skills measured as of Apr 17, 2026): [AZ-104 study guide](https://learn.microsoft.com/credentials/certifications/resources/study-guides/az-104). Five domains, weighted below.

## Week 0 — Setup (do once, ~2 hrs)

- [x] Azure account with **pay-as-you-go** + the **$200 free credit** (new accounts). If credit is used, set a hard spending cap.
- [ ] **Cost guardrails (this is also AZ-104 Domain 1):** create a **Budget + alert** at $25, and put **auto-shutdown** on every VM. Delete resource groups at the end of each lab. _Treat cost control as a graded exercise, not overhead._
- [ ] Install locally: **Azure CLI** (`az`), **VS Code + Bicep extension**, **Python 3** with a venv, and the SDK: `pip install azure-identity azure-mgmt-resource azure-mgmt-compute azure-mgmt-network azure-mgmt-storage`.
- [ ] Create a **GitHub repo `az104-labs`** — every Bicep file and Python script gets committed. This becomes a portfolio piece you can point Tier-2/3 employers to.

## Where to start (given your Docker + Linux home lab)

You don't have to go in order. Since you're **already standing up Docker + Linux locally**, ride that momentum — start at **Weeks 5–6 (Compute)**, because that's exactly where your home lab plugs into Azure:

- **Your local Docker skills transfer directly** → containerize an app locally, push the image to **Azure Container Registry (ACR)**, run it on **Azure Container Apps / ACI**. Same Docker workflow, just a cloud registry + runtime on the end.
- **Your local Linux box → Azure Linux VMs** are the same OS skills (SSH, systemd, nginx, bash, `cloud-init`). What you practice at home *is* the lab.
- **Concrete first lab this week:** containerize your **FastAPI dashboard** locally with Docker (home lab) → `az acr build` to push it → deploy to Container Apps. That single exercise is the seed of the Week-10 capstone *and* covers a chunk of the highest-weighted exam domain.

Just do a **30-min pre-step first**: learn `az login`, resource groups, and a minimal Bicep deploy (from Week 0/Week 1) so you have somewhere to put things. Then jump to Compute. Circle back to identity/governance, storage, and networking after — you already have the AZ-900 conceptual base, so leading with hands-on Compute won't leave gaps.

> One bridge worth knowing: **Azure Arc** can onboard your *home* Linux box into Azure as a managed server (governance, monitoring, Update Manager). It's lightly in AZ-104 and core to AZ-800 — a satisfying way to make the home lab and the cloud one continuous environment once you're rolling.

## Week-by-week (mapped to exam domains)

### Weeks 1–2 — Identity & Governance (20–25%)
MS Learn path: *Manage identities and governance in Azure.*
- **Topics:** Entra users/groups, RBAC roles & scopes, subscriptions, Azure Policy, tags, resource locks, management groups, cost (budgets/alerts).
- **Linux/Python/Bicep lab:**
  - Python script using `azure-identity` + `azure-mgmt-resource` to **list every resource and flag any untagged** one, then apply a default tag. (Real automation, real Python.)
  - Bicep: deploy a resource group with an **Azure Policy** that *denies* untagged resources.
  - CLI: create users/groups and assign RBAC at different scopes via `az role assignment create`.

### Weeks 3–4 — Storage (15–20%)
MS Learn path: *Implement and manage storage in Azure.*
- **Topics:** storage accounts, redundancy, SAS tokens, access keys, Blob & Files, tiers, lifecycle management, AzCopy.
- **Linux/Python/Bicep lab:**
  - Bicep: deploy a storage account + blob container.
  - Python (`azure-mgmt-storage` / `azure-storage-blob`): script that **uploads files, sets a SAS token, and moves blobs between tiers**.
  - From a **Linux VM**, mount an **Azure Files** share over SMB and use `azcopy` from the CLI.

### Weeks 5–6 — Compute (20–25%) ← the heart of the Linux work
MS Learn path: *Deploy and manage Azure compute resources.*
- **Topics:** ARM/**Bicep** deployment, **Linux VMs**, VM scale sets, disks, **containers** (ACI, Container Apps, ACR), App Service.
- **Linux/Python/Bicep lab:**
  - Bicep: deploy an **Ubuntu VM**; SSH in, install **nginx** via a `cloud-init`/bash script, serve a page.
  - Containerize a small app (your FastAPI dashboard is a perfect candidate), push the image to **ACR**, run it on **Azure Container Apps**.
  - Python: script to **start/stop/resize** VMs on a schedule (cost discipline + automation in one).

### Weeks 7–8 — Networking (15–20%)
MS Learn path: *Configure and manage virtual networking.*
- **Topics:** VNets, subnets, peering, NSGs, Bastion, service/private endpoints, Azure DNS, load balancer.
- **Linux/Python/Bicep lab:**
  - Bicep: deploy **two Linux VMs behind an Azure Load Balancer** in a VNet; lock down with **NSGs**; reach them via **Bastion** (no public IP).
  - CLI/Python: script that audits NSG rules and reports anything open to `0.0.0.0/0`.

### Weeks 9 — Monitor & Maintain (10–15%) + KQL
MS Learn path: *Monitor and maintain Azure resources.*
- **Topics:** Azure Monitor, **Log Analytics + KQL**, Network Watcher, Backup, Site Recovery.
- **Linux/Python/Bicep lab:**
  - Point your Week 5–8 VMs at a **Log Analytics workspace**; write **KQL** queries for CPU, failed SSH logins, and HTTP errors. _(KQL is cross-cutting — it also shows up in SC-200, AZ-400, and even MD-102.)_
  - Configure **Azure Backup** on a VM via Bicep.

### Week 10 — Capstone + exam prep
- **Capstone (portfolio piece):** one Bicep deployment + Python wrapper that stands up **2 Linux web VMs behind a load balancer, in a secured VNet, with monitoring and a budget alert** — one command, fully reproducible. Commit to `az104-labs` with a README. _This is the artifact you link from the `devops-cloud` and `systems-infra` résumés._
- Take the **free [AZ-104 practice assessment](https://learn.microsoft.com/credentials/certifications/exams/az-104/practice/assessment)**; review weak domains.
- **Schedule the exam** (passing = 700).

## How this feeds the job search

- **Tier 2 interviews:** when the Azure/M365 SysAdmin JD asks about VMs, networking, identity, and IaC — you answer from labs you built this week, not theory.
- **Portfolio:** the `az104-labs` repo + capstone is concrete proof for `devops-cloud` / `systems-infra` résumés and the GitHub profile README.
- **Next rung:** AZ-104 → AZ-400 (DevOps Expert), or AZ-204 if you lean developer. Either way, the Linux + Python + Bicep base carries straight over.

## Resources

- Official skills outline + free practice assessment (links above).
- Microsoft Learn AZ-104 learning paths (free, hands-on sandbox modules — use these before spending your own credit).
- Azure CLI docs / `az` interactive; Bicep docs; Azure SDK for Python docs.
