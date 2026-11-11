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
    if detail is None:
        parts = []
        title = event.get("title")
        company = event.get("company")
        score = event.get("score")
        if isinstance(title, str) and title:
            parts.append(title)
        if isinstance(company, str) and company:
            parts.append(company)
        if parts:
            detail = " — ".join(parts)
        if score is not None and not isinstance(score, bool):
            suffix = f"score {score}"
            detail = f"{detail} · {suffix}" if detail else suffix
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


def _scan_sort_key(path: Path) -> tuple:
    """Newest-first key that survives a vanished or dangling scan file."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = -1.0
    return (mtime, path.name)


def load_latest_scan() -> dict:
    """Newest scan-*.json with a jobs list; sort jobs by score, missing last."""
    outputs = SCOUT_OUTPUTS
    outputs = Path(outputs) if outputs is not None else None
    if outputs is None or not outputs.exists() or not outputs.is_dir():
        return {"scan": None, "files": {}, "error": "No Scout scan yet."}

    candidates = sorted(outputs.glob("scan-*.json"), key=_scan_sort_key, reverse=True)

    had_files = bool(candidates)
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


# ── Interviews tab wiring ─────────────────────────────────────
# One job id per tracker row, derived by code so Job Reader and CV Adapter
# write to paths the dashboard can find again without guessing.
JOB_ID_MAX = 80
READING_FIELDS = (
    ("responsibilities", "Responsibilities"),
    ("required_skills", "Required skills"),
    ("preferred_skills", "Preferred skills"),
    ("language_requirements", "Language requirements"),
)
MAX_READING_ITEMS = 30
MAX_LEADS = 8


def job_id(company: str, role: str) -> str:
    """`company-role` as a lowercase slug; empty when nothing usable remains."""
    slug = re.sub(r"[^a-z0-9]+", "-", f"{company} {role}".lower()).strip("-")
    return slug[:JOB_ID_MAX].strip("-")


def _rel(path: Path) -> str:
    try:
        return path.relative_to(Path(WORKSPACE)).as_posix()
    except ValueError:
        return str(path)


def load_job_reading(jid: str) -> dict | None:
    """Job Reader's extraction for one job id, or None when absent or unreadable.

    Only lists of plain strings are shown; anything else in the file is ignored.
    """
    if not jid:
        return None
    path = Path(AGENT_STATE) / "job-reader" / "outputs" / f"{jid}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    sections = []
    for key, label in READING_FIELDS:
        value = data.get(key)
        items = [v.strip() for v in value if isinstance(v, str) and v.strip()] if isinstance(value, list) else []
        if items:
            sections.append({"label": label, "items": items[:MAX_READING_ITEMS]})
    return {"path": _rel(path), "sections": sections}


def base_cv_path() -> str | None:
    path = Path(AGENT_STATE) / "cv-adapter" / "outputs" / "base-cv.json"
    return _rel(path) if path.is_file() else None


def application_agents(company: str, role: str, url: str) -> dict:
    """What the agents have produced, and can be asked to produce, for one row."""
    jid = job_id(company, role)
    reading = load_job_reading(jid)
    tailored = Path(AGENT_STATE) / "cv-adapter" / "outputs" / f"tailored-{jid}.md"
    is_web = isinstance(url, str) and url.startswith(("http://", "https://")) and not re.search(r"\s", url)
    return {
        "job_id": jid,
        # Prefill for the Job Reader card: "<job id> <posting URL>".
        "reader_input": f"{jid} {url}" if jid and is_web else "",
        "reading": reading,
        "tailored": _rel(tailored) if jid and tailored.is_file() else "",
    }


def scout_leads(scan: dict | None, tracked: set[tuple[str, str]]) -> list[dict]:
    """Top-scored jobs of the latest scan that the tracker does not hold yet."""
    leads = []
    for job in (scan or {}).get("jobs") or []:
        title, company = job.get("title"), job.get("company")
        if not (isinstance(title, str) and title.strip() and isinstance(company, str) and company.strip()):
            continue
        if (company.strip().casefold(), title.strip().casefold()) in tracked:
            continue
        url = job.get("url")
        text = lambda key: job[key].strip() if isinstance(job.get(key), str) else ""  # noqa: E731
        leads.append(
            {
                "title": title.strip(),
                "company": company.strip(),
                "score": job.get("score") if isinstance(job.get("score"), (int, float)) and not isinstance(job.get("score"), bool) else None,
                "location": text("location"),
                "salary": text("salary"),
                "rationale": text("rationale"),
                "url": url if isinstance(url, str) and url.startswith(("http://", "https://")) else "",
            }
        )
        if len(leads) >= MAX_LEADS:
            break
    return leads


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
