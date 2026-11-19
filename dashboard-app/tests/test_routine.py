"""Today routine parsing and Weekly Review write-back stay source-backed."""

import sys
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as dashboard  # noqa: E402
from core import config  # noqa: E402
from core.today import parse_routine_view  # noqa: E402


def test_parse_routine_view_extracts_today_review_rules_and_dates(tmp_path):
    source = """# Routine
_Last updated: 2026-11-06 (Week 45 weekly review)_

**Current context:** Search is active.

## The working rhythm
| Slot | What | Notes |
|---|---|---|
| **Workday** | Search + portfolio | Keep it focused. |
| 1 project block/week | Build | Tutorial format. |

**Weekly build/study totals:** baseline, not a new schedule.
---

## Weekly Review (~10 min, weekend)
### Review notes
- [ ] **Career review:** applications and portfolio
- [x] [TASKS.md](TASKS.md): refresh priorities

## Rules
1. **Income first.**
2. Keep the build log.

## Key Dates Ahead
| Date | Event | What to do |
|---|---|---|
| **Q4 2026** | Exam prep | Shift project blocks. |
"""
    path = tmp_path / "routine.md"
    path.write_text(source)

    routine = dashboard.parse_routine_view(date(2026, 11, 9), path)

    assert routine["available"] is True
    assert routine["updated"] == "2026-11-06 (Week 45 weekly review)"
    assert routine["context"] == "Search is active."
    assert routine["rhythm"][0] == {
        "slot": "Workday",
        "what": "Search + portfolio",
        "notes": "Keep it focused.",
        "is_today": True,
    }
    assert routine["rhythm"][1]["is_today"] is False
    assert routine["rhythm_summary"] == [
        "Weekly build/study totals: baseline, not a new schedule."
    ]
    assert [item["display_text"] for item in routine["review"]] == [
        "Career review: applications and portfolio",
        "TASKS.md: refresh priorities",
    ]
    assert routine["review"][1]["text"] == "[TASKS.md](TASKS.md): refresh priorities"
    assert [item["done"] for item in routine["review"]] == [False, True]
    assert routine["rules"] == ["Income first.", "Keep the build log."]
    assert routine["dates"] == [["Q4 2026", "Exam prep", "Shift project blocks."]]


def test_routine_toggle_requires_csrf_and_only_writes_weekly_review(tmp_path, monkeypatch):
    routine_file = tmp_path / "routine.md"
    source = (
        "# Routine\n"
        "## Other\n"
        "- [ ] Do not change\n"
        "## Weekly Review (~10 min, weekend)\n"
        "- [ ] Review me\n"
    )
    routine_file.write_text(source)
    monkeypatch.setattr(config, "WORKSPACE", tmp_path)

    with TestClient(dashboard.app) as client:
        missing_csrf = client.post(
            "/api/tasks/toggle",
            json={"realm": "routine", "line": 5, "done": True, "text": "Review me"},
        )
        assert missing_csrf.status_code == 403
        assert routine_file.read_text() == source

        moved_source = source.replace(
            "## Weekly Review (~10 min, weekend)\n",
            "## Weekly Review (~10 min, weekend)\n<!-- inserted while page was open -->\n",
        )
        routine_file.write_text(moved_source)
        updated = client.post(
            "/api/tasks/toggle",
            headers={"X-Requested-With": "XMLHttpRequest"},
            json={"realm": "routine", "line": 5, "done": True, "text": "Review me"},
        )
        assert updated.status_code == 200
        assert updated.json() == {
            "ok": True,
            "realm": "routine",
            "line": 6,
            "done": True,
        }
        assert "- [x] Review me\n" in routine_file.read_text()

        outside_review = client.post(
            "/api/tasks/toggle",
            headers={"X-Requested-With": "XMLHttpRequest"},
            json={
                "realm": "routine",
                "line": 3,
                "done": True,
                "text": "Do not change",
            },
        )
        assert outside_review.status_code == 400
        assert routine_file.read_text() == moved_source.replace(
            "- [ ] Review me", "- [x] Review me"
        )
