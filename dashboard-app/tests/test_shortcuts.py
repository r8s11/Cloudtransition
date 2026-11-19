"""Today's Shortcuts card and the Job search / Money rows in Daily.

Contract: docs/plans/command-center-shortcuts/eval.md.
"""

from __future__ import annotations

import re
import socket
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as module  # noqa: E402
from core import config  # noqa: E402
from core.today import command_centre, money_row, shortcut_groups  # noqa: E402

ROW = re.compile(r'<a\s+class="daily-row"\s+href="([^"]+)"([^>]*)>', re.S)


def today_html() -> str:
    with TestClient(module.app) as client:
        r = client.get("/")
    assert r.status_code == 200
    page = r.text
    return page[page.index('id="page-today"'):]


def card(html: str) -> str:
    return html[html.index('id="shortcutsTitle"'):html.index('id="routineTitle"')]


def group(section: str, name: str, following: str | None) -> str:
    start = section.index(f'<div class="task-category-header">{name}</div>')
    end = section.index(f'<div class="task-category-header">{following}</div>') if following else len(section)
    return section[start:end]


def centre(counts=None) -> list[dict]:
    return command_centre(
        {"total_active": 0}, {"today_blocks": [], "inbox_items": []}, 0, None, counts
    )["daily"]


def test_card_position_and_groups():
    html = today_html()
    assert html.index('id="inboxList"') < html.index('id="shortcutsTitle"') < html.index('id="routineTitle"')
    section = card(html)
    order = [section.index(m) for m in ('id="mapFindForm"', "Find a file", ">Apps<", ">Files<", ">Folders<")]
    assert order == sorted(order)
    labels = re.findall(r'<span class="daily-label">([^<]+)</span>', section)
    assert labels == [t["label"] for t in config.SHORTCUTS]


def test_app_and_file_tiles_resolve():
    section = card(today_html())
    apps = ROW.findall(group(section, "Apps", "Files"))
    assert [href for href, _ in apps][:3] == ["/workspace-map/", "/reader", "/mission-control/"]
    assert all('target="_blank"' in rest and 'rel="noopener noreferrer"' in rest for _, rest in apps)
    files = [href for href, _ in ROW.findall(group(section, "Files", "Folders"))]
    assert files == [
        "/workspace-file/TASKS.md",
        "/workspace-file/DASHBOARD.md",
        "/workspace-file/resume/master.md",
        "/workspace-file/interviews/job-applications.yml",
    ]
    with TestClient(module.app) as client:
        for href in ["/workspace-map/", "/reader", *files]:
            assert client.get(href).status_code == 200, href


def test_folder_tiles_carry_map_query():
    rows = ROW.findall(group(card(today_html()), "Folders", None))
    assert all(href == "#workspace-map" for href, _ in rows)
    queries = [re.search(r'data-map-query="([^"]+)"', rest).group(1) for _, rest in rows]
    assert queries == [
        "folder=resume",
        "folder=interviews",
        "folder=artifacts",
        "folder=docs/plans",
        "folder=IT%20Mgmt",
        "folder=second-brain/memories",
    ]


def test_daily_job_search_and_money_rows(tmp_path, monkeypatch):
    tracker = tmp_path / "finance" / "tracker.yml"
    tracker.parent.mkdir()
    tracker.write_text("debts:\n  - name: Card A\n  - name: Card B\n")
    monkeypatch.setattr(config, "MONEY_CANDIDATES", [tracker])
    daily = centre({"tracked": 27, "active": 6, "leads": 21})
    labels = [d["label"] for d in daily]
    jobs = daily[labels.index("Job search")]
    assert jobs["href"] == "#interviews"
    assert jobs["value"] == "27 live · 6 in conversation · 21 new leads"
    assert labels.index("Job search") == labels.index("Tasks") + 1
    money = daily[labels.index("Money")]
    assert labels.index("Money") == labels.index("Projects") + 1
    assert (money["href"], money["value"]) == ("#money", "2 debts on file")
    assert not money.get("placeholder")

    tracker.write_text("as_of: today\ndebts: []\n")
    money = money_row()
    assert money["value"] == "No debts entered yet" and money["placeholder"] is True

    action = {"key": "Acme|IT", "company": "Acme", "when": "today", "date": "2026-11-12", "overdue": False}
    first = command_centre({"total_active": 0}, {"today_blocks": [], "inbox_items": []}, 0, action)["daily"][0]
    assert first["label"] == "Interview mode"


def test_port_tile_follows_listener(monkeypatch):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    monkeypatch.setattr(config, "SHORTCUTS", [{"group": "Apps", "label": "Local app", "port": port, "note": "Mac only"}])
    try:
        row = shortcut_groups()[0]["rows"][0]
        assert row["ok"] and row["new_tab"] and row["note"] == "Mac only"
        assert row["href"] == f"http://127.0.0.1:{port}/"
    finally:
        server.close()
    row = shortcut_groups()[0]["rows"][0]
    assert row["ok"] is False and row["note"] == "Not running"


def test_real_list_has_arms_review_fourth():
    apps = [t for t in config.SHORTCUTS if t["group"] == "Apps"]
    assert (apps[3]["label"], apps[3]["port"]) == ("ARMS review", 8790)


def test_unavailable_tiles_are_placeholders(monkeypatch):
    monkeypatch.setattr(config, "SHORTCUTS", [
        {"group": "Files", "label": "Gone", "file": "nope/x.md"},
        {"group": "Files", "label": "Private", "file": "College Planning/README.md"},
        {"group": "Folders", "label": "Empty", "folder": "no-such-folder"},
    ],)
    section = card(today_html())
    assert section.count('<span class="daily-row is-placeholder">') == 3
    assert section.count("Not available") == 3
    assert not ROW.findall(section)
    hrefs = " ".join(re.findall(r'href="([^"]*)"', section))
    assert not any(bad in hrefs for bad in ("nope", "College", "no-such-folder"))


def test_money_row_survives_bad_tracker(tmp_path, monkeypatch):
    path = tmp_path / "finance" / "tracker.yml"
    path.parent.mkdir()
    monkeypatch.setattr(config, "MONEY_CANDIDATES", [path])
    row = money_row()
    assert (row["value"], row["placeholder"]) == ("No money tracker yet", True)
    for text in ('debts: "oops"\n', "debts: [\n"):
        path.write_text(text)
        row = money_row()
        assert (row["value"], row["placeholder"]) == ("Tracker unreadable", True)
    assert any(d["label"] == "Money" for d in centre())


def test_today_card_order_unchanged():
    html = today_html()
    marks = [
        'id="dailyTitle"',
        ">Next up<",
        'id="captureForm"',
        'id="inboxList"',
        'id="shortcutsTitle"',
        'id="routineTitle"',
        'id="artifactsTitle"',
        ">Quick tools<",
        'id="brainAskForm"',
    ]
    order = [html.index(m) for m in marks]
    assert order == sorted(order)
    artifacts = html[html.index('id="artifactsTitle"'):html.index(">Quick tools<")]
    assert 'class="artifact-row" href="/workspace-file/artifacts/' in artifacts


def test_existing_daily_rows_unchanged():
    daily = {d["label"]: d for d in centre()}
    expected = {
        "Tasks": "#tasks",
        "Routine": "/workspace-file/routine.md",
        "Projects": "#projects",
        "Recent artifacts": "#workspace-map",
        "Workspace map": "#workspace-map",
        "Mission Control": "#mission-control",
        "Second brain": "#today",
        "Metrics": "#metrics",
    }
    kept = [label for label in daily if label in expected]
    assert kept == list(expected)
    assert {label: daily[label]["href"] for label in expected} == expected
    assert daily["Metrics"]["placeholder"] is True
