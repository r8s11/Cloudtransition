"""Line-targeted edits to interviews/job-applications.yml.

The tracker is hand-written YAML: comments, group headers and per-entry notes
are part of the file. Loading and re-dumping it would delete that, so every
edit here rewrites only the lines it owns. Each function returns new file text
and re-parses it as a guard, raising InterviewEditError instead of ever
handing back something PyYAML cannot read.

Entries are addressed by (company, role) — both are rendered in the UI and are
unique in the tracker. User-supplied scalars are written as JSON strings, which
are valid YAML double-quoted scalars; note bodies use block scalars so line
breaks survive.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date

import yaml

SECTION = "active_applications:"
STATUSES = (
    "new_lead",
    "applied",
    "screening",
    "assessment",
    "interviewing",
    "onsite",
    "offer",
    "rejected",
    "withdrawn",
)
PRIORITIES = ("high", "medium", "low")
MAX_TEXT = 4000

_FIELD_RE = re.compile(r"^    ([A-Za-z_][A-Za-z0-9_]*):(?:[ \t]*(.*))?$")
_BLOCK_MARKS = {"", "|", "|-", ">", ">-"}


class InterviewEditError(ValueError):
    """The edit could not be applied safely; nothing should be written."""


@dataclass
class Entry:
    start: int
    end: int
    company: str
    role: str
    field_lines: dict[str, int] = field(default_factory=dict)
    block_bounds: dict[str, tuple[int, int]] = field(default_factory=dict)


def _split(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def _section(lines: list[str]) -> tuple[int, int]:
    start = next(
        (i for i, line in enumerate(lines) if line.rstrip("\r\n") == SECTION), None
    )
    if start is None:
        raise InterviewEditError("active_applications: not found")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        line = lines[j]
        if line.strip() and not line[0].isspace() and not line.lstrip().startswith("#"):
            end = j
            break
    return start, end


def _entries(text: str) -> tuple[list[str], list[Entry]]:
    lines = _split(text)
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise InterviewEditError(f"tracker is not valid YAML: {exc}") from exc
    apps = data.get("active_applications") or []
    start, section_end = _section(lines)
    starts = [
        i for i in range(start + 1, section_end) if lines[i].startswith("  - ")
    ]
    if len(starts) != len(apps):
        raise InterviewEditError("could not map tracker entries to their lines")

    entries = []
    for idx, (entry_start, app) in enumerate(zip(starts, apps, strict=True)):
        end = starts[idx + 1] if idx + 1 < len(starts) else section_end
        content_end = end
        # Blank lines and group comments belong to what follows, not this entry.
        while content_end > entry_start and (
            not lines[content_end - 1].strip()
            or lines[content_end - 1].lstrip().startswith("#")
        ):
            content_end -= 1

        field_lines: dict[str, int] = {}
        blocks: dict[str, tuple[int, int]] = {}
        i = entry_start + 1
        while i < content_end:
            match = _FIELD_RE.match(lines[i].rstrip("\r\n"))
            if not match:
                i += 1
                continue
            key, value = match.group(1), (match.group(2) or "")
            field_lines[key] = i
            if value.strip() in _BLOCK_MARKS:
                j = i + 1
                while j < content_end and (
                    not lines[j].strip()
                    or len(lines[j]) - len(lines[j].lstrip()) > 4
                ):
                    j += 1
                # A blank line before the next key is spacing, not block content.
                while j > i + 1 and not lines[j - 1].strip():
                    j -= 1
                blocks[key] = (i + 1, j)
            i += 1

        entries.append(
            Entry(
                start=entry_start,
                end=content_end,
                company=str(app.get("company") or ""),
                role=str(app.get("role") or ""),
                field_lines=field_lines,
                block_bounds=blocks,
            )
        )
    return lines, entries


def _find(entries: list[Entry], company: str, role: str) -> Entry:
    matches = [e for e in entries if e.company == company and e.role == role]
    if not matches:
        raise InterviewEditError("application not found in the tracker")
    if len(matches) > 1:
        raise InterviewEditError("application is ambiguous; make company/role unique")
    return matches[0]


def _scalar(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _validate(text: str, company: str, role: str) -> dict:
    data = yaml.safe_load(text) or {}
    for app in data.get("active_applications") or []:
        if str(app.get("company")) == company and str(app.get("role")) == role:
            return app
    raise InterviewEditError("edit did not produce the expected application")


def _insert_before(entry: Entry, keys: tuple[str, ...]) -> int:
    for key in keys:
        if key in entry.field_lines:
            return entry.field_lines[key]
    return entry.end


def _check_text(value: str, label: str) -> str:
    value = (value or "").strip()
    if len(value) > MAX_TEXT:
        raise InterviewEditError(f"{label} is too long")
    return value


def set_field(text: str, company: str, role: str, key: str, value: str) -> str:
    """Set one scalar field (status, priority, location, …) on an entry."""
    if key not in {"status", "priority", "location", "salary_range"}:
        raise InterviewEditError("that field cannot be edited here")
    value = _check_text(value, key)
    if key == "status" and value not in STATUSES:
        raise InterviewEditError("unknown status")
    if key == "priority" and value not in PRIORITIES:
        raise InterviewEditError("unknown priority")

    lines, entries = _entries(text)
    entry = _find(entries, company, role)
    new_line = f"    {key}: {_scalar(value)}\n"
    if key in entry.field_lines:
        lines[entry.field_lines[key]] = new_line
    else:
        anchor = entry.field_lines.get("role", entry.field_lines.get("company", entry.start))
        lines.insert(anchor + 1, new_line)

    updated = "".join(lines)
    if str(_validate(updated, company, role).get(key) or "") != value:
        raise InterviewEditError("edit did not stick")
    return updated


def set_next_step(text: str, company: str, role: str, task: str, due: str) -> str:
    """Replace the entry's next_steps list with one action (optionally dated)."""
    task = _check_text(task, "next action")
    if not task:
        raise InterviewEditError("next action is empty")
    due = (due or "").strip()
    if due:
        _inter_date(due)

    lines, entries = _entries(text)
    entry = _find(entries, company, role)
    block = ["    next_steps:\n", f"      - task: {_scalar(task)}\n"]
    block.append(f"        date: {_scalar(due)}\n" if due else "        date:\n")

    if "next_steps" in entry.block_bounds:
        start, end = entry.block_bounds["next_steps"]
        lines[start:end] = block
    elif "next_steps" in entry.field_lines:
        idx = entry.field_lines["next_steps"]
        lines[idx : idx + 1] = block
    else:
        at = _insert_before(entry, ("notes", "interview_notes"))
        lines[at:at] = block

    updated = "".join(lines)
    steps = _validate(updated, company, role).get("next_steps") or []
    if not steps or steps[0].get("task") != task:
        raise InterviewEditError("next action did not stick")
    return updated


def append_timeline(
    text: str, company: str, role: str, when: str, stage: str, notes: str
) -> str:
    """Append one dated signal to the entry's timeline."""
    when = _inter_date(when).isoformat()
    stage = _check_text(stage, "stage")
    if not stage:
        raise InterviewEditError("stage is empty")
    notes = _check_text(notes, "notes")

    item = [f"      - date: {_scalar(when)}\n", f"        stage: {_scalar(stage)}\n"]
    if notes:
        item.append("        notes: |\n")
        item.extend(f"          {line}\n" for line in notes.splitlines())

    lines, entries = _entries(text)
    entry = _find(entries, company, role)
    if "timeline" in entry.block_bounds:
        _, end = entry.block_bounds["timeline"]
        lines[end:end] = item
    else:
        at = _insert_before(entry, ("next_steps", "notes", "interview_notes"))
        lines[at:at] = ["    timeline:\n", *item]

    updated = "".join(lines)
    timeline = _validate(updated, company, role).get("timeline") or []
    if not timeline or str(timeline[-1].get("date")) != when:
        raise InterviewEditError("timeline entry did not stick")
    return updated


# Keys the dashboard owns. `interview_prep` is deliberately absent: the tracker
# already uses it for a list of prep-file paths (Ground Up), and replacing that
# list with prose would delete it. Preparation prose gets its own key.
TEXT_BLOCKS = {
    "interview_notes": "notes",
    "interview_questions": "questions to ask",
    "interview_preparation": "preparation",
}


def set_text_block(text: str, company: str, role: str, key: str, value: str) -> str:
    """Store a free-form block on an entry (notes, questions, preparation).

    Each key stays separate from the hand-written job-fit `notes:` field, so the
    tracker's own prose survives anything typed in the dashboard.
    """
    if key not in TEXT_BLOCKS:
        raise InterviewEditError("that field cannot be edited here")
    lines, entries = _entries(text)
    entry = _find(entries, company, role)
    # `interview_prep:` holds a list of paths on some entries; a list must never
    # be turned into prose, so refuse instead of overwriting structured data.
    existing = _validate(text, company, role).get(key)
    if existing is not None and not isinstance(existing, str):
        raise InterviewEditError(f"{key} holds structured data; not overwriting it")
    value = (value or "").replace("\r\n", "\n").strip("\n")
    if len(value) > MAX_TEXT:
        raise InterviewEditError(f"{TEXT_BLOCKS[key]} is too long")
    block = (
        [f"    {key}: |\n"] + [f"      {line}\n" for line in value.split("\n")]
        if value
        else [f'    {key}: ""\n']
    )

    if key in entry.block_bounds:
        start, end = entry.block_bounds[key]
        lines[start:end] = block[1:]
    elif key in entry.field_lines:
        idx = entry.field_lines[key]
        lines[idx : idx + 1] = block
    else:
        at = _insert_before(entry, ("interview_notes", "notes"))
        lines[at:at] = block

    updated = "".join(lines)
    stored = _validate(updated, company, role).get(key) or ""
    if str(stored).strip("\n") != value:
        raise InterviewEditError(f"{TEXT_BLOCKS[key]} did not stick")
    return updated


def add_application(
    text: str,
    *,
    company: str,
    role: str,
    status: str = "new_lead",
    priority: str = "medium",
    location: str = "",
    salary_range: str = "",
    job_url: str = "",
    next_step: str = "",
    due: str = "",
) -> str:
    """Append a new application to the end of active_applications."""
    company = _check_text(company, "company")
    role = _check_text(role, "role")
    if not company or not role:
        raise InterviewEditError("company and role are required")
    if status not in STATUSES:
        raise InterviewEditError("unknown status")
    if priority not in PRIORITIES:
        raise InterviewEditError("unknown priority")
    due = (due or "").strip()
    if due:
        _inter_date(due)

    lines, entries = _entries(text)
    if any(e.company == company and e.role == role for e in entries):
        raise InterviewEditError("that application is already in the tracker")

    block = [
        f"  - company: {_scalar(company)}\n",
        f"    role: {_scalar(role)}\n",
        f"    status: {_scalar(status)}\n",
        f"    priority: {_scalar(priority)}\n",
    ]
    for key, value in (
        ("location", location),
        ("salary_range", salary_range),
        ("job_url", job_url),
    ):
        if (value or "").strip():
            block.append(f"    {key}: {_scalar(value.strip())}\n")
    if next_step.strip():
        block.append("    next_steps:\n")
        block.append(f"      - task: {_scalar(next_step.strip())}\n")
        block.append(f"        date: {_scalar(due)}\n" if due else "        date:\n")

    _, section_end = _section(lines)
    insert = section_end
    while insert > 0 and not lines[insert - 1].strip():
        insert -= 1
    lines[insert:insert] = ["\n", *block, "\n"]

    updated = "".join(lines)
    _validate(updated, company, role)
    return updated


def _inter_date(value: str) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise InterviewEditError("date must be YYYY-MM-DD") from exc
