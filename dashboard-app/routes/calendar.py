"""Google Calendar: service lifecycle, same-origin guard, local source writes and policy."""

from contextlib import asynccontextmanager

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from core import calendar_sources, config
from core.google_calendar import CalendarService
from core.store import _FILE_WRITE_LOCK, _atomic_write
from core.tasks import parse_tasks_from_file

router = APIRouter()

calendar_service = CalendarService(
    config.WORKSPACE, config.REALMS, config.JOBS_FILE, source_lock=_FILE_WRITE_LOCK, write_source=_atomic_write
)


@asynccontextmanager
async def calendar_lifespan(application):
    calendar_service.start()
    try:
        yield
    finally:
        calendar_service.stop()


# POSTs that write local sources or Google policy (calendar + capture) refuse
# cross-site requests; app.py registers this as HTTP middleware.
async def calendar_origin_guard(request: Request, call_next):
    if request.method != "GET" and (
        request.url.path.startswith("/api/calendar/") or request.url.path == "/api/capture"
    ):
        origin = request.headers.get("origin")
        expected = f"{request.url.scheme}://{request.url.netloc}"
        if (origin and origin != expected) or request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"error": "Same-origin requests only"}, status_code=403)
    return await call_next(request)


# ── Google Calendar: local source writes and explicit policy ────
@router.get("/api/calendar")
def calendar_snapshot():
    return calendar_service.snapshot()


def _calendar_action(action, x_requested_with):
    if x_requested_with != "XMLHttpRequest":
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    try:
        return JSONResponse(action())
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except (OSError, RuntimeError):
        return JSONResponse({"error": "Calendar unavailable; local work is unchanged."}, status_code=503)


@router.post("/api/calendar/refresh")
def calendar_refresh(x_requested_with: str = Header(default="")):
    return _calendar_action(calendar_service.refresh, x_requested_with)


@router.post("/api/calendar/config")
def calendar_config(payload: dict, x_requested_with: str = Header(default="")):
    return _calendar_action(lambda: calendar_service.configure(payload), x_requested_with)


@router.post("/api/calendar/preview")
def calendar_preview(payload: dict, x_requested_with: str = Header(default="")):
    return _calendar_action(lambda: calendar_service.preview(payload), x_requested_with)


@router.post("/api/calendar/enable")
def calendar_enable(payload: dict, x_requested_with: str = Header(default="")):
    return _calendar_action(
        lambda: calendar_service.enable(payload.get("config"), payload.get("review")),
        x_requested_with,
    )


@router.post("/api/calendar/pause")
def calendar_pause(x_requested_with: str = Header(default="")):
    return _calendar_action(calendar_service.pause, x_requested_with)


@router.post("/api/calendar/schedule")
def calendar_schedule(payload: dict, x_requested_with: str = Header(default="")):
    def save():
        with _FILE_WRITE_LOCK:
            target, updated = calendar_sources.schedule_item(
                config.WORKSPACE, config.REALMS, config.JOBS_FILE, payload
            )
            _atomic_write(target, updated)
        result = {"ok": True, "message": "Saved locally. Google outcome appears in Upcoming calendar."}
        if payload.get("source") != "interviews":
            result["items"] = parse_tasks_from_file(target, payload["source"])
        return result
    return _calendar_action(save, x_requested_with)
