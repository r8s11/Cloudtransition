"""
Career Dashboard — FastAPI app that reads workspace YAML/MD files directly.

Run:  uvicorn app:app --reload
Open: http://localhost:8000
"""

from pathlib import Path
from datetime import date
import os
import re
import tempfile

import yaml
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# ── Paths ──────────────────────────────────────────────────────
WORKSPACE = Path(__file__).resolve().parent.parent  # Cloudtransition/
SKILLS_FILE = WORKSPACE / "skills" / "skills-inventory.yml"
GOALS_FILE = WORKSPACE / "goals" / "career-goals.yml"
JOBS_FILE = WORKSPACE / "interviews" / "job-applications.yml"
NETWORK_FILE = WORKSPACE / "networking" / "contacts.yml"
TASKS_FILE = WORKSPACE / "TASKS.md"
DASHBOARD_FILE = WORKSPACE / "DASHBOARD.md"
EDU_FILE = WORKSPACE / "College Planning" / "education-data.yml"
BOOKS_FILE = WORKSPACE / "Books" / "books-data.yml"

# ── Realm Configuration ───────────────────────────────────────
REALMS = [
    {"id": "tasks",     "name": "Tasks",     "file": "TASKS.md",                           "color": "#D97757", "icon": "📋"},
    {"id": "react",     "name": "React",     "file": "plans/react_plan.md",                 "color": "#61dafb", "icon": "⚛️"},
    {"id": "sql",       "name": "SQL",       "file": "plans/sql_plan.md",                   "color": "#e0b840", "icon": "🗄️"},
    {"id": "azure",     "name": "Azure",     "file": "plans/azure-az204-plan.md",            "color": "#0078d4", "icon": "☁️"},
    {"id": "devops",    "name": "DevOps",    "file": "plans/devops-learning-plan.md",        "color": "#5cc98a", "icon": "🔧"},
    {"id": "books",     "name": "Books",     "file": "plans/books-reading-plan.md",          "color": "#9478d4", "icon": "📚"},
    {"id": "education", "name": "Education", "file": "snhu-plan.md",                        "color": "#e05555", "icon": "🎓"},
    {"id": "college",   "name": "College",   "file": "College Planning/education-plan.md",   "color": "#3aa8c1", "icon": "🏫"},
]

# ── App ────────────────────────────────────────────────────────
app = FastAPI(title="Career Dashboard")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


# ── YAML Loader ────────────────────────────────────────────────
def load_yaml(path: Path) -> dict:
    """Load a YAML file, return empty dict if missing or invalid."""
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


# ── Task Parser ────────────────────────────────────────────────
CHECKBOX_RE = re.compile(r'^(\s*- \[)([ xX])(\] .+)$')


def parse_tasks_from_file(path: Path, realm_id: str) -> list[dict]:
    """Parse checklist items from any markdown file, preserving line numbers."""
    if not path.exists():
        return []

    items = []
    current_category = ""
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        stripped = line.strip()

        # Track nearest heading (any level) as category
        if stripped.startswith("#"):
            current_category = stripped.lstrip("#").strip()
            # Remove emoji prefixes
            current_category = re.sub(r'^[\U0001F300-\U0001FAFF\u2600-\u27BF\u2702-\u27B0]+\s*', '', current_category).strip()
            continue

        m = CHECKBOX_RE.match(line)
        if m:
            done = m.group(2) in ("x", "X")
            text = m.group(3)[2:]  # strip "] " prefix
            items.append({
                "text": text,
                "cat": current_category,
                "done": done,
                "realm": realm_id,
                "line": lineno,
            })

    return items


def parse_all_realms() -> dict:
    """Parse tasks across all realms, returning structured data."""
    all_items = []
    realm_stats = []

    for realm in REALMS:
        path = WORKSPACE / realm["file"]
        items = parse_tasks_from_file(path, realm["id"])
        active = [i for i in items if not i["done"]]
        done = [i for i in items if i["done"]]
        realm_stats.append({
            **realm,
            "total": len(items),
            "done_count": len(done),
            "active_count": len(active),
            "pct": round(len(done) / len(items) * 100) if items else 0,
        })
        all_items.extend(items)

    active = [i for i in all_items if not i["done"]]
    done = [i for i in all_items if i["done"]]
    return {
        "active": active,
        "done": done,
        "all": all_items,
        "realm_stats": realm_stats,
        "total": len(all_items),
        "total_done": len(done),
        "total_active": len(active),
    }



class ToggleRequest(BaseModel):
    realm: str
    line: int
    done: bool


# ── Dashboard Parser ──────────────────────────────────────────
def parse_week_number(path: Path) -> int:
    """Extract current week number from DASHBOARD.md."""
    if not path.exists():
        return 1
    content = path.read_text()
    for line in content.splitlines():
        if "(Week" in line:
            try:
                start = line.index("(Week") + 5
                end = line.index(")", start)
                return int(line[start:end].strip())
            except (ValueError, IndexError):
                pass
    return 1


# ── Build Context ─────────────────────────────────────────────
def build_context() -> dict:
    """Read all workspace files and return template context."""

    skills_data = load_yaml(SKILLS_FILE)
    goals_data = load_yaml(GOALS_FILE)
    jobs_data = load_yaml(JOBS_FILE)
    network_data = load_yaml(NETWORK_FILE)
    realm_tasks = parse_all_realms()
    current_week = parse_week_number(DASHBOARD_FILE)
    today = date.today()

    # Skills — flatten for template
    technical_skills = []
    for cat in skills_data.get("technical_skills", []):
        category_name = cat.get("category", "Other")
        for sk in cat.get("skills", []):
            technical_skills.append({
                "name": sk.get("name", ""),
                "category": category_name,
                "proficiency": sk.get("proficiency", "beginner"),
                "years": sk.get("years_experience", 0),
                "last_used": sk.get("last_used", ""),
            })

    soft_skills = []
    for sk in skills_data.get("soft_skills", []):
        soft_skills.append({
            "name": sk.get("name", ""),
            "proficiency": sk.get("proficiency", "low"),
        })

    certifications = []
    for cert in skills_data.get("certifications", []):
        certifications.append({
            "name": cert.get("name", ""),
            "issuer": cert.get("issuer", ""),
            "obtained": cert.get("date_obtained"),
            "expires": cert.get("expires"),
            "credential_id": cert.get("credential_id"),
        })

    # Job stats
    stats = jobs_data.get("statistics", {}).get("2026", {})
    job_stats = {
        "applied": stats.get("applications_sent", 0),
        "screening": stats.get("screening_calls", 0),
        "interviews": stats.get("technical_interviews", 0),
        "onsites": stats.get("onsites", 0),
        "offers": stats.get("offers", 0),
        "rejections": stats.get("rejections", 0),
        "pending": stats.get("pending", 0),
    }

    # Networking goals
    net_goals = []
    for g in network_data.get("networking_goals", []):
        net_goals.append({
            "goal": g.get("goal", ""),
            "progress": g.get("progress", "0/0"),
        })

    # Vision/goals
    vision = goals_data.get("vision", {})
    has_goals = bool(vision.get("title"))

    # Year/quarter progress
    year_pct = round((current_week / 52) * 100)
    q1_pct = min(100, round((current_week / 13) * 100))
    q2_pct = max(0, min(100, round(((current_week - 13) / 13) * 100))) if current_week > 13 else 0
    q3_pct = max(0, min(100, round(((current_week - 26) / 13) * 100))) if current_week > 26 else 0
    q4_pct = max(0, min(100, round(((current_week - 39) / 13) * 100))) if current_week > 39 else 0  # noqa: used in template

    # Projects (from DASHBOARD.md — hardcoded since MD parsing is complex)
    projects = [
        {
            "name": "WODCard",
            "status": "Restarting Week 1",
            "q1_goal": "MVP Live",
            "color": "#D97757",
            "features": [
                "React + Vite + TypeScript frontend",
                "FastAPI backend structure",
                "Card component with flip animation",
                "Timer component, exercise data model",
            ],
        },
        {
            "name": "SalsaSegura",
            "status": "Restarting Week 1",
            "q1_goal": "50 events",
            "color": "#4a7fb5",
            "features": [
                "React TypeScript app deployed to Azure",
                "Events display, header, footer, hero section",
                "Work in progress page",
            ],
        },
        {
            "name": "SalsaTD",
            "status": "Restarting Week 1",
            "q1_goal": "MVP v1.0",
            "color": "#7c5cbf",
            "features": [
                "Game board with turn-based play (2-30 players)",
                "Truth & Dare decks with spiciness levels",
                "Dark mode, scroll indicator, mobile optimized",
                "Card UI with animations, deck reshuffling",
                "Penalty system, Azure Cosmos DB prototype",
            ],
        },
    ]

    # Skill-project matrix
    learning_matrix = [
        {"skill": "React", "wod": True, "salsa": True, "td": True},
        {"skill": "FastAPI", "wod": True, "salsa": False, "td": True},
        {"skill": "Cosmos DB", "wod": True, "salsa": False, "td": True},
        {"skill": "Auth", "wod": True, "salsa": True, "td": True},
        {"skill": "CI/CD", "wod": True, "salsa": True, "td": True},
        {"skill": "Docker", "wod": True, "salsa": False, "td": False},
        {"skill": "K8s/AKS", "wod": True, "salsa": False, "td": False},
        {"skill": "Terraform", "wod": True, "salsa": False, "td": False},
    ]

    # Success metrics
    success_metrics = [
        {"category": "Projects", "goal": "3 production apps", "metric": "Live URLs, real users"},
        {"category": "Certification", "goal": "AZ-204", "metric": "Pass by November"},
        {"category": "GitHub", "goal": "500+ commits", "metric": "Consistent activity"},
        {"category": "Russian", "goal": "B1 Level", "metric": "30-min conversation"},
        {"category": "Books", "goal": "10-12 completed", "metric": "Notes taken"},
        {"category": "Career", "goal": "New role", "metric": "Interviews + offers"},
    ]

    # Application checklist
    app_checklist = jobs_data.get("application_strategy", {}).get("application_checklist", [])

    # Education data
    edu_data = load_yaml(EDU_FILE)
    edu_program = edu_data.get("program", {})
    edu_stats = edu_data.get("degree_stats", {})
    edu_sources = edu_data.get("credit_sources", [])
    edu_phases = edu_data.get("transfer_phases", [])
    edu_timeline = edu_data.get("timeline", [])
    edu_cost = edu_data.get("cost", {})
    edu_actions = edu_data.get("actions", [])

    # Compute total credits by status for stacked bar
    credits_completed = sum(s.get("credits", 0) for s in edu_sources if s.get("status") == "completed")
    credits_planned = sum(s.get("credits", 0) for s in edu_sources if s.get("status") != "completed")

    # Books data
    books_data = load_yaml(BOOKS_FILE)
    books_list = books_data.get("books", [])
    books_categories = books_data.get("categories", [])

    # Build category lookup
    cat_meta = {c["name"]: c for c in books_categories}

    # Stats
    total_books = len(books_list)
    in_plan_count = sum(1 for b in books_list if b.get("in_plan"))
    new_picks = total_books - in_plan_count

    # Group books by category (preserve insertion order, O(n) via dict)
    cat_groups: dict[str, dict] = {}
    for b in books_list:
        cat = b.get("category", "Uncategorized")
        if cat not in cat_groups:
            meta = cat_meta.get(cat, {})
            cat_groups[cat] = {
                "name": cat,
                "icon": meta.get("icon", "📖"),
                "color": meta.get("color", "#888"),
                "books": [],
            }
        cat_groups[cat]["books"].append(b)
    books_by_category = list(cat_groups.values())

    # Quarter counts
    q_counts = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    for b in books_list:
        q = b.get("quarter", "Q1")
        if q in q_counts:
            q_counts[q] += 1

    return {
        "today": today.isoformat(),
        "edu_program": edu_program,
        "edu_stats": edu_stats,
        "edu_sources": edu_sources,
        "edu_phases": edu_phases,
        "edu_timeline": edu_timeline,
        "edu_cost": edu_cost,
        "edu_actions": edu_actions,
        "credits_completed": credits_completed,
        "credits_planned": credits_planned,
        "current_week": current_week,
        "year_pct": year_pct,
        "q1_pct": q1_pct,
        "q2_pct": q2_pct,
        "q3_pct": q3_pct,
        "q4_pct": q4_pct,
        "realm_tasks": realm_tasks,
        "realms": REALMS,
        "technical_skills": technical_skills,
        "soft_skills": soft_skills,
        "certifications": certifications,
        "has_goals": has_goals,
        "vision": vision,
        "job_stats": job_stats,
        "net_goals": net_goals,
        "projects": projects,
        "learning_matrix": learning_matrix,
        "success_metrics": success_metrics,
        "app_checklist": app_checklist,
        "books_by_category": books_by_category,
        "total_books": total_books,
        "in_plan_count": in_plan_count,
        "new_picks": new_picks,
        "q_counts": q_counts,
    }


# ── Markdown File Discovery ───────────────────────────────────
EXCLUDED_DIRS = {"node_modules", ".git", "venv", "__pycache__", "dashboard-app"}


def discover_md_files() -> list[dict]:
    """Walk workspace and return .md files grouped by directory."""
    files = []
    for md in sorted(WORKSPACE.rglob("*.md")):
        # Skip excluded directories
        rel = md.relative_to(WORKSPACE)
        if any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        files.append({
            "path": str(rel),
            "name": md.name,
            "folder": str(rel.parent) if str(rel.parent) != "." else "",
            "size": md.stat().st_size,
        })
    return files


# ── Routes ────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    ctx = build_context()
    ctx["request"] = request
    return templates.TemplateResponse("index.html", ctx)


@app.get("/reader", response_class=HTMLResponse)
def reader(request: Request):
    return templates.TemplateResponse("reader.html", {"request": request})


@app.get("/api/files")
def api_files():
    return JSONResponse(discover_md_files())


@app.get("/api/file")
def api_file(path: str = Query(...)):
    # Resolve to absolute path and confirm it lives inside WORKSPACE.
    # Using Path.resolve() handles symlinks, "..", and absolute injections
    # (e.g. Path("/workspace") / Path("/etc/passwd") == Path("/etc/passwd")).
    workspace = WORKSPACE.resolve()
    target = (workspace / path).resolve()
    if not str(target).startswith(str(workspace) + os.sep) and target != workspace:
        return JSONResponse({"error": "Invalid path"}, status_code=400)
    if not target.exists() or not target.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)
    return JSONResponse({"path": path, "content": target.read_text(errors="replace")})


@app.post("/api/tasks/toggle")
def toggle_task(req: ToggleRequest):
    """Toggle a checkbox in the source markdown file."""
    # Find realm config
    realm_cfg = next((r for r in REALMS if r["id"] == req.realm), None)
    if not realm_cfg:
        return JSONResponse({"error": "Unknown realm"}, status_code=400)

    target = WORKSPACE / realm_cfg["file"]
    if not target.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)

    lines = target.read_text().splitlines(keepends=True)
    idx = req.line - 1  # convert to 0-based

    if idx < 0 or idx >= len(lines):
        return JSONResponse({"error": "Line out of range"}, status_code=400)

    line = lines[idx]
    m = CHECKBOX_RE.match(line.rstrip('\n').rstrip('\r'))
    if not m:
        return JSONResponse({"error": "No checkbox on that line"}, status_code=400)

    new_mark = "x" if req.done else " "
    lines[idx] = m.group(1) + new_mark + m.group(3) + "\n"
    # Write atomically: crash mid-write won't corrupt the source file.
    with tempfile.NamedTemporaryFile(
        "w", dir=target.parent, delete=False, suffix=".tmp"
    ) as tf:
        tf.write("".join(lines))
    os.replace(tf.name, target)

    return JSONResponse({"ok": True, "realm": req.realm, "line": req.line, "done": req.done})
