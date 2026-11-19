# Operations Index

The weekly operating cadence and the IT management practice. Read the operational core first — it carries current state.

## Operational Core (read these first)

| File | What | Use when |
| --- | --- | --- |
| `TASKS.md` | Active task list across all realms, markdown checkboxes | Checking what is open or due |
| `DASHBOARD.md` | Current context, active workstreams, targets | Establishing what is in flight |
| `routine.md` | Weekly rhythm table, A/B project weeks, review checklist | Determining this week's shape |
| `progress/` | Progress logs | Reviewing what shipped |
| `reflections/` | Retrospective notes | Looking back on a period |

These three markdown files are the source of truth. `dashboard-app/` renders them live — it never caches, so the files always win.

## Review tools

- `python3 tools/arms/app.py` opens the local review service at `http://127.0.0.1:8790`; it does not replace the operational core.
- `tools/arms/routines.py` inventories schedules and produces local checks and recommendations. Suggested routines are not enabled automatically.
- `second-brain/README.md` documents source-linked memory queries and atomic saves.
- `artifacts/index.html` is the searchable artifact inbox; source and image-description navigation lives in [CONTENT.md](CONTENT.md).
- `tools/arms/README.md` records all twelve ARMS levels, verification and remaining external prerequisites.

## IT Management Playbook

Vendor-neutral operational playbook, numbered by lifecycle stage. See `IT Mgmt/README.md` for scope and `IT Mgmt/MANIFEST.md` for the module list.

| Path | Stage |
| --- | --- |
| `IT Mgmt/00-meta/` | Authoring rules — `AGENT-CONTRACT.md`, `BLUEPRINT.md`, `TAXONOMY.md`, `STYLE-GUIDE.md` |
| `IT Mgmt/10-day1-takeover/` | Day-1 takeover framework |
| `IT Mgmt/20-hardware-lifecycle/` | Hardware and asset operations |
| `IT Mgmt/30-sop-engine/` | SOP governance |
| `IT Mgmt/40-saas-lifecycle/` | SaaS lifecycle management |
| `IT Mgmt/50-tool-mappings/` | Vendor-neutral tool mappings |
| `IT Mgmt/60-people-lifecycle/` | Onboarding and offboarding |
| `IT Mgmt/70-change-incident/` | Change and incident management |
| `IT Mgmt/80-continuity-ops/` | Continuity operations |
| `IT Mgmt/90-case-studies/` | Worked examples |
| `IT Mgmt/tools/validate.py` | Playbook structure validator |
| `IT Mgmt/PARKING.md` | Deferred ideas |

Read `IT Mgmt/00-meta/AGENT-CONTRACT.md` before authoring playbook content.

**Excluded:** `IT Mgmt/Employer-IT-Playbook-Private/` — employer-specific, not indexed.

## Related

- Dashboard that renders the operational core: `dashboard-app/` → [CODE.md](CODE.md)
- Study and certification plans: `plans/` → [LEARNING.md](LEARNING.md)
