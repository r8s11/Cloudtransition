"""Triage inbox on Jev: the filing rules, the edit, and the failure paths."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import triage_jev  # noqa: E402

TASKS = """# Tasks

_Last updated: 2026-11-06_

## Inbox

- [ ] setup jev
- [ ] rotate the router password

## Active

### DevOps block — automation builds (weekly)

- [ ] Seed the candidate list: pull 3 scriptable manual steps
- [ ] Build #1: pick the smallest one

### Debt plan (inventory not yet complete)

- [ ] List all debts: balance, APR, minimum payment

---

## Recurring (weekly, light)

- [ ] ~10-min review
"""


def reply(fits, section, confidence=0.9, probabilities=None):
    """A TypeSafe response body for the two questions this tool asks."""
    return {
        "model": "jev-1.14",
        "answers": {
            "fits_existing_section": {"type": "noul", "noul": fits},
            "best_section": {
                "type": "choice",
                "choice": section,
                "confidence": confidence,
                "probabilities": probabilities or {section: confidence},
            },
        },
        "usage": {"input_tokens": 120, "output_tokens": 12},
    }


# ── Reading the file ─────────────────────────────────────────────────────────


def test_inbox_lines_are_unchecked_items_inside_the_inbox_section_only():
    lines = TASKS.split("\n")
    found = [triage_jev.item_text(lines[i]) for i in triage_jev.inbox_lines(lines)]
    assert found == ["setup jev", "rotate the router password"]


def test_destinations_are_third_level_headings_only():
    sections = triage_jev.destinations(TASKS.split("\n"))
    assert [s["name"] for s in sections] == [
        "devops_block_automation_builds_weekly",
        "debt_plan_inventory_not_yet_complete",
    ]
    assert sections[0]["heading"] == "DevOps block — automation builds (weekly)"
    # Nothing from inside a section travels in the state.
    assert set(sections[0]) == {"name", "heading"}
    assert "~10-min review" not in [s["heading"] for s in sections]


def test_descriptive_names_of_duplicate_headings_stay_unique():
    text = "\n".join(["### Same heading", "- [ ] one", "### Same heading", "- [ ] four"])
    sections = triage_jev.destinations(text.split("\n"))
    assert [s["name"] for s in sections] == ["same_heading", "same_heading_2"]


# ── The questions ────────────────────────────────────────────────────────────


def test_payload_names_every_section_and_carries_the_item():
    sections = triage_jev.destinations(TASKS.split("\n"))
    payload = triage_jev.build_payload("setup jev", sections)
    assert payload["model"] == triage_jev.MODEL
    assert payload["state"]["item_to_file"] == {"text": "setup jev"}
    questions = payload["questions"]
    assert questions["fits_existing_section"]["type"] == "noul"
    # The null case is asked separately: a Choice always picks something.
    assert questions["best_section"]["type"] == "choice"
    assert set(questions["best_section"]["criteria"]) == {s["name"] for s in sections}
    for section in sections:
        assert section["heading"] in questions["best_section"]["criteria"][section["name"]]


# ── The truth table ──────────────────────────────────────────────────────────


def test_confident_yes_files_the_item():
    verdict, details = triage_jev.decide(reply(0.93, "debt_plan_inventory_not_yet_complete"))
    assert verdict == "file"
    assert details["section"] == "debt_plan_inventory_not_yet_complete"


def test_no_matching_section_holds_the_item():
    verdict, details = triage_jev.decide(reply(0.12, "debt_plan_inventory_not_yet_complete"))
    assert verdict == "hold"
    assert "no existing section" in details["reason"]


def test_unsettled_noul_holds_the_item():
    verdict, details = triage_jev.decide(reply(0.55, "debt_plan_inventory_not_yet_complete"))
    assert verdict == "hold"
    assert "unsettled" in details["reason"]


def test_split_sections_hold_the_item():
    verdict, details = triage_jev.decide(
        reply(
            0.95,
            "debt_plan_inventory_not_yet_complete",
            confidence=0.41,
            probabilities={
                "debt_plan_inventory_not_yet_complete": 0.41,
                "devops_block_automation_builds_weekly": 0.39,
            },
        )
    )
    assert verdict == "hold"
    assert "split" in details["reason"]
    assert "debt_plan" in details["reason"] and "devops_block" in details["reason"]


# ── Recorded live answers ────────────────────────────────────────────────────


def test_thresholds_hold_against_recorded_live_answers():
    """Replay real jev-latest output; these are the cases the rules were read against."""
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "jev_triage_rehearsal.json").read_text(
            encoding="utf-8"
        )
    )
    expected = {
        "Add the two credit card balances and their APRs to the debt spreadsheet": (
            "file",
            "debt_plan_inventory_not_yet_complete",
        ),
        # Automation work, but also documentation the Playbook block owns: held.
        "Write a tutorial-format guide for the robocopy backup script I built": ("hold", ""),
        "Renew the passport before it expires in April": ("hold", ""),
        "Sort out the printer situation": ("hold", ""),
    }
    assert {case["item"] for case in fixture["cases"]} == set(expected)
    for case in fixture["cases"]:
        verdict, details = triage_jev.decide(case["answer"])
        want_verdict, want_section = expected[case["item"]]
        assert verdict == want_verdict, case["item"]
        if want_section:
            assert details["section"] == want_section
        else:
            assert details["reason"]


# ── The edit ─────────────────────────────────────────────────────────────────


def test_move_appends_to_the_section_and_keeps_every_other_line():
    moves = [("- [ ] setup jev", "Debt plan (inventory not yet complete)")]
    result = triage_jev.apply_moves(TASKS, moves)
    assert result == TASKS.replace(
        "- [ ] setup jev\n", ""
    ).replace(
        "- [ ] List all debts: balance, APR, minimum payment",
        "- [ ] List all debts: balance, APR, minimum payment\n- [ ] setup jev",
    )
    assert result.count("- [ ] setup jev") == 1


def test_empty_inbox_keeps_its_heading():
    text = "## Inbox\n\n- [ ] only item\n\n## Active\n\n### Somewhere\n\n- [ ] existing\n"
    result = triage_jev.apply_moves(text, [("- [ ] only item", "Somewhere")])
    assert "## Inbox\n\n## Active" in result
    assert "- [ ] existing\n- [ ] only item" in result


def test_section_of_prose_gets_a_separated_task_line():
    text = "## Inbox\n\n- [ ] a task\n\n## Active\n\n### Prose only\n\nSome words about it.\n\n## Next\n"
    result = triage_jev.apply_moves(text, [("- [ ] a task", "Prose only")])
    assert "Some words about it.\n\n- [ ] a task\n\n## Next" in result


# ── Running it ───────────────────────────────────────────────────────────────


@pytest.fixture
def tasks_file(tmp_path, monkeypatch):
    path = tmp_path / "TASKS.md"
    path.write_text(TASKS, encoding="utf-8")
    monkeypatch.setattr(triage_jev, "TASKS_FILE", path)
    return path


def test_missing_key_fails_without_touching_the_file(tasks_file, capsys):
    def no_key(payload):
        raise RuntimeError("TYPESAFE_API_KEY is not set; no model call was made")

    assert triage_jev.main([], client=no_key) == 3
    assert tasks_file.read_text(encoding="utf-8") == TASKS
    assert "TYPESAFE_API_KEY" in capsys.readouterr().err


def test_api_failure_never_reads_as_no_section_fits(tasks_file, capsys):
    def broken(payload):
        raise RuntimeError("TypeSafe returned HTTP 500: boom")

    out = triage_jev.main([], client=broken)
    captured = capsys.readouterr()
    assert out == 3
    assert "stays in Inbox" not in captured.out
    assert "HTTP 500" in captured.err
    assert tasks_file.read_text(encoding="utf-8") == TASKS


def test_confident_run_files_and_reports_the_destination(tasks_file, capsys):
    def client(payload):
        item = payload["state"]["item_to_file"]["text"]
        if item == "setup jev":
            return reply(0.91, "devops_block_automation_builds_weekly")
        return reply(0.2, "debt_plan_inventory_not_yet_complete")

    assert triage_jev.main([], client=client) == 0
    result = tasks_file.read_text(encoding="utf-8")
    assert "- [ ] Build #1: pick the smallest one\n- [ ] setup jev" in result
    # The held item kept its exact place and wording.
    assert "## Inbox\n\n- [ ] rotate the router password" in result
    out = capsys.readouterr().out
    assert "setup jev\n    -> DevOps block — automation builds (weekly)" in out
    assert "rotate the router password\n    -> stays in Inbox" in out


def test_dry_run_calls_jev_and_writes_nothing(tasks_file, capsys):
    def client(payload):
        return reply(0.91, "devops_block_automation_builds_weekly")

    assert triage_jev.main(["--dry-run"], client=client) == 0
    assert tasks_file.read_text(encoding="utf-8") == TASKS
    assert "would move" in capsys.readouterr().out


def test_payload_mode_prints_the_request_without_calling(tasks_file, capsys):
    def client(payload):  # pragma: no cover - must not be reached
        raise AssertionError("no call expected")

    assert triage_jev.main(["--payload"], client=client) == 0
    printed = capsys.readouterr().out
    assert '"model": "jev-latest"' in printed
    assert "setup jev" in printed


def test_empty_inbox_exits_cleanly(tasks_file, capsys):
    tasks_file.write_text("# Tasks\n\n## Inbox\n\n## Active\n", encoding="utf-8")

    def client(payload):  # pragma: no cover - must not be reached
        raise AssertionError("no call expected")

    assert triage_jev.main([], client=client) == 0
    assert "Inbox is empty" in capsys.readouterr().out
