"""Waiting status: parked in its own bottom card, tracked but not active work.

Every test runs against a temporary tracker; the real
interviews/job-applications.yml is never written.
"""

from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest  # noqa: E402
import yaml  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as module  # noqa: E402

CSRF = {"X-Requested-With": "XMLHttpRequest"}
TODAY = date(2026, 11, 16)

APPLICATIONS = [
    {"company": "Talks", "role": "IT Engineer", "status": "interviewing", "priority": "high"},
    {
        "company": "Sent",
        "role": "Support Engineer",
        "status": "applied",
        "priority": "medium",
        "job_url": "https://example.com/sent",
    },
    {"company": "Fresh", "role": "Help Desk", "status": "new_lead", "priority": "low"},
    {
        "company": "Parked",
        "role": "Systems Admin",
        "status": "waiting",
        "priority": "medium",
        "job_url": "https://example.com/parked",
    },
    {"company": "Gone", "role": "Desktop Support", "status": "rejected", "priority": "low"},
]


def write_tracker(path: Path, applications: list[dict]) -> Path:
    lines = ["active_applications:"]
    for a in applications:
        first = True
        for key, value in a.items():
            lines.append(f"  {'- ' if first else '  '}{key}: \"{value}\"")
            first = False
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture()
def tracker(tmp_path, monkeypatch):
    target = write_tracker(tmp_path / "job-applications.yml", APPLICATIONS)
    monkeypatch.setattr(module, "JOBS_FILE", target)
    return target


def view_of(applications=APPLICATIONS) -> dict:
    return module.build_interview_view({"active_applications": applications}, TODAY)


def set_status(client, company: str, role: str, value: str):
    return client.post(
        "/api/interviews/field",
        headers=CSRF,
        json={"company": company, "role": role, "field": "status", "value": value},
    )


def interviews_page(client) -> str:
    html = client.get("/").text
    start = html.index('id="page-interviews"')
    end = html.index('class="page"', start)
    return html[start:end]


def entry_html(page: str, company: str) -> str:
    start = page.index(f'data-interview data-company="{company}"')
    nxt = page.find('class="interview-entry"', start)
    return page[start : nxt if nxt != -1 else len(page)]


def test_status_endpoint_accepts_waiting(tracker):
    before = tracker.read_text().splitlines()
    with TestClient(module.app) as client:
        r = set_status(client, "Sent", "Support Engineer", "waiting")
    assert r.status_code == 200, r.text
    row = r.json()["row"]
    assert row["status"] == "waiting"
    assert row["status_label"] == "Waiting"
    after = tracker.read_text().splitlines()
    changed = [(b, a) for b, a in zip(before, after) if b != a]
    assert len(before) == len(after)
    assert changed == [('    status: "applied"', '    status: "waiting"')]


def test_waiting_option_is_offered(tracker):
    with TestClient(module.app) as client:
        page = interviews_page(client)
    add_form = page[page.index('id="interviewAddForm"') : page.index("</form>", page.index('id="interviewAddForm"'))]
    row_select = entry_html(page, "Talks")
    row_select = row_select[row_select.index('data-interview-select="status"') :]
    row_select = row_select[: row_select.index("</select>")]
    for block in (add_form, row_select):
        values = re.findall(r'<option value="([a-z_]+)"', block)
        assert '<option value="waiting"' in block
        assert re.search(r'<option value="waiting"[^>]*>Waiting</option>', block)
        assert values.index("offer") < values.index("waiting") < values.index("rejected")


def test_waiting_rows_get_their_own_bottom_card(tracker):
    view = view_of()
    assert [r["company"] for r in view["interview_waiting"]] == ["Parked"]
    assert sorted(r["company"] for r in view["interview_active"]) == ["Sent", "Talks"]
    assert [r["company"] for r in view["interview_leads"]] == ["Fresh"]

    with TestClient(module.app) as client:
        page = interviews_page(client)
    waiting_at = page.index('data-interview-section="waiting"')
    assert page.index('data-interview-section="leads"') < waiting_at
    assert page.index('id="interviewAgents"') < waiting_at
    closed_at = page.index('<details class="interview-closed">')
    assert waiting_at < closed_at
    card = page[waiting_at:closed_at]
    assert re.search(r"Waiting\s*<span[^>]*data-interview-count=\"waiting\"[^>]*>1</span>", card)
    assert "Applied or interviewed; waiting to hear back. Not counted as active work." in card
    assert 'data-company="Parked"' in card
    assert 'data-company="Sent"' not in card


def test_waiting_round_trip_restores_counts(tracker):
    with TestClient(module.app) as client:
        start = set_status(client, "Sent", "Support Engineer", "applied").json()["counts"]
        parked = set_status(client, "Sent", "Support Engineer", "waiting").json()["counts"]
        back = set_status(client, "Sent", "Support Engineer", "interviewing")
    assert parked["active"] == start["active"] - 1
    assert parked["waiting"] == start["waiting"] + 1
    assert parked["tracked"] == start["tracked"]
    body = back.json()
    assert body["row"]["status"] == "interviewing"
    assert body["counts"] == start
    apps = yaml.safe_load(tracker.read_text())["active_applications"]
    assert next(a for a in apps if a["company"] == "Sent")["status"] == "interviewing"


def test_counts_include_waiting_only_in_tracked(tracker):
    counts = view_of()["interview_counts"]
    assert counts["tracked"] == 4
    assert counts["active"] == 2
    assert counts["leads"] == 1
    assert counts["waiting"] == 1
    assert counts["closed"] == 1

    with TestClient(module.app) as client:
        page = interviews_page(client)
    stats = page[page.index("job-stats") : page.index("interview-note")]
    assert re.findall(r'data-interview-count="([a-z]+)"', stats) == [
        "tracked",
        "active",
        "leads",
        "waiting",
        "high",
    ]
    assert re.findall(r'<div class="stat-label">([^<]+)</div>', stats) == [
        "Tracked",
        "In conversation",
        "New leads",
        "Waiting",
        "High priority",
    ]


def test_today_never_picks_waiting():
    soon = (TODAY + timedelta(days=1)).isoformat()
    later = (TODAY + timedelta(days=5)).isoformat()
    parked = {
        "company": "Parked",
        "role": "Systems Admin",
        "status": "waiting",
        "priority": "high",
        "next_steps": [{"task": "Check in", "date": soon}],
    }
    sent = {
        "company": "Sent",
        "role": "Support Engineer",
        "status": "applied",
        "priority": "low",
        "next_steps": [{"task": "Follow up", "date": later}],
    }
    rows = view_of([parked, sent])["interview_rows"]
    assert module.next_interview_action(rows, TODAY)["company"] == "Sent"
    only_waiting = view_of([parked])["interview_rows"]
    assert module.next_interview_action(only_waiting, TODAY) is None


def test_waiting_row_keeps_controls(tracker):
    with TestClient(module.app) as client:
        page = interviews_page(client)
    row = entry_html(page, "Parked")
    assert "data-interview-mode" in row
    assert 'href="https://example.com/parked"' in row
    assert "Update application" in row
    for hook in (
        'data-interview-select="status"',
        'data-interview-select="priority"',
        "data-interview-next-form",
        "data-interview-signal-form",
        "data-interview-notes-form",
    ):
        assert hook in row


def test_update_panel_is_grouped(tracker):
    with TestClient(module.app) as client:
        page = interviews_page(client)
    row = entry_html(page, "Talks")
    panel = row[row.index('<details class="interview-tools">') : row.index("</details>")]
    assert panel.count("<fieldset") == 4
    assert re.findall(r"<legend>([^<]+)</legend>", panel) == [
        "Status and priority",
        "Next action",
        "Log a signal",
        "Interview notes",
    ]
    assert re.search(r'<textarea[^>]*name="task"[^>]*rows="3"', panel)
    dates = re.findall(r'<input[^>]*type="date"[^>]*>', panel)
    assert len(dates) == 2 and all("interview-field-date" in d for d in dates)
    for hook in (
        'data-interview-select="status"',
        'data-interview-select="priority"',
        "data-interview-field-status",
        "data-interview-next-form",
        "data-interview-signal-form",
        "data-interview-notes-form",
        'name="task"',
        'name="date"',
        'name="stage"',
        'name="notes"',
    ):
        assert hook in panel
    assert panel.count("data-interview-feedback") == 3


def test_unknown_status_still_rejected(tracker):
    before = tracker.read_bytes()
    with TestClient(module.app) as client:
        for value in ("waiting_list", "WAITING"):
            r = set_status(client, "Sent", "Support Engineer", value)
            assert r.status_code == 400, value
            assert "error" in r.json()
    assert tracker.read_bytes() == before


def test_no_waiting_card_when_empty(tmp_path, monkeypatch):
    target = write_tracker(
        tmp_path / "job-applications.yml",
        [a for a in APPLICATIONS if a["status"] != "waiting"],
    )
    monkeypatch.setattr(module, "JOBS_FILE", target)
    with TestClient(module.app) as client:
        page = interviews_page(client)
    assert 'data-interview-section="waiting"' not in page
    assert re.search(r'data-interview-count="waiting">0<', page)
    assert "waiting to hear back" not in page


def test_career_page_lists_waiting_rows(tracker):
    with TestClient(module.app) as client:
        html = client.get("/").text
    start = html.index('id="page-career"')
    career = html[start : html.index('class="page"', start)]
    # The Career page lists applications as "Company — Role" options; it has
    # never shown a status label, so presence of the row is the contract.
    assert 'data-employer="Parked" data-position="Systems Admin"' in career
    assert "Parked — Systems Admin" in career
