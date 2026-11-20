"""Read-only skill registry: the skills OpenCode 2.3 registers for this workspace.

Mirrors OpenCode's documented discovery (opencode.ai/docs/skills, checked
2026-11-17) for a run started at the workspace root, which is where every
dashboard run starts (`_run_env()` pins PWD). Nothing here writes, and a
skill never grants anything: whether an agent may load one is decided only
by that agent's OpenCode `skill` permission rules.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from core import agents

HOME = Path.home()
MAX_DEPTH = 6  # OpenCode stops six directories below a source root.
ID_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ID_MAX = 64

# Registration order, lowest precedence first: for a duplicate ID the source
# registered later is the one OpenCode loads. Built-in and plugin skills are
# registered first but cannot be enumerated from files, so they are not listed.
# (key, label, path relative to HOME or to the workspace, scope)
SOURCES = (
    ("claude-global", "~/.claude/skills", "home", ".claude/skills"),
    ("claude-project", ".claude/skills", "workspace", ".claude/skills"),
    ("agents-global", "~/.agents/skills", "home", ".agents/skills"),
    ("agents-project", ".agents/skills", "workspace", ".agents/skills"),
    ("opencode-global", "~/.config/opencode/skills", "home", ".config/opencode/skills"),
    ("opencode-project", ".opencode/skills", "workspace", ".opencode/skills"),
)
# Project sources below the workspace root load only when OpenCode runs there.
SCOPED_SOURCES = (
    ("dashboard-claude", "dashboard-app/.claude/skills", "workspace", "dashboard-app/.claude/skills"),
    ("dashboard-agents", "dashboard-app/.agents/skills", "workspace", "dashboard-app/.agents/skills"),
    ("dashboard-opencode", "dashboard-app/.opencode/skills", "workspace", "dashboard-app/.opencode/skills"),
)
CONFIG_FILES = (
    ("home", ".config/opencode/opencode.json"),
    ("home", ".config/opencode/opencode.jsonc"),
    ("workspace", "opencode.json"),
    ("workspace", "opencode.jsonc"),
)


def _root(base: str) -> Path:
    return HOME if base == "home" else Path(agents.WORKSPACE)


def _display(path: Path) -> str:
    """Workspace-relative, or ~/-relative, for display and /api/file."""
    try:
        return path.relative_to(Path(agents.WORKSPACE)).as_posix()
    except ValueError:
        try:
            return "~/" + path.relative_to(HOME).as_posix()
        except ValueError:
            return str(path)


def _skill_files(root: Path) -> tuple[list[tuple[str, Path]], list[str]]:
    """(id, file) pairs OpenCode registers from one source, plus ignored files.

    Root-level *.md files are skills named by their stem. Files named exactly
    SKILL.md are skills named by their folder, at any depth up to MAX_DEPTH;
    a folder holding SKILL.md is one skill and is not searched further.
    Hidden entries and node_modules are skipped.
    """
    found, ignored = [], []
    for entry in sorted(root.iterdir()):
        if entry.name.startswith(".") or entry.name == "node_modules":
            continue
        if entry.is_file() and entry.suffix == ".md":
            found.append((entry.stem, entry))
    for current, dirs, files in os.walk(root, followlinks=True):
        here = Path(current)
        depth = len(here.relative_to(root).parts)
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "node_modules")
        if depth == 0:
            continue
        if "SKILL.md" in files:
            found.append((here.name, here / "SKILL.md"))
            for nested, nested_dirs, nested_files in os.walk(here, followlinks=True):
                nested_depth = len(Path(nested).relative_to(root).parts)
                nested_dirs[:] = [] if nested_depth >= MAX_DEPTH else [
                    d for d in nested_dirs if not d.startswith(".") and d != "node_modules"
                ]
                if Path(nested) != here and "SKILL.md" in nested_files:
                    ignored.append(_display(Path(nested) / "SKILL.md"))
            dirs[:] = []
        elif depth >= MAX_DEPTH:
            dirs[:] = []
    return found, ignored


def _read_skill(skill_id: str, path: Path, source: tuple) -> dict:
    key, label = source[0], source[1]
    skill = {
        "id": skill_id,
        "path": _display(path),
        "source": key,
        "source_label": label,
        "in_workspace": not _display(path).startswith(("~/", "/")),
        "name": skill_id,
        "description": "",
        "advertised": False,
        "version": None,
        "size": None,
        "warnings": [],
    }
    try:
        text = path.read_text(encoding="utf-8")
        skill["size"] = len(text.encode("utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        skill["warnings"].append(f"Cannot be read ({exc.__class__.__name__}).")
        return skill
    meta, body, error = agents._parse_frontmatter(text)
    if error:
        skill["warnings"].append(f"Frontmatter: {error}.")
    name, description = meta.get("name"), meta.get("description")
    if isinstance(name, str) and name.strip():
        skill["name"] = name.strip()
    if isinstance(description, str) and description.strip():
        skill["description"] = description.strip()
    else:
        skill["warnings"].append("No description, so OpenCode never advertises it to the model.")
    metadata = meta.get("metadata") if isinstance(meta.get("metadata"), dict) else {}
    autoinvoke = metadata.get("opencode/autoinvoke")
    if autoinvoke is None and meta.get("disable-model-invocation") is True:
        autoinvoke = False
    skill["autoinvoke"] = autoinvoke is not False
    skill["advertised"] = bool(skill["description"]) and skill["autoinvoke"]
    if not ID_PATTERN.match(skill_id) or len(skill_id) > ID_MAX:
        skill["warnings"].append(
            "ID is not lowercase kebab-case of 1-64 characters (OpenCode accepts it, but it is not portable)."
        )
    if path.name != "SKILL.md" and skill_id.upper() == skill_id and skill_id.isalpha():
        skill["warnings"].append("A root-level Markdown file that looks like documentation is registered as a skill.")
    skill["version"] = hashlib.sha256(" ".join(body.split()).encode()).hexdigest()[:8]
    return skill


def config_warnings() -> list[str]:
    """`skills` entries in OpenCode config: V2 expects an array of paths/URLs."""
    warnings = []
    for base, rel in CONFIG_FILES:
        path = _root(base) / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text) if path.suffix == ".json" else None
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        if data is None and '"skills"' in text:
            warnings.append(f"{_display(path)} sets skills in JSONC; not parsed here.")
            continue
        value = (data or {}).get("skills")
        if isinstance(value, dict):
            warnings.append(
                f"{_display(path)} uses the V1 form skills: {{paths: [...]}}. OpenCode 2.x documents an array; "
                "whether these entries add a later, higher-precedence source is not verified."
            )
        elif isinstance(value, list):
            warnings.append(f"{_display(path)} adds skill sources {value}; they are not scanned here.")
    return warnings


def discover_skills() -> dict:
    """Every skill file in OpenCode's sources, grouped by ID with the loaded copy marked.

    Returns {"skills", "sources", "warnings", "counts"}. Each skill entry has
    the winning copy (`loaded`, from the highest-precedence source), every copy,
    and warnings: duplicates with different instructions, invalid frontmatter,
    no description, non-portable IDs.
    """
    warnings = config_warnings()
    if not Path(agents.WORKSPACE).is_dir():
        return {"skills": [], "sources": [], "warnings": [f"Workspace {agents.WORKSPACE} is not available."] + warnings,
                "counts": {"skills": 0, "files": 0, "duplicates": 0, "advertised": 0}}
    by_id: dict[str, list[dict]] = {}
    sources = []
    for scoped, group in ((False, SOURCES), (True, SCOPED_SOURCES)):
        for source in group:
            root = _root(source[2]) / source[3]
            info = {"key": source[0], "label": source[1], "path": _display(root), "scoped": scoped,
                    "exists": root.is_dir(), "files": 0, "ignored": []}
            sources.append(info)
            if not info["exists"]:
                continue
            found, info["ignored"] = _skill_files(root)
            info["files"] = len(found)
            for skill_id, path in found:
                copy = _read_skill(skill_id, path, source)
                copy["scoped"] = scoped
                by_id.setdefault(skill_id, []).append(copy)
            if info["ignored"]:
                warnings.append(f"{info['label']}: {len(info['ignored'])} SKILL.md inside another skill are ignored by OpenCode.")
    skills = []
    for skill_id in sorted(by_id, key=str.lower):
        copies = by_id[skill_id]
        effective = [c for c in copies if not c["scoped"]]
        loaded = effective[-1] if effective else None  # later source wins
        versions = {c["version"] for c in copies if c["version"]}
        skill_warnings = list(loaded["warnings"]) if loaded else []
        if len(effective) > 1:
            shadowed = ", ".join(c["path"] for c in effective[:-1])
            if len({c["version"] for c in effective}) > 1:
                skill_warnings.append(f"Duplicate ID with different instructions; OpenCode loads {loaded['path']} over {shadowed}.")
            else:
                skill_warnings.append(f"Duplicate ID, same instructions; {loaded['path']} shadows {shadowed}.")
        if not effective:
            skill_warnings.append("Only in dashboard-app/: not registered for runs started at the workspace root.")
        skills.append({
            "id": skill_id,
            "loaded": loaded,
            "copies": copies,
            "versions": len(versions),
            "registered": loaded is not None,
            "advertised": bool(loaded and loaded["advertised"]),
            "warnings": skill_warnings,
        })
    counts = {
        "skills": sum(s["registered"] for s in skills),
        "files": sum(len(s["copies"]) for s in skills),
        "duplicates": sum(len([c for c in s["copies"] if not c["scoped"]]) > 1 for s in skills),
        "conflicts": sum(1 for s in skills if any("different instructions" in w for w in s["warnings"])),
        "advertised": sum(s["advertised"] for s in skills),
        "invalid": sum(1 for s in skills if s["loaded"] and s["loaded"]["warnings"]),
    }
    return {"skills": skills, "sources": sources, "warnings": warnings, "counts": counts}


def skill_access(rules: list, skill: dict) -> str:
    """What an agent's resolved OpenCode rules let its model do with one skill.

    `loadable`: the skill tool loads it without approval; `ask`: OpenCode asks
    first (a non-interactive run has nobody to answer); `denied`: hidden and
    rejected. `hidden`: permitted, but never advertised (no description or
    autoinvoke off), so the model only learns of it if told the ID.
    """
    effect = agents.permission_effect(rules, "skill", skill["id"])
    if effect == "deny":
        return "denied"
    if effect == "ask":
        return "ask"
    return "loadable" if skill["advertised"] else "hidden"


def agent_matrix(resolved: list | None, skills: list[dict], agent_ids: list[str]) -> list[dict]:
    """Per agent: counts of skills by access, from OpenCode's resolved rules.

    Agents OpenCode does not list (Claude- or Codex-only) are reported as not
    evaluated: those tools use their own skill loading and rules.
    """
    by_id = {a.get("id"): a for a in resolved or [] if isinstance(a, dict)}
    registered = [s for s in skills if s["registered"]]
    rows = []
    for agent_id in agent_ids:
        entry = by_id.get(agent_id)
        if resolved is None or entry is None:
            rows.append({"agent": agent_id, "evaluated": False,
                         "reason": "OpenCode did not answer." if resolved is None else "Not an OpenCode agent for this workspace."})
            continue
        rules = [r for r in entry.get("permissions") or [] if isinstance(r, dict)]
        skill_rules = [f"{r.get('effect')} {r.get('action')} {r.get('resource')}" for r in rules
                       if agents._wildcard(str(r.get("action", "")), "skill")]
        access = {s["id"]: skill_access(rules, s) for s in registered}
        counts = {k: sum(1 for v in access.values() if v == k) for k in ("loadable", "hidden", "ask", "denied")}
        rows.append({"agent": agent_id, "evaluated": True, "counts": counts, "skill_rules": skill_rules,
                     "access": access})
    return rows


def approved_skills(matrix_row: dict, skills: list[dict]) -> list[str]:
    """Skills a future per-run picker could offer: loadable, valid, unambiguous."""
    if not matrix_row.get("evaluated"):
        return []
    clean = {s["id"] for s in skills if s["registered"] and not s["loaded"]["warnings"]
             and not any("different instructions" in w for w in s["warnings"])}
    return sorted(k for k, v in matrix_row["access"].items() if v == "loadable" and k in clean)
