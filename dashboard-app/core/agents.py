"""Read-only agent registry: definitions, hub config, and each agent's brain.

The workspace files are the database. Every function tolerates missing or
malformed files and returns an explicit empty/error value instead of raising.
Nothing here writes, creates or moves a file or folder; callers persist.
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from datetime import datetime
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
AGENT_STATE = WORKSPACE / "workspace" / "agents"
SCOUT_OUTPUTS = AGENT_STATE / "scout" / "outputs"
HUB_CONFIG = WORKSPACE / "agentic-os" / "config" / "agentic-os.yaml"

# Presentation order only; discovery is not limited to these.
ROSTER_ORDER = ("forge", "scout", "job-reader", "cv-adapter")
AGENT_LABELS = {
    "forge": "Forge",
    "scout": "Scout",
    "job-reader": "Job Reader",
    "cv-adapter": "CV Adapter",
}
MAX_EVENTS = 5
MAX_OUTPUT_FILES = 20
MAX_HEADINGS = 6

# Definition folders in display precedence: the first readable copy is the one
# the dashboard shows. The load status says whether that tool reads the folder
# when run in this repository, per each tool's documented convention
# (checked 2026-11-17; see docs/agent-registry.md):
#   active     read from the workspace root and any folder below it
#   scoped     read only when the tool runs inside dashboard-app/
#   unverified no documented convention covers this folder
DEFINITION_SOURCES = (
    (".opencode/agents", ".md", "OpenCode", "active",
     "OpenCode reads .opencode/agents/ from the working folder upward."),
    (".claude/agents", ".md", "Claude Code", "active",
     "Claude Code reads every .claude/agents/ from the working folder up to the repository root."),
    (".codex/agents", ".toml", "Codex", "active",
     "Codex reads the project's .codex/agents/*.toml once the project is trusted."),
    ("dashboard-app/.claude/agents", ".md", "Claude Code", "scoped",
     "Read only when Claude Code runs inside dashboard-app/, where it overrides a root copy of the same name."),
    ("dashboard-app/.codex/agents", ".toml", "Codex", "unverified",
     "Codex documents .codex/agents/ at the project root; a nested folder is not documented."),
    ("dashboard-app/.github/agents", ".md", "GitHub Copilot", "unverified",
     "Copilot reads .github/agents/*.agent.md at the repository root; this folder is nested."),
)
LOAD_LABELS = {
    "active": "Loaded from workspace root",
    "scoped": "Loaded only inside dashboard-app/",
    "unverified": "Load unverified",
    "none": "No definition",
}
CODEX_REQUIRED = ("name", "description", "developer_instructions")
# Memory text is shown inline only for the job-search team, whose memory the
# Agents tab already showed. Every other agent is metadata-only until an access
# policy is reviewed. The files stay readable through /api/file regardless.
MEMORY_CONTENT_AGENTS = ROSTER_ORDER
OPENCODE_GLOBAL_AGENTS = Path.home() / ".config" / "opencode" / "agents"


def _parse_frontmatter(text: str) -> tuple[dict, str, str | None]:
    """Return (frontmatter dict, body, error). Absent frontmatter is not an error."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, None
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text, "frontmatter has no closing ---"
    fm_text = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1 :])
    try:
        data = yaml.safe_load(fm_text)
    except yaml.YAMLError:
        return {}, body, "frontmatter is not valid YAML"
    if data is None:
        return {}, body, None
    if not isinstance(data, dict):
        return {}, body, "frontmatter is not a key/value map"
    return data, body, None


def _agent_name(slug: str, body: str, meta_name: str = "") -> str:
    """`Your name is X.` from the body, else a frontmatter name, label or title."""
    match = re.search(r"Your name is\s+([^.\n]+)\.", body)
    if match:
        return match.group(1).strip()
    if meta_name:
        return meta_name
    if slug in AGENT_LABELS:
        return AGENT_LABELS[slug]
    return slug.replace("-", " ").title()


def _mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="minutes")
    except OSError:
        return None


def _lines(body: str) -> list[str]:
    return [" ".join(line.split()) for line in body.splitlines() if line.strip()]


def _version(body: str) -> str:
    """Short hash of whitespace-normalized instructions; equal text, equal version."""
    return hashlib.sha256(" ".join(body.split()).encode()).hexdigest()[:8]


def _definition_id(path: Path) -> str:
    """Stable ID = filename stem; Copilot's `x.agent.md` is `x`."""
    return path.name.removesuffix(".agent.md") if path.name.endswith(".agent.md") else path.stem


def _read_definition(path: Path, source: tuple) -> dict:
    """One definition copy: where it is, who loads it, its body hash and problems."""
    folder, suffix, tool, load, note = source
    rel = _rel(path)
    copy = {
        "path": rel,
        "folder": folder,
        "tool": tool,
        "load": load,
        "load_note": note,
        "modified": _mtime(path),
        "meta": {},
        "body": "",
        "version": None,
        "warnings": [],
    }
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        copy["warnings"].append(f"{rel} could not be read ({exc.__class__.__name__}).")
        copy["load"] = "unverified"
        return copy
    if suffix == ".toml":
        try:
            meta = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            copy["warnings"].append(f"{rel} is not valid TOML ({exc}).")
            copy["load"] = "unverified"
            return copy
        missing = [k for k in CODEX_REQUIRED if not (isinstance(meta.get(k), str) and meta[k].strip())]
        if missing:
            copy["warnings"].append(f"{rel} lacks {', '.join(missing)}, which Codex requires.")
            copy["load"] = "unverified"
        body = meta.get("developer_instructions")
        body = body if isinstance(body, str) else ""
    else:
        meta, body, error = _parse_frontmatter(text)
        if error:
            copy["warnings"].append(f"{rel}: {error}.")
    if tool == "GitHub Copilot" and not path.name.endswith(".agent.md"):
        copy["warnings"].append(f"{rel} lacks the .agent.md suffix Copilot requires.")
    if ".Codex/" in body:
        copy["warnings"].append(
            f"{rel} refers to .Codex/ (capital C); that resolves on this Mac's "
            "case-insensitive drive but not on Linux (parrot)."
        )
    copy["meta"], copy["body"] = meta, body
    copy["version"] = _version(body)
    return copy


def _discover_copies() -> tuple[dict[str, list[dict]], list[str]]:
    """Every definition copy by ID, in precedence order, plus missing-folder warnings."""
    by_id: dict[str, list[dict]] = {}
    warnings = []
    for source in DEFINITION_SOURCES:
        folder = Path(WORKSPACE) / source[0]
        if not folder.is_dir():
            warnings.append(f"Definition folder {source[0]}/ is missing; nothing was created.")
            continue
        for path in sorted(folder.glob(f"*{source[1]}")):
            by_id.setdefault(_definition_id(path), []).append(_read_definition(path, source))
    return by_id, warnings


def _versions(copies: list[dict], shown: dict) -> list[dict]:
    """Group copies with identical normalized instructions; compare each to the shown one."""
    groups: dict[str, list[dict]] = {}
    for copy in copies:
        if copy["version"] is not None:
            groups.setdefault(copy["version"], []).append(copy)
    shown_lines = set(_lines(shown["body"]))
    versions = []
    for vid, members in groups.items():
        extra = [line for line in _lines(members[0]["body"]) if line not in shown_lines]
        versions.append(
            {
                "id": vid,
                "paths": [m["path"] for m in members],
                "newest": max((m["modified"] for m in members if m["modified"]), default=None),
                "displayed": vid == shown["version"],
                "extra_lines": len(extra),
                "extra_headings": [l.lstrip("#").strip() for l in extra if l.startswith("#")][:MAX_HEADINGS],
            }
        )
    return versions


def _version_warnings(versions: list[dict], shown: dict) -> list[str]:
    if len(versions) < 2:
        return []
    warnings = [f"{len(versions)} different instruction versions; the dashboard shows {shown['path']}."]
    shown_newest = next((v["newest"] for v in versions if v["displayed"]), None) or ""
    for v in versions:
        if v["displayed"] or not v["newest"] or v["newest"] <= shown_newest:
            continue
        text = (
            f"Newer copy {', '.join(v['paths'])} ({v['newest']}) has {v['extra_lines']} "
            "lines not in the displayed copy"
        )
        if v["extra_headings"]:
            text += f", including: {'; '.join(v['extra_headings'])}"
        warnings.append(text + ".")
    return warnings


def _file_meta(path: Path) -> dict:
    try:
        size = path.stat().st_size
    except OSError:
        size = None
    return {"path": _rel(path), "name": path.name, "modified": _mtime(path), "size": size}


def load_state(slug: str) -> dict:
    """Metadata for workspace/agents/<slug>/: memory files and outputs, no content."""
    root = Path(AGENT_STATE) / slug
    memory = root / "memory"
    index, log = memory / "index.md", memory / "log.jsonl"
    log_meta = None
    if log.is_file():
        log_meta = _file_meta(log)
        try:
            log_meta["entries"] = sum(1 for line in log.read_text(encoding="utf-8").splitlines() if line.strip())
        except (OSError, UnicodeDecodeError):
            log_meta["entries"] = None
    files = []
    outputs = root / "outputs"
    if outputs.is_dir():
        files = [_file_meta(p) for p in outputs.iterdir() if p.is_file() and not p.name.startswith(".")]
        files.sort(key=lambda f: (f["modified"] or "", f["name"]), reverse=True)
    return {
        "path": _rel(root),
        "exists": root.is_dir(),
        "memory_index": _file_meta(index) if index.is_file() else None,
        "memory_log": log_meta,
        "outputs_dir": outputs.is_dir(),
        "output_count": len(files),
        "outputs": files[:MAX_OUTPUT_FILES],
    }


def load_hub() -> tuple[dict, str | None]:
    """`hub.agents` from agentic-os.yaml, or ({}, why it is unavailable)."""
    path = Path(HUB_CONFIG)
    rel = _rel(path)
    if not path.is_file():
        return {}, f"{rel} not found; hub status is unknown."
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        return {}, f"{rel} could not be read ({exc.__class__.__name__}); hub status is unknown."
    hub = data.get("hub") if isinstance(data, dict) else None
    entries = hub.get("agents") if isinstance(hub, dict) else None
    if not isinstance(entries, dict):
        return {}, f"{rel} has no hub.agents map; hub status is unknown."
    return {str(k): v for k, v in entries.items() if isinstance(v, dict)}, None


def _hub_view(slug: str, cfg: dict) -> tuple[dict, list[str]]:
    """The hub entry plus any path that disagrees with workspace/agents/<slug>/."""
    warnings = []
    expected = f"workspace/agents/{slug}"
    for key, sub in (("memoryDir", "memory"), ("outputDirs", "outputs")):
        value = cfg.get(key)
        for path in value if isinstance(value, list) else [value]:
            if not isinstance(path, str) or not path.strip():
                continue
            if path.rstrip("/") != f"{expected}/{sub}":
                warnings.append(f"agentic-os.yaml {key} is {path}, not {expected}/{sub}.")
            if not (Path(WORKSPACE) / path).is_dir():
                warnings.append(f"agentic-os.yaml {key} {path} does not exist.")
    view = {
        "name": cfg.get("name"),
        "installed": cfg.get("installed") is True,
        "coordinator": cfg.get("coordinator"),
        "cost_class": cfg.get("costClass"),
        "memory_dir": cfg.get("memoryDir"),
        "output_dirs": cfg.get("outputDirs"),
    }
    return view, warnings


def _public(copy: dict) -> dict:
    """A copy without its instruction text; bodies load on demand via /api/file."""
    view = {k: v for k, v in copy.items() if k not in ("body", "meta")}
    view["load_label"] = LOAD_LABELS[copy["load"]]
    return view


def _roster_key(slug: str) -> tuple:
    idx = ROSTER_ORDER.index(slug) if slug in ROSTER_ORDER else len(ROSTER_ORDER)
    return (idx, slug)


def launch_definition(agent_id: str) -> dict | None:
    """The .opencode copy OpenCode should load from the workspace root, hashed now.

    `sha256` covers the exact file bytes; `version` is the registry's
    normalized-instructions hash, comparable with OpenCode's resolved prompt.
    """
    path = Path(WORKSPACE) / ".opencode" / "agents" / f"{agent_id}.md"
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    _, body, _ = _parse_frontmatter(raw.decode("utf-8", errors="replace"))
    return {"path": _rel(path), "sha256": hashlib.sha256(raw).hexdigest(), "version": _version(body)}


def check_resolved_agent(agent_id: str, resolved: list, expected: dict, policy: dict | None = None) -> dict:
    """Compare OpenCode's resolved agent (`opencode debug agents`) with the expected copy.

    This proves which instructions OpenCode resolved, not which file it read:
    an identical global copy cannot be told apart. With `policy`, the resolved
    permission rules must also give each probe its expected effect.
    """
    entry = next((a for a in resolved if isinstance(a, dict) and a.get("id") == agent_id), None)
    if entry is None:
        return {"check": "missing", "detail": f"OpenCode does not list an agent named {agent_id}."}
    system = entry.get("system") if isinstance(entry.get("system"), str) else ""
    if _version(system) != expected["version"]:
        return {
            "check": "mismatch",
            "detail": f"OpenCode resolved different instructions for {agent_id} than {expected['path']}.",
        }
    detail = f"OpenCode's resolved instructions for {agent_id} match {expected['path']}."
    global_copy = OPENCODE_GLOBAL_AGENTS / f"{agent_id}.md"
    if global_copy.is_file():
        try:
            _, global_body, _ = _parse_frontmatter(global_copy.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            global_body = None
        if global_body is not None and _version(global_body) == expected["version"]:
            detail += (
                f" ~/.config/opencode/agents/{agent_id}.md has the same instructions, "
                "so OpenCode's output cannot show which of the two files it read."
            )
        else:
            detail += f" ~/.config/opencode/agents/{agent_id}.md differs, so the project copy is the one resolved."
    rules = [p for p in entry.get("permissions") or [] if isinstance(p, dict)]
    permissions = [f"{p.get('effect')} {p.get('action')} {p.get('resource')}" for p in rules]
    if policy and (problems := policy_violations(rules, policy)):
        return {
            "check": "policy",
            "detail": f"OpenCode's resolved permissions for {agent_id} fail the card's policy: {'; '.join(problems)}.",
            "permissions": permissions,
        }
    return {"check": "matched", "detail": detail, "permissions": permissions}


def _wildcard(pattern: str, value: str) -> bool:
    """OpenCode V2 whole-value match: `*` any run (including `/`), `?` one char."""
    regex = "".join(".*" if c == "*" else "." if c == "?" else re.escape(c) for c in pattern)
    return re.fullmatch(regex, value, re.DOTALL) is not None


def permission_effect(rules: list, action: str, resource: str) -> str:
    """Effect OpenCode's documented rule order gives: last match wins, none = ask."""
    effect = "ask"
    for rule in rules:
        if (
            isinstance(rule, dict)
            and _wildcard(str(rule.get("action", "")), action)
            and _wildcard(str(rule.get("resource", "")), resource)
        ):
            effect = str(rule.get("effect"))
    return effect


def policy_violations(rules: list, policy: dict) -> list[str]:
    """Probes in `policy` ({"deny": [...], "allow": [...]}) whose effect differs."""
    problems = []
    for expected in ("deny", "allow"):
        for action, resource in policy.get(expected, ()):
            got = permission_effect(rules, action, resource)
            if got != expected:
                problems.append(f"{action} {resource} resolves to {got}, not {expected}")
    return problems


def discover_agents() -> dict:
    """Every agent found in definitions, the hub config or state folders.

    Returns {"agents", "warnings", "counts"}. An agent is *discovered* when a
    definition file exists, *registered* when agentic-os.yaml lists it, and
    *loadable* when some copy sits where a CLI tool documents reading it.
    """
    if not Path(WORKSPACE).is_dir():
        return {
            "agents": [],
            "warnings": [f"Workspace {WORKSPACE} is not available (is the USB drive mounted?). Nothing was created."],
            "counts": {"discovered": 0, "registered": 0, "loadable": 0, "files": 0},
        }
    by_id, warnings = _discover_copies()
    hub, hub_error = load_hub()
    if hub_error:
        warnings.append(hub_error)
    state_root = Path(AGENT_STATE)
    if not state_root.is_dir():
        warnings.append(f"Agent state folder {_rel(state_root)}/ is missing; nothing was created.")
        state_ids = set()
    else:
        state_ids = {p.name for p in state_root.iterdir() if p.is_dir() and not p.name.startswith(".")}

    agents = []
    for slug in sorted(set(by_id) | set(hub) | state_ids, key=_roster_key):
        copies = by_id.get(slug, [])
        shown = next((c for c in copies if c["version"] is not None), copies[0] if copies else None)
        agent_warnings = [w for c in copies for w in c["warnings"]]
        versions = []
        if shown:
            versions = _versions(copies, shown)
            agent_warnings += _version_warnings(versions, shown)
        hub_view = None
        if slug in hub:
            hub_view, hub_warnings = _hub_view(slug, hub[slug])
            agent_warnings += hub_warnings
            if not copies:
                agent_warnings.append("Registered in agentic-os.yaml, but no definition file was found.")
        elif not copies:
            agent_warnings.append(f"State folder workspace/agents/{slug}/ has no definition and no hub entry.")
        loads = {c["load"] for c in copies}
        loadable = next((s for s in ("active", "scoped", "unverified") if s in loads), "none")
        meta = shown["meta"] if shown else {}
        meta_name = next((c["meta"]["name"] for c in copies if isinstance(c["meta"].get("name"), str)), "")
        description = next(
            (c["meta"]["description"] for c in copies if isinstance(c["meta"].get("description"), str)), ""
        )
        mode = meta.get("mode")
        agents.append(
            {
                "slug": slug,
                "name": _agent_name(slug, shown["body"] if shown else "", meta_name),
                "description": description,
                "mode": mode if isinstance(mode, str) else "",
                "displayed": _public(shown) if shown else None,
                "copies": [_public(c) for c in copies],
                "versions": versions,
                "discovered": bool(copies),
                "registered": hub_view is not None,
                "hub": hub_view,
                "loadable": loadable,
                "loadable_label": LOAD_LABELS[loadable],
                "state": load_state(slug),
                "memory_content": slug in MEMORY_CONTENT_AGENTS,
                "warnings": agent_warnings,
            }
        )
    counts = {
        "discovered": sum(a["discovered"] for a in agents),
        "registered": sum(a["registered"] for a in agents),
        "loadable": sum(a["loadable"] in ("active", "scoped") for a in agents),
        "files": sum(len(a["copies"]) for a in agents),
    }
    return {"agents": agents, "warnings": warnings, "counts": counts}


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
# Keys the model must supply; fetched_at and provenance are set by the runner.
READING_STRINGS = ("job_id", "title", "company", "source_url")
MODEL_SUPPLIED_DROP = ("fetched_at", "provenance")
MAX_STAGED_BYTES = 1_000_000


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


def validate_staged_reading(staged: Path, jid: str) -> tuple[dict | None, str | None]:
    """Check the file a Job Reader run left in its staging folder: (data, None) or (None, why).

    The staging folder is created empty by the runner for this run only, so
    anything in it was written by this run. Requires a JSON object (at most
    MAX_STAGED_BYTES) with the contract keys and types, naming the requested
    job id. Extra keys are allowed; consumers ignore them.
    """
    path = Path(staged) / f"{jid}.json"
    rel = _rel(path)
    try:
        if path.stat().st_size > MAX_STAGED_BYTES:
            return None, f"{rel} is larger than {MAX_STAGED_BYTES} bytes."
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"No output written to {rel}."
    except (OSError, UnicodeDecodeError, ValueError):
        return None, f"{rel} is not readable JSON."
    if not isinstance(data, dict):
        return None, f"{rel} is not a JSON object."
    bad = [k for k in READING_STRINGS if not isinstance(data.get(k), str)]
    bad += [
        k for k, _ in READING_FIELDS
        if not (isinstance(data.get(k), list) and all(isinstance(i, str) for i in data[k]))
    ]
    if bad:
        return None, f"{rel} is missing or mistypes: {', '.join(bad)}."
    if data["job_id"] != jid:
        return None, f"{rel} names job_id {data['job_id']!r}, not {jid!r}."
    return data, None


def finalize_reading(data: dict, run: dict, launched_at: datetime, exited_at: datetime, published_at: datetime) -> dict:
    """The published reading: the model's extraction plus timestamps from this process.

    Any timestamp or provenance the model wrote is dropped. `fetched_at` keeps
    the contract key Interviews and CV Adapter read, set to the CLI exit time:
    the fetch happened between `launched_at` and `exited_at`.
    """
    final = {k: v for k, v in data.items() if k not in MODEL_SUPPLIED_DROP}
    final["fetched_at"] = exited_at.isoformat(timespec="seconds")
    final["provenance"] = {
        "run_id": run.get("id"),
        "launched_at": launched_at.isoformat(timespec="seconds"),
        "exited_at": exited_at.isoformat(timespec="seconds"),
        "published_at": published_at.isoformat(timespec="seconds"),
        "provider": run.get("provider"),
        "model": run.get("model"),
        "definition_version": (run.get("definition") or {}).get("version"),
        "fetched_at_meaning": "CLI exit time recorded by the dashboard; the fetch happened between launched_at and exited_at.",
    }
    return final


def job_reader_event(run: dict, jid: str, url: str, data: dict | None, error: str | None) -> dict:
    """The one memory event the runner records for a Job Reader run."""
    event = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "event": "jd_read" if data else "jd_read_failed",
        "job_id": jid,
        "source_url": url,
        "run_id": run.get("id"),
        "provider": run.get("provider"),
        "model": run.get("model"),
        "definition_version": (run.get("definition") or {}).get("version"),
        "recorded_by": "dashboard",
    }
    if data:
        event.update(
            title=data["title"],
            company=data["company"],
            fetched_at=data["fetched_at"],
            output=f"outputs/{jid}.json",
        )
    else:
        event["detail"] = error
    return event


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
    """Assemble agents, agent_events, agent_registry and the latest Scout scan."""
    registry = discover_agents()
    agent_events = {}
    for agent in registry["agents"]:
        events = []
        if agent["memory_content"] and agent["state"]["exists"]:
            memory = load_memory(agent["slug"])
            agent.update(memory)
            events = memory["events"]
        agent_events[agent["slug"]] = events

    scan_view = load_latest_scan()
    return {
        "agents": registry["agents"],
        "agent_events": agent_events,
        "agent_registry": {"warnings": registry["warnings"], "counts": registry["counts"]},
        "agent_scan": scan_view.get("scan"),
        "agent_scan_files": scan_view.get("files", {}),
        "agent_scan_error": scan_view.get("error"),
    }
