#!/usr/bin/env python3
"""Judge job leads with Jev: does the resume meet the posted must-haves?

Each lead in the tracker that carries a `requirements:` list is judged against
the resume variant named on its own row. Jev answers one question per posted
requirement — does the resume show evidence for this one — and `score()` in this
file counts those answers into met / thin / missing and an apply / gap story /
skip verdict. Nothing is written: the tracker, the resume and the leads doc are
read only.

    python3 dashboard-app/leads_jev.py             # judge every tagged lead
    python3 dashboard-app/leads_jev.py --payload   # print the requests, no call
    python3 dashboard-app/leads_jev.py --company CAIS

The requirements are the posting's own must-haves, recorded in the tracker; the
"why / gaps" prose from the leads doc is deliberately not sent, so Jev's answer
is its own read rather than an agreement with one already written down. Contact
details from the resume are stripped before anything leaves the machine.

Exit codes: 0 judged or nothing to judge, 2 not configured, 3 API failure.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parent.parent
LEADS_FILE = WORKSPACE / "interviews" / "job-applications.yml"
RESUME_DIR = WORKSPACE / "resume"

API_URL = "https://api.typesafe.ai/v1/systemone"
API_KEY_ENV = "TYPESAFE_API_KEY"
MODEL = "jev-latest"

# A Noul's probability of yes, on the same pair the inbox triage uses: at or
# above 0.7 the posting reads as met, at or below 0.3 as not met, and the band
# between means the resume neither claims nor clearly lacks the evidence.
MATCH_YES = 0.7
MATCH_NO = 0.3

# Contact details, kept out of every request. A resume is written for employers,
# not for a third-party API that only has to judge its content.
REDACTIONS = (
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email]"),
    (re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"), "[phone]"),
)


# ── Reading the tracker ──────────────────────────────────────────────────────


def load_leads(path: Path | None = None) -> list[dict]:
    """Tracker rows that carry a requirements list, in file order."""
    data = yaml.safe_load((path or LEADS_FILE).read_text(encoding="utf-8"))
    rows = data.get("active_applications") or []
    return [row for row in rows if row.get("requirements")]


def resume_path_for(lead: dict, resume_dir: Path | None = None) -> Path | None:
    """The markdown source of the variant named on the row.

    Rows name the exported PDF (`2026-10/resume-2026-10-it-support-tech.pdf`);
    the markdown it is built from sits beside its variant folder.
    """
    resume_dir = resume_dir or RESUME_DIR
    name = Path(str(lead.get("resume") or "")).stem
    if not name:
        return None
    for candidate in sorted(resume_dir.glob(f"*/{name}.md")):
        return candidate
    if name == "master":
        return resume_dir / "master.md"
    return None


# ── Reading the resume ───────────────────────────────────────────────────────


def parse_resume(text: str) -> dict:
    """The resume as sections of content: what an employer actually reads.

    Bullets and table rows are kept verbatim; front matter, rules and the
    version footer are dropped. Nothing is summarised here, so a weaker resume
    stays weak in the state.
    """
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    sections: dict[str, list[str]] = {}
    heading = None
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("_Resume version"):
            continue
        match = re.match(r"^##\s+(.*)$", line)
        if match:
            heading = match.group(1).strip()
            sections[heading] = []
            continue
        if heading is None or not stripped or stripped == "---":
            continue
        sections[heading].append(stripped)

    evidence = {"summary": " ".join(sections.get("Professional Summary", [])).strip()}
    evidence["certifications"] = [
        line.lstrip("- ").strip() for line in sections.get("Certifications", [])
    ]
    skills: list[str] = []
    for line in sections.get("Technical Skills", []):
        if not line.startswith("|"):
            continue
        if set(line) <= set("|-: "):  # the rule under a table header
            skills.pop()
            continue
        skills.append(line.strip("| ").strip())
    evidence["skills"] = skills
    jobs: list[dict] = []
    for line in sections.get("Professional Experience", []):
        if line.startswith("### "):
            jobs.append({"title": line[4:].strip(), "highlights": []})
        elif not jobs:
            continue
        elif "employer" not in jobs[-1] and line.startswith("**"):
            jobs[-1]["employer"] = re.sub(r"^\*\*(.*?)\*\*", r"\1", line).strip()
        else:
            jobs[-1]["highlights"].append(line.lstrip("- ").strip())
    evidence["experience"] = jobs
    return {key: value for key, value in evidence.items() if value}


# ── The questions ────────────────────────────────────────────────────────────


def slug(text: str) -> str:
    """A content-describing option name derived from a requirement.

    Option names are sent to the model, so they carry the requirement's own
    words rather than a position. A leading digit gets a prefix: "1Password
    administration" is not a name an option should start with.
    """
    asciiish = "".join(ch if ch.isascii() else " " for ch in text).lower()
    words = re.findall(r"[a-z0-9]+", asciiish)
    name = "_".join(words)[:48].strip("_") or "requirement"
    return f"req_{name}" if name[0].isdigit() else name


def requirement_options(requirements: list[str]) -> list[dict]:
    """Each requirement as a named option, kept distinct if two slug the same."""
    out: list[dict] = []
    seen: dict[str, int] = {}
    for requirement in requirements:
        name = slug(requirement)
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            name = f"{name}_{seen[name]}"
        out.append({"name": name, "requirement": requirement})
    return out


def build_payload(lead: dict, evidence: dict) -> dict:
    """One request per lead, one question per requirement.

    Each requirement is judged on its own. Asking once whether the resume meets
    *every* requirement makes the answer a conjunction: with seven must-haves a
    strong candidate still reads near zero, and every lead lands in the floor of
    the scale. Counting the individual answers in `score()` is code, and it
    keeps a single missing requirement from swallowing the rest.
    """
    options = requirement_options(list(lead["requirements"]))
    questions = {}
    for option in options:
        requirement = option["requirement"]
        questions[f"covers_{option['name']}"] = {
            "type": "noul",
            "instructions": (
                "Does `candidate_resume` show evidence for this requirement of "
                f"`role`: \"{requirement}\"?"
            ),
            "criteria": {
                "true": f"The resume gives concrete evidence of: {requirement}.",
                "false": f"The resume has no concrete evidence of: {requirement}.",
            },
        }
    return {
        "model": MODEL,
        "state": {
            "role": {
                "company": lead.get("company"),
                "title": lead.get("role"),
                "location": lead.get("location"),
                "posted_requirements": [option["requirement"] for option in options],
            },
            "candidate_resume": evidence,
        },
        "questions": questions,
    }


def redact(payload: dict) -> dict:
    """Strip email addresses and phone numbers from the whole request body."""
    text = json.dumps(payload, ensure_ascii=False)
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    return json.loads(text)


def classify(probability: float) -> str:
    """One requirement's answer, in code: met, thin or missing."""
    if probability >= MATCH_YES:
        return "met"
    if probability <= MATCH_NO:
        return "missing"
    return "thin"


def verdict_for(missing: int, thin: int) -> str:
    """The lead's verdict from its counts, in code.

    One requirement with no evidence is survivable — that is the interview
    question to prepare for. Two or more means the application is a lottery.
    """
    if missing == 0 and thin == 0:
        return "apply"
    if missing <= 1:
        return "gap story"
    return "skip"


def score(answer: dict, requirements: list[str]) -> dict:
    """Count the per-requirement answers into one verdict row."""
    probabilities: dict[str, float] = {}
    for option in requirement_options(requirements):
        key = f"covers_{option['name']}"
        probabilities[option["requirement"]] = answer["answers"][key]["noul"]
    by_class = {"met": [], "thin": [], "missing": []}
    for requirement, probability in probabilities.items():
        by_class[classify(probability)].append((requirement, probability))
    for group in by_class.values():
        group.sort(key=lambda pair: pair[1])
    return {
        "probabilities": probabilities,
        "met": by_class["met"],
        "thin": by_class["thin"],
        "missing": by_class["missing"],
        "mean": sum(probabilities.values()) / len(probabilities),
        "verdict": verdict_for(len(by_class["missing"]), len(by_class["thin"])),
    }


# ── Jev ──────────────────────────────────────────────────────────────────────


def post_systemone(payload: dict) -> dict:
    """POST one request to TypeSafe. Raises RuntimeError on any failure."""
    key = os.environ.get(API_KEY_ENV)
    if not key:
        raise RuntimeError(f"{API_KEY_ENV} is not set; no model call was made")
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"TypeSafe returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"TypeSafe request failed: {exc.reason}") from exc
    except ValueError as exc:
        raise RuntimeError(f"TypeSafe returned a non-JSON body: {exc}") from exc


# ── Entry point ──────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None, client=post_systemone) -> int:
    parser = argparse.ArgumentParser(description="Judge job leads with Jev.")
    parser.add_argument("--payload", action="store_true", help="print requests, no call")
    parser.add_argument("--company", help="only this company (case-insensitive match)")
    parser.add_argument("--limit", type=int, help="judge at most N leads")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    parser.add_argument("-v", "--verbose", action="store_true", help="every requirement")
    args = parser.parse_args(argv)

    leads = load_leads()
    if args.company:
        wanted = args.company.lower()
        leads = [lead for lead in leads if wanted in str(lead.get("company", "")).lower()]
    if args.limit:
        leads = leads[: args.limit]

    print(f"Job leads — {MODEL}, judged against the resume named on each row")
    if not leads:
        print("No lead in the tracker carries a `requirements:` list; nothing to judge.")
        return 0

    rows: list[dict] = []
    errors: list[str] = []

    for lead in leads:
        label = f"{lead.get('company')} — {lead.get('role')}"
        path = resume_path_for(lead)
        if path is None:
            print(f"  ! {label}: no resume markdown for {lead.get('resume')!r}", file=sys.stderr)
            errors.append(label)
            continue
        payload = redact(build_payload(lead, parse_resume(path.read_text(encoding="utf-8"))))
        if args.payload:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            continue
        try:
            answer = client(payload)
        except RuntimeError as exc:
            errors.append(f"{label}: {exc}")
            continue
        try:
            details = score(answer, list(lead["requirements"]))
        except (KeyError, TypeError) as exc:
            errors.append(f"{label}: unusable answer ({exc})")
            continue
        rows.append({
            "company": lead.get("company"),
            "role": lead.get("role"),
            "priority": lead.get("priority"),
            "resume": path.name,
            **details,
        })

    if args.payload:
        return 0

    if errors:
        for message in errors:
            print(f"  ! {message}", file=sys.stderr)
        print("\nNo verdict for the leads above.", file=sys.stderr)

    # Best first: fewest requirements with no evidence, then the strongest
    # average, then the fewest thin ones.
    rows.sort(
        key=lambda row: (
            len(row["missing"]),
            -round(row["mean"], 3),
            len(row["thin"]),
            str(row["company"]),
        )
    )
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 3 if errors else 0

    for index, row in enumerate(rows, start=1):
        total = len(row["probabilities"])
        print(
            f"\n{index}. {row['company']} — {row['role']}  "
            f"({row['priority']} priority)  ->  {row['verdict']}"
        )
        print(
            f"   met {len(row['met'])}/{total} (mean {row['mean']:.2f}); "
            f"thin {len(row['thin'])}, missing {len(row['missing'])}"
        )
        for requirement, probability in row["missing"]:
            print(f"   missing: {requirement}  ({probability:.2f})")
        for requirement, probability in row["thin"]:
            print(f"   thin:    {requirement}  ({probability:.2f})")
        if args.verbose:
            for requirement, probability in row["met"]:
                print(f"   met:     {requirement}  ({probability:.2f})")
    print(
        f"\nJudged {len(rows)} lead(s), one question per requirement. "
        f"Bands: {MATCH_YES:.1f}+ met, {MATCH_NO:.1f} or below missing. "
        "Verdict: no missing and nothing thin -> apply; at most one missing -> "
        "gap story; more -> skip."
    )
    return 3 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
