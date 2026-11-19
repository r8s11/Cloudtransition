"""
Command Center — FastAPI app that reads workspace YAML/MD files directly.

Run:  uvicorn app:app --reload
Open: http://localhost:8000
"""

import http.client
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core import config
from core import now as now_engine
from core import workspace_content as wc
from core import agents as forge_agents
from core import skills as skill_reg
from core.agents import build_agents_view
from core import calendar_sources
from core.interview_view import attach_agents, build_interview_view, next_interview_action
from core.store import _FILE_WRITE_LOCK, _atomic_write, load_yaml
from core.tasks import CHECKBOX_RE, insert_inbox_item, parse_all_realms, parse_tasks_from_file
from core.today import (
    _routine_review_items,
    build_today_view,
    command_centre,
    current_week_of_year,
    live_projects,
    money_available,
    parse_routine_folds,
)
from routes import calendar, files, interviews, metrics
from routes import runs as run_routes
from routes.common import templates


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
        attach_agents(interview_row)
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
            agent: {"skill": skill, "last": run_routes._last_finished_run(skill)}
            for agent, skill in config.AGENT_CARD_RUNNERS.items()
        },
        "interview_scout_leads": scout_leads,
    }


# ── Routes ────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    # The Run tab reads this catalogue; build it while the page renders.
    run_routes._warm_skill_catalog()
    ctx = build_context()
    # Tailscale serve arrives with the tailnet Host; Mission links are Mac-only.
    ctx["is_local"] = request.url.hostname in {"127.0.0.1", "localhost"}
    return templates.TemplateResponse(request, "index.html", ctx)


@app.get("/agents/skills", response_class=HTMLResponse)
def skill_registry(request: Request):
    """Read-only Skill Registry: what OpenCode registers, and what each agent may load.

    Access comes from OpenCode's own resolved rules (`opencode debug agents`),
    so this page takes a few seconds; it never changes a skill or an agent.
    """
    registry = skill_reg.discover_skills()
    agent_ids = [a["slug"] for a in forge_agents.discover_agents()["agents"] if a["discovered"]]
    resolved = run_routes._opencode_resolved_agents()
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


# Workspace map viewer assets; eligibility and privacy rules live in workspace_content.py.
app.mount(
    "/workspace-map/assets",
    StaticFiles(directory=wc.VIEWER_HTML.parent / "assets", follow_symlink=False),
    name="workspace-map-assets",
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
        with run_routes._RUNS_LOCK:
            live = sorted(run_routes._RUNS.values(), key=lambda run: run["started"], reverse=True)
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


# ── Routers ────────────────────────────────────────────────────
app.include_router(metrics.router)
app.include_router(calendar.router)
app.include_router(interviews.router)
app.include_router(run_routes.router)
app.include_router(files.router)
