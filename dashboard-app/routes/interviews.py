"""Interviews and Career APIs: tracker edits, Interview mode, prep sheet, work-search log."""

from datetime import date, timedelta

import yaml
from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from core import config
from core import interview_editor as ie
from core import now as now_engine
from core import work_search as ws
from core.interview_view import attach_agents, build_interview_view
from core.store import _FILE_WRITE_LOCK, _atomic_write, load_yaml
from routes.common import templates

router = APIRouter()


class WorkSearchRequest(BaseModel):
    id: str
    date: str
    activity_type: str
    description: str
    position: str = ""
    employer: str
    address: str = ""
    result: str = ""


@router.get("/api/career/work-search")
def work_search_report(start: date | None = None):
    from datetime import timedelta

    start = start or (date.today() - timedelta(days=date.today().weekday()))
    try:
        return ws.report(load_yaml(config.JOBS_FILE), start)
    except (ValueError, yaml.YAMLError, OverflowError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/api/career/work-search")
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


@router.post("/api/interviews/field")
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


@router.post("/api/interviews/next-step")
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


@router.post("/api/interviews/timeline")
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


@router.post("/api/interviews/applied")
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


@router.get("/api/interviews/detail")
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
    return JSONResponse({"ok": True, "row": attach_agents(row)})


@router.get("/interviews/sheet", response_class=HTMLResponse)
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


@router.post("/api/interviews/text")
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


@router.post("/api/interviews/create")
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
