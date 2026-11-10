"""Read-only views of the Forge job-hunting agents.

The workspace files are the database. Every function tolerates missing or
malformed files and returns an explicit empty/error value instead of raising.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parent.parent
AGENT_DEFS = WORKSPACE / ".opencode" / "agents"
AGENT_STATE = WORKSPACE / "workspace" / "agents"
SCOUT_OUTPUTS = AGENT_STATE / "scout" / "outputs"

ROSTER_ORDER = ("forge", "scout", "job-reader", "cv-adapter")
AGENT_LABELS = {
    "forge": "Forge",
    "scout": "Scout",
    "job-reader": "Job Reader",
    "cv-adapter": "CV Adapter",
}
MAX_EVENTS = 5


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter dict, body). Bad or absent YAML is an empty dict."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    fm_text = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1 :])
    try:
        data = yaml.safe_load(fm_text)
    except yaml.YAMLError:
        return {}, body
    if not isinstance(data, dict):
        return {}, body
    return data, body


def _agent_name(slug: str, body: str) -> str:
    """Read `Your name is X.` from the body, else the known label or title."""
    match = re.search(r"Your name is\s+([^.\n]+)\.", body)
    if match:
        return match.group(1).strip()
    if slug in AGENT_LABELS:
        return AGENT_LABELS[slug]
    return slug.replace("-", " ").title()


def load_roster() -> list[dict]:
    """Read .opencode/agents/*.md in roster order; unknown files appended."""
    defs = Path(AGENT_DEFS)
    if not defs.exists() or not defs.is_dir():
        return []
    entries = []
    for path in defs.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        fm, body = _parse_frontmatter(text)
        slug = path.stem
        mode = fm.get("mode", "")
        if mode is None:
            mode = ""
        description = fm.get("description", "")
        if description is None:
            description = ""
        try:
            definition = path.relative_to(Path(WORKSPACE)).as_posix()
        except ValueError:
            definition = str(path)
        entries.append(
            {
                "slug": slug,
                "name": _agent_name(slug, body),
                "mode": mode,
                "description": description,
                "definition": definition,
            }
        )

    def sort_key(entry):
        slug = entry["slug"]
        idx = ROSTER_ORDER.index(slug) if slug in ROSTER_ORDER else len(ROSTER_ORDER)
        return (idx, slug)

    entries.sort(key=sort_key)
    return entries


def _detail_value(value):
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _event_view(event: dict) -> dict:
    """Normalize one log object to {when, event, detail}."""
    when = event.get("ts", event.get("timestamp"))
    ev = event.get("event")
    if ev is None:
        ev = event.get("type")
    if ev is None:
        ev = "event"
    detail = None
    for key in ("detail", "summary", "notes", "result"):
        if key in event:
            detail = _detail_value(event.get(key))
            break
    return {"when": when, "event": ev, "detail": detail}


def load_memory(slug: str) -> dict:
    """Read index.md and the newest MAX_EVENTS valid JSONL objects."""
    memory_dir = Path(AGENT_STATE) / slug / "memory"
    index_path = memory_dir / "index.md"
    summary = ""
    summary_missing = True
    try:
        if index_path.is_file():
            summary = index_path.read_text(encoding="utf-8").rstrip("\n")
            summary_missing = False
    except (OSError, UnicodeDecodeError):
        summary = ""
        summary_missing = True

    events = []
    events_error = None
    log_path = memory_dir / "log.jsonl"
    if log_path.is_file():
        valid = []
        try:
            raw = log_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            raw = ""
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(obj, dict):
                valid.append(obj)
        if not valid:
            events_error = "log.jsonl contains no valid JSON objects."
        else:
            recent = list(reversed(valid))[:MAX_EVENTS]
            events = [_event_view(o) for o in recent]

    return {
        "summary": summary,
        "summary_missing": summary_missing,
        "events": events,
        "events_error": events_error,
    }


def load_latest_scan() -> dict:
    """Newest scan-*.json with a jobs list; sort jobs by score, missing last."""
    outputs = SCOUT_OUTPUTS
    outputs = Path(outputs) if outputs is not None else None
    if outputs is None or not outputs.exists() or not outputs.is_dir():
        return {"scan": None, "files": {}, "error": "No Scout scan yet."}

    candidates = sorted(outputs.glob("scan-*.json"), key=lambda p: (p.stat().st_mtime, p.name), reverse=True)

    had_files = bool(list(outputs.glob("scan-*.json")))
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        jobs = data.get("jobs")
        if not isinstance(jobs, list):
            continue

        # skip non-dict jobs
        clean_jobs = [j for j in jobs if isinstance(j, dict)]

        def score_key(job):
            score = job.get("score")
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                return -1.0
            return float(score)

        sorted_jobs = sorted(clean_jobs, key=score_key, reverse=True)

        primary_count = sum(1 for j in clean_jobs if j.get("track") == "primary")
        secondary_count = sum(1 for j in clean_jobs if j.get("track") == "secondary")

        scan = dict(data)
        scan["jobs"] = sorted_jobs
        scan["job_count"] = len(clean_jobs)
        scan["primary_count"] = primary_count
        scan["secondary_count"] = secondary_count

        try:
            json_rel = path.relative_to(Path(WORKSPACE)).as_posix()
        except ValueError:
            json_rel = str(path)
        files = {"json": json_rel}
        md_path = path.with_suffix(".md")
        if md_path.is_file():
            try:
                md_rel = md_path.relative_to(Path(WORKSPACE)).as_posix()
            except ValueError:
                md_rel = str(md_path)
            files["markdown"] = md_rel

        return {"scan": scan, "files": files, "error": None}

    # no valid candidate
    if not had_files:
        return {"scan": None, "files": {}, "error": "No Scout scan yet."}
    return {"scan": None, "files": {}, "error": "Scout scan unreadable."}


def build_agents_view() -> dict:
    """Assemble agents, agent_events, agent_scan, agent_scan_files, agent_scan_error."""
    roster = load_roster()
    agents_list = []
    agent_events = {}
    for entry in roster:
        slug = entry["slug"]
        memory = load_memory(slug)
        merged = {**entry, **memory}
        agents_list.append(merged)
        agent_events[slug] = memory.get("events", [])

    scan_view = load_latest_scan()
    return {
        "agents": agents_list,
        "agent_events": agent_events,
        "agent_scan": scan_view.get("scan"),
        "agent_scan_files": scan_view.get("files", {}),
        "agent_scan_error": scan_view.get("error"),
    }
