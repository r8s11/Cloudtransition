"""Read-only access to workspace files for the Workspace map and Today artifacts.

A file is served only when it is listed in the Visual Second Brain index or is a
live artifact (artifacts/catalog.py rules), and it still passes the indexer's
curated-scope and privacy rules at request time: approved root, no excluded
name or folder, no symlink anywhere on the path, inside the workspace. The
index's absolute paths are never trusted. Active documents (HTML, SVG, XML)
are sandboxed with no scripts and no network.
"""

from __future__ import annotations

import importlib.util
import json
import mimetypes
from pathlib import Path
from urllib.parse import quote

WORKSPACE = Path(__file__).resolve().parent.parent
VIEWER_DIR = WORKSPACE / "visual-second-brain"
VIEWER_HTML = VIEWER_DIR / "visual-second-brain.html"
INDEX_FILE = VIEWER_DIR / "workspace-index.json"
INDEX_SCHEMA = 2
ARTIFACTS_DIR = "artifacts"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# One source of truth for scope and privacy rules: the indexer itself.
_rules = _load_module("vsb_refresh_index", VIEWER_DIR / "refresh-index.py")
_catalog = _load_module("artifact_catalog", WORKSPACE / ARTIFACTS_DIR / "catalog.py")


class ContentError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


_index_cache: dict = {"key": None, "paths": frozenset()}


def indexed_paths(index_path: Path) -> frozenset[str]:
    """relativePath set from the current index; 503 when missing, damaged or outdated."""
    try:
        stat = index_path.stat()
        key = (str(index_path), stat.st_mtime_ns, stat.st_size)
        if _index_cache["key"] == key:
            return _index_cache["paths"]
        data = json.loads(index_path.read_text(encoding="utf-8"))
        if data.get("schemaVersion") != INDEX_SCHEMA or not isinstance(data.get("files"), list):
            raise ValueError("unsupported index")
        paths = frozenset(str(f["relativePath"]) for f in data["files"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ContentError(503, "Workspace index unavailable; run refresh-index.py") from exc
    _index_cache.update(key=key, paths=paths)
    return paths


def artifact_entries(workspace: Path = WORKSPACE) -> list[dict]:
    """Live artifacts, newest first, as workspace-relative rows that pass the privacy rules."""
    root = workspace / ARTIFACTS_DIR
    if root.is_symlink() or not root.is_dir():
        return []
    rows = []
    for entry in _catalog.collect_entries(root):
        rel = f"{ARTIFACTS_DIR}/{entry['relativePath']}"
        if _rule_violation(rel.split("/")) is None:
            rows.append({**entry, "relativePath": rel})
    return rows


# Reasons that protect private content. The dashboard's markdown reader and
# run-output viewer (/api/file) apply only these; scope and cache rules belong
# to the Workspace map alone.
PRIVACY_REASONS = {
    "secret_name", "private_or_employer", "employer_work_log", "office_lock",
    "personal_academic_records", "employer_private",
    "private_kb",
}


def privacy_violation(rel: str) -> str | None:
    """Privacy reason for a workspace-relative path, checked on every component, or None.

    Private folder paths also match when mirrored deeper (caches, backups,
    e.g. ".trail/cache/College Planning/…"), not only from the workspace root.
    """
    parts = rel.split("/")
    for i, part in enumerate(parts):
        reason = _rules.exclusion("/".join(parts[: i + 1]), part, i < len(parts) - 1)
        if reason in PRIVACY_REASONS:
            return reason
    low = [p.lower() for p in parts]
    for start in range(1, len(low)):
        for end in range(start + 1, len(low) + 1):
            reason = _rules.EXCLUDE_PATHS.get("/".join(low[start:end]))
            if reason in PRIVACY_REASONS:
                return reason
    return None



def _rule_violation(parts: list[str]) -> str | None:
    if len(parts) == 1:
        ext = Path(parts[0]).suffix.lstrip(".").lower()
        if _rules.classify_type(ext, parts[0]) not in _rules.ROOT_FILE_TYPES:
            return "root_type"
    elif parts[0] not in _rules.INCLUDE_ROOTS:
        return "outside_scope"
    for i, part in enumerate(parts):
        reason = _rules.exclusion("/".join(parts[: i + 1]), part, i < len(parts) - 1)
        if reason:
            return reason
    return None


def resolve_file(workspace: Path, index_path: Path, rel: str) -> Path:
    """Absolute path for an eligible workspace-relative path, else ContentError 403/404/503."""
    # Split on "/" only: on macOS "\" and "C:" are ordinary filename characters.
    if not rel or len(rel) > 1024 or "\x00" in rel or rel.startswith("/"):
        raise ContentError(403, "Invalid path")
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise ContentError(403, "Invalid path")
    if _rule_violation(parts):
        raise ContentError(403, "Not available")
    live_artifact = parts[0] == ARTIFACTS_DIR and _catalog.is_artifact("/".join(parts[1:]))
    if not live_artifact and rel not in indexed_paths(index_path):
        raise ContentError(403, "Not in the workspace index")
    for i in range(1, len(parts) + 1):
        if workspace.joinpath(*parts[:i]).is_symlink():
            raise ContentError(403, "Not available")
    target = workspace.joinpath(*parts)
    if not target.is_file():
        raise ContentError(404, "File not found")
    resolved = target.resolve()
    if not resolved.is_relative_to(workspace.resolve()):
        raise ContentError(403, "Not available")
    return resolved


# Allowlist: only these render in the browser. Anything else downloads as
# octet-stream, so unknown active types (.xht, .svgz, .xsl, …) never execute.
ACTIVE_TYPES = {  # rendered, but sandboxed: no scripts, forms, popups or network
    ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8",
    ".xhtml": "application/xhtml+xml", ".svg": "image/svg+xml", ".xml": "text/xml; charset=utf-8",
}
PASSIVE_TYPES = {
    ".css": "text/css; charset=utf-8", ".pdf": "application/pdf",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
    ".webp": "image/webp", ".avif": "image/avif", ".bmp": "image/bmp", ".ico": "image/x-icon",
    ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf",
}
# Everything the indexer can preview is shown as source, never executed.
TEXT_EXT = {f".{e}" for e in _rules.PREVIEWABLE} - set(ACTIVE_TYPES) - set(PASSIVE_TYPES)
NO_NETWORK_CSP = (
    "default-src 'none'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; media-src 'self'; frame-ancestors 'self'"
)


def file_headers(path: Path, download: bool) -> tuple[str, dict]:
    """Media type and response headers for serving a resolved workspace file."""
    ext = path.suffix.lower()
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "no-cache",
    }
    if ext in TEXT_EXT:
        media = "text/plain; charset=utf-8"
        headers["Content-Security-Policy"] = NO_NETWORK_CSP
    elif ext in PASSIVE_TYPES:
        media = PASSIVE_TYPES[ext]
        if media.startswith("text/"):
            headers["Content-Security-Policy"] = NO_NETWORK_CSP
    else:
        media = ACTIVE_TYPES.get(ext, "application/octet-stream")
        headers["Content-Security-Policy"] = "sandbox; " + NO_NETWORK_CSP
    inline = not download and media != "application/octet-stream"
    headers["Content-Disposition"] = f"{'inline' if inline else 'attachment'}; filename*=UTF-8''{quote(path.name)}"
    return media, headers
