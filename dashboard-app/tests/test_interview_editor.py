"""interview_editor: edits keep comments, neighbours and YAML validity intact."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest  # noqa: E402
import yaml  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import interview_editor as ie  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture()
def tracker() -> str:
    return (
        "# Tracker\n"
        "\n"
        "active_applications:\n"
        "  # ====== LIVE ======\n"
        "  - company: Acme\n"
        "    role: IT Support\n"
        "    status: interviewing\n"
        "    priority: high\n"
        "    contacts:\n"
        "      - name: Ada\n"
        "        role: Recruiter\n"
        "    timeline:\n"
        "      - date: 2026-10-01\n"
        "        stage: recruiter_screen\n"
        "        notes: First call.\n"
        "    next_steps:\n"
        "      - task: \"Follow up\"\n"
        "        date: 2026-10-10\n"
        "    notes: |\n"
        "      Job-fit note that must survive edits.\n"
        "\n"
        "  - company: Beta\n"
        "    role: Systems Admin\n"
        "    status: new_lead\n"
        "    priority: low\n"
        "\n"
        "past_applications: []\n"
    )


def parsed(text: str) -> list[dict]:
    return yaml.safe_load(text)["active_applications"]


def test_set_field_changes_only_the_target_line(tracker):
    updated = ie.set_field(tracker, "Acme", "IT Support", "status", "offer")
    apps = parsed(updated)
    assert apps[0]["status"] == "offer"
    assert apps[1]["status"] == "new_lead"
    assert apps[0]["notes"].startswith("Job-fit note")
    assert "# ====== LIVE ======" in updated
    assert updated.count("status:") == 2


def test_set_field_adds_a_missing_field(tracker):
    updated = ie.set_field(tracker, "Beta", "Systems Admin", "location", "New York, NY")
    apps = parsed(updated)
    assert apps[1]["location"] == "New York, NY"
    assert apps[0]["status"] == "interviewing"


def test_set_next_step_replaces_the_list_with_one_action(tracker):
    updated = ie.set_next_step(
        tracker, "Acme", "IT Support", 'Send thank-you: "30 min"', "2026-11-07"
    )
    steps = parsed(updated)[0]["next_steps"]
    assert steps == [{"task": 'Send thank-you: "30 min"', "date": "2026-11-07"}]


def test_set_next_step_creates_the_block_when_missing(tracker):
    updated = ie.set_next_step(tracker, "Beta", "Systems Admin", "Apply", "")
    steps = parsed(updated)[1]["next_steps"]
    assert steps[0]["task"] == "Apply"
    assert steps[0]["date"] is None


def test_append_timeline_keeps_earlier_signals(tracker):
    updated = ie.append_timeline(
        tracker, "Acme", "IT Support", "2026-11-06", "technical_screen",
        "Asked about Intune baselines.\nQuestions to revisit: Autopilot ESP.",
    )
    timeline = parsed(updated)[0]["timeline"]
    assert [t["stage"] for t in timeline] == ["recruiter_screen", "technical_screen"]
    assert timeline[-1]["date"] == "2026-11-06"
    assert "Autopilot ESP" in timeline[-1]["notes"]
    assert parsed(updated)[1].get("timeline") is None


def test_append_timeline_creates_the_block_when_missing(tracker):
    updated = ie.append_timeline(
        tracker, "Beta", "Systems Admin", "2026-11-06", "applied", ""
    )
    timeline = parsed(updated)[1]["timeline"]
    assert timeline == [{"date": "2026-11-06", "stage": "applied"}]


def test_interview_notes_roundtrip_with_punctuation_and_blank_lines(tracker):
    notes = 'Q: "tell me about a hard outage"\n\nA: used the playbook: triage, comms, postmortem.'
    updated = ie.set_text_block(tracker, "Acme", "IT Support", "interview_notes", notes)
    assert parsed(updated)[0]["interview_notes"] == notes + "\n"
    # The job-fit notes field is untouched.
    assert parsed(updated)[0]["notes"].startswith("Job-fit note")

    replaced = ie.set_text_block(updated, "Acme", "IT Support", "interview_notes", "Shorter note.")
    assert parsed(replaced)[0]["interview_notes"] == "Shorter note.\n"
    assert parsed(replaced)[0]["notes"].startswith("Job-fit note")


def test_add_application_appends_a_parseable_entry(tracker):
    updated = ie.add_application(
        tracker,
        company='Fireworks "AI"',
        role="IT Support: Tier 2",
        status="applied",
        priority="medium",
        location="New York, NY",
        salary_range="$110-150K",
        job_url="https://example.com/job",
        next_step="Follow up in a week",
        due="2026-11-13",
    )
    apps = parsed(updated)
    assert len(apps) == 3
    assert apps[-1]["company"] == 'Fireworks "AI"'
    assert apps[-1]["role"] == "IT Support: Tier 2"
    assert apps[-1]["next_steps"][0]["date"] == "2026-11-13"
    assert "# Tracker" in updated and updated.rstrip().endswith("past_applications: []")


def test_edits_refuse_unknown_or_ambiguous_targets(tracker):
    with pytest.raises(ie.InterviewEditError):
        ie.set_field(tracker, "Nope", "Nope", "status", "applied")
    with pytest.raises(ie.InterviewEditError):
        ie.set_field(tracker, "Acme", "IT Support", "status", "ghosted")
    with pytest.raises(ie.InterviewEditError):
        ie.add_application(tracker, company="Acme", role="IT Support")
    with pytest.raises(ie.InterviewEditError):
        ie.append_timeline(tracker, "Acme", "IT Support", "not-a-date", "call", "")


def test_real_tracker_is_editable_without_losing_structure():
    source = (ROOT / "interviews" / "job-applications.yml").read_text(encoding="utf-8")
    first = parsed(source)[0]
    updated = ie.set_field(source, first["company"], first["role"], "status", "applied")
    assert parsed(updated)[0]["status"] == "applied"
    assert source.count("\n") == updated.count("\n")
    assert "# Job Applications Tracker" in updated


PREP_LIST = (
    "# Tracker\n"
    "\n"
    "active_applications:\n"
    "  - company: Ground Up\n"
    "    role: Senior IT Support\n"
    "    status: screening\n"
    "    priority: high\n"
    "    interview_prep:\n"
    "      - interviews/Ground Up/prep.md\n"
    "      - interviews/Ground Up/jd-senior-it-support-specialist.md\n"
    "    notes: |\n"
    "      Strong JD match.\n"
)


def test_preparation_uses_its_own_key_and_leaves_the_prep_file_list_alone():
    updated = ie.set_text_block(
        PREP_LIST,
        "Ground Up",
        "Senior IT Support",
        "interview_preparation",
        "Ready: Intune/Entra story\nAsk: what does week one look like?",
    )
    app = parsed(updated)[0]
    # The recorded prep-file paths are still paths.
    assert app["interview_prep"] == [
        "interviews/Ground Up/prep.md",
        "interviews/Ground Up/jd-senior-it-support-specialist.md",
    ]
    assert app["interview_preparation"] == (
        "Ready: Intune/Entra story\nAsk: what does week one look like?\n"
    )
    assert app["notes"].startswith("Strong JD match")

    # And a second save replaces the prose only.
    again = ie.set_text_block(
        updated, "Ground Up", "Senior IT Support", "interview_preparation", "One line."
    )
    assert parsed(again)[0]["interview_preparation"] == "One line.\n"
    assert len(parsed(again)[0]["interview_prep"]) == 2


def test_text_blocks_refuse_to_overwrite_structured_data(monkeypatch):
    monkeypatch.setitem(ie.TEXT_BLOCKS, "interview_prep", "preparation")
    with pytest.raises(ie.InterviewEditError, match="structured data"):
        ie.set_text_block(PREP_LIST, "Ground Up", "Senior IT Support", "interview_prep", "prose")
    # Nothing was handed back, so the path list is still a list.
    assert parsed(PREP_LIST)[0]["interview_prep"][0] == "interviews/Ground Up/prep.md"


def test_questions_and_notes_stay_separate_blocks(tracker):
    updated = ie.set_text_block(
        tracker, "Acme", "IT Support", "interview_questions", "What does success look like?"
    )
    updated = ie.set_text_block(updated, "Acme", "IT Support", "interview_notes", "They asked about DNS.")
    app = parsed(updated)[0]
    assert app["interview_questions"] == "What does success look like?\n"
    assert app["interview_notes"] == "They asked about DNS.\n"
    assert app["notes"].startswith("Job-fit note")
