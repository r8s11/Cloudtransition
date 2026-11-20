"""Interview dashboard: rows built from interviews/job-applications.yml.

These tests pin the mapping from the tracker's fields (status, priority,
timeline, next steps) to what the Interviews tab shows, plus the tab wiring.
No real application data is required.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.interview_view import _prep_files, build_interview_view, next_interview_action  # noqa: E402
from core.today import command_centre  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def entry(**overrides) -> dict:
    base = {
        "company": "Acme",
        "role": "IT Support Engineer",
        "status": "new_lead",
        "priority": "low",
    }
    base.update(overrides)
    return base


def test_row_maps_status_contact_timeline_and_next_step():
    data = {
        "active_applications": [
            entry(
                status="interviewing",
                priority="high",
                location="New York, NY",
                salary_range="$100-120K",
                job_url="https://example.com/job",
                contacts=[{"name": "Heather", "role": "Recruiter"}],
                timeline=[
                    {"date": "2026-09-01", "stage": "recruiter_screen", "notes": "first"},
                    {"date": "2026-11-02", "stage": "hiring_manager_interview", "notes": "45 min"},
                ],
                next_steps=[{"task": "Follow up with Heather", "date": "2026-11-01"}],
            )
        ]
    }
    view = build_interview_view(data, date(2026, 11, 6))
    row = view["interview_rows"][0]

    assert row["status_label"] == "Interviewing"
    assert row["status_badge"] == "badge-status-active"
    assert row["priority_badge"] == "badge-p1"
    assert row["contacts"] == [{"name": "Heather", "role": "Recruiter", "email": ""}]
    # The last timeline entry is the signal, not the first.
    assert row["last_event"]["date"] == "2026-11-02"
    assert row["last_event"]["stage"] == "hiring manager interview"
    assert row["next_step"] == {"task": "Follow up with Heather", "date": "2026-11-01"}
    assert row["overdue"] is True
    assert view["interview_counts"] == {
        "tracked": 1,
        "active": 1,
        "leads": 0,
        "waiting": 0,
        "high": 1,
        "closed": 0,
    }


def test_missing_fields_stay_blank_and_do_not_crash():
    view = build_interview_view({"active_applications": [entry()]}, date(2026, 11, 6))
    row = view["interview_rows"][0]

    assert row["location"] == ""
    assert row["salary"] == ""
    assert row["url"] == ""
    assert row["contacts"] == []
    assert row["last_event"] is None
    assert row["next_step"] is None
    assert row["overdue"] is False
    assert view["interview_counts"]["leads"] == 1


def test_sorting_puts_closest_stage_first_and_priority_breaks_ties():
    data = {
        "active_applications": [
            entry(company="Lead", status="new_lead", priority="high"),
            entry(company="Screen", status="screening", priority="low"),
            entry(company="Offer", status="offer", priority="low"),
            entry(company="Medium interview", status="interviewing", priority="medium"),
            entry(company="High interview", status="interviewing", priority="high"),
        ]
    }
    view = build_interview_view(data, date(2026, 11, 6))
    assert [r["company"] for r in view["interview_rows"]] == [
        "Offer",
        "High interview",
        "Medium interview",
        "Screen",
        "Lead",
    ]
    assert [r["company"] for r in view["interview_leads"]] == ["Lead"]


def test_unknown_status_gets_a_readable_fallback():
    view = build_interview_view(
        {"active_applications": [entry(status="take_home")]}, date(2026, 11, 6)
    )
    row = view["interview_rows"][0]
    assert row["status_label"] == "Take home"
    assert row["status_badge"] == "badge"


def test_empty_and_malformed_sources_return_an_empty_view():
    for data in ({}, {"active_applications": None}, {"active_applications": [None]}):
        view = build_interview_view(data, date(2026, 11, 6))
        assert view["interview_rows"] == []
        assert view["interview_counts"]["tracked"] == 0


def test_interviews_tab_is_wired_into_the_shell():
    index = (ROOT / "templates" / "index.html").read_text()
    page = (ROOT / "templates" / "pages" / "interviews.html").read_text()
    assert '("interviews", "Interviews")' in index
    assert 'include "pages/interviews.html"' in index
    assert 'id="page-interviews"' in page
    assert 'aria-labelledby="tab-interviews"' in page


def test_interview_mode_dialog_is_wired():
    index = (ROOT / "templates" / "index.html").read_text()
    page = (ROOT / "templates" / "pages" / "interviews.html").read_text()
    script = (ROOT / "static" / "interviews.js").read_text()
    # The dialog lives outside the tab panels, next to the run-output dialog.
    assert 'id="interviewMode"' in index
    for target in (
        "interviewModeTitle",
        "interviewModeContacts",
        "interviewModeFiles",
        "interviewModeFit",
        "interviewModeHistory",
        "interviewModeQuestions",
        "interviewModePreparation",
        "interviewModeNotes",
    ):
        assert f'id="{target}"' in index
    # Each row opens it; each editable block names the field it writes.
    assert "data-interview-mode" in page
    for field in ("interview_questions", "interview_preparation", "interview_notes"):
        assert f'data-interview-save="{field}"' in index
    assert "/api/interviews/detail" in script
    assert "/api/interviews/text" in script


def test_row_maps_preparation_prep_files_fit_notes_and_history():
    data = {
        "active_applications": [
            entry(
                status="screening",
                priority="high",
                resume="tailored/2026-10/resume.pdf",
                job_url="https://example.com/job",
                interview_questions="What does success look like?",
                interview_preparation="Outage story",
                interview_notes="They asked about DNS.",
                interview_prep=["interviews/Ground Up/prep.md"],
                notes="Strong JD match.\n",
                contacts=[{"name": "Ada", "role": "Recruiter", "email": "ada@example.com"}],
                timeline=[
                    {"date": "2026-10-01", "stage": "recruiter_screen", "notes": "first"},
                    {"date": "2026-11-02", "stage": "hiring_manager_interview", "notes": "45 min"},
                ],
            )
        ]
    }
    row = build_interview_view(data, date(2026, 11, 6))["interview_rows"][0]

    assert row["questions"] == "What does success look like?"
    assert row["preparation"] == "Outage story"
    assert row["notes"] == "They asked about DNS."
    assert row["fit_notes"] == "Strong JD match."
    assert row["contacts"][0]["email"] == "ada@example.com"
    # Newest signal first, for the "what happened so far" list.
    assert [h["date"] for h in row["history"]] == ["2026-11-02", "2026-10-01"]
    assert row["history"][0]["stage"] == "hiring manager interview"
    # A recorded file that is not on disk is listed but not linked, never hidden.
    assert row["prep_files"] == [
        {
            "path": "interviews/Ground Up/prep.md",
            "label": "Prep notes",
            "href": "/workspace-file/interviews/Ground%20Up/prep.md",
        }
    ]
    # The resume is under resume/, so an un-tailored path resolves the same way.
    assert row["resume_href"].startswith("/workspace-file/resume/") or row["resume_href"] == ""


def test_prep_files_accepts_a_bare_string_and_skips_junk():
    assert [f["label"] for f in _prep_files("interviews/x/prep.md")] == ["Prep notes"]
    assert _prep_files(None) == []
    assert [f["label"] for f in _prep_files([None, "", "  ", "a/b.md"])] == ["B"]
    assert [f["label"] for f in _prep_files(["a/jd-senior-it.md", "a/company-notes.md"])] == [
        "Job description",
        "Company notes",
    ]


def _dated(company, status, priority, task, due):
    return entry(
        company=company,
        status=status,
        priority=priority,
        next_steps=[{"task": task, "date": due}],
    )


def test_next_interview_action_picks_the_soonest_upcoming_date():
    rows = build_interview_view(
        {
            "active_applications": [
                _dated("Later", "screening", "high", "Second", "2026-11-09"),
                _dated("Today", "applied", "low", "First", "2026-11-06"),
                _dated("Past", "screening", "high", "Old", "2026-11-01"),
            ]
        },
        date(2026, 11, 6),
    )["interview_rows"]
    action = next_interview_action(rows, date(2026, 11, 6))
    assert action["company"] == "Today"
    assert action["when"] == "today"
    assert action["overdue"] is False
    assert action["task"] == "First"
    assert action["key"] == "Today|IT Support Engineer"


def test_next_interview_action_falls_back_to_the_most_recent_overdue():
    rows = build_interview_view(
        {
            "active_applications": [
                _dated("Older", "screening", "high", "Old", "2026-10-01"),
                _dated("Recent", "screening", "low", "Newer", "2026-11-01"),
            ]
        },
        date(2026, 11, 6),
    )["interview_rows"]
    action = next_interview_action(rows, date(2026, 11, 6))
    assert action["company"] == "Recent"
    assert action["overdue"] is True
    assert action["when"] == "overdue 5 days"


def test_next_interview_action_without_dates_is_none():
    rows = build_interview_view(
        {"active_applications": [entry(company="No date", status="screening")]},
        date(2026, 11, 6),
    )["interview_rows"]
    assert next_interview_action(rows, date(2026, 11, 6)) is None
    assert next_interview_action([], date(2026, 11, 6)) is None


def test_today_daily_list_starts_with_the_interview_action():
    centre = command_centre(
        {"total_active": 0},
        {"today_blocks": [], "inbox_items": []},
        0,
        {
            "company": "Acme",
            "role": "IT Support",
            "key": "Acme|IT Support",
            "date": "2026-11-06",
            "when": "today",
            "overdue": False,
            "status_label": "Screening",
            "task": "Call them",
        },
    )
    first = centre["daily"][0]
    assert first["label"] == "Interview mode"
    assert first["href"] == "#interviews"
    assert first["interview_key"] == "Acme|IT Support"
    assert "today" in first["value"]


def test_today_page_and_script_wire_the_quick_action():
    today = (ROOT / "templates" / "pages" / "today.html").read_text()
    script = (ROOT / "static" / "interviews.js").read_text()
    assert "data-interview-open" in today
    assert "data-interview-open" in script
    assert "/api/interviews/detail" in script


def test_rows_carry_a_sheet_href():
    row = build_interview_view(
        {"active_applications": [entry(company="A B", role="R/S")]}, date(2026, 11, 6)
    )["interview_rows"][0]
    assert row["sheet_href"] == "/interviews/sheet?company=A+B&role=R%2FS"


def test_next_interview_action_ignores_closed_threads():
    rows = build_interview_view(
        {
            "active_applications": [
                _dated("Closed", "rejected", "high", "Dead follow-up", "2026-11-07"),
                _dated("Live", "screening", "low", "Still open", "2026-11-20"),
            ]
        },
        date(2026, 11, 6),
    )["interview_rows"]
    action = next_interview_action(rows, date(2026, 11, 6))
    assert action["company"] == "Live"


def test_next_interview_action_is_none_when_only_closed_threads_have_dates():
    rows = build_interview_view(
        {
            "active_applications": [
                _dated("Withdrawn", "withdrawn", "high", "Nope", "2026-11-01"),
            ]
        },
        date(2026, 11, 6),
    )["interview_rows"]
    assert next_interview_action(rows, date(2026, 11, 6)) is None


def test_closed_threads_are_split_out_of_live_cards_and_counts():
    data = {
        "active_applications": [
            entry(company="Live", status="screening", priority="high"),
            entry(company="Lead", status="new_lead", priority="low"),
            entry(
                company="Dead",
                status="rejected",
                priority="high",
                timeline=[{"date": "2026-10-20", "stage": "rejected", "notes": "no"}],
            ),
            entry(company="Gone", status="withdrawn", priority="low"),
        ]
    }
    view = build_interview_view(data, date(2026, 11, 6))
    assert [r["company"] for r in view["interview_active"]] == ["Live"]
    assert [r["company"] for r in view["interview_leads"]] == ["Lead"]
    assert [r["company"] for r in view["interview_closed"]] == ["Dead", "Gone"]
    # A closed thread is neither a card row nor counted as work.
    assert view["interview_counts"] == {
        "tracked": 2,
        "active": 1,
        "leads": 1,
        "waiting": 0,
        "high": 1,
        "closed": 2,
    }


def test_closed_threads_sort_newest_signal_first():
    data = {
        "active_applications": [
            entry(
                company="Old rejection",
                status="rejected",
                timeline=[{"date": "2026-05-01", "stage": "rejected"}],
            ),
            entry(
                company="Recent rejection",
                status="rejected",
                timeline=[{"date": "2026-09-30", "stage": "rejected"}],
            ),
            entry(company="No signal", status="withdrawn"),
        ]
    }
    closed = build_interview_view(data, date(2026, 11, 6))["interview_closed"]
    assert [r["company"] for r in closed] == [
        "Recent rejection",
        "Old rejection",
        "No signal",
    ]


def test_interviews_page_renders_a_collapsed_closed_card():
    page = (ROOT / "templates" / "pages" / "interviews.html").read_text()
    script = (ROOT / "static" / "interviews.js").read_text()
    assert "Closed threads" in page
    assert 'data-interview-list-closed' in page
    assert 'data-interview-closed="rejected,withdrawn"' in page
    assert "<details class=\"interview-closed\">" in page
    # A status change moves the row out of (or back into) the live cards.
    assert "closedStatuses" in script
    assert "data-interview-list-closed" in script
