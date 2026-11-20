"""Explicit, privacy-checked schedules from named dashboard sources only.

Schedule annotations carry a local opaque identity. Public schedules never include it.
This module only returns changed source text; the caller owns locking and atomic writes.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from kb_privacy import contains_private_key, is_excluded_path, is_secret_path, redact
from core.workspace_content import privacy_violation


class CalendarSourceError(ValueError):
    """A safe source validation error, without source text or parser details."""


_DAY = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}\Z")
_ID = re.compile(r"(?:[0-9a-f]{32}|[0-9a-f]{64})\Z")
_META = re.compile(r"<!--\s*calendar\s*:\s*(.*?)\s*-->", re.DOTALL)
_META_START = re.compile(r"<!--\s*calendar\s*:")
_BOX = re.compile(r"^(\s*- \[)([ xX])(\] )(.+)$")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
_FIELDS = {"date", "start", "end", "timezone"}


def _require(ok, message):
    if not ok:
        raise CalendarSourceError(message)


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_schedule(value):
    """Return a strict date-only or complete local-time schedule; {} stays local."""
    _require(type(value) is dict, "Schedule must be an object.")
    if not value:
        return {}
    if set(value) == {"date"}:
        day = value["date"]
        _require(isinstance(day, str) and _DAY.fullmatch(day), "Choose a YYYY-MM-DD date.")
        try:
            date.fromisoformat(day)
        except ValueError:
            raise CalendarSourceError("Choose a valid calendar date.") from None
        return {"date": day}
    _require(set(value) == {"start", "end", "timezone"},
             "Use either a date or start, end and timezone together.")
    zone = value["timezone"]
    _require(isinstance(zone, str) and zone and not zone.startswith(("/", ".", "posix/", "right/"))
             and zone not in {"localtime", "posixrules"} and ".." not in zone.split("/"),
             "Choose an IANA timezone.")
    try:
        tz = ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        raise CalendarSourceError("Choose a known IANA timezone.") from None
    moments = []
    for field in ("start", "end"):
        raw = value[field]
        _require(isinstance(raw, str) and _TIME.fullmatch(raw),
                 "Use explicit YYYY-MM-DDTHH:MM start and end times.")
        try:
            local = datetime.fromisoformat(raw)
        except ValueError:
            raise CalendarSourceError("Choose valid start and end times.") from None
        candidates = set()
        for fold in (0, 1):
            aware = local.replace(tzinfo=tz, fold=fold)
            instant = aware.astimezone(timezone.utc)
            if instant.astimezone(tz).replace(tzinfo=None) == local:
                candidates.add(instant)
        _require(len(candidates) == 1,
                 "Time is nonexistent or ambiguous at daylight-saving change; choose another time.")
        moments.append(next(iter(candidates)))
    _require(moments[1] > moments[0], "End time must be after start time.")
    return {"start": value["start"], "end": value["end"], "timezone": zone}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "Calendar metadata contains duplicate fields.")
        result[key] = value
    return result


def _metadata(raw):
    _require(isinstance(raw, str), "Task text must be a string.")
    matches = list(_META.finditer(raw))
    _require(len(matches) == len(_META_START.findall(raw)) and len(matches) <= 1,
             "Calendar metadata is malformed or repeated.")
    if not matches:
        return raw.strip(), {}, None
    match = matches[0]
    try:
        payload = json.loads(match[1], object_pairs_hook=_unique_object)
    except (ValueError, TypeError):
        raise CalendarSourceError("Calendar metadata must be valid JSON.") from None
    _require(type(payload) is dict and set(payload) <= _FIELDS | {"id"},
             "Calendar metadata has unsupported fields.")
    identity = payload.get("id")
    _require(identity is None or isinstance(identity, str) and _ID.fullmatch(identity),
             "Calendar source identity is malformed.")
    schedule = validate_schedule({k: v for k, v in payload.items() if k != "id"})
    return (raw[:match.start()] + raw[match.end():]).strip(), schedule, identity


def split_metadata(raw):
    """Hide only calendar metadata; reject malformed metadata without guessing."""
    title, schedule, _ = _metadata(raw)
    return title, schedule


def annotate(text, schedule):
    """Replace calendar metadata, preserving other comments and any existing identity."""
    schedule = validate_schedule(schedule)
    title, _, identity = _metadata(text)
    if schedule:
        _title(title)
    if not schedule and not identity and not _META.search(text):
        return text
    return _annotate(text, schedule, identity or uuid.uuid4().hex)


def _annotate(text, schedule, identity):
    matches = list(_META.finditer(text))
    payload = {"id": identity, **schedule}
    annotation = "<!-- calendar: " + json.dumps(payload, ensure_ascii=False,
                                               separators=(",", ":")) + " -->"
    if matches:
        match = matches[0]
        return text[:match.start()] + annotation + text[match.end():]
    return text + ("" if not text or text[-1].isspace() else " ") + annotation


def _title(text):
    _require(isinstance(text, str) and not contains_private_key(text),
             "Private key material cannot be scheduled.")
    # Comments are local annotations, not outgoing task titles.
    title = redact(re.sub(r"<!--[\s\S]*?-->", "", text)).strip()
    _require(bool(title) and len(title) <= 1024 and len(text) <= 1024,
             "Task title must contain 1–1024 characters.")
    _require(not any(ord(char) < 32 for char in title), "Task title must be one line.")
    return title


def _source_path(workspace, configured):
    root = Path(workspace).resolve()
    path = Path(configured)
    if path.is_absolute():
        try:
            relative = path.relative_to(root)
        except ValueError:
            raise CalendarSourceError("Source must stay inside the workspace.") from None
    else:
        relative = path
    _require(relative.parts and not any(p in ("..", ".") for p in relative.parts)
             and "\\" not in str(relative), "Source path is not allowed.")
    rel = relative.as_posix()
    _require(not privacy_violation(rel) and not is_secret_path(rel) and not is_excluded_path(rel),
             "Source is excluded by workspace privacy rules.")
    current = root
    for part in relative.parts:
        current = current / part
        _require(not current.is_symlink(), "Symlink sources are not allowed.")
    _require(current.resolve().is_relative_to(root), "Source must stay inside the workspace.")
    _require(current.is_file(), "Source file is unavailable.")
    return current, rel


def source_choices(workspace, realms, jobs_file):
    """List only configured realm files and the configured interview tracker."""
    choices, seen = [], set()
    for config in [*realms, {"id": "interviews", "name": "Interview next actions", "file": jobs_file}]:
        identity = config.get("id")
        _require(isinstance(identity, str) and re.fullmatch(r"[a-zA-Z0-9_-]+", identity)
                 and identity not in seen, "Source registry has an invalid or repeated id.")
        seen.add(identity)
        configured = str(config.get("file", ""))
        path = Path(configured)
        file = configured
        if path.is_absolute():
            try:
                file = path.relative_to(Path(workspace).resolve()).as_posix()
            except ValueError:
                file = ""
        choice = {"id": identity, "name": str(config.get("name", identity)),
                  "file": file, "available": False, "reason": ""}
        try:
            _, choice["file"] = _source_path(workspace, configured)
            choice["available"] = True
        except (CalendarSourceError, OSError, ValueError) as exc:
            choice["reason"] = str(exc) if isinstance(exc, CalendarSourceError) else "Source file is unavailable."
        choices.append(choice)
    return choices


def _selected(workspace, realms, jobs_file, source_ids):
    _require(isinstance(source_ids, (list, tuple)) and all(isinstance(x, str) for x in source_ids)
             and len(source_ids) == len(set(source_ids)), "Choose named source ids only.")
    choices = {c["id"]: c for c in source_choices(workspace, realms, jobs_file)}
    selected, files = [], set()
    for identity in source_ids:
        _require(identity in choices, "Unknown calendar source.")
        choice = choices[identity]
        _require(choice["available"], choice["reason"] or "Source is unavailable.")
        path, rel = _source_path(workspace, choice["file"])
        if rel not in files:
            selected.append((identity, path, rel))
            files.add(rel)
    return selected


def _read(path):
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise CalendarSourceError("Cannot read the selected source.") from None


def _markdown(text):
    fence = None
    for line, raw in enumerate(text.splitlines(), 1):
        marker = _FENCE.match(raw)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
            continue
        if marker:
            fence = (marker[1][0], len(marker[1]))
            continue
        box = _BOX.match(raw)
        if box:
            yield line, box, box[4]


def _pairs(node, relevant=None):
    _require(isinstance(node, MappingNode), "Tracker action must use a YAML mapping.")
    result = {}
    for key, value in node.value:
        _require(isinstance(key, ScalarNode) and (
            key.value not in result or relevant is not None and key.value not in relevant
        ), "Tracker contains duplicate or unsupported keys.")
        result[key.value] = (key, value)
    return result


def _tracker(text):
    try:
        _require(not any(isinstance(event, yaml.events.AliasEvent) for event in yaml.parse(text)),
                 "Tracker aliases cannot be scheduled safely.")
        root = yaml.compose(text)
        root_fields = _pairs(root, {"active_applications"})
        apps_node = root_fields.get("active_applications", (None, None))[1]
        if apps_node is None:
            return []
        _require(isinstance(apps_node, SequenceNode), "Tracker applications must be a list.")
        apps = yaml.safe_load(text).get("active_applications")
        identities = Counter((a.get("company"), a.get("role")) for a in apps if isinstance(a, dict)
                             and isinstance(a.get("company"), str) and isinstance(a.get("role"), str))
        result = []
        for app, node in zip(apps, apps_node.value, strict=True):
            try:
                fields = _pairs(node, {"company", "role", "next_steps"})
            except CalendarSourceError:
                # An ambiguous application must not block unrelated local actions.
                continue
            company, role = app.get("company"), app.get("role")
            if not isinstance(company, str) or not isinstance(role, str):
                continue
            next_node = fields.get("next_steps", (None, None))[1]
            if next_node is None or next_node.tag == "tag:yaml.org,2002:null":
                continue
            _require(isinstance(next_node, SequenceNode), "Tracker next actions must be a list.")
            steps = app.get("next_steps")
            for index, (step, step_node) in enumerate(zip(steps, next_node.value, strict=True)):
                if not isinstance(step_node, MappingNode):
                    continue
                try:
                    step_fields = _pairs(step_node, {"task", "calendar_id", *_FIELDS})
                except CalendarSourceError:
                    continue
                if not isinstance(step, dict) or not isinstance(step.get("task"), str):
                    continue
                result.append({"company": company, "role": role, "index": index,
                               "step": step, "node": step_node, "fields": step_fields,
                               "ambiguous": identities[(company, role)] > 1})
        return result
    except (yaml.YAMLError, TypeError, AttributeError, ValueError) as exc:
        if isinstance(exc, CalendarSourceError):
            raise
        raise CalendarSourceError("Tracker YAML cannot be scheduled safely.") from None


def _step_schedule(step):
    value = {k: (v.isoformat() if type(v) is date else v)
             for k, v in step.items() if k in _FIELDS and v is not None and v != ""}
    return validate_schedule(value)


def _item(source, rel, title, schedule, opaque, fallback, location):
    safe = _title(title)
    binding = {"file": rel, "title": safe, "schedule": schedule, "content": _digest(title),
               "identity": opaque}
    key = opaque if opaque and len(opaque) == 64 else _digest(
        [rel, "id", opaque] if opaque else [rel, "title", fallback])
    return {"key": key,
            "binding": binding, "title": safe, "schedule": schedule, "source": source,
            "location": {**location, "text": safe, "binding": binding},
            "status": "eligible" if schedule else "needs_date"}


def collect(workspace, realms, jobs_file, source_ids):
    """Read allowed source actions, with no notes, contacts or adjacent source content."""
    items = []
    for source, path, rel in _selected(workspace, realms, jobs_file, source_ids):
        text = _read(path)
        if source == "interviews":
            try:
                actions = _tracker(text)
            except CalendarSourceError:
                continue
            for action in actions:
                step = action["step"]
                if step.get("done") is True or step.get("completed") is True:
                    continue
                try:
                    schedule = _step_schedule(step)
                    opaque = step.get("calendar_id")
                    _require(opaque is None or isinstance(opaque, str) and _ID.fullmatch(opaque),
                             "Calendar source identity is malformed.")
                    title = step["task"]
                    items.append(_item(source, rel, title, schedule, opaque,
                                       [action["company"], action["role"], title],
                                       {"source": source, "company": action["company"],
                                        "role": action["role"], "index": action["index"]}))
                    if action["ambiguous"]:
                        items[-1]["status"] = "needs_review"
                except CalendarSourceError:
                    continue
        else:
            for line, box, raw in _markdown(text):
                if box[2] != " ":
                    continue
                try:
                    title, schedule, opaque = _metadata(raw)
                    items.append(_item(source, rel, title, schedule, opaque, title,
                                       {"source": source, "line": line}))
                except CalendarSourceError:
                    continue
    counts = Counter(item["key"] for item in items)
    for item in items:
        if counts[item["key"]] > 1:
            item["status"] = "needs_review"
    return items


def _edit_step(text, action, schedule, identity):
    _require(not action["node"].flow_style, "Use block-style YAML for a scheduled next action.")
    lines = text.splitlines(keepends=True)
    newline = "\r\n" if "\r\n" in text else "\n"
    fields = action["fields"]
    values = {**{key: None for key in _FIELDS if key in fields}, **schedule}
    if identity is not None:
        values["calendar_id"] = identity
    additions = []
    for key, value in values.items():
        encoded = json.dumps(value, ensure_ascii=False)
        if key not in fields:
            additions.append(f"{' ' * action['node'].start_mark.column}{key}: {encoded}{newline}")
            continue
        key_node, value_node = fields[key]
        _require(isinstance(value_node, ScalarNode) and value_node.start_mark.line == key_node.start_mark.line
                 and value_node.end_mark.line == key_node.start_mark.line,
                 "Schedule fields must be single-line YAML scalars.")
        line = key_node.start_mark.line
        lines[line] = (lines[line][:key_node.end_mark.column + 1] + " " + encoded
                       + lines[line][value_node.end_mark.column:])
    if additions:
        last = max((value.end_mark for _, value in fields.values()), key=lambda mark: (mark.line, mark.column))
        at = last.line + (1 if last.column else 0)
        if at and not lines[at - 1].endswith(("\n", "\r")):
            lines[at - 1] += newline
        lines[at:at] = additions
    updated = "".join(lines)
    # Reparse rather than trusting line marks after the surgical write.
    changed = next((a for a in _tracker(updated) if a["company"] == action["company"]
                    and a["role"] == action["role"] and a["index"] == action["index"]), None)
    _require(changed is not None and _step_schedule(changed["step"]) == schedule
             and changed["step"].get("calendar_id") == identity,
             "Schedule edit could not be verified safely.")
    return updated


def schedule_item(workspace, realms, jobs_file, request_dict):
    """Return (Path, changed_text); perform no writes. Caller must hold its write lock."""
    _require(type(request_dict) is dict, "Invalid scheduling request.")
    source = request_dict.get("source")
    selected = _selected(workspace, realms, jobs_file, [source])
    _, path, rel = selected[0]
    schedule = validate_schedule(request_dict.get("schedule"))
    text = _read(path)
    requested = request_dict.get("text")
    _require(isinstance(requested, str), "Current task text is required.")
    available = collect(workspace, realms, jobs_file, [source])
    if source == "interviews":
        company, role, index = (request_dict.get(k) for k in ("company", "role", "index"))
        _require(isinstance(company, str) and isinstance(role, str) and type(index) is int and index >= 0,
                 "Choose an existing interview action.")
        actions = _tracker(text)
        # Duplicate application mappings must never be selected by list position.
        root = yaml.safe_load(text) or {}
        _require(sum(1 for a in root.get("active_applications", [])
                     if a.get("company") == company and a.get("role") == role) == 1,
                 "Application is missing or ambiguous.")
        matches = [a for a in actions if a["company"] == company and a["role"] == role and a["index"] == index]
        _require(len(matches) == 1 and matches[0]["step"]["task"] == requested,
                 "Interview action changed; reload before scheduling.")
        action = matches[0]
        found = [i for i in available if i["location"].get("company") == company
                 and i["location"].get("role") == role and i["location"].get("index") == index]
        _require(len(found) == 1 and found[0]["status"] != "needs_review",
                 "Action is unsafe or ambiguous; make it unique before scheduling.")
        _require("binding" not in request_dict or request_dict["binding"] == found[0]["binding"],
                 "Interview schedule changed; reload before scheduling.")
        return path, _edit_step(text, action, schedule, action["step"].get("calendar_id") or found[0]["key"])
    line = request_dict.get("line")
    _require(type(line) is int and line > 0, "Choose an existing task line.")
    rows = list(_markdown(text))
    matches = [(n, box, raw) for n, box, raw in rows if box[2] == " " and raw == requested]
    target = next((row for row in matches if row[0] == line), None)
    if target is None:
        _require(len(matches) == 1, "Task changed or became ambiguous; reload before scheduling.")
        target = matches[0]
    found = [i for i in available if i["location"].get("line") == target[0]]
    _require(len(found) == 1 and found[0]["status"] != "needs_review",
             "Task is unsafe or ambiguous; make it unique before scheduling.")
    _require("binding" not in request_dict or request_dict["binding"] == found[0]["binding"],
             "Task schedule changed; reload before scheduling.")
    lines = text.splitlines(keepends=True)
    original = lines[target[0] - 1]
    ending = original[len(original.rstrip("\r\n")):]
    opaque = _metadata(target[2])[2] or found[0]["key"]
    lines[target[0] - 1] = target[1][1] + target[1][2] + target[1][3] + _annotate(target[2], schedule, opaque) + ending
    return path, "".join(lines)


def pin_item(workspace, realms, jobs_file, item):
    """Return a verified identity-only source edit before the first remote intent.

    The service must hold the same source lock used by dashboard writes and persist
    this text atomically before publishing. Raw source text never leaves this helper.
    """
    _require(type(item) is dict and isinstance(item.get("location"), dict),
             "Choose an existing source item.")
    source = item.get("source")
    selected = _selected(workspace, realms, jobs_file, [source])
    _, path, _ = selected[0]
    current = [value for value in collect(workspace, realms, jobs_file, [source])
               if value["key"] == item.get("key") and value["binding"] == item.get("binding")]
    _require(len(current) == 1 and current[0]["status"] != "needs_review",
             "Source changed or became ambiguous; review before publishing.")
    found = current[0]
    text = _read(path)
    if found["binding"]["identity"]:
        return path, text
    request = {**found["location"], "schedule": found["schedule"]}
    if source == "interviews":
        actions = [action for action in _tracker(text)
                   if action["company"] == request["company"] and action["role"] == request["role"]
                   and action["index"] == request["index"]]
        _require(len(actions) == 1, "Interview action changed; review before publishing.")
        request["text"] = actions[0]["step"]["task"]
    else:
        rows = [raw for line, box, raw in _markdown(text)
                if line == request["line"] and box[2] == " "]
        _require(len(rows) == 1, "Task changed; review before publishing.")
        request["text"] = rows[0]
    return schedule_item(workspace, realms, jobs_file, request)


def edit_first_action(text, company, role, task, due):
    """Edit an existing first action without replacing siblings or opaque identity.

    Return None only when the application has no next actions, so the existing
    interview editor can create its normal block.
    """
    actions = _tracker(text)
    data = yaml.safe_load(text) or {}
    apps = [app for app in data.get("active_applications", [])
            if isinstance(app, dict) and app.get("company") == company and app.get("role") == role]
    _require(len(apps) == 1, "Application is missing or ambiguous.")
    if not apps[0].get("next_steps"):
        return None
    matches = [action for action in actions if action["company"] == company
               and action["role"] == role and action["index"] == 0]
    _require(len(matches) == 1, "First next action cannot be edited safely.")
    action = matches[0]
    _require(not action["node"].flow_style, "Use block-style YAML for a scheduled next action.")
    if due:
        schedule = validate_schedule({"date": due})
    else:
        current_schedule = _step_schedule(action["step"])
        schedule = current_schedule if "start" in current_schedule else {}
    key_node, value_node = action["fields"]["task"]
    _require(isinstance(value_node, ScalarNode) and value_node.start_mark.line == key_node.start_mark.line
             and value_node.end_mark.line == key_node.start_mark.line,
             "Next action title must use a single-line YAML scalar.")
    lines = text.splitlines(keepends=True)
    line = key_node.start_mark.line
    lines[line] = (lines[line][:key_node.end_mark.column + 1] + " " + json.dumps(task, ensure_ascii=False)
                   + lines[line][value_node.end_mark.column:])
    changed = "".join(lines)
    action = next(value for value in _tracker(changed) if value["company"] == company
                  and value["role"] == role and value["index"] == 0)
    return _edit_step(changed, action, schedule, action["step"].get("calendar_id"))
