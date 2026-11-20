"""Today's "Now" directive: what to do at this moment, from the files.

Pure functions, no I/O. Inputs are the interview tracker (raw YAML for the
full timelines, plus the view rows the Interviews tab already builds), the
parsed routine.md view and the open TASKS.md items. Output is one directive
("Now") plus the next two ("Then"), each naming the routine.md rule it
serves. Nothing is invented: an application counts only when the tracker
has an `applied` timeline entry for it.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

# routine.md names the slots (workday mornings, afternoons, Saturday blocks,
# Sunday review) but not clock times; these boundaries are the dashboard's.
MORNING_START = time(6, 0)
AFTERNOON_START = time(13, 0)
EVENING_START = time(19, 0)

DEFAULT_DAY_GOAL = 2
DEFAULT_WEEK_GOAL = 10
FOLLOW_UP_DAYS = 7
PREP_WINDOW_DAYS = 2

LIVE_STAGES = ("screening", "assessment", "interviewing", "onsite", "offer")
AFTER_APPLY = ("applied", "waiting")
PRIORITY = {"high": 0, "medium": 1, "low": 2}


def _day(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def _key(company: str, role: str) -> str:
    return f"{company}|{role}"


def goals(routine: dict) -> tuple[int, int]:
    """Daily and weekly application targets as routine.md states them."""
    text = " ".join(
        [routine.get("context") or ""]
        + [f"{r.get('what', '')} {r.get('notes', '')}" for r in routine.get("rhythm") or []]
    )
    day = re.search(r"(\d+)\s+applications?\s*/\s*day", text)
    week = re.search(r"(\d+)\s+applications?\s+a\s+week", text)
    return (
        int(day.group(1)) if day else DEFAULT_DAY_GOAL,
        int(week.group(1)) if week else DEFAULT_WEEK_GOAL,
    )


def application_log(jobs_data: dict) -> dict[str, list[date]]:
    """Every `applied` timeline date per application key."""
    log: dict[str, list[date]] = {}
    for entry in (jobs_data or {}).get("active_applications") or []:
        if not isinstance(entry, dict):
            continue
        key = _key(entry.get("company") or "", entry.get("role") or "")
        for item in entry.get("timeline") or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("stage") or "").strip().casefold() == "applied":
                when = _day(item.get("date"))
                if when:
                    log.setdefault(key, []).append(when)
    return log


def application_counts(log: dict[str, list[date]], today: date) -> dict:
    monday = today - timedelta(days=today.weekday())
    dates = [d for ds in log.values() for d in ds]
    return {
        "today": sum(d == today for d in dates),
        "week": sum(monday <= d <= today for d in dates),
    }


def block(now: datetime) -> tuple[str, datetime]:
    """The routine slot the clock is in, and when it ends."""
    today, clock = now.date(), now.time()
    midnight = datetime.combine(today + timedelta(days=1), time(0, 0))
    if clock < MORNING_START:
        return "night", datetime.combine(today, MORNING_START)
    if clock >= EVENING_START:
        return "evening", midnight
    morning = clock < AFTERNOON_START
    ends = datetime.combine(today, AFTERNOON_START if morning else EVENING_START)
    weekday = today.weekday()
    if weekday < 5:
        return ("workday" if morning else "afternoon"), ends
    if weekday == 5:
        return ("project" if morning else "devops"), ends
    return "review", ends


def _rule(routine: dict, word: str, fallback: str) -> str:
    """The routine.md rule that mentions `word`, as the reason for an action."""
    for rule in routine.get("rules") or []:
        if word.casefold() in rule.casefold():
            return rule
    return fallback


def _prep_items(rows: list[dict], today: date, routine: dict) -> list[dict]:
    why = _rule(routine, "screen", "Every booked screen gets written prep before the call.")
    items = []
    for r in rows:
        step = r.get("next_step") or {}
        when = _day(step.get("date"))
        if r["status"] not in LIVE_STAGES or not when:
            continue
        if today <= when <= today + timedelta(days=PREP_WINDOW_DAYS):
            items.append(
                {
                    "kind": "prep",
                    "verb": "Prep",
                    "title": f"{r['company']} — {r['status_label'].lower()} {_when(when, today)}",
                    "detail": step.get("task") or r["role"],
                    "why": why,
                    "tone": "signal",
                    "key": _key(r["company"], r["role"]),
                    "sort": (when, PRIORITY.get(r.get("priority"), 3)),
                    "actions": _row_actions(r, interview_mode=True),
                }
            )
    return sorted(items, key=lambda i: i["sort"])


def _overdue_items(rows: list[dict], today: date, routine: dict) -> list[dict]:
    why = _rule(routine, "same-day", "Same-day tracking: every step goes in the tracker the day it happens.")
    items = []
    for r in rows:
        step = r.get("next_step") or {}
        when = _day(step.get("date"))
        if r["status"] in LIVE_STAGES and when and when < today:
            items.append(
                {
                    "kind": "overdue",
                    "verb": "Act",
                    "title": f"{r['company']} — {r['status_label'].lower()}",
                    "detail": f"{step.get('task')} (due {when.isoformat()}, {_when(when, today)})",
                    "why": why,
                    "tone": "warn",
                    "key": _key(r["company"], r["role"]),
                    "sort": (when,),
                    "actions": _row_actions(r, interview_mode=True),
                }
            )
    return sorted(items, key=lambda i: i["sort"])


def lead_queue(rows: list[dict], log: dict[str, list[date]]) -> list[dict]:
    """New leads not yet applied to: priority, then a tailored CV, then a
    posting link, then the oldest target date; tracker order breaks ties."""
    leads = [
        (i, r)
        for i, r in enumerate(rows)
        if r["status"] == "new_lead" and _key(r["company"], r["role"]) not in log
    ]

    def rank(pair):
        i, r = pair
        when = _day((r.get("next_step") or {}).get("date"))
        return (
            PRIORITY.get(r.get("priority"), 3),
            0 if (r.get("agent") or {}).get("tailored") else 1,
            0 if r.get("url") else 1,
            when or date.max,
            i,
        )

    return [r for _, r in sorted(leads, key=rank)]


def _apply_item(lead: dict, counts: dict, day_goal: int, routine: dict, late: bool) -> dict:
    why = _rule(routine, "job search comes first", "The job search comes first.")
    detail = lead["role"]
    if lead.get("location"):
        detail += f" · {lead['location']}"
    tailored = (lead.get("agent") or {}).get("tailored")
    detail += " · tailored CV ready" if tailored else " · standard résumé variant"
    if late:
        detail += f" · morning slot passed, {day_goal - counts['today']} still to send today"
    return {
        "kind": "apply",
        "verb": "Apply",
        "title": lead["company"],
        "detail": detail,
        "why": why,
        "tone": "signal",
        "key": _key(lead["company"], lead["role"]),
        "actions": [
            {"label": "Mark applied", "mark_applied": _key(lead["company"], lead["role"]), "primary": True},
            *_row_actions(lead, interview_mode=False),
        ],
    }


def _follow_up_items(rows: list[dict], log: dict[str, list[date]], today: date, routine: dict) -> list[dict]:
    why = _rule(routine, "same-day", "Same-day tracking: every step goes in the tracker the day it happens.")
    items = []
    for r in rows:
        if r["status"] not in AFTER_APPLY:
            continue
        step = r.get("next_step") or {}
        due = _day(step.get("date"))
        applied = max(log.get(_key(r["company"], r["role"]), []), default=None)
        if due is None and applied:
            due = applied + timedelta(days=FOLLOW_UP_DAYS)
        if due and due <= today:
            since = applied or _day((r.get("last_event") or {}).get("date"))
            parts = [f"No reply since {since.isoformat()}" if since else "No reply recorded"]
            task = step.get("task") or ""
            if task and task != "Follow up if no reply":
                parts.append(f"recorded next step: {_short(task)}")
            parts.append(f"due {_when(due, today)}")
            items.append(
                {
                    "kind": "follow_up",
                    "verb": "Follow up",
                    "title": r["company"],
                    "detail": " · ".join(parts),
                    "why": why,
                    "tone": "warn" if due < today else "signal",
                    "key": _key(r["company"], r["role"]),
                    "sort": (due,),
                    "actions": _row_actions(r, interview_mode=False),
                }
            )
    return sorted(items, key=lambda i: i["sort"])


def _short(text: str, limit: int = 90) -> str:
    """One line of a long tracker note, cut at a word."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def _task_item(open_tasks: list[dict], lane: str, verb: str, title: str, why: str) -> dict:
    task = next((t for t in open_tasks if lane in t["cat"].casefold()), None)
    return {
        "kind": "block",
        "verb": verb,
        "title": title,
        "detail": task["text"] if task else f"No open {title} task in TASKS.md — pick one first",
        "detail_md": bool(task),
        "why": why,
        "tone": "calm",
        "actions": [{"label": "Tasks", "href": "#tasks"}],
    }


def _row_actions(r: dict, interview_mode: bool) -> list[dict]:
    actions = []
    if interview_mode:
        actions.append({"label": "Interview mode", "interview_open": _key(r["company"], r["role"])})
    if r.get("url"):
        actions.append({"label": "Posting", "href": r["url"], "new_tab": True})
    tailored = (r.get("agent") or {}).get("tailored")
    if tailored:
        actions.append({"label": "Tailored CV", "file": tailored})
    if r.get("sheet_href"):
        actions.append({"label": "Prep sheet", "href": r["sheet_href"], "new_tab": True})
    return actions


def _when(when: date, today: date) -> str:
    delta = (when - today).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "tomorrow"
    if delta > 1:
        return f"in {delta} days"
    return "yesterday" if delta == -1 else f"{-delta} days ago"


def build_now(
    now: datetime,
    jobs_data: dict,
    rows: list[dict],
    routine: dict,
    open_tasks: list[dict],
) -> dict:
    """One directive for this moment plus the next two, with the week's count."""
    today = now.date()
    day_goal, week_goal = goals(routine)
    log = application_log(jobs_data)
    counts = application_counts(log, today)
    slot, until = block(now)
    rows = [r for r in rows if r.get("status") not in ("rejected", "withdrawn")]

    urgent = _prep_items(rows, today, routine) + _overdue_items(rows, today, routine)
    follow_ups = _follow_up_items(rows, log, today, routine)
    leads = lead_queue(rows, log)
    short = max(day_goal - counts["today"], 0)
    applies = [
        _apply_item(lead, counts, day_goal, routine, late=slot == "afternoon")
        for lead in leads[:short]
    ]

    if slot == "workday":
        flow = applies + follow_ups
    elif slot == "afternoon":
        freelance = {
            "kind": "block",
            "verb": "Freelance",
            "title": "Income block",
            "detail": "Fixed-scope packages first, hourly gigs second; log cash received and its date.",
            "why": _rule(routine, "freelance", "Freelance is cash, not the career."),
            "tone": "calm",
            "actions": [{"label": "Lane A services", "file": "freelance/lane-a-services.md"}],
        }
        flow = applies + follow_ups + [freelance]
    elif slot == "project":
        flow = [
            _task_item(open_tasks, "salsasegura", "Build", "SalsaSegura.com",
                       _rule(routine, "builds", "Builds, not courses.")),
            *follow_ups,
        ]
    elif slot == "devops":
        flow = [
            _task_item(open_tasks, "devops", "Build", "DevOps automation",
                       _rule(routine, "builds", "Builds, not courses.")),
            *follow_ups,
        ]
    elif slot == "review":
        review = next((i for i in routine.get("review") or [] if not i.get("done")), None)
        flow = [
            {
                "kind": "review",
                "verb": "Review",
                "title": "Weekly review",
                "detail": review["display_text"] if review else "Every review item is checked.",
                "why": f"{counts['week']} of {week_goal} applications logged this week.",
                "tone": "calm",
                # Scroll, never a hash link: the hash selects tabs.
                "actions": [{"label": "Open the review", "scroll": "routineTitle"}] if review else [],
            },
            *follow_ups,
        ]
    else:
        flow = []

    items = urgent + flow
    if not items:
        tomorrow = (
            f"workday, {day_goal} applications first thing"
            if (today + timedelta(days=1)).weekday() < 5
            else "weekend build block"
        )
        items = [
            {
                "kind": "rest",
                "verb": "Rest",
                "title": "Done for today" if slot in ("evening", "night") else "Nothing due right now",
                "detail": f"{counts['today']} of {day_goal} applications today · next: {tomorrow}.",
                "why": _rule(routine, "rest", "Rest is productive."),
                "tone": "calm",
                "actions": [],
            }
        ]
    for item in items:
        item.pop("sort", None)
    return {
        "now": items[0],
        "then": items[1:3],
        "slot": slot,
        "until": until.isoformat(timespec="minutes"),
        "as_of": now.strftime("%H:%M"),
        "counts": {**counts, "day_goal": day_goal, "week_goal": week_goal},
        "leads_left": len(leads),
    }
