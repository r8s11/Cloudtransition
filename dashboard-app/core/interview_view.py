"""Interviews tab rows and Today's next interview action, from job-applications.yml."""

import urllib.parse
from datetime import date
from pathlib import Path

from core import config
from core import interview_editor as ie
from core.workspace_content import workspace_file_href


# ── Interview dashboard ───────────────────────────────────────
# interviews/job-applications.yml is the source of truth. Statuses the file
# uses today: interviewing | assessment | screening | applied | new_lead
# (rejected/withdrawn entries are closed and not shown as live work).
INTERVIEW_STATUS_ORDER = {
    "offer": 0,
    "onsite": 1,
    "interviewing": 2,
    "assessment": 3,
    "screening": 4,
    "applied": 5,
    "new_lead": 6,
    "waiting": 7,
}
INTERVIEW_STATUS_LABELS = {
    "offer": "Offer",
    "onsite": "Onsite",
    "interviewing": "Interviewing",
    "assessment": "Assessment",
    "screening": "Screening",
    "applied": "Applied",
    "new_lead": "New lead",
    "waiting": "Waiting",
}
INTERVIEW_STATUS_BADGES = {
    "offer": "badge-done",
    "onsite": "badge-p2",
    "interviewing": "badge-status-active",
    "assessment": "badge-status-pending",
    "screening": "badge-status-planned",
    "applied": "badge-status-upcoming",
    "new_lead": "badge",
    "waiting": "badge-status-waiting",
}
INTERVIEW_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
INTERVIEW_PRIORITY_BADGES = {
    "high": "badge-p1",
    "medium": "badge-p2",
    "low": "badge-p3",
}
# Everything except a bare lead has a live conversation to show first.
INTERVIEW_ACTIVE_STATUSES = ("offer", "onsite", "interviewing", "assessment", "screening", "applied")
# Closed threads stay in the file for history; Today must never point at one.
INTERVIEW_CLOSED_STATUSES = ("rejected", "withdrawn")
# Applied or interviewed, waiting to hear back: still tracked, but parked in
# its own card and never offered as Today's next action.
INTERVIEW_WAITING_STATUSES = ("waiting",)


def _iso_text(value) -> str:
    """YAML unquoted dates parse as date objects; JSON and the template want text."""
    if not value:
        return ""
    return value.isoformat() if isinstance(value, date) else str(value)


def _inter_date(value) -> date | None:
    """An ISO date from YAML, or None — never guess from a human sentence."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _workspace_href(recorded: str) -> str:
    """A servable link for a workspace-relative file, or "" if it is missing.

    Absolute paths and `..` are refused: the tracker stores workspace paths, and
    a link should never reach outside it.
    """
    if not recorded:
        return ""
    rel = Path(str(recorded))
    if rel.is_absolute() or ".." in rel.parts:
        return ""
    if not (config.WORKSPACE / rel).is_file():
        return ""
    return workspace_file_href(rel.as_posix())


def _resume_href(recorded: str) -> str:
    """A servable link for a resume recorded as a path under resume/."""
    if not recorded:
        return ""
    rel = Path(str(recorded))
    if rel.is_absolute() or ".." in rel.parts:
        return ""
    if not (config.WORKSPACE / "resume" / rel).is_file():
        return ""
    return workspace_file_href(f"resume/{rel.as_posix()}")


def _prep_label(path: str) -> str:
    """A role label for a prep file: the filename already says what it is."""
    name = Path(path).name
    lower = name.lower()
    if lower.startswith("jd-") or lower.startswith("jd_") or "job-description" in lower:
        return "Job description"
    if lower.startswith("prep"):
        return "Prep notes"
    return Path(path).stem.replace("-", " ").replace("_", " ").strip().capitalize()


def _prep_files(recorded) -> list[dict]:
    """Prep/JD files the tracker lists under `interview_prep:`.

    The tracker stores paths (interviews/Ground Up/prep.md). Only files that
    exist are linked; a recorded-but-missing path is reported, not invented.
    """
    if isinstance(recorded, str):
        recorded = [recorded]
    files = []
    for item in recorded or []:
        if not isinstance(item, str) or not item.strip():
            continue
        path = item.strip()
        files.append(
            {
                "path": path,
                "label": _prep_label(path),
                "href": _workspace_href(path),
            }
        )
    return files


def _relative_day(when: date, today: date) -> str:
    """"today" / "tomorrow" / "in N days" / "overdue N days" for a date."""
    delta = (when - today).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "tomorrow"
    if delta > 1:
        return f"in {delta} days"
    if delta == -1:
        return "overdue 1 day"
    return f"overdue {-delta} days"


def next_interview_action(rows: list[dict], today: date) -> dict | None:
    """The application whose next action is nearest — Today's one-tap entry.

    Soonest upcoming date wins; when every recorded date has passed, the most
    recent one is offered and flagged overdue. Nothing is invented: a row with
    no next-step date is simply not a candidate.
    """
    dated = [
        r
        for r in rows
        if r.get("next_step")
        and _inter_date(r["next_step"].get("date"))
        and r.get("status") not in INTERVIEW_CLOSED_STATUSES
        and r.get("status") not in INTERVIEW_WAITING_STATUSES
    ]
    if not dated:
        return None

    def sort_key(row: dict):
        when = _inter_date(row["next_step"].get("date"))
        return (
            when,
            INTERVIEW_STATUS_ORDER.get(row["status"], 9),
            INTERVIEW_PRIORITY_ORDER.get(row["priority"], 9),
        )

    upcoming = [r for r in dated if sort_key(r)[0] >= today]
    pick = min(upcoming, key=sort_key) if upcoming else max(dated, key=sort_key)
    when = _inter_date(pick["next_step"].get("date"))
    return {
        "company": pick["company"],
        "role": pick["role"],
        # company|role is the tracker's key and survives the pipe-free data here.
        "key": f"{pick['company']}|{pick['role']}",
        "date": when.isoformat(),
        "when": _relative_day(when, today),
        "overdue": when < today,
        "status_label": pick["status_label"],
        "task": pick["next_step"]["task"],
    }


def _interview_sheet_href(company: str, role: str) -> str:
    """A printable one-page sheet for one application."""
    query = urllib.parse.urlencode({"company": company, "role": role})
    return f"/interviews/sheet?{query}"


def build_interview_view(jobs_data: dict, today: date | None = None) -> dict:
    """Rows for the Interviews tab, read live from job-applications.yml.

    A row carries what the file actually records: status, priority, contacts,
    the latest timeline entry and the first next step. Missing fields stay
    blank rather than being filled in.
    """
    today = today or date.today()
    rows = []
    for entry in jobs_data.get("active_applications") or []:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "new_lead")
        priority = str(entry.get("priority") or "").casefold()
        timeline = entry.get("timeline") or []
        last = timeline[-1] if timeline else {}
        step = (entry.get("next_steps") or [{}])[0]
        step_date = _inter_date(step.get("date"))
        rows.append(
            {
                "company": entry.get("company") or "Company not recorded",
                "role": entry.get("role") or "Role not recorded",
                "status": status,
                "status_label": INTERVIEW_STATUS_LABELS.get(
                    status, status.replace("_", " ").capitalize()
                ),
                "status_badge": INTERVIEW_STATUS_BADGES.get(status, "badge"),
                "priority": priority,
                "priority_label": priority.capitalize() if priority else "",
                "priority_badge": INTERVIEW_PRIORITY_BADGES.get(priority, "badge"),
                "location": entry.get("location") or "",
                "salary": entry.get("salary_range") or "",
                "url": entry.get("job_url") or "",
                "resume": entry.get("resume") or "",
                "resume_href": _resume_href(entry.get("resume") or ""),
                "application_date": _iso_text(entry.get("application_date")),
                # Dashboard-owned blocks, each separate from the hand-written
                # job-fit `notes:` so the tracker's own prose survives edits.
                "notes": entry.get("interview_notes") or "",
                "questions": entry.get("interview_questions") or "",
                "preparation": entry.get("interview_preparation") or "",
                "fit_notes": str(entry.get("notes") or "").strip(),
                "prep_files": _prep_files(entry.get("interview_prep")),
                "contacts": [
                    {
                        "name": c.get("name") or "",
                        "role": c.get("role") or "",
                        "email": c.get("email") or "",
                    }
                    for c in (entry.get("contacts") or [])
                    if isinstance(c, dict)
                ],
                "history": [
                    {
                        "date": _iso_text(t.get("date")),
                        "stage": str(t.get("stage") or "").replace("_", " "),
                        "notes": t.get("notes") or "",
                    }
                    for t in timeline
                    if isinstance(t, dict)
                ][-4:][::-1],
                "last_event": (
                    {
                        "date": _iso_text(last.get("date")),
                        "stage": str(last.get("stage") or "").replace("_", " "),
                        "notes": last.get("notes") or "",
                    }
                    if last
                    else None
                ),
                "next_step": {
                    "task": step.get("task") or "",
                    "date": step_date.isoformat() if step_date else "",
                }
                if step.get("task")
                else None,
                "calendar_steps": [
                    {"index": i, "task": s.get("task") or "",
                     "schedule": {k: _iso_text(s[k]) for k in ("date", "start", "end", "timezone") if s.get(k)}}
                    for i, s in enumerate(entry.get("next_steps") or [])
                    if isinstance(s, dict) and s.get("task")
                ],
                "overdue": bool(step_date and step_date < today),
                "sheet_href": _interview_sheet_href(
                    entry.get("company") or "Company not recorded",
                    entry.get("role") or "Role not recorded",
                ),
            }
        )

    rows.sort(
        key=lambda r: (
            INTERVIEW_STATUS_ORDER.get(r["status"], 9),
            INTERVIEW_PRIORITY_ORDER.get(r["priority"], 9),
        )
    )
    # Closed threads (rejected/withdrawn) are kept for history but never shown
    # as live work: they get their own collapsed card and stay out of the counts.
    live = [r for r in rows if r["status"] not in INTERVIEW_CLOSED_STATUSES]
    closed = [r for r in rows if r["status"] in INTERVIEW_CLOSED_STATUSES]
    waiting = [r for r in live if r["status"] in INTERVIEW_WAITING_STATUSES]
    active = [r for r in live if r["status"] in INTERVIEW_ACTIVE_STATUSES]
    leads = [
        r
        for r in live
        if r["status"] not in INTERVIEW_ACTIVE_STATUSES
        and r["status"] not in INTERVIEW_WAITING_STATUSES
    ]
    # Newest signal first, so the most recent rejection reads at the top.
    closed.sort(
        key=lambda r: (
            r["last_event"]["date"] if r["last_event"] else "",
            r["company"],
        ),
        reverse=True,
    )
    return {
        "interview_rows": rows,
        "interview_active": active,
        "interview_leads": leads,
        "interview_waiting": waiting,
        "interview_closed": closed,
        "interview_counts": {
            "tracked": len(live),
            "active": len(active),
            "leads": len(leads),
            "waiting": len(waiting),
            "high": sum(1 for r in live if r["priority"] == "high"),
            "closed": len(closed),
        },
        "interview_active_statuses": list(INTERVIEW_ACTIVE_STATUSES),
        "interview_waiting_statuses": list(INTERVIEW_WAITING_STATUSES),
        "interview_statuses": [
            {
                "value": status,
                "label": INTERVIEW_STATUS_LABELS.get(
                    status, status.replace("_", " ").capitalize()
                ),
            }
            for status in ie.STATUSES
        ],
        "interview_priorities": [
            {"value": priority, "label": priority.capitalize()}
            for priority in ie.PRIORITIES
        ],
    }
