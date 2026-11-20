"""Next up ranking: routine.md's lanes decide the three tasks the Today page shows.

TASKS.md is still the source; these tests only cover selection order, the
reference sections that must not surface as work, and the alternating week.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.today import select_next_up  # noqa: E402


def task(cat: str, text: str) -> dict:
    return {"cat": cat, "text": text, "done": False, "realm": "tasks", "line": 1}


def words(tasks: list[dict]) -> list[str]:
    return [t["text"] for t in tasks]


def test_security_outranks_income_and_debt():
    tasks = [
        task("Debt plan (inventory not yet complete)", "debt"),
        task("SECURITY — `pstools` secrets exposure", "security"),
        task("Monetization — playbook → income", "income"),
    ]
    assert words(select_next_up(tasks, date(2026, 11, 6))) == [
        "security",
        "income",
        "debt",
    ]


def test_bills_lane_outranks_devops_and_devops_outranks_bogatyr():
    tasks = [
        task("Bogatyr (project block — Week B)", "bogatyr"),
        task("DevOps block — automation builds (weekly)", "devops"),
        task("IT Mgmt Playbook (project block — Week A)", "playbook"),
    ]
    assert words(select_next_up(tasks, date(2026, 11, 6))) == [
        "playbook",
        "devops",
        "bogatyr",
    ]


def test_live_project_week_moves_the_other_project_behind_devops():
    tasks = [
        task("Bogatyr (project block — Week B)", "bogatyr"),
        task("DevOps block — automation builds (weekly)", "devops"),
        task("IT Mgmt Playbook (project block — Week A)", "playbook"),
    ]
    # Week 46 (even) is Week B, so Bogatyr leads its lane and Playbook waits.
    assert words(select_next_up(tasks, date(2026, 11, 9))) == [
        "bogatyr",
        "devops",
        "playbook",
    ]


@pytest.mark.parametrize(
    "category",
    [
        "Inbox",
        "Recurring (weekly, light)",
        "Someday",
        "Waiting On",
        "$3,000 income sprint (locked 2026-08-10; target window elapsed, outcome unverified)",
    ],
)
def test_reference_sections_never_surface_as_work(category):
    tasks = [task(category, "not work"), task("Security", "real work")]
    assert words(select_next_up(tasks, date(2026, 11, 6))) == ["real work"]


def test_three_items_at_most_and_file_order_breaks_ties():
    tasks = [task("Security", f"security {n}") for n in range(5)]
    assert words(select_next_up(tasks, date(2026, 11, 6))) == [
        "security 0",
        "security 1",
        "security 2",
    ]


def test_empty_when_everything_is_reference():
    tasks = [task("Someday", "later")]
    assert select_next_up(tasks, date(2026, 11, 6)) == []
