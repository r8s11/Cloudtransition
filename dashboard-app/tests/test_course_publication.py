from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as module  # noqa: E402


def test_course_shortcut_is_available_from_today():
    row = next(
        row
        for group in module.shortcut_groups()
        if group["name"] == "Apps"
        for row in group["rows"]
        if row["label"] == "Pydantic AI course"
    )
    assert (row["href"], row["new_tab"], row["note"]) == (
        "/learn/pydantic-ai/",
        True,
        "8 lessons",
    )
    daily = module.command_centre(
        {"total_active": 0}, {"today_blocks": [], "inbox_items": []}, 0
    )["daily"]
    daily_course = next(row for row in daily if row["label"] == "Pydantic AI course")
    assert (daily.index(daily_course), daily_course["href"], daily_course["new_tab"]) == (
        2,
        "/learn/pydantic-ai/",
        True,
    )


def test_course_routes_serve_pages_styles_and_reference():
    with TestClient(module.app, follow_redirects=False) as client:
        response = client.get("/learn/pydantic-ai/")
        assert response.status_code == 307
        assert response.headers["location"] == "/learn/pydantic-ai/lessons/0001-first-agent.html"
        lesson = client.get("/learn/pydantic-ai/lessons/0001-first-agent.html")
        stylesheet = client.get("/learn/pydantic-ai/assets/course.css")
        reference = client.get("/learn/pydantic-ai/reference/personal-agents.html")
        assert lesson.status_code == stylesheet.status_code == reference.status_code == 200
        assert "Your First Pydantic AI Agent" in lesson.text
        assert "--paper" in stylesheet.text
        assert "Personal agents" in reference.text


def test_course_documents_are_allowlisted_and_gmail_guide_uses_privacy_route():
    with TestClient(module.app, follow_redirects=False) as client:
        for filename in ("MISSION.md", "RESOURCES.md"):
            assert client.get(f"/learn/pydantic-ai/{filename}").status_code == 200

        guide = client.get("/learn/pydantic-ai/KB-README.md")
        assert guide.status_code == 307
        assert guide.headers["location"] == "/workspace-file/KB-README.md"
        assert client.get("/learn/pydantic-ai/.env").status_code == 404
