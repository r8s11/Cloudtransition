"""
Command Center — FastAPI app that reads workspace YAML/MD files directly.

Run:  uvicorn app:app --reload
Open: http://localhost:8000
"""

import http.client
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import yaml
from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from core import config
from core import interview_editor as ie
from core import now as now_engine
from core import work_search as ws
from core import workspace_content as wc
from core import agents as forge_agents
from core import skills as skill_reg
from core.agents import build_agents_view
from core import calendar_sources
from core.interview_view import build_interview_view, next_interview_action
from core.store import _FILE_WRITE_LOCK, _atomic_write, load_yaml
from core.tasks import CHECKBOX_RE, insert_inbox_item, parse_all_realms, parse_tasks_from_file
from core.today import (
    _routine_plain_text,
    _routine_review_items,
    build_today_view,
    command_centre,
    current_week_of_year,
    live_projects,
    md_inline,
    money_available,
    parse_routine_folds,
)
from routes import calendar, metrics


def _load_env_file(path: Path, environ: dict[str, str] | None = None) -> None:
    """Load KEY=VALUE lines from a local .env without overriding real env vars.

    The dashboard runs under launchd with its own environment, so a
    gitignored dashboard-app/.env is where local keys such as
    OPENROUTER_API_KEY belong.
    """
    target = os.environ if environ is None else environ
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        target.setdefault(key, value)


_load_env_file(Path(__file__).resolve().parent / ".env")


# ── App ────────────────────────────────────────────────────────


app = FastAPI(title="Command Center", lifespan=calendar.calendar_lifespan)
app.middleware("http")(calendar.calendar_origin_guard)

app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)
app.mount(
    "/learn/pydantic-ai/lessons",
    StaticFiles(directory=config.COURSE_LESSONS, follow_symlink=False),
    name="pydantic-ai-lessons",
)
app.mount(
    "/learn/pydantic-ai/assets",
    StaticFiles(directory=config.COURSE_ASSETS, follow_symlink=False),
    name="pydantic-ai-assets",
)
app.mount(
    "/learn/pydantic-ai/reference",
    StaticFiles(directory=config.COURSE_REFERENCE, follow_symlink=False),
    name="pydantic-ai-reference",
)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


class ToggleRequest(BaseModel):
    realm: str
    line: int
    done: bool
    # Task text as rendered. Lines shift when a capture or an outside edit lands
    # after the page loaded; the text lets the server find the item again.
    text: str | None = None


# ── Inbox capture ─────────────────────────────────────────────
CAPTURE_MAX = 300


class CaptureRequest(BaseModel):
    text: str
    schedule: dict | None = None


templates.env.filters["md"] = md_inline
templates.env.filters["plain"] = _routine_plain_text


# ── Build Context ─────────────────────────────────────────────
def build_context() -> dict:
    """Read all workspace files and return template context."""

    skills_data = load_yaml(config.SKILLS_FILE)
    goals_data = load_yaml(config.GOALS_FILE)
    jobs_data = load_yaml(config.JOBS_FILE)
    network_data = load_yaml(config.NETWORK_FILE)
    realm_tasks = parse_all_realms()
    today = date.today()
    current_week = current_week_of_year(today)

    # Skills — flatten for template
    technical_skills = []
    for cat in skills_data.get("technical_skills", []):
        category_name = cat.get("category", "Other")
        for sk in cat.get("skills", []):
            technical_skills.append(
                {
                    "name": sk.get("name", ""),
                    "category": category_name,
                    "proficiency": sk.get("proficiency", "beginner"),
                    "years": sk.get("years_experience", 0),
                    "last_used": sk.get("last_used", ""),
                }
            )

    soft_skills = []
    for sk in skills_data.get("soft_skills", []):
        soft_skills.append(
            {
                "name": sk.get("name", ""),
                "proficiency": sk.get("proficiency", "low"),
            }
        )

    certifications = []
    for cert in skills_data.get("certifications", []):
        certifications.append(
            {
                "name": cert.get("name", ""),
                "issuer": cert.get("issuer", ""),
                "obtained": cert.get("date_obtained"),
                "expires": cert.get("expires"),
                "credential_id": cert.get("credential_id"),
            }
        )

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

    interview_view = build_interview_view(jobs_data, today)
    for interview_row in interview_view["interview_rows"]:
        _attach_agents(interview_row)
    agents_view = build_agents_view()
    scout_leads = forge_agents.scout_leads(
        agents_view["agent_scan"],
        {(r["company"].casefold(), r["role"].casefold()) for r in interview_view["interview_rows"]},
    )

    # Networking goals
    net_goals = []
    for g in network_data.get("networking_goals", []):
        net_goals.append(
            {
                "goal": g.get("goal", ""),
                "progress": g.get("progress", "0/0"),
            }
        )

    # Vision/goals
    vision = goals_data.get("vision", {})
    has_goals = bool(vision.get("title"))

    # Year/quarter progress
    year_pct = round((current_week / 52) * 100)
    q1_pct = min(100, round((current_week / 13) * 100))
    q2_pct = (
        max(0, min(100, round(((current_week - 13) / 13) * 100)))
        if current_week > 13
        else 0
    )
    q3_pct = (
        max(0, min(100, round(((current_week - 26) / 13) * 100)))
        if current_week > 26
        else 0
    )
    q4_pct = (
        max(0, min(100, round(((current_week - 39) / 13) * 100)))
        if current_week > 39
        else 0
    )  # noqa: used in template

    # Parked and planned apps. Live project work is read from TASKS.md by
    # live_projects(); this list only changes when an app is parked or revived.
    projects = [
        {
            "name": "WODCard",
            "status": "Deprioritized — maintenance only",
            "goal": "Resume after school stabilizes",
            "color": config.SAFE_HUES["ember"],
            "features": [
                "React + Vite + TypeScript frontend",
                "FastAPI backend structure",
                "Card component with flip animation",
                "Timer component, exercise data model",
            ],
        },
        {
            "name": "SalsaSegura",
            "status": "Deprioritized — maintenance only",
            "goal": "Resume after school stabilizes",
            "color": config.SAFE_HUES["blue"],
            "features": [
                "React TypeScript app deployed to Azure",
                "Events display, header, footer, hero section",
                "Work in progress page",
            ],
        },
        {
            "name": "SalsaTD",
            "status": "Deprioritized — maintenance only",
            "goal": "Resume after school stabilizes",
            "color": config.SAFE_HUES["purple"],
            "features": [
                "Game board with turn-based play (2-30 players)",
                "Truth & Dare decks with spiciness levels",
                "Dark mode, scroll indicator, mobile optimized",
                "Card UI with animations, deck reshuffling",
                "Penalty system, Azure Cosmos DB prototype",
            ],
        },
        {
            "name": "Capstone (genomics-style batch pipeline)",
            "status": "Planned — Phase 7 of roadmap, builds in 2027",
            "goal": "Public GitHub repo by end of 2027",
            "color": config.SAFE_HUES["green"],
            "features": [
                "Terraform-managed VPC + EKS cluster",
                "Fan-out workflow: S3 → SQS → Karpenter worker pods",
                "Argo Workflows or AWS Batch (Fargate)",
                "Prometheus + Grafana + Loki + AWS X-Ray",
                "GitHub Actions CI/CD with Trivy + ArgoCD",
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

    # Success metrics — aligned to plans/year-plan-2026-2027.md (Regeneron-class role by end of 2027)
    success_metrics = [
        {
            "category": "Career",
            "goal": "Stepping-stone role (IT eng / sysadmin / cloud-adjacent)",
            "metric": "Offer signed by end of 2026",
        },
        {
            "category": "Long-term Career",
            "goal": "Lead Cloud DevOps Engineer (Regeneron-class)",
            "metric": "Apply by Q4 2027",
        },
        {
            "category": "School",
            "goal": "SNHU CS BS (or Cybersecurity BS)",
            "metric": "1 course/term, on track each term",
        },
        {
            "category": "Roadmap",
            "goal": "Phases 1–7 + capstone complete",
            "metric": "End of 2027 — see year plan",
        },
        {
            "category": "Certifications",
            "goal": "CKA, Terraform Associate, AWS DOP",
            "metric": "Stack alongside roadmap phases",
        },
        {
            "category": "Projects",
            "goal": "Genomics-style batch pipeline (capstone)",
            "metric": "Public GitHub repo by end of 2027",
        },
    ]

    # Application checklist
    app_checklist = jobs_data.get("application_strategy", {}).get(
        "application_checklist", []
    )

    # Education data
    edu_data = load_yaml(config.EDU_FILE)
    edu_program = edu_data.get("program", {})
    edu_stats = edu_data.get("degree_stats", {})
    edu_sources = [
        {**s, "color": config.safe_hue(s.get("color"))}
        for s in edu_data.get("credit_sources", [])
    ]
    edu_phases = edu_data.get("transfer_phases", [])
    edu_timeline = edu_data.get("timeline", [])
    edu_cost = edu_data.get("cost", {})
    edu_actions = edu_data.get("actions", [])

    # Compute total credits by status for stacked bar
    credits_completed = sum(
        s.get("credits", 0) for s in edu_sources if s.get("status") == "completed"
    )
    credits_planned = sum(
        s.get("credits", 0) for s in edu_sources if s.get("status") != "completed"
    )

    # Books data
    books_data = load_yaml(config.BOOKS_FILE)
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
                "color": config.safe_hue(meta.get("color")),
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

    # Routine folds
    fold_steps = parse_routine_folds(today)
    today_view = build_today_view(realm_tasks, fold_steps, today)
    live = live_projects(realm_tasks, today)

    return {
        "today": today.isoformat(),
        "fold_steps": fold_steps,
        **today_view,
        **command_centre(
            realm_tasks,
            today_view,
            len(live),
            next_interview_action(interview_view["interview_rows"], today),
            interview_view["interview_counts"],
        ),
        # Today's "Now" card: one directive from the clock, routine.md and the tracker.
        "now_plan": now_engine.build_now(
            datetime.now(),
            jobs_data,
            interview_view["interview_rows"],
            today_view["routine"],
            [t for t in realm_tasks["active"] if t["realm"] == "tasks"],
        ),
        "money_available": money_available(),
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
        "realms": config.REALMS,
        "technical_skills": technical_skills,
        "soft_skills": soft_skills,
        "certifications": certifications,
        "has_goals": has_goals,
        "vision": vision,
        "job_stats": job_stats,
        **interview_view,
        "net_goals": net_goals,
        "projects": projects,
        "live_projects": live,
        "learning_matrix": learning_matrix,
        "success_metrics": success_metrics,
        "app_checklist": app_checklist,
        "books_by_category": books_by_category,
        "total_books": total_books,
        "in_plan_count": in_plan_count,
        "new_picks": new_picks,
        "q_counts": q_counts,
        **agents_view,
        "agent_card_runs": {
            agent: {"skill": skill, "last": _last_finished_run(skill)}
            for agent, skill in config.AGENT_CARD_RUNNERS.items()
        },
        "interview_scout_leads": scout_leads,
    }


def _attach_agents(row: dict) -> dict:
    """Add the Job Reader / CV Adapter state for one tracker row (read-only)."""
    row["agent"] = forge_agents.application_agents(row["company"], row["role"], row.get("url") or "")
    return row


# ── Markdown File Discovery ───────────────────────────────────
EXCLUDED_DIRS = {"node_modules", ".git", "venv", "__pycache__", "dashboard-app"}


def discover_md_files() -> list[dict]:
    """Walk workspace and return .md files grouped by directory."""
    files = []
    for md in sorted(config.WORKSPACE.rglob("*.md")):
        # Skip excluded directories and anything the privacy rules protect
        rel = md.relative_to(config.WORKSPACE)
        if md.is_symlink() or any(part in EXCLUDED_DIRS for part in rel.parts) or wc.privacy_violation(
            rel.as_posix()
        ):
            continue
        files.append(
            {
                "path": str(rel),
                "name": md.name,
                "folder": str(rel.parent) if str(rel.parent) != "." else "",
                "size": md.stat().st_size,
            }
        )
    return files


# ── Routes ────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    # The Run tab reads this catalogue; build it while the page renders.
    _warm_skill_catalog()
    ctx = build_context()
    # Tailscale serve arrives with the tailnet Host; Mission links are Mac-only.
    ctx["is_local"] = request.url.hostname in {"127.0.0.1", "localhost"}
    return templates.TemplateResponse(request, "index.html", ctx)


@app.get("/reader", response_class=HTMLResponse)
def reader(request: Request):
    return templates.TemplateResponse(request, "reader.html")


@app.get("/agents/skills", response_class=HTMLResponse)
def skill_registry(request: Request):
    """Read-only Skill Registry: what OpenCode registers, and what each agent may load.

    Access comes from OpenCode's own resolved rules (`opencode debug agents`),
    so this page takes a few seconds; it never changes a skill or an agent.
    """
    registry = skill_reg.discover_skills()
    agent_ids = [a["slug"] for a in forge_agents.discover_agents()["agents"] if a["discovered"]]
    resolved = _opencode_resolved_agents()
    matrix = skill_reg.agent_matrix(resolved, registry["skills"], agent_ids)
    for row in matrix:
        row["approved"] = skill_reg.approved_skills(row, registry["skills"])
    loaders = {
        s["id"]: [r["agent"] for r in matrix if r.get("evaluated") and r["access"].get(s["id"]) == "loadable"]
        for s in registry["skills"]
    }
    return templates.TemplateResponse(
        request,
        "skills_registry.html",
        {"registry": registry, "matrix": matrix, "loaders": loaders, "opencode_ok": resolved is not None},
    )


@app.get("/learn/pydantic-ai", include_in_schema=False)
@app.get("/learn/pydantic-ai/", include_in_schema=False)
def pydantic_ai_course():
    return RedirectResponse("/learn/pydantic-ai/lessons/0001-first-agent.html")


@app.get("/learn/pydantic-ai/{filename}", include_in_schema=False)
def pydantic_ai_course_document(filename: str):
    if filename == "KB-README.md":
        return RedirectResponse("/workspace-file/KB-README.md")
    documents = {
        "MISSION.md": config.WORKSPACE / "MISSION.md",
        "RESOURCES.md": config.WORKSPACE / "RESOURCES.md",
    }
    document = documents.get(filename)
    if document is None:
        return PlainTextResponse("Not found", status_code=404)
    return FileResponse(document, media_type="text/plain")


# ── Workspace map (visual-second-brain) + safe file access ─────
# Read-only. Eligibility and privacy rules live in workspace_content.py.
app.mount(
    "/workspace-map/assets",
    StaticFiles(directory=wc.VIEWER_HTML.parent / "assets", follow_symlink=False),
    name="workspace-map-assets",
)

@app.get("/workspace-map", include_in_schema=False)
def workspace_map_redirect():
    return RedirectResponse("/workspace-map/")


@app.get("/workspace-map/")
def workspace_map():
    return FileResponse(
        wc.VIEWER_HTML, media_type="text/html", headers={"Cache-Control": "no-cache"}
    )


@app.get("/workspace-map/workspace-index.json")
def workspace_map_index():
    if not wc.INDEX_FILE.is_file():
        return JSONResponse(
            {"error": "Workspace index missing; run refresh-index.py"}, status_code=503
        )
    # X-Workspace-Open tells the viewer where its Open/Download links point.
    return FileResponse(
        wc.INDEX_FILE,
        media_type="application/json",
        headers={"Cache-Control": "no-store", "X-Workspace-Open": "/workspace-file"},
    )


@app.get("/workspace-file/{path:path}")
def workspace_file(path: str, download: bool = False):
    """Serve one indexed file or live artifact; relative links inside artifacts resolve here too."""
    try:
        target = wc.resolve_file(config.WORKSPACE, wc.INDEX_FILE, path)
    except wc.ContentError as exc:
        return PlainTextResponse(
            str(exc),
            status_code=exc.status,
            headers={"X-Content-Type-Options": "nosniff"},
        )
    media, headers = wc.file_headers(target, download)
    return FileResponse(target, media_type=media, headers=headers)


@app.get("/api/workspace/artifacts")
def workspace_artifacts():
    try:
        return JSONResponse({"artifacts": wc.artifact_entries()})
    except OSError:
        return JSONResponse(
            {"error": "artifacts/ could not be read; is the drive mounted?"},
            status_code=503,
        )


@app.get("/mission-control")
@app.get("/mission-control/{path:path}", response_class=HTMLResponse)
def mission_control(path: str = ""):
    return proxy_mission_control(path)


@app.post("/mission-control/{path:path}")
async def mission_control_post(path: str, request: Request):
    """Forward only Pause mission and Stop all runs; other writes answer 405."""
    if not config.MISSION_CONTROL_WRITE_ALLOWLIST.match(path):
        return JSONResponse(
            {"error": "Only pause and stop-runs are writable through the dashboard"},
            status_code=405,
        )
    body = await request.body()
    upstream = config.MISSION_CONTROL_UPSTREAM + "/" + path.lstrip("/")
    req = urllib.request.Request(
        upstream,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=config.MISSION_CONTROL_TIMEOUT) as resp:
            return Response(
                content=resp.read(),
                media_type=resp.headers.get("Content-Type", "application/json"),
                status_code=resp.status,
            )
    except urllib.error.HTTPError as exc:
        return Response(
            content=exc.read(),
            media_type=exc.headers.get("Content-Type", "application/json"),
            status_code=exc.code,
        )
    except (urllib.error.URLError, OSError):
        return JSONResponse({"error": "Mission Control is offline"}, status_code=502)


@app.get("/api/files")
def api_files():
    return JSONResponse(discover_md_files())


@app.get("/api/file")
def api_file(path: str = Query(...)):
    # Resolve to absolute path and confirm it lives inside WORKSPACE.
    # Using Path.resolve() handles symlinks, "..", and absolute injections
    # (e.g. Path("/workspace") / Path("/etc/passwd") == Path("/etc/passwd")).
    workspace = config.WORKSPACE.resolve()
    target = (workspace / path).resolve()
    try:
        resolved_rel = target.relative_to(workspace).as_posix()
    except ValueError:
        return JSONResponse({"error": "Invalid path"}, status_code=400)
    # Same privacy rules as the Workspace map, on the requested and the real path.
    if wc.privacy_violation(path.strip("/")) or wc.privacy_violation(resolved_rel):
        return JSONResponse({"error": "File not available"}, status_code=403)
    if not target.exists() or not target.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)
    ALLOWED_EXTENSIONS = {
        ".md",
        ".txt",
        ".yaml",
        ".yml",
        ".json",
        ".csv",
        ".html",
        ".py",
    }
    if target.suffix.lower() not in ALLOWED_EXTENSIONS:
        return JSONResponse({"error": "File type not allowed"}, status_code=403)
    return JSONResponse({"path": path, "content": target.read_text(errors="replace")})


@app.post("/api/tasks/toggle")
def toggle_task(req: ToggleRequest, x_requested_with: str = Header(default="")):
    """Toggle a checkbox in the source markdown file."""
    if x_requested_with != "XMLHttpRequest":
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    if req.realm == "routine":
        target = config.WORKSPACE / "routine.md"
    else:
        realm_cfg = next((r for r in config.REALMS if r["id"] == req.realm), None)
        if not realm_cfg:
            return JSONResponse({"error": "Unknown realm"}, status_code=400)
        target = config.WORKSPACE / realm_cfg["file"]
    if not target.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)

    with _FILE_WRITE_LOCK:
        lines = target.read_text().splitlines(keepends=True)
        idx = req.line - 1  # convert to 0-based
        allowed_routine_lines = (
            {item["line"]: item["text"] for item in _routine_review_items(lines)}
            if req.realm == "routine"
            else None
        )
        if (
            allowed_routine_lines is not None
            and idx + 1 not in allowed_routine_lines
            and req.text not in allowed_routine_lines.values()
        ):
            return JSONResponse(
                {"error": "Only Weekly Review items can be changed here"},
                status_code=400,
            )

        def text_at(i: int) -> str | None:
            if not 0 <= i < len(lines):
                return None
            if allowed_routine_lines is not None:
                return allowed_routine_lines.get(i + 1)
            m = CHECKBOX_RE.match(lines[i].rstrip("\r\n"))
            return m.group(3)[2:] if m else None

        if req.text is not None and not (
            0 <= idx < len(lines) and text_at(idx) == req.text
        ):
            # The file moved under the page. Follow the text, but only if unique.
            hits = [i for i in range(len(lines)) if text_at(i) == req.text]
            if len(hits) != 1:
                return JSONResponse(
                    {"error": "Task moved or changed — reload the page"},
                    status_code=409,
                )
            idx = hits[0]

        if idx < 0 or idx >= len(lines):
            return JSONResponse({"error": "Line out of range"}, status_code=400)

        m = CHECKBOX_RE.match(lines[idx].rstrip("\n").rstrip("\r"))
        if not m:
            return JSONResponse({"error": "No checkbox on that line"}, status_code=400)
        if allowed_routine_lines is not None and idx + 1 not in allowed_routine_lines:
            return JSONResponse(
                {"error": "Only Weekly Review items can be changed here"},
                status_code=400,
            )

        new_mark = "x" if req.done else " "
        lines[idx] = m.group(1) + new_mark + m.group(3) + "\n"
        _atomic_write(target, "".join(lines))

    return JSONResponse(
        {"ok": True, "realm": req.realm, "line": idx + 1, "done": req.done}
    )


@app.post("/api/capture")
def capture(req: CaptureRequest, x_requested_with: str = Header(default="")):
    """Append one item to the Inbox section of TASKS.md."""
    if x_requested_with != "XMLHttpRequest":
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    # Collapse newlines/tabs: one capture is exactly one checkbox line.
    text = " ".join(req.text.split())
    if not text:
        return JSONResponse({"error": "Nothing to capture"}, status_code=400)
    if len(text) > CAPTURE_MAX:
        return JSONResponse(
            {"error": f"Keep it under {CAPTURE_MAX} characters"}, status_code=400
        )

    try:
        schedule = calendar_sources.validate_schedule(req.schedule or {})
        scheduled_text = calendar_sources.annotate(text, schedule)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    with _FILE_WRITE_LOCK:
        source = config.TASKS_FILE.read_text() if config.TASKS_FILE.exists() else "# Tasks\n"
        new_text, line = insert_inbox_item(source, scheduled_text)
        _atomic_write(config.TASKS_FILE, new_text)

    return JSONResponse({"ok": True, "realm": "tasks", "line": line, "text": text,
                         "raw_text": scheduled_text, "schedule": schedule})


# ── Second brain (second-brain/brain.py, deterministic, no model) ──
BRAIN_TIMEOUT = 60


class RememberRequest(BaseModel):
    title: str
    summary: str
    body: str


def _brain(*args: str) -> JSONResponse:
    """Run one brain.py subcommand and relay its JSON. Arguments go in as
    separate argv elements with no shell, so input cannot become a command."""
    try:
        proc = subprocess.run(
            [sys.executable, str(config.BRAIN_CLI), *args],
            cwd=config.WORKSPACE,
            capture_output=True,
            text=True,
            timeout=BRAIN_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return JSONResponse({"error": f"brain.py failed: {exc}"}, status_code=500)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        detail = (proc.stderr or proc.stdout).strip()[-400:] or "no output"
        return JSONResponse({"error": detail}, status_code=500)
    return JSONResponse(data, status_code=200 if proc.returncode == 0 else 422)


@app.get("/api/brain/query")
def brain_query(q: str = Query(..., min_length=2, max_length=200)):
    return _brain("query", q)


@app.post("/api/brain/remember")
def brain_remember(req: RememberRequest, x_requested_with: str = Header(default="")):
    if x_requested_with != "XMLHttpRequest":
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    return _brain(
        "remember", "--title", req.title, "--summary", req.summary, "--body", req.body
    )


# Read-only live state for the bot/ personal assistant (Brain). One aggregating
# GET so any agent can answer from current data without scraping HTML.
ASSISTANT_SECTIONS = ("tasks", "interviews", "runs", "missions", "calendar")
_RUN_LOG_SAFE = ("timestamp", "id", "skill", "status", "model", "provider", "duration", "exit_code")


@app.get("/api/assistant/state")
def assistant_state(include: str = Query(default="tasks,interviews,runs,missions")):
    wanted = [part.strip() for part in include.split(",") if part.strip()]
    unknown = [part for part in wanted if part not in ASSISTANT_SECTIONS]
    if unknown or not wanted:
        return JSONResponse(
            {"error": f"unknown section: {', '.join(unknown) or include}"}, status_code=400
        )
    out: dict = {"generated_at": datetime.now().astimezone().isoformat()}
    if "tasks" in wanted:
        realms = []
        for realm in config.REALMS:
            items = parse_tasks_from_file(config.WORKSPACE / realm["file"], realm["id"])
            done = sum(1 for item in items if item["done"])
            realms.append(
                {
                    "id": realm["id"],
                    "name": realm["name"],
                    "file": realm["file"],
                    "open": len(items) - done,
                    "done": done,
                }
            )
        out["tasks"] = {"source": "workspace realm files", "realms": realms}
    if "interviews" in wanted:
        view = build_interview_view(load_yaml(config.JOBS_FILE), date.today())
        out["interviews"] = {
            "source": "interviews/job-applications.yml",
            "counts": view["interview_counts"],
            # No contact emails, no posting URLs: the assistant needs state, not PII.
            "rows": [
                {
                    "company": row["company"],
                    "role": row["role"],
                    "status": row["status"],
                    "status_label": row["status_label"],
                    "next_step": row["next_step"],
                    "overdue": row["overdue"],
                }
                for row in view["interview_rows"]
            ],
        }
    if "runs" in wanted:
        with _RUNS_LOCK:
            live = sorted(_RUNS.values(), key=lambda run: run["started"], reverse=True)
        recent = []
        try:
            for line in config.RUNS_LOG.read_text().splitlines()[-20:]:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                recent.append({key: entry.get(key) for key in _RUN_LOG_SAFE})
        except OSError:
            pass
        out["runs"] = {
            "source": "run engine + runs.log",
            "live": [
                {key: run.get(key) for key in ("id", "skill", "status", "started", "model", "provider")}
                for run in live
            ],
            "recent": recent,
        }
    if "missions" in wanted:
        try:
            with urllib.request.urlopen(
                f"{config.MISSION_CONTROL_UPSTREAM}/api/missions",
                timeout=config.MISSION_CONTROL_STATUS_TIMEOUT,
            ) as resp:
                data = json.load(resp)
            out["missions"] = {
                "source": config.MISSION_CONTROL_UPSTREAM,
                "rows": [
                    {key: mission.get(key) for key in ("id", "title", "status", "priority")}
                    for mission in data
                    if isinstance(mission, dict)
                ],
            }
        except (OSError, ValueError, http.client.HTTPException) as exc:
            out["missions"] = {"unavailable": f"Mission Control not reachable: {type(exc).__name__}"}
    if "calendar" in wanted:
        try:
            out["calendar"] = {"source": "calendar service", **calendar.calendar_service.snapshot()}
        except Exception as exc:  # calendar may need Google consent; degrade, never fail the call
            out["calendar"] = {"unavailable": f"{type(exc).__name__}: {exc}"}
    return JSONResponse(out)



class WorkSearchRequest(BaseModel):
    id: str
    date: str
    activity_type: str
    description: str
    position: str = ""
    employer: str
    address: str = ""
    result: str = ""


@app.get("/api/career/work-search")
def work_search_report(start: date | None = None):
    from datetime import timedelta

    start = start or (date.today() - timedelta(days=date.today().weekday()))
    try:
        return ws.report(load_yaml(config.JOBS_FILE), start)
    except (ValueError, yaml.YAMLError, OverflowError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.post("/api/career/work-search")
def work_search_save(req: WorkSearchRequest, x_requested_with: str = Header(default="")):
    if x_requested_with != "XMLHttpRequest":
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    if not config.JOBS_FILE.is_file():
        return JSONResponse({"error": "Application tracker not found"}, status_code=404)
    try:
        with _FILE_WRITE_LOCK:
            text = config.JOBS_FILE.read_text(encoding="utf-8")
            updated = ws.save(text, req.model_dump())
            _atomic_write(config.JOBS_FILE, updated)
    except (ValueError, yaml.YAMLError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except OSError:
        return JSONResponse({"error": "Could not save activity. Check tracker permissions and try again."}, status_code=500)
    return {"ok": True}

# ── Interview dashboard writes ─────────────────────────────────────────────
# Each endpoint edits only the lines it owns in interviews/job-applications.yml
# (see interview_editor.py), then answers with the rebuilt row so the page can
# update without a reload.
class InterviewFieldRequest(BaseModel):
    company: str
    role: str
    field: str
    value: str


class InterviewNextStepRequest(BaseModel):
    company: str
    role: str
    task: str
    date: str | None = None


class InterviewSignalRequest(BaseModel):
    company: str
    role: str
    date: str
    stage: str
    notes: str | None = None


class InterviewTextRequest(BaseModel):
    company: str
    role: str
    field: str
    text: str


class InterviewTargetRequest(BaseModel):
    company: str
    role: str


class InterviewCreateRequest(BaseModel):
    company: str
    role: str
    status: str = "new_lead"
    priority: str = "medium"
    location: str | None = None
    salary_range: str | None = None
    job_url: str | None = None
    next_step: str | None = None
    date: str | None = None


def _interview_target(company: str, role: str) -> tuple[str, str] | None:
    company, role = company.strip(), role.strip()
    if not company or not role or len(company) > 200 or len(role) > 200:
        return None
    return company, role


def _interview_write(edit, company: str, role: str):
    """Apply one editor function under the file lock, then return the new row."""
    if not config.JOBS_FILE.exists():
        return JSONResponse({"error": "Application tracker not found"}, status_code=404)
    with _FILE_WRITE_LOCK:
        text = config.JOBS_FILE.read_text(encoding="utf-8")
        try:
            updated = edit(text)
        except ie.InterviewEditError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        _atomic_write(config.JOBS_FILE, updated)

    view = build_interview_view(load_yaml(config.JOBS_FILE), date.today())
    row = next(
        (
            r
            for r in view["interview_rows"]
            if r["company"] == company and r["role"] == role
        ),
        None,
    )
    return JSONResponse({"ok": True, "row": row, "counts": view["interview_counts"]})


def _csrf_ok(x_requested_with: str) -> bool:
    return x_requested_with == "XMLHttpRequest"


@app.post("/api/interviews/field")
def interview_field(
    req: InterviewFieldRequest, x_requested_with: str = Header(default="")
):
    if not _csrf_ok(x_requested_with):
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    target = _interview_target(req.company, req.role)
    if not target:
        return JSONResponse({"error": "Company and role are required"}, status_code=400)
    company, role = target
    return _interview_write(
        lambda text: ie.set_field(text, company, role, req.field, req.value),
        company,
        role,
    )


@app.post("/api/interviews/next-step")
def interview_next_step(
    req: InterviewNextStepRequest, x_requested_with: str = Header(default="")
):
    if not _csrf_ok(x_requested_with):
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    target = _interview_target(req.company, req.role)
    if not target:
        return JSONResponse({"error": "Company and role are required"}, status_code=400)
    company, role = target
    return _interview_write(
        lambda text: ie.set_next_step(text, company, role, req.task, req.date or ""),
        company,
        role,
    )


@app.post("/api/interviews/timeline")
def interview_timeline(
    req: InterviewSignalRequest, x_requested_with: str = Header(default="")
):
    if not _csrf_ok(x_requested_with):
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    target = _interview_target(req.company, req.role)
    if not target:
        return JSONResponse({"error": "Company and role are required"}, status_code=400)
    company, role = target
    return _interview_write(
        lambda text: ie.append_timeline(
            text, company, role, req.date, req.stage, req.notes or ""
        ),
        company,
        role,
    )


@app.post("/api/interviews/applied")
def interview_applied(
    req: InterviewTargetRequest, x_requested_with: str = Header(default="")
):
    """One tap after submitting an application: log it, park it, schedule the follow-up.

    Appends an `applied` timeline entry dated today, sets status `waiting` and
    makes the first next step a follow-up a week out, in one atomic write.
    """
    if not _csrf_ok(x_requested_with):
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    target = _interview_target(req.company, req.role)
    if not target:
        return JSONResponse({"error": "Company and role are required"}, status_code=400)
    company, role = target
    today = date.today()
    follow_up = (today + timedelta(days=now_engine.FOLLOW_UP_DAYS)).isoformat()

    def edit(text: str) -> str:
        if str(ie._validate(text, company, role).get("status") or "new_lead") != "new_lead":
            raise ie.InterviewEditError("only a new lead can be marked applied")
        text = ie.append_timeline(text, company, role, today.isoformat(), "applied", "")
        text = ie.set_field(text, company, role, "status", "waiting")
        return ie.set_next_step(text, company, role, "Follow up if no reply", follow_up)

    return _interview_write(edit, company, role)


@app.get("/api/interviews/detail")
def interview_detail(
    company: str = Query(..., min_length=1, max_length=200),
    role: str = Query(..., min_length=1, max_length=200),
):
    """One application as the Interview mode dialog needs it."""
    view = build_interview_view(load_yaml(config.JOBS_FILE), date.today())
    row = next(
        (
            r
            for r in view["interview_rows"]
            if r["company"] == company.strip() and r["role"] == role.strip()
        ),
        None,
    )
    if row is None:
        return JSONResponse({"error": "Application not found"}, status_code=404)
    return JSONResponse({"ok": True, "row": _attach_agents(row)})


@app.get("/interviews/sheet", response_class=HTMLResponse)
def interview_sheet(
    request: Request,
    company: str = Query(..., min_length=1, max_length=200),
    role: str = Query(..., min_length=1, max_length=200),
):
    """Standalone printable prep sheet: browser Print → PDF for offline use."""
    view = build_interview_view(load_yaml(config.JOBS_FILE), date.today())
    row = next(
        (
            r
            for r in view["interview_rows"]
            if r["company"] == company.strip() and r["role"] == role.strip()
        ),
        None,
    )
    if row is None:
        return HTMLResponse("Application not found", status_code=404)
    return templates.TemplateResponse(
        request,
        "interview_sheet.html",
        {"row": row, "printed": date.today().isoformat(), "workspace": str(config.WORKSPACE)},
    )


@app.post("/api/interviews/text")
def interview_text(
    req: InterviewTextRequest, x_requested_with: str = Header(default="")
):
    if not _csrf_ok(x_requested_with):
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    target = _interview_target(req.company, req.role)
    if not target:
        return JSONResponse({"error": "Company and role are required"}, status_code=400)
    if req.field not in ie.TEXT_BLOCKS:
        return JSONResponse({"error": "Unknown field"}, status_code=400)
    company, role = target
    return _interview_write(
        lambda text: ie.set_text_block(text, company, role, req.field, req.text),
        company,
        role,
    )


@app.post("/api/interviews/create")
def interview_create(
    req: InterviewCreateRequest, x_requested_with: str = Header(default="")
):
    if not _csrf_ok(x_requested_with):
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    target = _interview_target(req.company, req.role)
    if not target:
        return JSONResponse({"error": "Company and role are required"}, status_code=400)
    company, role = target

    def edit(text: str) -> str:
        return ie.add_application(
            text,
            company=company,
            role=role,
            status=req.status,
            priority=req.priority,
            location=req.location or "",
            salary_range=req.salary_range or "",
            job_url=req.job_url or "",
            next_step=req.next_step or "",
            due=req.date or "",
        )

    return _interview_write(edit, company, role)


# ── Connected systems: Mission Control ─────────────────────────
OFFLINE_CARD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Mission Control offline</title>
<style>
  body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
       background:#131722;color:#e6e9ef;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,sans-serif;}
  .card{max-width:420px;text-align:center;padding:2rem;border:1px solid #232838;border-radius:14px;}
  h1{font-size:1.15rem;margin:0 0 .5rem;color:#7c9eff;}
  p{color:#8b93a7;font-size:.9rem;line-height:1.5;margin:.4rem 0;}
  code{background:#1b2130;border:1px solid #232838;padding:.15em .45em;border-radius:6px;font-size:.85em;}
</style></head>
<body><div class="card">
  <h1>&#x1F6AB; Mission Control offline</h1>
  <p>The agentic-os API on 127.0.0.1:8787 is not answering. Restart it:</p>
  <p><code>launchctl kickstart -k gui/$(id -u)/com.cloudtransition.mission-control</code></p>
  <p>First install: see <code>agentic-os/launchd/</code>. Then reload this tab.</p>
</div></body></html>"""


def proxy_mission_control(path: str = ""):
    """Reverse proxy to the agentic-os Mission Control server (:8787).

    HTML responses are rewritten so the dashboard's root-absolute /api/*
    fetches land back through this proxy. API routes forward byte-for-byte.
    """
    upstream = config.MISSION_CONTROL_UPSTREAM + "/" + path.lstrip("/")
    try:
        with urllib.request.urlopen(upstream, timeout=config.MISSION_CONTROL_TIMEOUT) as resp:
            ctype = resp.headers.get("Content-Type", "")
            body = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return HTMLResponse(OFFLINE_CARD, status_code=502)

    if path.startswith("api/"):
        return Response(content=body, media_type=ctype, status_code=200)

    html = body.decode(errors="replace")
    html = html.replace('"/api/', '"/mission-control/api/').replace(
        "'/api/", "'/mission-control/api/"
    )
    return HTMLResponse(html, status_code=200)


# ══════════════════════════════════════════════════════════════
# Skill runner — fire Claude Code skills headlessly from buttons
# ══════════════════════════════════════════════════════════════
# Security model: the browser sends a skill *id* from the allowlist below,
# never an arbitrary prompt or command. Inputs are validated and passed as
# subprocess arguments, without shell=True.

RUN_TIMEOUT = 1800  # 30 min — real skill passes take minutes, not seconds
MAX_RUNS_KEPT = 50
RUNS_LOG_TAIL = 262144  # bytes of runs.log read for "last run"


def _last_finished_run(skill: str) -> dict | None:
    """Newest finished runs.log event for one runner card; survives restarts."""
    try:
        with config.RUNS_LOG.open("rb") as fh:
            size = fh.seek(0, 2)
            fh.seek(max(0, size - RUNS_LOG_TAIL))
            tail = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    for line in reversed(tail.splitlines()):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("skill") == skill and event.get("status") != "running":
            return event
    return None


# ── Model providers for Run executions ───────────────────────────
# Claude keeps its existing aliases; Codex/OpenCode/OpenRouter are
# provider-labelled as "provider:model_id" (e.g. "codex:gpt-6.1-sol",
# "opencode:opencode/beam-free", "openrouter:nvidia/...:free").
PROVIDERS = ("claude", "codex", "opencode", "openrouter")

# `claude --model` takes an alias or a full name. Aliases stay valid as
# models are replaced; pinned full names rot.
ALLOWED_MODELS = ("sonnet", "opus", "fable")
ALLOWED_EFFORT = ("default", "low", "medium", "high")

# Local catalogue locations (no credentials, no network at build time).
CODEX_CACHE = Path.home() / ".codex" / "models_cache.json"
OPENROUTER_CATALOG = Path.home() / ".hermes.bak" / "cache" / "openrouter_curated_catalog.json"
OPENROUTER_METADATA = Path.home() / ".hermes.bak" / "cache" / "openrouter_model_metadata.json"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"

# Bounds for workspace text inlined into OpenRouter prompts (no file tools).
CONTEXT_MAX_FILE_CHARS = 80_000
CONTEXT_MAX_CHARS = 160_000


def _is_free_model_id(model_id: str) -> bool:
    """OpenCode/OpenRouter free models are marked with -free or :free."""
    return model_id.endswith(":free") or model_id.endswith("-free")


def _load_codex_models():
    """Visible Codex catalogue entries: [{id, label, efforts}], available, reason."""
    if _resolve_codex_exe() is None:
        return [], False, "codex executable not on PATH"
    try:
        raw = json.loads(CODEX_CACHE.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        return [], False, f"Codex catalogue unreadable: {exc}"
    entries = raw.get("models") if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        return [], False, "Codex catalogue has no model list"
    seen = set()
    models = []
    for m in entries:
        if not isinstance(m, dict):
            continue
        if m.get("visibility") != "list" or not m.get("supported_in_api"):
            continue
        slug = m.get("slug") or m.get("id")
        if not slug or slug in seen:
            continue
        seen.add(slug)
        levels = m.get("supported_reasoning_levels") or []
        efforts = ["default"]
        for lv in levels:
            if isinstance(lv, dict) and lv.get("effort") and lv["effort"] not in efforts:
                efforts.append(lv["effort"])
        models.append({"id": slug, "label": m.get("display_name") or slug, "efforts": efforts})
    models.sort(key=lambda x: x["label"])
    return (models, True, None) if models else ([], False, "Codex catalogue has no visible entries")


def _resolve_executable(name: str, fallbacks: tuple[Path, ...]) -> str | None:
    """Locate an executable on PATH, then at known install locations.

    launchd starts the dashboard with a minimal PATH that does not include
    per-user bin directories, so PATH alone is not enough.
    """
    try:
        proc = subprocess.run(["which", name], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip().splitlines()[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    for candidate in fallbacks:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _resolve_opencode_exe() -> str | None:
    """Locate the `opencode` executable, checking PATH then common install spots."""
    return _resolve_executable(
        "opencode",
        (
            Path.home() / ".opencode" / "bin" / "opencode",
            Path("/usr/local/bin/opencode"),
            Path("/opt/homebrew/bin/opencode"),
        ),
    )


def _resolve_codex_exe() -> str | None:
    """Locate the `codex` executable, checking PATH then common install spots."""
    return _resolve_executable(
        "codex",
        (
            Path.home() / ".local" / "bin" / "codex",
            Path("/opt/homebrew/bin/codex"),
            Path("/usr/local/bin/codex"),
        ),
    )


def _load_opencode_models():
    """Free OpenCode models from `opencode models`: [{id, label, efforts}], available, reason."""
    exe = _resolve_opencode_exe()
    if exe is None:
        return [], False, "opencode executable not on PATH"
    try:
        # --standalone runs a private server per call instead of depending on the
        # shared background service, whose stale registration can make this hang.
        proc = subprocess.run(
            [exe, "models", "--standalone"], capture_output=True, text=True, timeout=15
        )
    except subprocess.TimeoutExpired:
        return [], False, "opencode models timed out"
    except OSError as exc:
        return [], False, f"opencode models failed to start: {exc}"
    if proc.returncode != 0:
        return [], False, f"opencode models exited {proc.returncode}: {proc.stderr.strip()[:200]}"
    ids = [line.strip() for line in proc.stdout.splitlines() if "/" in line.strip() and _is_free_model_id(line.strip()) and "opus" not in line.strip().lower()]
    seen = set()
    models = []
    for mid in ids:
        if mid in seen:
            continue
        seen.add(mid)
        models.append({"id": mid, "label": mid, "efforts": ["default"]})
    models.sort(key=lambda x: x["id"])
    return (models, True, None) if models else ([], False, "opencode catalogue has no free entries")


def _load_openrouter_models():
    """Free OpenRouter models from the curated catalogue: [{id, label, efforts}], available, reason."""
    try:
        raw = json.loads(OPENROUTER_CATALOG.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        return [], False, f"OpenRouter catalogue unreadable: {exc}"
    curated = raw.get("curated") if isinstance(raw, dict) else None
    if not isinstance(curated, list):
        return [], False, "OpenRouter catalogue has no curated list"
    metadata = {}
    try:
        metadata = json.loads(OPENROUTER_METADATA.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    seen = set()
    models = []
    for entry in curated:
        if not isinstance(entry, (list, tuple)) or len(entry) < 1:
            continue
        mid = entry[0]
        if not isinstance(mid, str) or not mid or any(char.isspace() for char in mid):
            continue
        is_free = _is_free_model_id(mid)
        # zero-price confirmation from metadata (listing is not entitlement).
        # Missing pricing is NOT treated as free: only explicitly zero-priced
        # models qualify.
        info = metadata.get(mid) or metadata.get(mid.split(":")[0]) or {}
        if not isinstance(info, dict):
            info = {}
        pricing = info.get("pricing") if isinstance(info.get("pricing"), dict) else None
        if pricing is not None:
            try:
                prompt_price = float(pricing["prompt"])
                comp_price = float(pricing["completion"])
            except (KeyError, TypeError, ValueError):
                prompt_price = comp_price = None
            if prompt_price == 0 and comp_price == 0:
                is_free = True
        if not is_free:
            continue
        if mid in seen:
            continue
        seen.add(mid)
        models.append({"id": mid, "label": mid, "efforts": ["default"]})
    models.sort(key=lambda x: x["id"])
    return (models, True, None) if models else ([], False, "OpenRouter catalogue has no free entries")


def _fetch_skill_catalog():
    """Assemble the full provider-labelled catalogue (fresh on each call)."""
    claude_models = [
        {"id": m, "label": m.capitalize(), "efforts": list(ALLOWED_EFFORT)} for m in ALLOWED_MODELS
    ]
    codex_models, codex_ok, codex_reason = _load_codex_models()
    opencode_models, opencode_ok, opencode_reason = _load_opencode_models()
    openrouter_models, openrouter_ok, openrouter_reason = _load_openrouter_models()
    return {
        "models": list(ALLOWED_MODELS),
        "effort": list(ALLOWED_EFFORT),
        "provider_models": {
            "claude": claude_models,
            "codex": codex_models,
            "opencode": opencode_models,
            "openrouter": openrouter_models,
        },
        "provider_available": {
            "claude": True,
            "codex": codex_ok,
            "opencode": opencode_ok,
            "openrouter": openrouter_ok,
        },
        "provider_unavailable_reason": {
            "codex": codex_reason,
            "opencode": opencode_reason,
            "openrouter": openrouter_reason,
        },
    }

# The catalogue is read by the Run tab on open. OpenCode listing spawns a
# private server (~4 s), so cache the assembled payload and warm it from any
# dashboard visit; "Refresh models" still forces a rebuild.
_SKILL_CATALOG_TTL = 300.0
_SKILL_CATALOG: dict[str, object] = {
    "payload": None,
    "built_at": 0.0,
    "building": False,
}
_SKILL_CATALOG_LOCK = threading.Lock()


def runner_engine(cfg: dict) -> dict:
    """What a runner spends when it runs; cards are tagged and ordered by this.

    A shell runner is local unless it declares the API it calls: `kind` alone
    cannot tell `brain.py index` from `triage_jev.py`, which bills Jev.
    """
    if cfg.get("engine") == "jev":
        return {"tier": "api", "label": "Jev API · paid"}
    if cfg["kind"] == "shell":
        return {"tier": "local", "label": "No model · $0"}
    if cfg.get("providers") == ["opencode"]:
        return {"tier": "model", "label": "Model · OpenCode free"}
    return {"tier": "model", "label": "Model · Claude by default"}


def _skill_catalog_payload() -> dict:
    """The full catalogue response (provider models plus renderable skills)."""
    return {
        **_fetch_skill_catalog(),
        "skills": [
            {
                "id": sid,
                "label": cfg["label"],
                "blurb": cfg["blurb"],
                "icon": cfg["icon"],
                "kind": cfg["kind"],
                "model": cfg.get("model"),
                "options": cfg.get("options", cfg["kind"] == "claude"),
                "input_label": cfg.get("input_label"),
                "input_type": cfg.get("input_type", "url"),
                "providers": cfg.get("providers"),
                "engine": runner_engine(cfg),
            }
            for sid, cfg in config.SKILL_RUNNERS.items()
        ],
    }


def _cached_skill_catalog(force: bool = False) -> dict:
    """Return a cached catalogue, rebuilding it when stale or forced."""
    now = time.monotonic()
    with _SKILL_CATALOG_LOCK:
        cached = _SKILL_CATALOG["payload"]
        if (
            not force
            and cached is not None
            and now - float(_SKILL_CATALOG["built_at"]) < _SKILL_CATALOG_TTL
        ):
            return cached  # type: ignore[return-value]
        payload = _skill_catalog_payload()
        _SKILL_CATALOG["payload"] = payload
        _SKILL_CATALOG["built_at"] = time.monotonic()
        return payload


def _warm_skill_catalog() -> None:
    """Build the catalogue off the request path so the next Run visit is fast."""
    now = time.monotonic()
    with _SKILL_CATALOG_LOCK:
        cached = _SKILL_CATALOG["payload"]
        if (
            cached is not None
            and now - float(_SKILL_CATALOG["built_at"]) < _SKILL_CATALOG_TTL
        ):
            return
        if _SKILL_CATALOG["building"]:
            return
        _SKILL_CATALOG["building"] = True

    def build() -> None:
        try:
            # Not forced: if a page request filled the cache first, reuse it.
            _cached_skill_catalog()
        except Exception:  # noqa: BLE001 — a failed warm must not break the page
            pass
        finally:
            with _SKILL_CATALOG_LOCK:
                _SKILL_CATALOG["building"] = False

    threading.Thread(target=build, name="skill-catalog-warm", daemon=True).start()


_RUNS: dict[str, dict] = {}
_RUNS_LOCK = threading.Lock()


class RunRequest(BaseModel):
    skill: str
    model: str | None = None
    effort: str | None = None
    input: str | None = None


def _log_run(entry: dict) -> None:
    """Append one JSON event per state change; preserve command and output path."""
    with config.RUNS_LOG.open("a") as fh:
        fh.write(
            json.dumps(
                {
                    "timestamp": datetime.now().astimezone().isoformat(),
                    **entry,
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def _build_update_sheet_prompt() -> str:
    """Reuse the prompt already embedded in index.html so there is one copy."""
    today = date.today()
    src = (Path(__file__).parent / "templates" / "index.html").read_text()
    m = re.search(r'<template id="update-sheet-prompt">(.*?)</template>', src, re.S)
    if not m:
        return (
            "Update the CloudTransition workspace so every dated file reflects today."
        )
    return (
        m.group(1)
        .replace("{{ today }}", today.isoformat())
        .replace("{{ current_week }}", str(current_week_of_year(today)))
    )


def _parse_model(value: str | None) -> tuple[str, str] | None:
    """Parse a model selection into (provider, model_id).

    Accepts "provider:model_id" for any provider, or a bare Claude alias
    (sonnet/opus/fable) treated as "claude:<alias>" for backward compatibility.
    Returns None when the value cannot be parsed.
    """
    if value is None:
        return None
    if value in ALLOWED_MODELS:
        return "claude", value
    if ":" in value:
        provider, _, model_id = value.partition(":")
        if provider in PROVIDERS and model_id:
            return provider, model_id
    return None


def _card_allows_provider(cfg: dict, provider: str) -> tuple[bool, str | None]:
    """Whether a provider may run this card, respecting read/write boundaries.

    A card that declares ``providers`` is restricted to exactly those
    providers; every other card keeps the permissive behavior. For those
    unrestricted cards, Claude is always allowed (its existing per-card tool
    restrictions apply) and every other provider is allowed too: the user
    accepts that the provider cannot machine-enforce the card's read-only or
    file/command allowlist. Boundary enforcement is then the user's
    responsibility when choosing a provider.
    """
    allowed = cfg.get("providers")
    if allowed and provider not in allowed:
        return False, f"{cfg['label']} only supports {', '.join(allowed)} models."
    return True, None


def _run_openrouter(model_id: str, prompt: str) -> dict:
    """Call the OpenRouter chat API. Returns {status, exit_code, body}.

    Never logs the API key. Returns a failed result when
    OPENROUTER_API_KEY is unset, so no model call is made.
    """
    api_key = os.environ.get(OPENROUTER_API_KEY_ENV)
    if not api_key:
        return {
            "status": "failed",
            "exit_code": -1,
            "body": (
                "OpenRouter is not configured: set OPENROUTER_API_KEY. "
                "No model call was made."
            ),
        }
    payload = json.dumps(
        {"model": model_id, "messages": [{"role": "user", "content": prompt}]}
    ).encode()
    request = urllib.request.Request(
        OPENROUTER_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=RUN_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", "replace")
            return {"status": "done", "exit_code": 0, "body": body}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:2000]
        return {"status": "failed", "exit_code": -1, "body": body}
    except urllib.error.URLError as exc:
        return {
            "status": "failed",
            "exit_code": -1,
            "body": f"OpenRouter request failed: {exc}",
        }
    except OSError as exc:
        return {"status": "failed", "exit_code": -1, "body": f"OpenRouter error: {exc}"}


def _workspace_context(files: list[str]) -> str:
    """Inline a card's declared files for providers that cannot read them.

    Paths outside the workspace and privacy-flagged paths are skipped, and the
    rendered text is bounded so a request cannot balloon.
    """
    base = config.WORKSPACE.resolve()
    remaining = CONTEXT_MAX_CHARS
    parts: list[str] = []
    for rel in files:
        rel_path = Path(rel)
        target = (config.WORKSPACE / rel_path).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            continue
        if wc.privacy_violation(rel_path.as_posix()) or not target.is_file():
            continue
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        limited = text[: min(CONTEXT_MAX_FILE_CHARS, max(remaining, 0))]
        if not limited:
            break
        numbered = "\n".join(
            f"{number:>5}| {line}"
            for number, line in enumerate(limited.splitlines(), start=1)
        )
        suffix = "\n… truncated" if len(limited) < len(text) else ""
        parts.append(f"### {rel_path.as_posix()}\n{numbered}{suffix}")
        remaining -= len(numbered)
        if remaining <= 0:
            break
    if not parts:
        return ""
    return (
        "Workspace context follows because this provider cannot read files. "
        "Use it and cite line numbers as path:line.\n\n" + "\n\n".join(parts)
    )

def _provider_skill_prompt(prompt: str, provider: str) -> str:
    """Resolve the allowlisted card's slash skill for non-Claude providers."""
    match = re.match(r"^/([a-z0-9-]+)(?:\s+|$)", prompt)
    if provider == "claude" or not match:
        return prompt
    name = match.group(1)
    roots = (
        config.WORKSPACE / ".claude" / "skills",
        config.WORKSPACE / ".agents" / "skills",
        Path.home() / ".claude" / "skills",
        Path.home() / ".agents" / "skills",
    )
    source = next((root / name / "SKILL.md" for root in roots if (root / name / "SKILL.md").is_file()), None)
    if source is None:
        raise ValueError(f"Skill {name} is not installed; no run started")
    try:
        instructions = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Skill {name} cannot be read; no run started") from exc
    if len(instructions) > CONTEXT_MAX_FILE_CHARS:
        raise ValueError(f"Skill {name} exceeds the prompt limit; no run started")
    access = (
        "You have no local file or command tools. Use the supplied context; report any "
        "missing references or capabilities instead of inventing results."
        if provider == "openrouter"
        else f"Resolve the skill's relative reference and script paths against {source.parent}."
    )
    return f"Apply the {name} skill to this task:\n{prompt[match.end():]}\n\n{access}\n\nSkill instructions ({source}):\n{instructions}"



def _resolve_run(cfg: dict, req: RunRequest, staging: str = "") -> tuple[dict, str]:
    """Build a run specification. Returns (run_spec, human-readable command).

    run_spec has a "kind" key: "shell", "claude", "codex", "opencode", or
    "openrouter". Subprocess kinds carry an "argv" list; OpenRouter carries
    "model" and "prompt" and is dispatched over HTTP in _execute_run.
    """
    if cfg["kind"] == "shell":
        argv = list(cfg["argv"])
        if cfg.get("input_argv") and req.input:
            argv.append(req.input)
        return {"kind": "shell", "argv": argv}, shlex.join(argv)

    today = date.today()
    if cfg.get("prompt") is None:
        prompt = _build_update_sheet_prompt()
    else:
        # Placeholders: {input} (validated form value), {today}, {week}, and
        # {staging} (a per-run folder path the server chose, never user input).
        prompt = cfg["prompt"].format(
            input=req.input or "",
            today=today.isoformat(),
            week=current_week_of_year(today),
            staging=staging,
        )

    options = cfg.get("options", True)
    if options and req.model is not None:
        parsed = _parse_model(req.model)
        if parsed is None:
            provider, model_id = "claude", cfg.get("model", "sonnet")
        else:
            provider, model_id = parsed
    else:
        provider, model_id = "claude", cfg.get("model", "sonnet")

    effort = req.effort if req.effort and req.effort != "default" else None
    prompt = _provider_skill_prompt(prompt, provider)


    # OpenRouter chats cannot read files, so inline the card's declared
    # workspace context for it. Local CLIs (claude/codex/opencode) read the
    # files themselves and must not get a copy in the prompt.
    if provider == "openrouter" and cfg.get("context_files"):
        if context := _workspace_context(cfg["context_files"]):
            prompt = f"{prompt}\n\n{context}"

    if provider == "claude":
        argv = [
            "claude",
            "-p",
            prompt,
            "--model",
            model_id,
            "--permission-mode",
            "dontAsk" if cfg.get("read_only") or cfg.get("permissions") else "acceptEdits",
            "--permission-prompts",
            "none",
        ]
        if cfg.get("read_only"):
            argv += [
                "--tools",
                "Read,Glob,Grep,Skill",
                "--allowedTools",
                "Read,Glob,Grep,Skill",
            ]
        if perms := cfg.get("permissions"):
            argv += ["--tools", ",".join(perms["tools"]), "--allowedTools", *perms["allow"]]
            for d in perms.get("add_dirs", []):
                argv += ["--add-dir", d]
        if effort:
            argv += ["--effort", effort]
        return {"kind": "claude", "argv": argv}, shlex.join(argv)

    if provider == "codex":
        exe = _resolve_codex_exe()
        if exe is None:
            return (
                {"kind": "error", "error": "codex executable not on PATH"},
                "codex exec -m <model> <prompt>",
            )
        sandbox = "read-only" if cfg.get("read_only") else "workspace-write"
        argv = [
            exe,
            "exec",
            "-m",
            model_id,
            "-s",
            sandbox,
            "-C",
            str(config.WORKSPACE),
            "--color",
            "never",
            prompt,
        ]
        if effort:
            argv += ["-c", f"model_reasoning_effort={effort}"]
        return {"kind": "codex", "argv": argv}, shlex.join(argv)

    if provider == "opencode":
        exe = _resolve_opencode_exe()
        if exe is None:
            return (
                {"kind": "error", "error": "opencode executable not on PATH"},
                "opencode run --standalone -m <model> <prompt>",
            )
        # --standalone avoids the shared background service so a stale service
        # registration cannot make the run hang.
        argv = [exe, "run", "--standalone"]
        if cfg.get("kind") == "opencode-agent":
            agent = cfg.get("agent")
            if not agent:
                return (
                    {
                        "kind": "error",
                        "error": "opencode-agent card has no agent configured",
                    },
                    "opencode run --standalone --agent <agent> -m <model> <prompt>",
                )
            argv += ["--agent", agent]
        argv += ["-m", model_id, prompt]
        return {"kind": "opencode", "argv": argv}, shlex.join(argv)

    # openrouter — dispatched over HTTP in _execute_run
    return (
        {"kind": "openrouter", "model": model_id, "prompt": prompt},
        f"openrouter {model_id} <prompt>",
    )


def _run_env() -> dict:
    """Child environment with PWD matching cwd.

    `opencode run` finds its project (agents, and the Location its relative
    permission paths are matched against) from $PWD, not the process cwd. The
    server's own PWD (e.g. dashboard-app/) would otherwise leak into runs.
    """
    return {**os.environ, "PWD": str(config.WORKSPACE)}


def _opencode_resolved_agents() -> list | None:
    """`opencode debug agents` from the workspace root: OpenCode's own resolution
    of every agent's instructions and permission rules, or None if it gives no
    readable answer."""
    try:
        proc = subprocess.run(
            [_resolve_opencode_exe() or "opencode", "debug", "agents", "--standalone"],
            cwd=config.WORKSPACE,
            env=_run_env(),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        resolved = json.loads(proc.stdout) if proc.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    return resolved if isinstance(resolved, list) else None


def _verify_opencode_agent(run_id: str, verify: dict) -> dict | None:
    """Check OpenCode's resolved agent against the definition hashed at launch.

    Records the outcome on the run. Fails closed: anything but "matched"
    (file changed, other instructions, unknown agent, a permission probe with
    the wrong effect, or no readable answer from OpenCode) returns a failed
    result and nothing launches. Returns None to go ahead.
    """
    expected = verify["expected"]
    current = forge_agents.launch_definition(verify["agent"])
    if current is None or current["sha256"] != expected["sha256"]:
        check = {"check": "mismatch", "detail": f"{expected['path']} changed or vanished after the run was requested."}
    else:
        resolved = _opencode_resolved_agents()
        if resolved is not None:
            check = forge_agents.check_resolved_agent(verify["agent"], resolved, expected, verify.get("policy"))
        else:
            check = {
                "check": "unverified",
                "detail": "opencode debug agents gave no readable answer, so the definition could not be verified.",
            }
    with _RUNS_LOCK:
        entry = _RUNS.get(run_id)
        if entry is not None:
            entry["definition"].update(check)
    if check["check"] != "matched":
        return {"status": "failed", "exit_code": -1, "body": f"Not started: {check['detail']}"}
    return None


def _append_agent_event(agent: str, event: dict) -> str | None:
    """Append one JSON line to an agent's existing memory log; None on success.

    Never creates the memory folder (a missing one usually means the drive or
    workspace is not what we expect). Adds a newline first if the log lacks one.
    """
    log = Path(forge_agents.AGENT_STATE) / agent / "memory" / "log.jsonl"
    if not log.parent.is_dir():
        return f"{log.parent} is missing; memory event not recorded and nothing was created."
    line = json.dumps(event, ensure_ascii=False) + "\n"
    try:
        with _FILE_WRITE_LOCK, log.open("a+b") as fh:
            fh.seek(0, 2)
            if fh.tell():
                fh.seek(-1, 2)
                if fh.read(1) != b"\n":
                    line = "\n" + line
            fh.write(line.encode("utf-8"))
    except OSError as exc:
        return f"Memory event not recorded: {exc}"
    return None


def _stage_job_reading(job: dict) -> str | None:
    """Create this run's empty staging folder; None on success, else why not.

    Only under an existing workspace/agents/job-reader/ (never recreated if the
    drive or agent folder is missing).
    """
    root = Path(forge_agents.AGENT_STATE) / "job-reader"
    if not root.is_dir():
        return f"{root} is missing; nothing was created."
    try:
        (root / "staging" / job["run_id"]).mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        return f"Cannot create the staging folder: {exc}"
    return None


def _discard_staging(job: dict) -> None:
    """Remove this run's staging folder only; other runs' folders are untouched."""
    shutil.rmtree(Path(forge_agents.AGENT_STATE) / "job-reader" / "staging" / job["run_id"], ignore_errors=True)


def _finish_job_reading(run_id: str, job: dict, result: dict, launched_at: datetime, exited_at: datetime) -> dict:
    """Validate the staged reading, publish it, then record the memory event.

    The agent can write only staging/<run id>/; publishing to outputs/ and the
    memory event are done here, so the agent cannot overwrite another job's
    output or its memory. Timestamps come from this process, never the model.
    A missing or invalid staged file fails the run visibly.
    """
    staged = Path(forge_agents.AGENT_STATE) / "job-reader" / "staging" / run_id
    data, error = forge_agents.validate_staged_reading(staged, job["job_id"])
    extras = sorted(p.name for p in staged.glob("*") if p.name != f"{job['job_id']}.json") if staged.is_dir() else []
    with _RUNS_LOCK:
        run = dict(_RUNS.get(run_id) or {"id": run_id})
    final = None
    if data:
        final = forge_agents.finalize_reading(data, run, launched_at, exited_at, datetime.now().astimezone())
        target = Path(forge_agents.AGENT_STATE) / "job-reader" / "outputs" / f"{job['job_id']}.json"
        try:
            with _FILE_WRITE_LOCK:
                _atomic_write(target, json.dumps(final, ensure_ascii=False, indent=2) + "\n")
        except OSError as exc:
            final, error = None, f"Could not publish the output: {exc}"
    _discard_staging(job)
    event = forge_agents.job_reader_event(run, job["job_id"], job["url"], final, error)
    memory_error = _append_agent_event("job-reader", event)
    check = (
        f"Output published: workspace/agents/job-reader/outputs/{job['job_id']}.json"
        if final
        else f"Output rejected: {error}"
    )
    if extras:
        check += f" (ignored other staged files: {', '.join(extras)})"
    memory = memory_error or f"Memory event recorded: {event['event']}"
    status = result["status"] if final and not memory_error else "failed"
    with _RUNS_LOCK:
        if run_id in _RUNS:
            _RUNS[run_id]["output_check"] = check
    return {**result, "status": status, "body": f"{result['body']}\n\n--- dashboard check ---\n{check}\n{memory}\n"}


def _execute_run(run_id: str, run_spec: dict) -> None:
    """Run the command to completion in a worker thread; record the result.

    run_spec["kind"] is "shell"/"claude"/"codex"/"opencode" (subprocess via
    run_spec["argv"]) or "openrouter" (HTTP via run_spec["model"]/prompt).
    """
    config.RUNS_DIR.mkdir(exist_ok=True)
    out_path = config.RUNS_DIR / f"{run_id}.txt"
    started = time.time()
    try:
        if run_spec["kind"] == "error":
            result = {
                "status": "failed",
                "exit_code": -1,
                "body": run_spec.get("error", "run spec error"),
            }
        elif run_spec["kind"] == "openrouter":
            result = _run_openrouter(run_spec["model"], run_spec["prompt"])
        elif run_spec.get("verify_agent") and (
            refused := _verify_opencode_agent(run_id, run_spec["verify_agent"])
        ):
            result = refused
        else:
            job = run_spec.get("job_reading")
            staging_error = _stage_job_reading(job) if job else None
            if staging_error:
                result = {"status": "failed", "exit_code": -1, "body": f"Not started: {staging_error}"}
            else:
                argv = run_spec["argv"]
                launched_at = datetime.now().astimezone()
                try:
                    proc = subprocess.run(
                        argv,
                        cwd=config.WORKSPACE,
                        env=_run_env(),
                        capture_output=True,
                        text=True,
                        timeout=RUN_TIMEOUT,
                        check=False,
                    )
                except BaseException:
                    if job:
                        _discard_staging(job)
                    raise
                body = proc.stdout + (
                    f"\n\n--- stderr ---\n{proc.stderr}" if proc.stderr.strip() else ""
                )
                result = {
                    "status": "done" if proc.returncode == 0 else "failed",
                    "exit_code": proc.returncode,
                    "body": body,
                }
                if job:
                    result = _finish_job_reading(run_id, job, result, launched_at, datetime.now().astimezone())
    except subprocess.TimeoutExpired:
        result = {
            "status": "failed",
            "exit_code": -1,
            "body": f"Timed out after {RUN_TIMEOUT}s.",
        }
    except FileNotFoundError:
        result = {
            "status": "failed",
            "exit_code": -1,
            "body": f"Command not found: {run_spec['argv'][0]}. Is it on PATH?",
        }
    except OSError as exc:
        result = {"status": "failed", "exit_code": -1, "body": f"Failed to start: {exc}"}

    out_path.write_text(result["body"])
    duration = f"{time.time() - started:.1f}s"

    with _RUNS_LOCK:
        entry = _RUNS.get(run_id)
        if entry is not None:
            entry.update(
                status=result["status"],
                exit_code=result["exit_code"],
                duration=duration,
                finished=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                output=str(out_path.relative_to(config.WORKSPACE)),
                preview=result["body"].strip()[-400:],
            )
            _log_run(entry)


@app.get("/api/skills/catalog")
def api_skill_catalog():
    """The buttons the UI should render, with provider-labelled model catalogues."""
    return JSONResponse(_cached_skill_catalog())


@app.post("/api/skills/catalog/refresh")
def api_skill_catalog_refresh():
    """Force a fresh read of the provider catalogues (Refresh models button)."""
    return JSONResponse(_cached_skill_catalog(force=True))


@app.post("/api/skills/run")
def api_skill_run(req: RunRequest, x_requested_with: str = Header(default="")):
    """Start one skill run in the background; return its id immediately."""
    if x_requested_with != "XMLHttpRequest":
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)

    cfg = config.SKILL_RUNNERS.get(req.skill)
    if cfg is None:
        return JSONResponse({"error": "Unknown skill"}, status_code=400)

    # Validate the selected model against its provider, not just its prefix.
    # Allowing a provider on a card does not allow arbitrary or paid model IDs.
    if cfg["kind"] == "shell":
        if req.model is not None or req.effort not in (None, "default"):
            return JSONResponse({"error": "Shell tools do not accept model or effort selections"}, status_code=400)
        provider, model_id = None, None
        valid_efforts = ["default"]
    else:
        selection = req.model if cfg.get("options", True) and req.model is not None else cfg.get("model", "sonnet")
        parsed = _parse_model(selection)
        if parsed is None:
            return JSONResponse({"error": "Unknown model"}, status_code=400)
        provider, model_id = parsed
        if provider == "claude":
            models = [{"id": model, "efforts": list(ALLOWED_EFFORT)} for model in ALLOWED_MODELS]
        else:
            loader = {
                "codex": _load_codex_models,
                "opencode": _load_opencode_models,
                "openrouter": _load_openrouter_models,
            }[provider]
            models, available, reason = loader()
            if not available:
                return JSONResponse({"error": reason}, status_code=400)
        selected = next((model for model in models if model["id"] == model_id), None)
        if selected is None:
            return JSONResponse({"error": f"Unknown model for {provider}"}, status_code=400)
        valid_efforts = selected["efforts"]
    effort = req.effort if req.effort is not None else "default"
    if effort not in valid_efforts:
        return JSONResponse({"error": "Unsupported effort for this model"}, status_code=400)

    # Permission parity: refuse provider/card pairings that cannot enforce the
    # card's read-only or command/template boundary.
    allowed, reason = _card_allows_provider(cfg, provider)
    if not allowed:
        return JSONResponse({"error": reason}, status_code=400)

    # OpenRouter requires a configured API key before anything launches.
    if provider == "openrouter" and not os.environ.get(OPENROUTER_API_KEY_ENV):
        return JSONResponse(
            {
                "error": "OpenRouter is not configured: set OPENROUTER_API_KEY. No model call was made."
            },
            status_code=400,
        )

    if cfg.get("input_label"):
        value = (req.input or "").strip()
        if not value and cfg.get("input_optional"):
            req.input = None
        elif not value:
            return JSONResponse(
                {"error": f"{cfg['input_label']} is required"}, status_code=400
            )
        elif not re.match(cfg["input_pattern"], value):
            return JSONResponse(
                {"error": f"Not a valid {cfg['input_label']}"}, status_code=400
            )
        else:
            req.input = value

    run_id = uuid4().hex
    # Job Reader writes only to this run's staging folder; the server picks it.
    staging = f"workspace/agents/job-reader/staging/{run_id}" if cfg.get("post_run") == "job-reading" else ""
    try:
        run_spec, shown = _resolve_run(cfg, req, staging)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    # Agent cards: hash the definition OpenCode should load before anything runs.
    agent_id = cfg.get("agent") if cfg["kind"] == "opencode-agent" else None
    definition = None
    if agent_id:
        definition = forge_agents.launch_definition(agent_id)
        if definition is None:
            return JSONResponse(
                {"error": f".opencode/agents/{agent_id}.md is missing; run not started"}, status_code=400
            )

    entry = {
        "id": run_id,
        "skill": req.skill,
        "label": cfg["label"],
        "provider": provider,
        "model": model_id,
        "effort": effort,
        "status": "running",
        "started": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "command": shown,
        "output": None,
        "duration": None,
        "preview": None,
    }
    if agent_id and run_spec["kind"] == "opencode":
        # The dashboard resolves this path; OpenCode's own resolution is checked
        # in _verify_opencode_agent just before launch.
        entry.update(
            agent=agent_id,
            runner="opencode-agent",
            cwd=str(config.WORKSPACE),
            log=str(config.RUNS_LOG.relative_to(config.WORKSPACE)),
            finished=None,
            definition={**definition, "check": "pending", "detail": "Not yet compared with OpenCode."},
        )
        run_spec["verify_agent"] = {"agent": agent_id, "expected": definition, "policy": cfg.get("policy")}
        if cfg.get("post_run") == "job-reading":
            # input_pattern already guarantees "<job id> <http(s) URL>".
            jid, url = req.input.split(" ", 1)
            run_spec["job_reading"] = {"job_id": jid, "url": url, "run_id": run_id}
    with _RUNS_LOCK:
        # Check and reserve together: double-clicks must not start two processes,
        # and one agent runs one task at a time (its memory has one writer).
        for r in _RUNS.values():
            if r["status"] != "running":
                continue
            if r["skill"] == req.skill:
                return JSONResponse({"error": "Already running"}, status_code=409)
            if agent_id and r.get("agent") == agent_id:
                return JSONResponse(
                    {"error": f"{agent_id} is already running {r['label']}"}, status_code=409
                )
        try:
            _log_run(entry)
        except OSError:
            return JSONResponse(
                {"error": "Cannot write runs.log; run not started"}, status_code=503
            )
        _RUNS[run_id] = entry
        completed = sorted(
            (key for key, run in _RUNS.items() if run["status"] != "running"),
            key=lambda key: _RUNS[key]["started"],
        )
        for stale in completed[:-MAX_RUNS_KEPT]:
            _RUNS.pop(stale, None)

    threading.Thread(target=_execute_run, args=(run_id, run_spec), daemon=True).start()
    return JSONResponse({"ok": True, "run": entry})


@app.get("/api/skills/runs")
def api_skill_runs():
    """Current status of every tracked run, newest first."""
    with _RUNS_LOCK:
        runs = sorted(_RUNS.values(), key=lambda r: r["started"], reverse=True)
    return JSONResponse({"runs": runs})


# ── Routers ────────────────────────────────────────────────────
app.include_router(metrics.router)
app.include_router(calendar.router)
