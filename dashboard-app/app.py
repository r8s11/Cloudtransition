"""
Command Center — FastAPI app that reads workspace YAML/MD files directly.

This module only wires the app: .env loading, lifespan, middleware, static
mounts and the routers in routes/. Workspace readers live in core/.

Run:  uvicorn app:app --reload
Open: http://localhost:8000
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core import config
from core import workspace_content as wc
from routes import calendar, files, interviews, metrics, pages, tasks
from routes import runs as run_routes


def _load_env_file(path: Path, environ: dict[str, str] | None = None) -> None:
    """Load KEY=VALUE lines from a local .env without overriding real env vars.

    The dashboard runs under launchd with its own environment, so a
    gitignored dashboard-app/.env is where local keys such as
    OPENROUTER_API_KEY belong.
    """
    target = os.environ if environ is None else environ
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        target.setdefault(key, value)


_load_env_file(Path(__file__).resolve().parent / ".env")


# ── App ────────────────────────────────────────────────────────
app = FastAPI(title="Command Center", lifespan=calendar.calendar_lifespan)
app.middleware("http")(calendar.calendar_origin_guard)

app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)
app.mount(
    "/learn/pydantic-ai/lessons",
    StaticFiles(directory=config.COURSE_LESSONS, follow_symlink=False),
    name="pydantic-ai-lessons",
)
app.mount(
    "/learn/pydantic-ai/assets",
    StaticFiles(directory=config.COURSE_ASSETS, follow_symlink=False),
    name="pydantic-ai-assets",
)
app.mount(
    "/learn/pydantic-ai/reference",
    StaticFiles(directory=config.COURSE_REFERENCE, follow_symlink=False),
    name="pydantic-ai-reference",
)
# Workspace map viewer assets; eligibility and privacy rules live in workspace_content.py.
app.mount(
    "/workspace-map/assets",
    StaticFiles(directory=wc.VIEWER_HTML.parent / "assets", follow_symlink=False),
    name="workspace-map-assets",
)

# ── Routers ────────────────────────────────────────────────────
app.include_router(metrics.router)
app.include_router(calendar.router)
app.include_router(interviews.router)
app.include_router(run_routes.router)
app.include_router(files.router)
app.include_router(tasks.router)
app.include_router(pages.router)
