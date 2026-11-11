"""Interview write endpoints persist to the tracker copy and reject bad input."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest  # noqa: E402
import yaml  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as module  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
CSRF = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture()
def tracker(tmp_path, monkeypatch):
    target = tmp_path / "job-applications.yml"
    shutil.copyfile(ROOT / "interviews" / "job-applications.yml", target)
    monkeypatch.setattr(module, "JOBS_FILE", target)
    return target


def apps(target: Path) -> list[dict]:
    return yaml.safe_load(target.read_text())["active_applications"]


def test_field_update_persists_and_returns_the_rebuilt_row(tracker):
    first = apps(tracker)[0]
    with TestClient(module.app) as client:
        r = client.post(
            "/api/interviews/field",
            headers=CSRF,
            json={
                "company": first["company"],
                "role": first["role"],
                "field": "priority",
                "value": "low",
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["row"]["priority"] == "low"
    # Tracked counts live threads only; rejected/withdrawn have their own count.
    live = [a for a in apps(tracker) if a.get("status") not in ("rejected", "withdrawn")]
    closed = [a for a in apps(tracker) if a.get("status") in ("rejected", "withdrawn")]
    assert body["counts"]["tracked"] == len(live)
    assert body["counts"]["closed"] == len(closed)
    assert apps(tracker)[0]["priority"] == "low"


def test_missing_csrf_header_is_rejected(tracker):
    first = apps(tracker)[0]
    with TestClient(module.app) as client:
        r = client.post(
            "/api/interviews/field",
            json={
                "company": first["company"],
                "role": first["role"],
                "field": "status",
                "value": "applied",
            },
        )
    assert r.status_code == 403


def test_invalid_status_is_rejected_without_writing(tracker):
    before = tracker.read_text()
    first = apps(tracker)[0]
    with TestClient(module.app) as client:
        r = client.post(
            "/api/interviews/field",
            headers=CSRF,
            json={
                "company": first["company"],
                "role": first["role"],
                "field": "status",
                "value": "ghosted",
            },
        )
    assert r.status_code == 400
    assert tracker.read_text() == before


def test_next_step_signal_and_notes_all_persist(tracker):
    first = apps(tracker)[0]
    key = {"company": first["company"], "role": first["role"]}
    with TestClient(module.app) as client:
        r1 = client.post(
            "/api/interviews/next-step",
            headers=CSRF,
            json={**key, "task": "Send thank-you", "date": "2026-11-07"},
        )
        r2 = client.post(
            "/api/interviews/timeline",
            headers=CSRF,
            json={**key, "date": "2026-11-06", "stage": "technical_screen", "notes": "Good call"},
        )
        r3 = client.post(
            "/api/interviews/text",
            headers=CSRF,
            json={**key, "field": "interview_notes", "text": "Q: tell me about an outage\nA: triage first"},
        )
    assert (r1.status_code, r2.status_code, r3.status_code) == (200, 200, 200)
    updated = apps(tracker)[0]
    assert updated["next_steps"][0]["task"] == "Send thank-you"
    assert updated["timeline"][-1]["stage"] == "technical_screen"
    assert updated["interview_notes"].startswith("Q: tell me about an outage")
    # The human-written job-fit note is still there.
    assert updated["notes"]


def test_create_application_appends_to_the_tracker(tracker):
    before = len(apps(tracker))
    with TestClient(module.app) as client:
        r = client.post(
            "/api/interviews/create",
            headers=CSRF,
            json={
                "company": "NewCo",
                "role": "Desktop Support",
                "status": "applied",
                "priority": "high",
                "location": "Brooklyn, NY",
                "next_step": "Follow up",
                "date": "2026-11-13",
            },
        )
    assert r.status_code == 200, r.text
    assert r.json()["row"]["company"] == "NewCo"
    assert len(apps(tracker)) == before + 1
    assert apps(tracker)[-1]["next_steps"][0]["task"] == "Follow up"


def test_unknown_application_returns_a_readable_error(tracker):
    with TestClient(module.app) as client:
        r = client.post(
            "/api/interviews/text",
            headers=CSRF,
            json={"company": "NoSuchCo", "role": "Nope", "field": "interview_notes", "text": "x"},
        )
    assert r.status_code == 400
    assert "not found" in r.json()["error"]


def test_detail_endpoint_carries_everything_interview_mode_shows(tracker):
    first = apps(tracker)[0]
    with TestClient(module.app) as client:
        r = client.get(
            "/api/interviews/detail",
            params={"company": first["company"], "role": first["role"]},
        )
    assert r.status_code == 200, r.text
    row = r.json()["row"]
    for key in (
        "company",
        "role",
        "status_label",
        "contacts",
        "resume_href",
        "url",
        "questions",
        "preparation",
        "notes",
        "fit_notes",
        "prep_files",
        "history",
    ):
        assert key in row
    assert row["fit_notes"]
    # History is newest-first, so the panel reads top-down like a call.
    history = row["history"]
    assert history[0]["date"] >= history[-1]["date"]


def test_detail_endpoint_404s_for_an_application_that_is_not_there(tracker):
    with TestClient(module.app) as client:
        r = client.get(
            "/api/interviews/detail", params={"company": "NoSuchCo", "role": "Nope"}
        )
    assert r.status_code == 404


def test_preparation_and_questions_persist_and_leave_job_fit_notes(tracker):
    first = apps(tracker)[0]
    key = {"company": first["company"], "role": first["role"]}
    with TestClient(module.app) as client:
        q = client.post(
            "/api/interviews/text",
            headers=CSRF,
            json={**key, "field": "interview_questions", "text": "What does success look like?\nWho do I escalate to?"},
        )
        p = client.post(
            "/api/interviews/text",
            headers=CSRF,
            json={**key, "field": "interview_preparation", "text": "Outage story\nM365 migration story"},
        )
    assert (q.status_code, p.status_code) == (200, 200)
    updated = apps(tracker)[0]
    assert updated["interview_questions"].startswith("What does success look like?")
    assert updated["interview_preparation"].startswith("Outage story")
    assert updated["notes"]  # hand-written job-fit prose survives
    assert q.json()["row"]["questions"].startswith("What does success look like?")
    assert p.json()["row"]["preparation"].startswith("Outage story")


def test_unknown_text_field_is_rejected_without_writing(tracker):
    before = tracker.read_text()
    first = apps(tracker)[0]
    with TestClient(module.app) as client:
        r = client.post(
            "/api/interviews/text",
            headers=CSRF,
            json={
                "company": first["company"],
                "role": first["role"],
                "field": "notes",
                "text": "trying to overwrite the job-fit prose",
            },
        )
    assert r.status_code == 400
    assert tracker.read_text() == before


def test_sheet_renders_a_printable_page_and_escapes_content(tracker):
    first = apps(tracker)[0]
    with TestClient(module.app) as client:
        r = client.get(
            "/interviews/sheet",
            params={"company": first["company"], "role": first["role"]},
        )
    assert r.status_code == 200, r.text
    body = r.text
    assert "<!doctype html>" in body
    assert first["company"] in body
    for section in ("Questions to ask", "Preparation", "Notes", "talking to"):
        assert section in body
    # Printing is the point: the stylesheet must define a print page.
    assert "@page" in body and "@media print" in body
    assert "window.print()" in body
    # No app chrome or scripts beyond the print button.
    assert "/static/app.js" not in body
    assert 'role="tab"' not in body


def test_sheet_404s_for_an_application_that_is_not_there(tracker):
    with TestClient(module.app) as client:
        r = client.get(
            "/interviews/sheet", params={"company": "NoSuchCo", "role": "Nope"}
        )
    assert r.status_code == 404


def test_sheet_does_not_escape_html_into_markup(tracker):
    with TestClient(module.app) as client:
        client.post(
            "/api/interviews/text",
            headers=CSRF,
            json={
                "company": apps(tracker)[0]["company"],
                "role": apps(tracker)[0]["role"],
                "field": "interview_questions",
                "text": "Ask about <script>alert(1)</script>",
            },
        )
        r = client.get(
            "/interviews/sheet",
            params={"company": apps(tracker)[0]["company"], "role": apps(tracker)[0]["role"]},
        )
    assert "<script>alert(1)</script>" not in r.text
    assert "&lt;script&gt;" in r.text
