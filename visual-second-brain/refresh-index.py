#!/usr/bin/env python3
"""Rebuild workspace-index.json for the Visual Second Brain.

THE FILESYSTEM IS THE SOURCE OF TRUTH.

Do not hand-edit workspace-index.json. Whenever files move, projects are
created, or the workspace changes substantially, rerun this script. The index
is always generated from the current filesystem, never maintained by hand.

Scope is curated: only INCLUDE_ROOTS (the folders the department routers link
to) plus document-like files at the workspace root. Private, secret-looking,
dependency, cache and generated paths are excluded completely: they are never
opened and never named in the index, only counted by reason.

Usage:  python3 refresh-index.py
        VSB_WORKSPACE=/path VSB_OUTPUT=/path/index.json python3 refresh-index.py
Stdlib only. No pip install, no npm, no network. Exits nonzero and keeps the
previous index when the workspace is missing or the scan finds nothing.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# ══════════════════════════════════════════════════════════════
# CONFIGURATION — edit these
# ══════════════════════════════════════════════════════════════

WORKSPACE = Path(os.environ.get("VSB_WORKSPACE") or Path(__file__).resolve().parent.parent)
OUTPUT = Path(os.environ.get("VSB_OUTPUT") or Path(__file__).resolve().parent / "workspace-index.json")
SCHEMA_VERSION = 2

# Workspace-relative folders to scan, from the department routers
# (OPERATIONS, CODE, MONEY, LEARNING, CONTENT). Anything else is not indexed.
INCLUDE_ROOTS = [
    # Operations
    "IT Mgmt", "plans", "progress", "reflections",
    # Career & money
    "resume", "cover-letters", "interviews", "networking", "goals", "finance", "freelance",
    # Learning
    "Azure", "DevOps", "FastAPI", "SQL", "Books", "skills",
    # Content & visuals
    "artifacts", "drafts", "prompts", "resources",
    # Code
    "docs", "agentic-os", "button-runner", "dashboard-app", "projects", "Python", "React",
    "powershell", "robonugget-second-brain-app", "second-brain", "tools", "visual-second-brain",
]

# Root-level files are included when they are one of these types.
ROOT_FILE_TYPES = {"document", "pdf", "image"}

# Directory names skipped anywhere: dependencies, caches, build output, run logs.
VENDOR_DIR_NAMES = {
    "node_modules", "venv", ".venv", "env", "__pycache__", "dist", "build", "out", "target",
    ".next", "coverage", "site-packages", "vendor", "runs", "graft", "playwright-report",
    "__snapshots__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".cache", ".tmp",
}

# Workspace-relative (lowercase) paths excluded with a named reason.
EXCLUDE_PATHS = {
    "college planning": "personal_academic_records",
    "it mgmt/employer-it-playbook-private": "employer_private",
    "andrej-karpathy-skills": "vendored_third_party",
    "shared": "synced_folder",
    "tools/arms/data": "runtime_data",
    "artifacts/index.html": "generated_catalog",
    "visual-second-brain/workspace-index.json": "own_output",
}

# Third-party repos cloned into the workspace: top-level files only.
SHALLOW_DIRS = {"projects/rendercv"}

# Never opened, never listed. Matched against the file name.
SECRET_EXT = {
    ".env", ".pem", ".key", ".p12", ".pfx", ".p8", ".crt", ".keystore", ".jks", ".kdbx",
    ".tfstate", ".tfvars", ".ovpn",
}
SECRET_NAME_RE = re.compile(
    r"(^|[-_.])(env|secret|secrets|credential|credentials|token|password|passwords|passwd|"
    r"apikey|api-key|id_rsa|id_ed25519|service-account|client_secret|private|kubeconfig)([-_.]|$)"
    r"|(^|[-_.])(api|private|secret|ssh|deploy|access|signing)[-_]?keys?([-_.]|$)"
    r"|_rsa$|\.tfstate",
    re.I,
)
PRIVATE_RE = re.compile(r"private|employer|secret|credential", re.I)
WORK_LOG_RE = re.compile(r"work-?log", re.I)

SKIP_EXTENSIONS = {"tsbuildinfo", "pyc", "pyo", "so", "dylib", "class", "lock", "map", "log", "tmp"}

MAX_PREVIEW_CHARS = 220
MAX_FILE_BYTES_FOR_PREVIEW = 400_000

# ══════════════════════════════════════════════════════════════

TYPE_BY_EXT = {
    "code": {"py", "js", "ts", "tsx", "jsx", "java", "go", "rs", "c", "cpp", "h", "cs", "rb",
             "php", "swift", "kt", "vue", "svelte"},
    "document": {"md", "txt", "rst", "adoc", "docx", "doc", "rtf", "typ", "tex"},
    "config": {"json", "yaml", "yml", "toml", "ini", "cfg", "conf", "env", "gitignore",
               "editorconfig", "xml", "plist"},
    "script": {"sh", "bash", "zsh", "ps1", "bat", "fish"},
    "data": {"csv", "tsv", "sql", "db", "sqlite", "parquet", "ndjson"},
    "image": {"png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "bmp", "avif"},
    "pdf": {"pdf"},
    "spreadsheet": {"xlsx", "xls", "ods"},
    "presentation": {"pptx", "ppt"},
    "archive": {"zip", "tar", "gz", "bz2", "xz", "7z", "rar"},
    "web": {"html", "htm", "css", "scss", "less"},
}
EXT_TO_TYPE = {e: t for t, exts in TYPE_BY_EXT.items() for e in exts}

PREVIEWABLE = {
    "md", "txt", "json", "yaml", "yml", "toml", "js", "ts", "tsx", "jsx", "py", "sh", "sql",
    "css", "html", "rst", "ini", "cfg", "conf", "typ", "csv", "bash", "ps1", "go", "rs",
    "java", "rb",
}

# Topic vocabulary. A key matches a whole word of the path/name, or the start
# of a word when the key has 4+ letters ("deploy" matches "deployment").
TOPIC_RULES = {
    "career": ["resume", "cv", "interview", "job", "jobs", "cover", "networking", "application",
               "applications", "career", "linkedin"],
    "finance": ["finance", "money", "budget", "debt", "invoice", "tracker", "capex", "opex",
                "consulting", "freelance", "monetization"],
    "learning": ["study", "course", "learn", "lesson", "exercise", "cert", "az104", "sc900",
                 "az900", "book", "books", "reading", "cheat"],
    "operations": ["sop", "runbook", "lifecycle", "incident", "change", "continuity", "playbook",
                   "routine", "weekly", "review", "takeover"],
    "planning": ["plan", "plans", "roadmap", "brief", "spec", "design", "proposal", "strategy",
                 "goals"],
    "infrastructure": ["infra", "azure", "aws", "cloud", "network", "server", "devops",
                       "kubernetes", "metrics", "monitoring"],
    "deployment": ["deploy", "docker", "ci", "workflow", "workflows", "netlify", "azd", "bicep",
                   "terraform", "launchd"],
    "agent": ["agent", "agents", "claude", "skill", "skills", "prompt", "prompts", "llm", "mcp",
              "gemini", "brain"],
    "frontend": ["component", "components", "ui", "css", "style", "template", "templates",
                 "react", "jsx", "tsx", "html"],
    "api": ["api", "endpoint", "route", "routes", "rest", "graphql", "fastapi"],
    "database": ["migration", "schema", "sql", "db", "sqlite", "postgres", "storage",
                 "repository"],
    "security": ["security", "recon", "scan", "vuln", "firewall", "auth", "rbac", "permission"],
    "assets": ["asset", "hardware", "inventory", "procurement"],
    "testing": ["test", "tests", "fixture", "mock", "e2e", "pytest", "vitest"],
    "docs": ["readme", "doc", "docs", "guide", "guides", "manual", "handbook", "tutorial"],
    "config": ["config", "settings", "setup", "manifest"],
    "data-science": ["notebook", "ipynb", "dataset", "ml", "karpathy"],
}

# Folder-level topic: the department a top-level folder belongs to wins first place.
FOLDER_TOPICS = {
    "resume": "career", "cover-letters": "career", "interviews": "career",
    "networking": "career", "goals": "career", "finance": "finance", "freelance": "finance",
    "IT Mgmt": "operations", "progress": "operations", "reflections": "operations",
    "Azure": "learning", "DevOps": "learning", "FastAPI": "learning", "SQL": "learning",
    "Books": "learning", "skills": "learning", "agentic-os": "agent", "second-brain": "agent",
}

ENTRY_POINT_NAMES = {
    "readme.md", "claude.md", "agents.md", "index.html", "index.ts", "index.js", "main.py",
    "app.py", "package.json", "pyproject.toml", "manifest.md", "design.md", "product.md",
    "tasks.md", "dashboard.md", "routine.md", "makefile", "dockerfile", "cli.ts", "server.ts",
    "server.js",
}

HEADING_RE = re.compile(r"^#{1,3}\s+(.{3,80})$", re.M)
WORD_SPLIT_RE = re.compile(r"[^a-z0-9]+")
CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def exclusion(rel: str, name: str, is_dir: bool) -> str | None:
    """Reason a path is excluded, or None. Applied before anything is opened."""
    low = name.lower()
    ext = os.path.splitext(low)[1]
    if low == "kb.sqlite" or low.startswith("kb.sqlite-") or low in {
        ".kb-private", ".kb-venv", "personal-kb", "kb-ingest.log", "eval-evidence",
    } or low.startswith(("kb-ingest.log.", "kb-approval")):
        return "private_kb"
    if is_dir:
        if low in VENDOR_DIR_NAMES:
            return "dependency_or_cache"
        if name.startswith("."):
            return "hidden"
    else:
        stem = os.path.splitext(low)[0]
        if ext in SECRET_EXT or low.startswith(".env") or SECRET_NAME_RE.search(stem):
            return "secret_name"
        if name.startswith("~$"):
            return "office_lock"
        if name.startswith("."):
            return "hidden"
        if WORK_LOG_RE.search(low):
            return "employer_work_log"
        if ext.lstrip(".") in SKIP_EXTENSIONS or low.endswith((".min.js", ".min.css")):
            return "generated"
    if PRIVATE_RE.search(low):
        return "private_or_employer"
    low_rel = rel.lower()
    if low_rel in EXCLUDE_PATHS:
        return EXCLUDE_PATHS[low_rel]
    # Also when mirrored deeper, e.g. docs/backup/College Planning.
    return next((r for p, r in EXCLUDE_PATHS.items() if low_rel.endswith("/" + p)), None)


def classify_type(ext: str, name: str) -> str:
    if name.lower() in ("makefile", "dockerfile", "procfile"):
        return "config"
    return EXT_TO_TYPE.get(ext, "other")


def infer_project(rel: Path) -> str:
    """First path segment is the project/area. Root files get 'workspace'."""
    parts = rel.parts
    if len(parts) == 1:
        return "workspace"
    top = parts[0]
    if top in ("projects", "apps") and len(parts) > 2:
        return f"{top}/{parts[1]}"
    if top == "agentic-os" and len(parts) > 2 and parts[1] in ("packages", "apps"):
        return f"agentic-os/{parts[2]}"
    return top


def words(text: str) -> set[str]:
    return {w for w in WORD_SPLIT_RE.split(CAMEL_RE.sub(" ", text).lower()) if w}


def match_topics(tokens: set[str]) -> list[str]:
    hits = []
    for topic, keys in TOPIC_RULES.items():
        if any(t == k or (len(k) >= 4 and t.startswith(k)) for k in keys for t in tokens):
            hits.append(topic)
    return hits


def infer_topics(rel: Path, preview: str) -> list[str]:
    topics = []
    if len(rel.parts) > 1 and rel.parts[0] in FOLDER_TOPICS:
        topics.append(FOLDER_TOPICS[rel.parts[0]])
    found = match_topics(words(rel.as_posix()))
    if not found and preview:
        found = match_topics(words(preview))
    topics += [t for t in found if t not in topics]
    return topics[:4]


def read_preview(path: Path, ext: str) -> str:
    if ext not in PREVIEWABLE:
        return ""
    try:
        if path.stat().st_size > MAX_FILE_BYTES_FOR_PREVIEW:
            return ""
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            raw = fh.read(4000)
    except OSError:
        return ""
    if ext == "md":
        heads = HEADING_RE.findall(raw)
        if heads:
            return " · ".join(h.strip() for h in heads[:4])[:MAX_PREVIEW_CHARS]
    return re.sub(r"\s+", " ", raw).strip()[:MAX_PREVIEW_CHARS]


def caption_preview(path: Path) -> str:
    """Text of an image's Markdown sidecar (`photo.png.md`, else `photo.md`)."""
    for side in (path.with_name(path.name + ".md"), path.with_suffix(".md")):
        if side.is_file() and not side.is_symlink() and exclusion("", side.name, False) is None:
            return read_preview(side, "md")
    return ""


def weight_for(name: str, rel: Path, type_: str, days_old: float) -> int:
    """1-5 visual importance. Entry points and fresh docs rank highest."""
    w = 2
    if name.lower() in ENTRY_POINT_NAMES:
        w += 2
    if len(rel.parts) <= 2:
        w += 1
    if len(rel.parts) >= 5:
        w -= 1
    if type_ == "document":
        w += 1
    if type_ in ("image", "archive", "other"):
        w -= 1
    if days_old <= 7:
        w += 1
    return max(1, min(5, w))


def walk(workspace: Path, excluded: Counter) -> list[Path]:
    """Curated file list. Symlinks are skipped, never followed."""
    found: list[Path] = []
    for entry in sorted(workspace.iterdir()):
        if entry.is_symlink():
            excluded["symlink"] += 1
        elif entry.is_file():
            reason = exclusion(entry.name, entry.name, False)
            ext = entry.suffix.lstrip(".").lower()
            if reason:
                excluded[reason] += 1
            elif classify_type(ext, entry.name) in ROOT_FILE_TYPES:
                found.append(entry)
    for top in INCLUDE_ROOTS:
        root = workspace / top
        if root.is_symlink() or not root.is_dir():
            continue
        reason = exclusion(top, top, True)
        if reason:
            excluded[reason] += 1
            continue
        # An unreadable folder is a read error, never a silent gap in coverage.
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda _e: excluded.update(["unreadable"])):
            here = Path(dirpath)
            rel_here = here.relative_to(workspace).as_posix()
            keep = []
            for d in dirnames:
                reason = "symlink" if (here / d).is_symlink() else exclusion(f"{rel_here}/{d}", d, True)
                if reason:
                    excluded[reason] += 1
                else:
                    keep.append(d)
            dirnames[:] = [] if rel_here in SHALLOW_DIRS else keep
            for fn in filenames:
                path = here / fn
                reason = "symlink" if path.is_symlink() else exclusion(f"{rel_here}/{fn}", fn, False)
                if reason:
                    excluded[reason] += 1
                else:
                    found.append(path)
    return found


def build(workspace: Path) -> dict:
    now = datetime.now(timezone.utc)
    excluded: Counter = Counter()
    read_errors = 0
    files = []

    paths = walk(workspace, excluded)
    read_errors += excluded.pop("unreadable", 0)
    for abs_path in paths:
        try:
            st = abs_path.stat()
        except OSError:
            read_errors += 1
            continue
        name = abs_path.name
        ext = abs_path.suffix.lstrip(".").lower()
        rel = abs_path.relative_to(workspace)
        type_ = classify_type(ext, name)
        mtime = datetime.fromtimestamp(st.st_mtime, timezone.utc)
        if type_ == "image":
            preview, kind = caption_preview(abs_path), "caption"
        else:
            preview, kind = read_preview(abs_path, ext), "text"
        if not preview:
            kind = "none"
        files.append(
            {
                "name": name,
                "path": str(abs_path),
                "relativePath": rel.as_posix(),
                "folder": rel.parent.as_posix() if rel.parent != Path(".") else "",
                "project": infer_project(rel),
                "extension": ext or "none",
                "type": type_,
                "size": st.st_size,
                "modified": mtime.astimezone().isoformat(timespec="seconds"),
                "topics": infer_topics(rel, preview),
                "preview": preview,
                "previewKind": kind,
                "weight": weight_for(name, rel, type_, (now - mtime).total_seconds() / 86400),
            }
        )

    files.sort(key=lambda f: f["modified"], reverse=True)

    projects: dict[str, dict] = {}
    for f in files:
        p = projects.setdefault(f["project"], {"name": f["project"], "count": 0, "modified": "", "topics": Counter()})
        p["count"] += 1
        p["modified"] = max(p["modified"], f["modified"])
        p["topics"].update(f["topics"])
    project_list = sorted(
        (
            {"name": p["name"], "count": p["count"], "modified": p["modified"],
             "topics": [t for t, _ in p["topics"].most_common(4)]}
            for p in projects.values()
        ),
        key=lambda p: p["count"],
        reverse=True,
    )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "generated": now.astimezone().isoformat(timespec="seconds"),
        "workspace": str(workspace),
        "coverage": {
            "roots": [r for r in INCLUDE_ROOTS if (workspace / r).is_dir()],
            "missingRoots": [r for r in INCLUDE_ROOTS if not (workspace / r).is_dir()],
            "rootFileTypes": sorted(ROOT_FILE_TYPES),
        },
        "excluded": dict(sorted(excluded.items())),
        "readErrors": read_errors,
        "fileCount": len(files),
        "projectCount": len(project_list),
        "projects": project_list,
        "files": files,
    }


def write_index(index: dict, output: Path) -> None:
    """Atomic replace; on any failure the previous index is left untouched."""
    tmp = output.with_name(output.name + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(index, separators=(",", ":"), ensure_ascii=False))
            fh.flush()
            os.fsync(fh.fileno())  # on disk before it replaces the old index (USB pulls)
        os.replace(tmp, output)
    finally:
        tmp.unlink(missing_ok=True)


def main() -> int:
    if not WORKSPACE.is_dir():
        print(f"Workspace not found: {WORKSPACE}. Is the drive mounted? Index left unchanged.", file=sys.stderr)
        return 2
    print(f"Scanning {WORKSPACE} ...")
    index = build(WORKSPACE)
    if index["fileCount"] == 0:
        print("Scan found no files; refusing to publish an empty index. Index left unchanged.", file=sys.stderr)
        return 1
    write_index(index, OUTPUT)
    print(f"  {index['fileCount']} files across {index['projectCount']} projects")
    print(f"  {sum(index['excluded'].values())} excluded entries by reason: {index['excluded']}")
    print(f"  {index['readErrors']} read error(s); missing roots: {index['coverage']['missingRoots'] or 'none'}")
    print(f"  wrote {OUTPUT}  ({OUTPUT.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
