"""Job leads on Jev: the questions, the bands, and what leaves the machine."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import leads_jev  # noqa: E402

RESUME = """# Roosevelt Segura

**IT Support · Endpoint Deployment**

Brooklyn, NY | 978-444-0922 | mail@roosevelt.info | [site](https://example.com)

## Professional Summary

Ten years of support.

---

## Certifications

- **AWS Certified Cloud Practitioner** — AWS (Dec 2023)

---

## Technical Skills

| Category | Technologies |
| --- | --- |
| **Devices** | Windows, macOS, printers |

---

## Professional Experience

### IT Support Technician

**Asset Inventories — Client: NY Ross** — New York, NY | Jun 2026 – Oct 2026

- Refreshed 100+ Windows endpoints
- Built a refresh tracker

### IT Specialist

**Ventus Therapeutics** — Waltham, MA | Jul 2022 – Jun 2023

- Co-managed the M365 tenant

_Resume version: IT Support Technician — October 2026_
<!-- ATS Keywords: intune, autopilot -->
"""

LEAD = {
    "company": "Example Co",
    "role": "IT Support Associate",
    "priority": "high",
    "resume": "2026-10/resume-2026-10-it-support-tech.pdf",
    "requirements": [
        "1-3 years of IT support experience",
        "Intune device management",
        "1Password administration",
    ],
}

TRACKER = """\
active_applications:
  - company: Example Co
    role: IT Support Associate
    status: new_lead
    priority: high
    resume: 2026-10/resume-2026-10-it-support-tech.pdf
    requirements:
      - "1-3 years of IT support experience"
      - "Intune device management"
      - "1Password administration"
  - company: Untagged Co
    role: Something
    status: new_lead
"""


def reply(per_requirement):
    """A TypeSafe body with one noul answer per requirement, keyed by its text."""
    answers = {}
    for option in leads_jev.requirement_options(LEAD["requirements"]):
        probability = per_requirement[option["requirement"]]
        answers[f"covers_{option['name']}"] = {"type": "noul", "noul": probability}
    return {
        "model": "jev-1.14",
        "answers": answers,
        "usage": {"input_tokens": 900, "output_tokens": 10},
    }


# ── Reading the inputs ───────────────────────────────────────────────────────


def test_only_rows_carrying_requirements_are_judged(tmp_path):
    path = tmp_path / "tracker.yml"
    path.write_text(TRACKER, encoding="utf-8")
    leads = leads_jev.load_leads(path)
    assert [lead["company"] for lead in leads] == ["Example Co"]


def test_resume_markdown_is_found_from_the_pdf_named_on_the_row(tmp_path):
    (tmp_path / "it-support-tech").mkdir()
    target = tmp_path / "it-support-tech" / "resume-2026-10-it-support-tech.md"
    target.write_text(RESUME, encoding="utf-8")
    assert leads_jev.resume_path_for(LEAD, tmp_path) == target


def test_resume_without_markdown_source_is_reported_not_guessed(tmp_path):
    assert leads_jev.resume_path_for(LEAD, tmp_path) is None


def test_resume_parses_into_sections_and_jobs():
    evidence = leads_jev.parse_resume(RESUME)
    assert evidence["summary"] == "Ten years of support."
    assert evidence["certifications"] == ["**AWS Certified Cloud Practitioner** — AWS (Dec 2023)"]
    assert evidence["skills"] == ["**Devices** | Windows, macOS, printers"]
    assert [job["title"] for job in evidence["experience"]] == [
        "IT Support Technician",
        "IT Specialist",
    ]
    # The bold markers around the employer are removed, and the city and dates
    # that follow them are kept.
    assert evidence["experience"][0]["employer"] == (
        "Asset Inventories — Client: NY Ross — New York, NY | Jun 2026 – Oct 2026"
    )
    assert evidence["experience"][0]["highlights"][0] == "Refreshed 100+ Windows endpoints"


def test_resume_comments_and_version_footer_are_not_carried():
    blob = json.dumps(leads_jev.parse_resume(RESUME))
    assert "ATS Keywords" not in blob
    assert "Resume version" not in blob


def test_contact_line_never_reaches_the_request_body():
    # The contact line sits above the first section heading, so the parser drops
    # it before the request is even built.
    payload = leads_jev.build_payload(LEAD, leads_jev.parse_resume(RESUME))
    blob = json.dumps(payload)
    assert "roosevelt.info" not in blob
    assert "978-444-0922" not in blob


def test_redaction_catches_contact_details_wherever_they_appear():
    payload = leads_jev.redact(
        {"state": {"note": "reach me at mail@roosevelt.info or 978-444-0922"}}
    )
    assert payload["state"]["note"] == "reach me at [email] or [phone]"


# ── The questions ────────────────────────────────────────────────────────────


def test_payload_asks_one_question_per_requirement():
    payload = leads_jev.build_payload(LEAD, {"summary": "x"})
    assert payload["model"] == leads_jev.MODEL
    assert payload["state"]["role"]["posted_requirements"] == LEAD["requirements"]
    questions = payload["questions"]
    assert len(questions) == len(LEAD["requirements"])
    # Every requirement is judged on its own: no question asks about all of them
    # at once, which would make the answer a conjunction.
    for question in questions.values():
        assert question["type"] == "noul"
        assert question["instructions"].count('"') == 2  # one quoted requirement
    asked = " ".join(q["instructions"] for q in questions.values())
    for requirement in LEAD["requirements"]:
        assert requirement in asked


def test_requirement_options_are_descriptive_and_start_with_a_letter():
    options = leads_jev.requirement_options(LEAD["requirements"])
    assert [option["name"] for option in options] == [
        "req_1_3_years_of_it_support_experience",
        "intune_device_management",
        "req_1password_administration",
    ]


def test_identical_requirements_stay_distinct_options():
    options = leads_jev.requirement_options(["Okta admin", "Okta admin"])
    assert [option["name"] for option in options] == ["okta_admin", "okta_admin_2"]


# ── The verdict ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "probability,group",
    [(1.0, "met"), (0.7, "met"), (0.69, "thin"), (0.31, "thin"), (0.3, "missing"), (0.0, "missing")],
)
def test_requirement_thresholds(probability, group):
    assert leads_jev.classify(probability) == group


@pytest.mark.parametrize(
    "missing,thin,verdict",
    [
        (0, 0, "apply"),
        (0, 2, "gap story"),
        (1, 0, "gap story"),
        (2, 0, "skip"),
    ],
)
def test_verdict_counts(missing, thin, verdict):
    assert leads_jev.verdict_for(missing, thin) == verdict


def test_every_requirement_met_is_an_apply():
    row = leads_jev.score(
        reply({r: 0.9 for r in LEAD["requirements"]}), LEAD["requirements"]
    )
    assert row["verdict"] == "apply"
    assert len(row["met"]) == len(LEAD["requirements"])
    assert not row["thin"] and not row["missing"]


def test_one_requirement_without_evidence_is_a_gap_story():
    answers = {r: 0.9 for r in LEAD["requirements"]}
    answers["1Password administration"] = 0.05
    row = leads_jev.score(reply(answers), LEAD["requirements"])
    assert row["verdict"] == "gap story"
    assert [requirement for requirement, _ in row["missing"]] == ["1Password administration"]


def test_two_requirements_without_evidence_is_a_skip():
    answers = {r: 0.9 for r in LEAD["requirements"]}
    answers["1Password administration"] = 0.05
    answers["Intune device management"] = 0.1
    row = leads_jev.score(reply(answers), LEAD["requirements"])
    assert row["verdict"] == "skip"
    # Weakest first, so the report leads with the worst gap.
    assert [p for _, p in row["missing"]] == [0.05, 0.1]


def test_a_single_missing_requirement_does_not_sink_a_strong_lead():
    """The conjunction that put every lead at the floor: six strong, one absent."""
    answers = {r: 0.95 for r in LEAD["requirements"]}
    answers["1Password administration"] = 0.02
    row = leads_jev.score(reply(answers), LEAD["requirements"])
    assert row["mean"] > 0.6
    assert row["verdict"] == "gap story"


# ── Running it ───────────────────────────────────────────────────────────────


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    resume_dir = tmp_path / "resume" / "it-support-tech"
    resume_dir.mkdir(parents=True)
    (resume_dir / "resume-2026-10-it-support-tech.md").write_text(RESUME, encoding="utf-8")
    tracker = tmp_path / "job-applications.yml"
    tracker.write_text(TRACKER, encoding="utf-8")
    monkeypatch.setattr(leads_jev, "LEADS_FILE", tracker)
    monkeypatch.setattr(leads_jev, "RESUME_DIR", tmp_path / "resume")
    return tmp_path


def test_leads_are_printed_with_their_counts(workspace, capsys):
    def client(payload):
        return reply({r: 0.9 for r in LEAD["requirements"]})

    assert leads_jev.main([], client=client) == 0
    out = capsys.readouterr().out
    assert "Example Co — IT Support Associate  (high priority)  ->  apply" in out
    assert "met 3/3" in out
    assert "Judged 1 lead(s)" in out


def test_verbose_lists_the_met_requirements(workspace, capsys):
    def client(payload):
        return reply({r: 0.9 for r in LEAD["requirements"]})

    assert leads_jev.main(["-v"], client=client) == 0
    assert "met:     Intune device management" in capsys.readouterr().out


def test_api_failure_is_reported_as_a_failure(workspace, capsys):
    def broken(payload):
        raise RuntimeError("TypeSafe returned HTTP 429: slow down")

    assert leads_jev.main([], client=broken) == 3
    captured = capsys.readouterr()
    assert "HTTP 429" in captured.err
    assert "met 3/3" not in captured.out


def test_unreadable_resume_is_an_error_not_a_skip(workspace, capsys):
    tracker = workspace / "job-applications.yml"
    tracker.write_text(
        TRACKER.replace("2026-10/resume-2026-10-it-support-tech.pdf", "2026-10/missing.pdf"),
        encoding="utf-8",
    )

    def client(payload):  # pragma: no cover - must not be reached
        raise AssertionError("no call expected")

    assert leads_jev.main([], client=client) == 3
    assert "no resume markdown" in capsys.readouterr().err


def test_payload_mode_calls_nothing(workspace, capsys):
    def client(payload):  # pragma: no cover - must not be reached
        raise AssertionError("no call expected")

    assert leads_jev.main(["--payload"], client=client) == 0
    printed = capsys.readouterr().out
    assert '"covers_intune_device_management"' in printed
    assert "978-444-0922" not in printed


# ── The real tracker ─────────────────────────────────────────────────────────


def test_real_leads_build_a_payload_with_no_contact_details():
    """Every tagged lead in the repo, over its real resume source."""
    leads = leads_jev.load_leads()
    if not leads:  # pragma: no cover - the tracker currently has tagged leads
        pytest.skip("no lead carries a requirements list")
    for lead in leads:
        path = leads_jev.resume_path_for(lead)
        assert path is not None, lead["company"]
        payload = leads_jev.redact(
            leads_jev.build_payload(lead, leads_jev.parse_resume(path.read_text(encoding="utf-8")))
        )
        blob = json.dumps(payload)
        assert "mail@roosevelt.info" not in blob, lead["company"]
        assert "978-444-0922" not in blob, lead["company"]
        assert payload["state"]["role"]["posted_requirements"] == lead["requirements"]
