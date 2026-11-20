"""Task writes: checkbox toggle across REALMS and Weekly Review, and Inbox capture."""

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core import calendar_sources, config
from core.store import _FILE_WRITE_LOCK, _atomic_write
from core.tasks import CHECKBOX_RE, insert_inbox_item
from core.today import _routine_review_items

router = APIRouter()


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


@router.post("/api/tasks/toggle")
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


@router.post("/api/capture")
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
