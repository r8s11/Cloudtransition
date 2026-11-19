"""Dashboard pages: the tabbed shell, Skill registry, Mission Control proxy and assistant state."""

import http.client
import json
import urllib.error
import urllib.request
from datetime import date, datetime

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from core import agents as forge_agents
from core import config
from core import now as now_engine
from core import skills as skill_reg
from core.agents import build_agents_view
from core.interview_view import attach_agents, build_interview_view, next_interview_action
from core.store import load_yaml
from core.tasks import parse_all_realms, parse_tasks_from_file
from core.today import (
    build_today_view,
    command_centre,
    current_week_of_year,
    live_projects,
    money_available,
    parse_routine_folds,
)
from core import views
from routes import calendar
from routes import runs as run_routes
from routes.common import templates

router = APIRouter()


# ── Build Context ─────────────────────────────────────────────
def build_context() -> dict:
    """Read the workspace once and compose every tab's template data."""
    skills_data = load_yaml(config.SKILLS_FILE)
    goals_data = load_yaml(config.GOALS_FILE)
    jobs_data = load_yaml(config.JOBS_FILE)
    network_data = load_yaml(config.NETWORK_FILE)
    realm_tasks = parse_all_realms()
    today = date.today()
    current_week = current_week_of_year(today)

    interview_view = build_interview_view(jobs_data, today)
    for interview_row in interview_view["interview_rows"]:
        attach_agents(interview_row)
    agents_view = build_agents_view()
    scout_leads = forge_agents.scout_leads(
        agents_view["agent_scan"],
        {(r["company"].casefold(), r["role"].casefold()) for r in interview_view["interview_rows"]},
    )

    # Today: routine folds, Next up and live projects
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
        **views.build_education_view(load_yaml(config.EDU_FILE)),
        **views.build_progress_view(current_week),
        "realm_tasks": realm_tasks,
        "realms": config.REALMS,
        **views.build_skills_view(skills_data),
        **views.build_career_view(jobs_data, goals_data, network_data),
        **interview_view,
        **views.build_projects_view(),
        "live_projects": live,
        **views.build_books_view(load_yaml(config.BOOKS_FILE)),
        **agents_view,
        "agent_card_runs": {
            agent: {"skill": skill, "last": run_routes._last_finished_run(skill)}
            for agent, skill in config.AGENT_CARD_RUNNERS.items()
        },
        "interview_scout_leads": scout_leads,
    }


# ── Routes ────────────────────────────────────────────────────
@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    # The Run tab reads this catalogue; build it while the page renders.
    run_routes._warm_skill_catalog()
    ctx = build_context()
    # Tailscale serve arrives with the tailnet Host; Mission links are Mac-only.
    ctx["is_local"] = request.url.hostname in {"127.0.0.1", "localhost"}
    return templates.TemplateResponse(request, "index.html", ctx)


@router.get("/agents/skills", response_class=HTMLResponse)
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


@router.get("/mission-control")
@router.get("/mission-control/{path:path}", response_class=HTMLResponse)
def mission_control(path: str = ""):
    return proxy_mission_control(path)


@router.post("/mission-control/{path:path}")
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


# Read-only live state for the bot/ personal assistant (Brain). One aggregating
# GET so any agent can answer from current data without scraping HTML.
ASSISTANT_SECTIONS = ("tasks", "interviews", "runs", "missions", "calendar")
_RUN_LOG_SAFE = ("timestamp", "id", "skill", "status", "model", "provider", "duration", "exit_code")


@router.get("/api/assistant/state")
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
