#!/usr/bin/env python3
"""Build the structured base CV JSON from resume/master.md.

Extraction only: every string comes from the markdown. No inference, no additions.
Source line numbers are 1-based master.md lines.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
MASTER = ROOT / "resume" / "master.md"


def clean_bold(s: str) -> str:
    return s.replace("**", "").strip()


def strip_heading_note(title: str) -> tuple[str, str | None]:
    m = re.match(r"^(.*?)\s*_\((.*)\)_\s*$", title)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return title.strip(), None


def split_items(raw: str) -> list[str]:
    """Split a comma list, respecting parentheses."""
    out, buf, depth = [], "", 0
    for ch in raw:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        out.append(buf.strip())
    return [x for x in out if x]


def section_bounds(lines, start_marker, end_marker=None):
    start = next(i for i, l in enumerate(lines) if l.startswith(start_marker))
    if end_marker:
        end = next(i for i, l in enumerate(lines) if i > start and l.startswith(end_marker))
    else:
        end = len(lines)
    return start, end


def parse_roles(lines, start, end):
    roles = []
    i = start
    while i < end:
        line = lines[i]
        if line.startswith("### "):
            title, note = strip_heading_note(line[4:])
            heading_line = i + 1
            i += 1
            while i < end and not lines[i].strip():
                i += 1
            employer_line = lines[i]
            m = re.match(r"^\*\*(.+?)\*\*\s+—\s+(.*)$", employer_line)
            if not m:
                raise ValueError(f"Unparsed employer line {i+1}: {employer_line!r}")
            employer, rest = m.group(1), m.group(2)
            location, dates = [p.strip() for p in rest.rsplit(" | ", 1)]
            start_date, end_date = [p.strip() for p in dates.split(" – ", 1)]
            employer_line_no = i + 1

            visibility = "all_variants"
            variant_note = None
            if note and "omitted from variants" in note:
                visibility = "master_only"
                variant_note = "Omitted from every variant by user decision, Oct 2026 (master.md line 8)."
            elif note:
                variant_note = note

            bullets = []
            i += 1
            while i < end and not lines[i].startswith("### "):
                if lines[i].startswith("- "):
                    raw = lines[i][2:].strip()
                    bullets.append(
                        {
                            "id": None,
                            "text": clean_bold(raw),
                            "emphasis_in_master": "**" in raw,
                            "source_lines": [i + 1],
                        }
                    )
                i += 1

            role = {
                "id": None,
                "title": title,
                "employer": employer,
                "location": location,
                "start": start_date,
                "end": end_date,
                "variant_visibility": visibility,
                "source_lines": [heading_line, employer_line_no],
                "bullets": bullets,
            }
            if variant_note:
                role["variant_note"] = variant_note
            if title == "Sr. Desktop Support Specialist" and employer == "Jounce Therapeutics":
                role["display_end_in_variants"] = "Jul 2022"
                role["variant_note"] = (
                    "Variants show Jul 2021 – Jul 2022, absorbing Pillar's dates by user decision, "
                    "Oct 2026 (master.md lines 5, 123)."
                )
            roles.append(role)
        else:
            i += 1
    return roles


def slug(s: str) -> str:
    s = s.lower()
    s = s.replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def main(out_path: Path):
    text = MASTER.read_text()
    lines = text.splitlines()
    sha = hashlib.sha256(text.encode()).hexdigest()

    name = next(l[2:].strip() for l in lines if l.startswith("# "))
    contact_line = next(l for l in lines if "mail@roosevelt.info" in l)
    availability = next(l for l in lines if l.startswith("Open to "))

    parts = [p.strip() for p in contact_line.split(" | ")]
    links = {}
    for p in parts:
        m = re.match(r"^\[([^\]]+)\]\(([^)]+)\)$", p)
        if m:
            key = {"chinola.app": "website", "GitHub": "github", "LinkedIn": "linkedin"}.get(m.group(1), slug(m.group(1)))
            links[key] = m.group(2)

    # Certifications
    cstart, cend = section_bounds(lines, "## Certifications", "## Technical Skills")
    certs = []
    for i in range(cstart, cend):
        m = re.match(r"^- \*\*(.+?)\*\*\s+—\s+(.+?)\s+\((.+)\)\s*$", lines[i])
        if m:
            certs.append({"name": m.group(1), "issuer": m.group(2), "date": m.group(3), "source_lines": [i + 1]})

    # Skills
    sstart, send = section_bounds(lines, "## Technical Skills", "## Professional Experience")
    skills, languages = [], []
    for i in range(sstart, send):
        line = lines[i]
        if not line.startswith("| **"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        category = cells[0].strip("*").strip()
        raw_items = cells[1]
        if category == "Languages":
            languages = split_items(raw_items)
            continue
        if ";" in raw_items:
            head, tail = raw_items.split(";", 1)
            items = split_items(head)
            if ":" in tail:
                in_progress = split_items(tail.split(":", 1)[1].strip())
                skills.append(
                    {
                        "category": category,
                        "items": items,
                        "in_progress": in_progress,
                        "source_lines": [i + 1],
                    }
                )
            else:
                # Semicolon joins one descriptive sub-group, e.g. "ITIL-aligned incident, problem, and change workflows".
                items = items + [tail.strip()]
                skills.append({"category": category, "items": items, "source_lines": [i + 1]})
        else:
            skills.append({"category": category, "items": split_items(raw_items), "source_lines": [i + 1]})

    # Experience
    estart, eend = section_bounds(lines, "## Professional Experience", "## Military Service")
    roles = parse_roles(lines, estart, eend)

    # Military
    mstart, mend = section_bounds(lines, "## Military Service", "## Projects")
    mtitle_line = next(i for i in range(mstart, mend) if lines[i].startswith("### "))
    mtitle, _ = strip_heading_note(lines[mtitle_line][4:])
    memployer_line = next(i for i in range(mtitle_line + 1, mend) if lines[i].startswith("**"))
    m = re.match(r"^\*\*(.+?)\*\*\s+—\s+(.*)$", lines[memployer_line])
    morg, mrest = m.group(1), m.group(2)
    mloc, mdates = [p.strip() for p in mrest.rsplit(" | ", 1)]
    mstart_d, mend_d = [p.strip() for p in mdates.split(" – ", 1)]
    mbullets = []
    for i in range(memployer_line + 1, mend):
        if lines[i].startswith("- "):
            raw = lines[i][2:].strip()
            mbullets.append({"id": None, "text": clean_bold(raw), "emphasis_in_master": "**" in raw, "source_lines": [i + 1]})

    # Projects
    pstart, pend = section_bounds(lines, "## Projects")
    projects = []
    for i in range(pstart, pend):
        line = lines[i]
        if not line.startswith("- "):
            continue
        raw = line[2:].strip()
        m = re.match(r"^\*\*(.+?)\*\*\s+—\s+(.*)$", raw)
        if not m:
            continue
        name_p, body = m.group(1), m.group(2)
        master_only = "_(master only" in body
        body = re.sub(r"\s*_\(master only[^)]*\)_", "", body).strip()
        projects.append(
            {
                "id": None,
                "name": name_p,
                "text": body,
                "variant_visibility": "master_only" if master_only else "projects_variants",
                "source_lines": [i + 1],
            }
        )

    # Stable ids
    role_ids = {
        "Asset Inventories — Client: NY Ross Buying Office": "ross",
        "Two Sigma": "two-sigma",
        "Peak Scientific": "peak",
        "Foundation Medicine (contract)": "foundation-medicine",
        "PSM Partners at Institute for Healthcare Improvement": "psm-partners",
        "Ventus Therapeutics": "ventus",
        "Pillar Biosciences": "pillar",
        "Jounce Therapeutics": "jounce",
        "Massachusetts General Hospital": "mgh",
    }
    for r in roles:
        r["id"] = role_ids[r["employer"]]
        for n, b in enumerate(r["bullets"], 1):
            b["id"] = f"{r['id']}-{n}"

    proj_ids = {
        "PC Refresh Tracking Hub (Ross refresh, 2026)": "pc-refresh-tracker",
        "IT Management Playbook (2026)": "it-management-playbook",
        "Jira Service Management Implementation (Ventus)": "jira-sm-implementation",
        "SQL Server Infrastructure (Ventus)": "sql-server-infra",
        "OneView — MGH/BWH Radiology Windows 10 Upgrade": "oneview-win10",
        "Bug-Tracking Web App (MGH Radiation Oncology)": "bug-tracking-app",
    }
    for p in projects:
        p["id"] = proj_ids[p["name"]]
    for n, b in enumerate(mbullets, 1):
        b["id"] = f"mil-{n}"

    base = {
        "schema_version": "1.0",
        "kind": "base_cv",
        "built_at": "2026-11-12T00:00:00Z",
        "built_by": "cv-adapter",
        "build_note": "Fresh extraction build for the NYC DSS tailoring run. Distinct filename from outputs/base-cv.json to avoid clashing with a parallel run.",
        "source": {
            "file": "resume/master.md",
            "document_title": "MASTER RESUME — single source of truth",
            "last_updated": "2026-10-19",
            "sha256": sha,
            "line_count": len(lines),
            "extraction_rule": "Every field below is copied or restructured from master.md only. Nothing inferred, nothing added. `source_lines` cite master.md line numbers.",
        },
        "identity": {
            "name": name,
            "location": parts[0],
            "phone": parts[1],
            "email": parts[2],
            "links": links,
            "availability_line": availability,
            "languages": languages,
            "source_lines": [12, 14, 16],
        },
        "certifications": certs,
        "skills": skills,
        "experience": roles,
        "military_service": {
            "title": mtitle,
            "organization": morg,
            "location": mloc,
            "start": mstart_d,
            "end": mend_d,
            "source_lines": [mtitle_line + 1, memployer_line + 1],
            "bullets": mbullets,
        },
        "projects": projects,
        "constraints": {
            "master_only_omitted_from_variants": ["two-sigma", "psm-partners", "pillar", "it-management-playbook"],
            "jounce_date_exception": "Variants display Jul 2021 – Jul 2022; master records Jul 2021 – Feb 2022.",
            "tenure_claim": "The '10+ years' tenure claim is the user's decision (master.md line 6). IT roles in master.md begin May 2019.",
            "no_education_section": "SNHU was discontinued; must not appear (resume/CLAUDE.md line 69).",
            "certifications_only_earned": "Do not list in-progress or expired certifications (resume/CLAUDE.md line 68).",
            "work_model": "master.md line 16 records Roosevelt's availability, not any job's work model. A tailored CV must not claim onsite, hybrid, or remote for a posting that does not state it.",
            "source_lines": [5, 6, 8, 16, 160],
        },
        "evidence_gaps": {
            "ai_tools": {
                "status": "absent",
                "searched_for": ["Claude", "ChatGPT", "Gemini", "Copilot", "AI tools", "LLM", "generative", "AI-assisted"],
                "result": "No mention anywhere in master.md. A pending addendum is not part of the fact base. Must not be claimed.",
            },
            "sccm_configmgr": {
                "status": "absent",
                "result": "Microsoft Configuration Manager / SCCM is not named anywhere in master.md. Intune, Autopilot, and traditional imaging are named instead.",
            },
            "lexmark": {
                "status": "absent",
                "result": "Printers appear as supported devices (lines 39, 74, 88) and as peripherals. No printer brand, model, or Lexmark repair evidence exists.",
            },
            "software_packaging": {
                "status": "absent_as_named_practice",
                "result": "Software appears as part of new-hire equipment setup (line 74) and application troubleshooting (line 76). No packaging, MSI, PSADT, or deployment-package work is recorded.",
            },
            "large_wan": {
                "status": "absent",
                "result": "Multi-site support (line 87), global teams (line 70), Cisco Meraki (line 130), and VPN (lines 87, 118) are recorded. The term WAN and any WAN scale claim are not.",
            },
            "powershell": {"status": "absent", "result": "Scripting row lists JavaScript, Node.js, HTML/CSS, Git, Bash; in progress: Python, Docker, GitHub Actions, Terraform, Kubernetes. No PowerShell."},
            "mfa": {"status": "absent", "result": "MFA is not named anywhere in master.md. Conditional Access is named (line 73) but MFA policy enforcement is not."},
            "least_privilege": {"status": "absent_as_named_practice", "result": "master.md records 'access controls' (line 107) and 'access, permissions' (line 108) but never the term least privilege."},
            "runbooks_kb_articles": {"status": "partial", "result": "master.md records detailed ticket documentation (line 63), written async handoffs (line 75), systems documentation (line 97, master-only role), and Jira request catalogs (line 106). It never records authored knowledge-base articles or runbooks."},
            "printer_support": {"status": "present_generic", "result": "Printers appear in the Devices row (line 39), in new-hire equipment setups (line 74), and in conference-room peripherals (line 88). Generic printer support only."},
            "active_directory": {"status": "present", "result": "Lines 35 (skills) and 85 (AD account creation at Foundation Medicine)."},
            "azure": {"status": "present", "result": "AZ-900 certification (line 23); Microsoft Azure in the Cloud row (line 37); Entra ID (Azure AD) in the identity row (line 32)."},
            "cloud_infrastructure": {"status": "present", "result": "AWS (EC2, S3, IAM, VPC) and Microsoft Azure (line 37); AWS Certified Cloud Practitioner (line 22)."},
            "macs": {"status": "present", "result": "macOS in OS and Apple rows (lines 33, 40); ABM + Intune ADE (line 72); mixed Windows/macOS fleet (line 109)."},
            "project_work": {"status": "present", "result": "OneView Windows 10 upgrade across 200+ workstations (line 137); 100+ endpoint refresh (line 52); office relocation with zero unplanned downtime (line 111); Jira Service Management built from scratch (line 106)."},
            "vendor_coordination": {"status": "present", "result": "External vendors on lab equipment maintenance and repair (line 131); GitHub Enterprise evaluated, procured, and deployed (line 107)."},
            "influencing_negotiation": {"status": "partial", "result": "Cross-team partnership (lines 78, 140) and a procurement (line 107) are recorded. Influencing or negotiation as a named skill is not."},
            "civil_service_title": {"status": "not_a_candidate_fact", "result": "IT Project Specialist (95710) is the posting's civil service title, not Roosevelt's title. It must not appear as his title or headline."},
        },
    }

    out_path.write_text(json.dumps(base, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")
    print(f"roles={len(roles)} bullets={sum(len(r['bullets']) for r in roles)} skills={len(skills)} certs={len(certs)} projects={len(projects)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
