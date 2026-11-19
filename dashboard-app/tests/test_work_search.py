"""Weekly reports use explicit completed activities, never pipeline guesses."""
from datetime import date
from pathlib import Path
import sys

import pytest
import yaml
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app as module
from core import work_search as ws

CSRF = {"X-Requested-With": "XMLHttpRequest"}
ACTIVITY = {
    "id": "c03beb13-f1e8-4739-853c-a18c28d09528",
    "date": "2026-11-16",
    "activity_type": "Employer Contact",
    "description": "Submitted a job application",
    "position": "Support Engineer",
    "employer": "Example Employer",
    "address": "12 Example Street\nNew York, NY",
    "result": "Awaiting response",
}


def test_week_boundaries_and_missing_fields_do_not_infer_pipeline_work():
    rows = [dict(ACTIVITY, date=d, id=str(i)) for i, d in enumerate([
        "2026-11-15", "2026-11-16", "2026-11-22", "2026-11-23"
    ])]
    rows[1]["address"] = ""
    report = ws.report({"work_search_activities": rows, "active_applications": [
        {"status": "applied", "application_date": "2026-11-17"}
    ]}, date(2026, 11, 16))
    assert [r["date"] for r in report["activities"]] == ["2026-11-16", "2026-11-22"]
    assert report["end"] == "2026-11-22"
    assert report["activities"][0]["missing"] == ["Employer address"]
    assert "Employer address: Not recorded" in report["text"]
    assert "Date of Activity: 11/16/2026" in report["text"]
    assert "Claimant" not in report["text"]
    assert ws.report({}, date(2026, 12, 28))["end"] == "2027-01-03"


def test_upsert_preserves_other_sections_and_retry_does_not_duplicate():
    original = '# Keep this comment\nactive_applications:\n  - company: "Example" # inline note\n    role: Support\nstatistics: {}\n'
    saved = ws.save(original, ACTIVITY, today=date(2026, 11, 16))
    assert saved.startswith(original)
    updated = ws.save(saved, dict(ACTIVITY, result="Interview scheduled"), today=date(2026, 11, 16))
    assert updated.startswith(original)
    records = yaml.safe_load(updated)["work_search_activities"]
    assert len(records) == 1
    assert records[0]["result"] == "Interview scheduled"
    # An owned block in the middle must not consume the following section.
    middle = saved + '\nnext_section:\n  value: "untouched" # keep\n'
    edited = ws.save(middle, ACTIVITY, today=date(2026, 11, 16))
    assert edited.endswith('\nnext_section:\n  value: "untouched" # keep\n')


@pytest.mark.parametrize("changes", [
    {"date": "2026-02-30"}, {"date": "2026-11-17"}, {"date": "20261116"},
    {"id": "not-an-id"}, {"employer": " "}, {"description": "x" * 1001},
])
def test_invalid_completed_activity_is_rejected(changes):
    with pytest.raises(ValueError):
        ws.save("active_applications: []\n", dict(ACTIVITY, **changes), today=date(2026, 11, 16))


def test_endpoints_persist_edit_filter_and_reject_unsafe_writes(tmp_path, monkeypatch):
    target = tmp_path / "job-applications.yml"
    original = "# Keep\nactive_applications: []\n"
    target.write_text(original)
    monkeypatch.setattr(module, "JOBS_FILE", target)
    monkeypatch.setattr(module, "_warm_skill_catalog", lambda: None)
    with TestClient(module.app) as client:
        assert client.post("/api/career/work-search", json=ACTIVITY).status_code == 403
        assert target.read_text() == original
        response = client.post("/api/career/work-search", headers=CSRF, json=ACTIVITY)
        assert response.status_code == 200, response.text
        assert client.post("/api/career/work-search", headers=CSRF, json=dict(ACTIVITY, result="Interview scheduled")).status_code == 200
        data = client.get("/api/career/work-search?start=2026-11-16").json()
        assert len(data["activities"]) == 1
        assert data["activities"][0]["result"] == "Interview scheduled"
        assert "Business / Employer name and address: Example Employer\n12 Example Street" in data["text"]
        assert client.get("/api/career/work-search?start=2026-11-23").json()["activities"] == []
        assert client.get("/api/career/work-search?start=2026-02-30").status_code == 422
        before = target.read_text()
        assert client.post("/api/career/work-search", headers=CSRF, json=dict(ACTIVITY, date="2099-01-01")).status_code == 400
        assert target.read_text() == before
        assert client.get("/").status_code == 200


def test_corrupt_ledger_is_not_overwritten():
    with pytest.raises(ValueError):
        ws.save("work_search_activities: not-a-list\n", ACTIVITY, today=date(2026, 11, 16))
