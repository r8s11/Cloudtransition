"""Read-only file access: Reader, Workspace map, /workspace-file, course pages, second brain."""

import json
import subprocess
import sys

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)
from pydantic import BaseModel

from core import config
from core import workspace_content as wc
from routes.common import templates

router = APIRouter()


# ── Markdown File Discovery ───────────────────────────────────
EXCLUDED_DIRS = {"node_modules", ".git", "venv", "__pycache__", "dashboard-app"}


def discover_md_files() -> list[dict]:
    """Walk workspace and return .md files grouped by directory."""
    files = []
    for md in sorted(config.WORKSPACE.rglob("*.md")):
        # Skip excluded directories and anything the privacy rules protect
        rel = md.relative_to(config.WORKSPACE)
        if md.is_symlink() or any(part in EXCLUDED_DIRS for part in rel.parts) or wc.privacy_violation(
            rel.as_posix()
        ):
            continue
        files.append(
            {
                "path": str(rel),
                "name": md.name,
                "folder": str(rel.parent) if str(rel.parent) != "." else "",
                "size": md.stat().st_size,
            }
        )
    return files


@router.get("/reader", response_class=HTMLResponse)
def reader(request: Request):
    return templates.TemplateResponse(request, "reader.html")


@router.get("/learn/pydantic-ai", include_in_schema=False)
@router.get("/learn/pydantic-ai/", include_in_schema=False)
def pydantic_ai_course():
    return RedirectResponse("/learn/pydantic-ai/lessons/0001-first-agent.html")


@router.get("/learn/pydantic-ai/{filename}", include_in_schema=False)
def pydantic_ai_course_document(filename: str):
    if filename == "KB-README.md":
        return RedirectResponse("/workspace-file/KB-README.md")
    documents = {
        "MISSION.md": config.WORKSPACE / "MISSION.md",
        "RESOURCES.md": config.WORKSPACE / "RESOURCES.md",
    }
    document = documents.get(filename)
    if document is None:
        return PlainTextResponse("Not found", status_code=404)
    return FileResponse(document, media_type="text/plain")


# ── Workspace map (visual-second-brain) + safe file access ─────
# Read-only. Eligibility and privacy rules live in workspace_content.py.

@router.get("/workspace-map", include_in_schema=False)
def workspace_map_redirect():
    return RedirectResponse("/workspace-map/")


@router.get("/workspace-map/")
def workspace_map():
    return FileResponse(
        wc.VIEWER_HTML, media_type="text/html", headers={"Cache-Control": "no-cache"}
    )


@router.get("/workspace-map/workspace-index.json")
def workspace_map_index():
    if not wc.INDEX_FILE.is_file():
        return JSONResponse(
            {"error": "Workspace index missing; run refresh-index.py"}, status_code=503
        )
    # X-Workspace-Open tells the viewer where its Open/Download links point.
    return FileResponse(
        wc.INDEX_FILE,
        media_type="application/json",
        headers={"Cache-Control": "no-store", "X-Workspace-Open": "/workspace-file"},
    )


@router.get("/workspace-file/{path:path}")
def workspace_file(path: str, download: bool = False):
    """Serve one indexed file or live artifact; relative links inside artifacts resolve here too."""
    try:
        target = wc.resolve_file(config.WORKSPACE, wc.INDEX_FILE, path)
    except wc.ContentError as exc:
        return PlainTextResponse(
            str(exc),
            status_code=exc.status,
            headers={"X-Content-Type-Options": "nosniff"},
        )
    media, headers = wc.file_headers(target, download)
    return FileResponse(target, media_type=media, headers=headers)


@router.get("/api/workspace/artifacts")
def workspace_artifacts():
    try:
        return JSONResponse({"artifacts": wc.artifact_entries()})
    except OSError:
        return JSONResponse(
            {"error": "artifacts/ could not be read; is the drive mounted?"},
            status_code=503,
        )


@router.get("/api/files")
def api_files():
    return JSONResponse(discover_md_files())


@router.get("/api/file")
def api_file(path: str = Query(...)):
    # Resolve to absolute path and confirm it lives inside WORKSPACE.
    # Using Path.resolve() handles symlinks, "..", and absolute injections
    # (e.g. Path("/workspace") / Path("/etc/passwd") == Path("/etc/passwd")).
    workspace = config.WORKSPACE.resolve()
    target = (workspace / path).resolve()
    try:
        resolved_rel = target.relative_to(workspace).as_posix()
    except ValueError:
        return JSONResponse({"error": "Invalid path"}, status_code=400)
    # Same privacy rules as the Workspace map, on the requested and the real path.
    if wc.privacy_violation(path.strip("/")) or wc.privacy_violation(resolved_rel):
        return JSONResponse({"error": "File not available"}, status_code=403)
    if not target.exists() or not target.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)
    ALLOWED_EXTENSIONS = {
        ".md",
        ".txt",
        ".yaml",
        ".yml",
        ".json",
        ".csv",
        ".html",
        ".py",
    }
    if target.suffix.lower() not in ALLOWED_EXTENSIONS:
        return JSONResponse({"error": "File type not allowed"}, status_code=403)
    return JSONResponse({"path": path, "content": target.read_text(errors="replace")})


# ── Second brain (second-brain/brain.py, deterministic, no model) ──
BRAIN_TIMEOUT = 60


class RememberRequest(BaseModel):
    title: str
    summary: str
    body: str


def _brain(*args: str) -> JSONResponse:
    """Run one brain.py subcommand and relay its JSON. Arguments go in as
    separate argv elements with no shell, so input cannot become a command."""
    try:
        proc = subprocess.run(
            [sys.executable, str(config.BRAIN_CLI), *args],
            cwd=config.WORKSPACE,
            capture_output=True,
            text=True,
            timeout=BRAIN_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return JSONResponse({"error": f"brain.py failed: {exc}"}, status_code=500)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        detail = (proc.stderr or proc.stdout).strip()[-400:] or "no output"
        return JSONResponse({"error": detail}, status_code=500)
    return JSONResponse(data, status_code=200 if proc.returncode == 0 else 422)


@router.get("/api/brain/query")
def brain_query(q: str = Query(..., min_length=2, max_length=200)):
    return _brain("query", q)


@router.post("/api/brain/remember")
def brain_remember(req: RememberRequest, x_requested_with: str = Header(default="")):
    if x_requested_with != "XMLHttpRequest":
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    return _brain(
        "remember", "--title", req.title, "--summary", req.summary, "--body", req.body
    )
