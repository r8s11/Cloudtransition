"""Today's Now directive (core/now.py) and the one-tap Mark applied write."""

from __future__ import annotations

import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as module  # noqa: E402
from core import config  # noqa: E402
from core import now  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
CSRF = {"X-Requested-With": "XMLHttpRequest"}
ROUTINE = {
    "context": "Job search is open and full-time: 10 applications a week.",
    "rhythm": [{"what": "Job search: 2 applications/day", "notes": ""}],
    "rules": [
        "The job search comes first. Ten applications a week.",
        "Same-day tracking. Every application goes in the tracker the day it happens.",
        "The screen stage is the known weak point. Every booked screen gets written prep.",
        "Rest is productive.",
    ],
    "review": [{"display_text": "Applications sent this week", "done": False}],
}
WED = date(2026, 11, 18)


def row(company, status="new_lead", priority="medium", step=None, url="", tailored=""):
    return {
        "company": company,
        "role": "IT Support",
        "status": status,
        "status_label": status.replace("_", " ").capitalize(),
        "priority": priority,
        "url": url,
        "location": "",
        "sheet_href": "",
        "agent": {"tailored": tailored},
        "next_step": {"task": step[0], "date": step[1].isoformat()} if step else None,
    }


def jobs(*applied):
    """Raw tracker data: one entry per (company, applied date)."""
    return {
        "active_applications": [
            {"company": c, "role": "IT Support", "timeline": [{"date": d, "stage": "applied"}]}
            for c, d in applied
        ]
    }


def at(day: date, hour: int) -> datetime:
    return datetime.combine(day, datetime.min.time()).replace(hour=hour)


def test_goals_come_from_routine_text():
    assert now.goals(ROUTINE) == (2, 10)
    assert now.goals({}) == (now.DEFAULT_DAY_GOAL, now.DEFAULT_WEEK_GOAL)


def test_weekday_morning_says_apply_to_the_best_unapplied_lead():
    rows = [
        row("Low Co", priority="low", url="https://x"),
        row("Applied Co", priority="high", url="https://x"),
        row("Tailored Co", priority="high", url="https://x", tailored="cv.md"),
    ]
    plan = now.build_now(at(WED, 9), jobs(("Applied Co", WED - timedelta(days=1))), rows, ROUTINE, [])
    assert plan["now"]["verb"] == "Apply"
    assert plan["now"]["title"] == "Tailored Co"  # high priority, CV ready; Applied Co already sent
    assert plan["now"]["actions"][0]["mark_applied"] == "Tailored Co|IT Support"
    assert plan["counts"] == {"today": 0, "week": 1, "day_goal": 2, "week_goal": 10}
    assert plan["leads_left"] == 2


def test_quota_met_moves_on_to_due_follow_ups():
    rows = [
        row("Fresh", url="https://x"),
        row("Quiet Co", status="waiting", step=("Follow up if no reply", WED - timedelta(days=2))),
    ]
    log = jobs(("A", WED), ("B", WED))
    plan = now.build_now(at(WED, 10), log, rows, ROUTINE, [])
    assert plan["now"]["verb"] == "Follow up"
    assert plan["now"]["title"] == "Quiet Co"
    assert plan["now"]["tone"] == "warn"  # due two days ago


def test_follow_up_falls_back_to_a_week_after_applying():
    rows = [row("Silent", status="waiting")]
    plan = now.build_now(at(WED, 10), jobs(("Silent", WED - timedelta(days=8)), ("A", WED), ("B", WED)), rows, ROUTINE, [])
    assert plan["now"]["verb"] == "Follow up"
    assert "No reply since" in plan["now"]["detail"]


def test_a_booked_screen_outranks_applying():
    rows = [
        row("Lead", url="https://x"),
        row("Screen Co", status="screening", step=("Phone screen", WED + timedelta(days=1))),
    ]
    plan = now.build_now(at(WED, 9), jobs(), rows, ROUTINE, [])
    assert plan["now"]["verb"] == "Prep"
    assert plan["now"]["title"].startswith("Screen Co")
    assert plan["then"][0]["verb"] == "Apply"


def test_afternoon_with_quota_short_still_applies_then_freelance():
    rows = [row("Lead", url="https://x")]
    plan = now.build_now(at(WED, 15), jobs(("A", WED)), rows, ROUTINE, [])
    assert plan["now"]["verb"] == "Apply"
    assert "1 still to send today" in plan["now"]["detail"]
    assert plan["then"][-1]["verb"] == "Freelance"


def test_saturday_morning_is_the_salsasegura_build():
    sat = date(2026, 11, 21)
    tasks = [{"cat": "Project — SalsaSegura.com", "text": "Ship the search filter"}]
    plan = now.build_now(at(sat, 10), jobs(), [row("Lead")], ROUTINE, tasks)
    assert (plan["now"]["verb"], plan["now"]["detail"]) == ("Build", "Ship the search filter")


def test_sunday_is_the_weekly_review_with_the_week_count():
    sun = date(2026, 11, 22)
    plan = now.build_now(at(sun, 10), jobs(("A", WED)), [], ROUTINE, [])
    assert plan["now"]["verb"] == "Review"
    assert plan["now"]["why"].startswith("1 of 10")


def test_evening_with_nothing_urgent_is_rest_and_closed_rows_never_show():
    rows = [row("Gone", status="rejected", step=("Thank-you note", WED - timedelta(days=1)))]
    plan = now.build_now(at(WED, 21), jobs(), rows, ROUTINE, [])
    assert plan["now"]["verb"] == "Rest"
    assert plan["until"] == "2026-11-19T00:00"


@pytest.fixture()
def tracker(tmp_path, monkeypatch):
    target = tmp_path / "job-applications.yml"
    shutil.copyfile(ROOT / "interviews" / "job-applications.yml", target)
    monkeypatch.setattr(config, "JOBS_FILE", target)
    return target


def apps(target: Path) -> list[dict]:
    return yaml.safe_load(target.read_text())["active_applications"]


def test_mark_applied_logs_parks_and_schedules_in_one_write(tracker):
    lead = next(a for a in apps(tracker) if a.get("status") == "new_lead")
    with TestClient(module.app) as client:
        r = client.post("/api/interviews/applied", headers=CSRF, json={"company": lead["company"], "role": lead["role"]})
        again = client.post("/api/interviews/applied", headers=CSRF, json={"company": lead["company"], "role": lead["role"]})
    assert r.status_code == 200, r.text
    saved = next(a for a in apps(tracker) if a["company"] == lead["company"] and a["role"] == lead["role"])
    assert saved["status"] == "waiting"
    assert str(saved["timeline"][-1]["date"]) == date.today().isoformat()
    assert saved["timeline"][-1]["stage"] == "applied"
    assert saved["next_steps"][0]["task"] == "Follow up if no reply"
    assert str(saved["next_steps"][0]["date"]) == (date.today() + timedelta(days=7)).isoformat()
    # A second tap must not log a second application.
    assert again.status_code == 400
    before = sum(t.get("stage") == "applied" for t in lead.get("timeline") or [])
    assert sum(t.get("stage") == "applied" for t in saved["timeline"]) == before + 1


def test_mark_applied_requires_the_csrf_header(tracker):
    lead = next(a for a in apps(tracker) if a.get("status") == "new_lead")
    with TestClient(module.app) as client:
        r = client.post("/api/interviews/applied", json={"company": lead["company"], "role": lead["role"]})
    assert r.status_code == 403
