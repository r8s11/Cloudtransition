"""Explicit completed work-search activities in the existing application tracker."""
from datetime import date, timedelta
import re
from uuid import UUID

import yaml

FIELDS = (
    ("date", "Date of Activity", 10),
    ("activity_type", "Type of Activity", 200),
    ("description", "Activity Description", 1000),
    ("position", "Position applied for", 200),
    ("employer", "Business / Employer name", 200),
    ("address", "Employer address", 1000),
    ("result", "Result of your contact", 1000),
)
SECTION = "work_search_activities"


def records(data: dict) -> list[dict]:
    rows = data.get(SECTION, [])
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Work-search records are malformed; repair the tracker before saving.")
    return rows


def report(data: dict, start: date) -> dict:
    end = start + timedelta(days=6)
    activities = []
    for row in records(data):
        try:
            day = date.fromisoformat(str(row.get("date", "")))
        except ValueError:
            raise ValueError("A work-search activity has an invalid date; repair the tracker.") from None
        if not start <= day <= end:
            continue
        activity = {key: str(row.get(key) or "") for key, _, _ in FIELDS}
        activity["id"] = str(row.get("id") or "")
        activity["missing"] = [label for key, label, _ in FIELDS if not activity[key].strip()]
        display = dict(activity, date=day.strftime("%m/%d/%Y"))
        activity["fields"] = [
            {"label": label, "value": display[key]}
            for key, label, _ in FIELDS if key not in {"employer", "address", "result"}
        ] + [
            {"label": "Business / Employer name and address",
             "value": "\n".join(value for value in (activity["employer"], activity["address"]) if value)},
            {"label": "Result of your contact", "value": activity["result"]},
        ]
        activity["text"] = "\n".join([
            f"Date of Activity: {display['date']}",
            f"Type of Activity: {activity['activity_type'] or 'Not recorded'}",
            f"Activity Description: {activity['description'] or 'Not recorded'}",
            f"Position applied for: {activity['position'] or 'Not recorded'}",
            f"Business / Employer name and address: {activity['employer'] or 'Not recorded'}\n{activity['address'] or 'Employer address: Not recorded'}",
            f"Result of your contact: {activity['result'] or 'Not recorded'}",
        ])
        activities.append(activity)
    activities.sort(key=lambda row: (row["date"], row["employer"].casefold(), row["id"]))
    heading = f"Work Search Activity Report\n{start.strftime('%m/%d/%Y')} – {end.strftime('%m/%d/%Y')}"
    return {
        "start": start.isoformat(), "end": end.isoformat(), "activities": activities,
        "text": heading + ("\n\n" + "\n\n".join(row["text"] for row in activities) if activities else "\n\nNo completed activities recorded for this period."),
    }


def save(text: str, values: dict, today: date | None = None) -> str:
    """Upsert only our YAML block; leave all application prose and comments intact."""
    today = today or date.today()
    try:
        activity_id = str(UUID(values.get("id", "")))
    except (ValueError, AttributeError, TypeError):
        raise ValueError("Activity ID must be a UUID.") from None
    row = {"id": activity_id}
    for key, label, maximum in FIELDS:
        value = str(values.get(key) or "").strip()
        if len(value) > maximum:
            raise ValueError(f"{label} must be {maximum} characters or fewer.")
        row[key] = value
    for key in ("date", "activity_type", "description", "employer"):
        if not row[key]:
            raise ValueError(f"{key.replace('_', ' ').capitalize()} is required.")
    try:
        day = date.fromisoformat(row["date"])
    except ValueError:
        raise ValueError("Activity date must be YYYY-MM-DD.") from None
    if day.isoformat() != row["date"] or day > today:
        raise ValueError("Use a YYYY-MM-DD date for an activity already completed, not a future date.")
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError("Application tracker must be a YAML mapping.")
    rows = records(data)
    matches = [i for i, existing in enumerate(rows) if existing.get("id") == activity_id]
    if len(matches) > 1:
        raise ValueError("Duplicate activity IDs; repair the tracker before saving.")
    if matches:
        rows[matches[0]] = row
    else:
        rows.append(row)
    block = yaml.safe_dump({SECTION: rows}, allow_unicode=True, sort_keys=False)
    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if re.match(rf"^{SECTION}\s*:", line)]
    if len(starts) > 1:
        raise ValueError("Duplicate work-search sections; repair the tracker before saving.")
    if starts:
        start = starts[0]
        end = next((i for i in range(start + 1, len(lines)) if lines[i].strip()
                    and not lines[i][0].isspace() and not lines[i].startswith(("#", "- "))), len(lines))
        # Trailing whitespace and comments belong to the following section.
        while end > start + 1 and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
            end -= 1
        lines[start:end] = [block]
        updated = "".join(lines)
    else:
        updated = text + ("" if text.endswith("\n") else "\n") + "\n" + block
    parsed = yaml.safe_load(updated)
    if parsed.get(SECTION) != rows:
        raise ValueError("Could not safely update work-search records.")
    return updated
