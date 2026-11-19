"""Read-only Markdown selection and exact Google Tasks preview validation."""
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import re

from kb_privacy import contains_private_key, redact

_CHECKBOX = re.compile(r"^(\s*- \[)([ xX])(\] .+)$")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
_EMOJI = re.compile(r"^[\U0001F300-\U0001FAFF\u2600-\u27BF\u2702-\u27B0]+\s*")
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
MARKER_PREFIX = "cloudtransition-checklist:"


class CalendarError(ValueError):
    """Safe local validation error, never a provider response or task body."""


def _require(condition, message):
    if not condition:
        raise CalendarError(message)


def _fields(value, expected):
    _require(type(value) is dict and set(value) == set(expected), "Invalid preview fields; create a new preview.")


def _canonical(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise CalendarError("Invalid preview encoding.") from None


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _scheduled_day(value):
    _require(isinstance(value, str) and _DAY.fullmatch(value) is not None, "Choose an explicit YYYY-MM-DD date for every item.")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise CalendarError("Invalid scheduled calendar day.") from None
    return value + "T00:00:00.000Z"


def list_items(source):
    """Return unchecked dashboard-style boxes, excluding fenced examples."""
    try:
        text = Path(source).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise CalendarError("Cannot read the selected checklist source.") from None
    items, heading, fence = [], "", None
    for line_number, line in enumerate(text.splitlines(), 1):
        match = _FENCE.match(line)
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= fence[1] and not match[2].strip():
                fence = None
            continue
        if match:
            fence = (match[1][0], len(match[1]))
            continue
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = _EMOJI.sub("", stripped.lstrip("#").strip()).strip()
            continue
        checkbox = _CHECKBOX.match(line)
        if checkbox and checkbox[2] == " ":
            items.append({"id": str(line_number), "line": line_number, "title": checkbox[3][2:], "heading": heading})
    return items


def _catalog(source):
    items = list_items(source)
    counts = Counter((item["heading"], item["title"]) for item in items)
    seen = defaultdict(int)
    for item in items:
        group = (item["heading"], item["title"])
        occurrence = seen[group]
        seen[group] += 1
        item["key"] = _digest([str(source), *group, occurrence])
        item["occurrence"] = occurrence
        item["count"] = counts[group]
    return items


def _snapshot(item):
    return {
        "line": item["line"], "title": redact(item["title"]), "heading": redact(item["heading"]),
        "occurrence": item["occurrence"], "count": item["count"],
    }


def _body(title, day, key):
    _require(not contains_private_key(title), "Private key material cannot be published.")
    title = re.sub(r"\s*<!--\s*calendar\s*:\s*.*?-->", "", title).strip()
    title = redact(title)
    _require(bool(title.strip()) and len(title) <= 1024, "Task title must contain 1–1024 characters.")
    return {"title": title, "due": _scheduled_day(day), "status": "needsAction", "notes": MARKER_PREFIX + key}


def make_preview(source, selections, tasklist):
    """Build a selected-only JSON value; perform no writes, login or network IO."""
    _require(isinstance(tasklist, str) and bool(tasklist.strip()) and tasklist == tasklist.strip(), "Choose an existing destination task-list ID.")
    _require(not any(ord(char) < 32 for char in tasklist), "Invalid destination task-list ID.")
    _require(isinstance(selections, list) and bool(selections), "Select at least one unchecked item.")
    source = Path(source).expanduser().resolve()
    catalog = {item["id"]: item for item in _catalog(source)}
    chosen, used = [], set()
    for selection in selections:
        _require(isinstance(selection, (list, tuple)) and len(selection) == 2, "Each selection requires LINE=YYYY-MM-DD.")
        identity, day = selection
        _require(isinstance(identity, str) and identity in catalog and identity not in used, "Selection is missing, checked, invalid or repeated; list the source again.")
        used.add(identity)
        item = catalog[identity]
        chosen.append({"key": item["key"], "source": _snapshot(item), "body": _body(item["title"], day, item["key"])})
    preview = {"version": 1, "source": str(source), "tasklist": tasklist, "items": chosen}
    preview["approval"] = _digest(preview)
    return preview


def validate_preview(preview):
    """Require exact approved fields and unchanged selected source identities."""
    _fields(preview, ("version", "source", "tasklist", "items", "approval"))
    _require(type(preview["version"]) is int and preview["version"] == 1, "Unsupported preview version.")
    _require(isinstance(preview["source"], str) and Path(preview["source"]).is_absolute(), "Preview requires an absolute source path.")
    tasklist = preview["tasklist"]
    _require(isinstance(tasklist, str) and bool(tasklist.strip()) and tasklist == tasklist.strip() and not any(ord(c) < 32 for c in tasklist), "Invalid destination task-list ID.")
    approval = preview["approval"]
    _require(isinstance(approval, str) and _HEX.fullmatch(approval) is not None, "Invalid approval fingerprint.")
    _require(approval == _digest({key: value for key, value in preview.items() if key != "approval"}), "Preview changed; review a new exact batch.")
    _require(isinstance(preview["items"], list) and bool(preview["items"]), "Preview must contain selected items.")
    source = Path(preview["source"])
    _require(str(source.resolve()) == str(source), "Source path changed; create a new preview.")
    catalog = {item["key"]: item for item in _catalog(source)}
    used = set()
    for entry in preview["items"]:
        _fields(entry, ("key", "source", "body"))
        key = entry["key"]
        _require(isinstance(key, str) and _HEX.fullmatch(key) is not None and key not in used, "Invalid or duplicate source identity.")
        used.add(key)
        _fields(entry["source"], ("line", "title", "heading", "occurrence", "count"))
        binding = entry["source"]
        _require(type(binding["line"]) is int and binding["line"] > 0, "Invalid source location.")
        _require(type(binding["count"]) is int and binding["count"] > 0 and type(binding["occurrence"]) is int and 0 <= binding["occurrence"] < binding["count"], "Invalid duplicate-source identity.")
        _require(isinstance(binding["title"], str) and isinstance(binding["heading"], str), "Invalid source fields.")
        current = catalog.get(key)
        _require(current is not None, "Selected source changed, disappeared or was checked; create a new preview.")
        snapshot = _snapshot(current)
        _require(all(binding[name] == snapshot[name] for name in binding if name != "line"), "Source contents or duplicate group changed; create a new preview.")
        _require(binding["count"] == 1 or binding["line"] == snapshot["line"], "Duplicate source moved ambiguously; select and preview again.")
        _fields(entry["body"], ("title", "due", "status", "notes"))
        body = entry["body"]
        _require(all(isinstance(value, str) for value in body.values()), "Invalid task payload types.")
        _require(len(body["notes"]) <= 8192 and len(body["due"]) == 24, "Invalid task payload bounds.")
        expected = _body(current["title"], body["due"][:10], key)
        _require(body == expected, "Task payload changed; create a new exact preview.")
