#!/usr/bin/env python3
"""Triage the TASKS.md Inbox with Jev, filing each item under a section.

Jev makes the judgement (does an existing section cover this item, and which
one); the filing itself is code, so the truth table below is visible and
testable. Item wording is never rewritten: a filed line is the same character
string that sat in the Inbox.

    python3 dashboard-app/triage_jev.py            # file items, edit TASKS.md
    python3 dashboard-app/triage_jev.py --dry-run  # call Jev, print, no write
    python3 dashboard-app/triage_jev.py --payload  # print the request, no call

Exit codes: 0 filed or nothing to do, 2 not configured, 3 API failure.
A failure never writes TASKS.md and never reads as "no section fits".
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

WORKSPACE = Path(__file__).resolve().parent.parent
TASKS_FILE = WORKSPACE / "TASKS.md"

API_URL = "https://api.typesafe.ai/v1/systemone"
API_KEY_ENV = "TYPESAFE_API_KEY"
MODEL = "jev-latest"

# A Noul's probability of yes. 0.7/0.3 are the starting pair from the TypeSafe
# guidance: above 0.7 reads as yes, below 0.3 as no, and the band between means
# the state does not settle it, which gets its own row in the truth table.
NOUL_YES = 0.7
NOUL_NO = 0.3
# A Choice's top probability below this means the sections split the answer, so
# code holds the item rather than picking the plurality winner.
CHOICE_MIN = 0.5

HEADING_RE = re.compile(r"^(#{2,3})\s+(.*?)\s*$")
CHECKBOX_RE = re.compile(r"^\s*-\s*\[[ xX]\]\s+(.*?)\s*$")
UNCHECKED_RE = re.compile(r"^\s*-\s*\[ \]\s+")


# ── Reading TASKS.md ─────────────────────────────────────────────────────────


def section_end(lines: list[str], start: int) -> int:
    """Index of the line that closes the section opened at `start`.

    Any level-2 or level-3 heading, or a `---` divider, closes a section.
    """
    for j in range(start + 1, len(lines)):
        stripped = lines[j].strip()
        if stripped == "---" or HEADING_RE.match(lines[j]):
            return j
    return len(lines)


def find_heading(lines: list[str], heading: str, level: int) -> int:
    """Index of an exact `#* heading` line; -1 when TASKS.md has no such line."""
    want = f"{'#' * level} {heading}"
    for i, line in enumerate(lines):
        if line.rstrip() == want:
            return i
    return -1


def item_text(line: str) -> str:
    """The task text of a checkbox line, with its checkbox stripped."""
    match = CHECKBOX_RE.match(line)
    return match.group(1) if match else line.strip()


def inbox_lines(lines: list[str]) -> list[int]:
    """Line indexes of the unchecked items inside the '## Inbox' section."""
    start = find_heading(lines, "Inbox", 2)
    if start < 0:
        return []
    end = section_end(lines, start)
    return [i for i in range(start + 1, end) if UNCHECKED_RE.match(lines[i])]


def slug(text: str) -> str:
    """A content-describing option name derived from a heading.

    Option names are sent to the model, so they carry the heading's words
    rather than a position: `security_pstools_secrets_exposure`.
    """
    asciiish = "".join(ch if ch.isascii() else " " for ch in text).lower()
    words = re.findall(r"[a-z0-9]+", asciiish)
    return "_".join(words)[:48].strip("_") or "section"


def destinations(lines: list[str]) -> list[dict]:
    """Every level-3 section, as its heading only.

    Heading text is what a person triaging would read, and it is the part of
    TASKS.md that carries no credentials and no employer-private detail. The
    items already filed under a heading, and the prose around them, are
    deliberately not sent: this file holds a secrets exposure and employer
    tasking, and none of it is needed to judge where an item goes.
    """
    out: list[dict] = []
    seen: dict[str, int] = {}
    for line in lines:
        match = HEADING_RE.match(line)
        if not match or match.group(1) != "###":
            continue
        heading = match.group(2).strip()
        name = slug(heading)
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:  # duplicate headings must stay distinct options
            name = f"{name}_{seen[name]}"
        out.append({"name": name, "heading": heading})
    return out


# ── The questions ────────────────────────────────────────────────────────────


def build_payload(text: str, sections: list[dict]) -> dict:
    """One request per item: Jev never sees items it is not judging."""
    criteria = {section["name"]: section["heading"] for section in sections}
    return {
        "model": MODEL,
        "state": {
            "task_file": (
                "TASKS.md, a personal task list. Its 'Inbox' section holds "
                "captured items that have not been filed under a section yet."
            ),
            "item_to_file": {"text": text},
            "destinations": sections,
        },
        "questions": {
            "fits_existing_section": {
                "type": "noul",
                "instructions": (
                    "Does one of the sections in `destinations` cover the work "
                    "described in `item_to_file.text`?"
                ),
                "criteria": {
                    "true": (
                        "One of the sections in `destinations` is where this task "
                        "would be worked on."
                    ),
                    "false": (
                        "None of the sections in `destinations` is about this work; "
                        "it would need a section that does not exist yet."
                    ),
                },
            },
            "best_section": {
                "type": "choice",
                "instructions": (
                    "Which section in `destinations` is the closest home for "
                    "`item_to_file.text`?"
                ),
                "criteria": criteria,
            },
        },
    }


def closest(choice: dict, count: int = 2) -> str:
    """The strongest options and their probabilities, for the run log."""
    ranked = sorted(choice["probabilities"].items(), key=lambda kv: kv[1], reverse=True)
    return " vs ".join(f"{name} {prob:.2f}" for name, prob in ranked[:count])


def decide(answer: dict) -> tuple[str, dict]:
    """The truth table, in code. Returns (verdict, details).

    verdict is "file" with details["section"] naming the option, or "hold"
    with details["reason"] saying which question did not settle it.
    """
    fits = answer["answers"]["fits_existing_section"]["noul"]
    choice = answer["answers"]["best_section"]
    details = {
        "fits": fits,
        "section": choice["choice"],
        "confidence": choice["confidence"],
        "probabilities": choice["probabilities"],
        "closest": closest(choice),
    }
    if fits <= NOUL_NO:
        details["reason"] = "no existing section covers it"
        return "hold", details
    if fits < NOUL_YES:
        details["reason"] = (
            f"unsettled whether a section fits (noul {fits:.2f}); "
            f"closest: {details['closest']}"
        )
        return "hold", details
    if choice["confidence"] < CHOICE_MIN:
        details["reason"] = f"sections split ({details['closest']})"
        return "hold", details
    return "file", details


# ── Editing TASKS.md ─────────────────────────────────────────────────────────


def apply_moves(text: str, moves: list[tuple[str, str]]) -> str:
    """Remove each moved line from Inbox and append it to its section.

    Lines are edited in place, so every other character of TASKS.md — prose,
    comments, checked items, blank lines — is left exactly as it was. The
    '## Inbox' heading survives an empty Inbox.
    """
    lines = text.split("\n")
    pending = {line: heading for line, heading in moves}
    # Drop each moved line, and one of the blanks it leaves behind when it was
    # the only content between two blank lines (an emptied Inbox would
    # otherwise gain a third newline).
    kept: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index] in pending:
            if (
                kept
                and not kept[-1].strip()
                and index + 1 < len(lines)
                and not lines[index + 1].strip()
            ):
                index += 1
            index += 1
            continue
        kept.append(lines[index])
        index += 1
    lines = kept

    for line, heading in moves:
        start = find_heading(lines, heading, 3)
        if start < 0:
            continue
        end = section_end(lines, start)
        last = start
        for j in range(start + 1, end):
            if lines[j].strip():
                last = j
        if CHECKBOX_RE.match(lines[last]):
            lines.insert(last + 1, line)
        else:  # after prose: new task list, separated by one blank line
            lines[last + 1 : last + 1] = ["", line]
    return "\n".join(lines)


# ── Jev ──────────────────────────────────────────────────────────────────────


def post_systemone(payload: dict) -> dict:
    """POST one request to TypeSafe. Raises RuntimeError on any failure."""
    key = os.environ.get(API_KEY_ENV)
    if not key:
        raise RuntimeError(f"{API_KEY_ENV} is not set; no model call was made")
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            # Text-only requests stay out of the image/long-context zones.
        },
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
    parser = argparse.ArgumentParser(description="File the TASKS.md Inbox with Jev.")
    parser.add_argument("--dry-run", action="store_true", help="call Jev, write nothing")
    parser.add_argument("--payload", action="store_true", help="print requests, no call")
    args = parser.parse_args(argv)

    text = TASKS_FILE.read_text(encoding="utf-8")
    lines = text.split("\n")
    sections = destinations(lines)
    items = [item_text(lines[i]) for i in inbox_lines(lines)]
    item_lines = [lines[i] for i in inbox_lines(lines)]

    print(f"Triage inbox — {MODEL} over {len(sections)} sections")
    if not items:
        print("Inbox is empty; nothing to file.")
        return 0
    print(
        f"Inbox: {len(items)} unchecked item(s). Sent to TypeSafe: each item's "
        "text and the section headings only — no section contents.\n"
    )

    moves: list[tuple[str, str]] = []
    verdicts: list[tuple[str, str, dict]] = []
    errors: list[str] = []

    for line, item in zip(item_lines, items):
        payload = build_payload(item, sections)
        if args.payload:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            continue
        try:
            answer = client(payload)
        except RuntimeError as exc:
            errors.append(f"{item}: {exc}")
            continue
        try:
            verdict, details = decide(answer)
        except (KeyError, TypeError) as exc:
            errors.append(f"{item}: unusable answer ({exc})")
            continue
        if verdict == "file":
            heading = next(
                s["heading"] for s in sections if s["name"] == details["section"]
            )
            moves.append((line, heading))
            verdicts.append((item, heading, details))
        else:
            verdicts.append((item, "", details))

    if args.payload:
        return 0

    if errors:
        # An API failure is reported as a failure, never as "no section fits".
        for message in errors:
            print(f"  ! {message}", file=sys.stderr)
        print("\nNo file was changed.", file=sys.stderr)
        return 3

    for item, heading, details in verdicts:
        if heading:
            print(f"- {item}\n    -> {heading}  (noul {details['fits']:.2f}, choice {details['confidence']:.2f})")
        else:
            print(f"- {item}\n    -> stays in Inbox — {details['reason']}")

    if not moves:
        print("\nNothing moved.")
        return 0
    if args.dry_run:
        print(f"\nDry run: {len(moves)} item(s) would move; TASKS.md unchanged.")
        return 0

    TASKS_FILE.write_text(apply_moves(text, moves), encoding="utf-8")
    print(f"\nMoved {len(moves)} item(s) in TASKS.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
