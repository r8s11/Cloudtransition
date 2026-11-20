"""Jinja environment shared by every router that renders a page."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from core.today import _routine_plain_text, md_inline

templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
templates.env.filters["md"] = md_inline
templates.env.filters["plain"] = _routine_plain_text
