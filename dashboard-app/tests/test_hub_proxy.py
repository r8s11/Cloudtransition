"""Mission Control proxy: only pause and stop-runs are writable (U6, U14, R6).

The fake upstream records every request; nothing here touches the real
agentic-os server on :8787 or the real tracker file.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as module  # noqa: E402
from core import config  # noqa: E402

UPSTREAM = config.MISSION_CONTROL_UPSTREAM
TAILNET_HOST = "roosevelts-macbook-air.tail9aa23.ts.net"


class FakeResponse:
    def __init__(self, body: bytes = b'{"ok":true}', ctype: str = "application/json"):
        self._body = body
        self.headers = {"Content-Type": ctype}
        self.status = 200
        self.code = 200

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeUpstream:
    """Records (method, url, body, content-type) for every proxied request."""

    def __init__(self):
        self.calls: list[tuple] = []
        self.response = FakeResponse()

    def __call__(self, req, timeout=None):
        if isinstance(req, urllib.request.Request):
            self.calls.append(
                (req.get_method(), req.full_url, req.data, req.get_header("Content-type"))
            )
        else:
            self.calls.append(("GET", req, None, None))
        return self.response


@pytest.fixture()
def upstream(monkeypatch):
    fake = FakeUpstream()
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return fake


def test_pause_and_stop_reach_the_hub(upstream):
    pause = "/mission-control/api/hub/missions/m-1/pause"
    with TestClient(module.app) as client:
        first = client.post(pause, json={})
        stop = client.post("/mission-control/api/hub/stop-runs", json={})
        second = client.post(pause, json={})  # a second pause is a 200 no-op upstream

    assert [r.status_code for r in (first, stop, second)] == [200, 200, 200]
    assert upstream.calls == [
        ("POST", f"{UPSTREAM}/api/hub/missions/m-1/pause", b"{}", "application/json"),
        ("POST", f"{UPSTREAM}/api/hub/stop-runs", b"{}", "application/json"),
        ("POST", f"{UPSTREAM}/api/hub/missions/m-1/pause", b"{}", "application/json"),
    ]


def test_only_pause_and_stop_are_writable(upstream):
    blocked = [
        "/mission-control/api/hub/missions/prepare-application",
        "/mission-control/api/hub/missions/m-1/messages",
        "/mission-control/api/hub/missions/m-1/waiting/w-1/resolve",
        "/mission-control/api/hub/missions/m-1/resume",
        "/mission-control/api/approvals/a-1/resolve",
    ]
    with TestClient(module.app) as client:
        for path in blocked:
            r = client.post(path, json={"decision": "approve"})
            assert r.status_code == 405, path
            assert "error" in r.json()
        # The read-only window keeps working.
        session = client.get("/mission-control/api/hub/missions/m-1/session")
        messages = client.get("/mission-control/api/hub/missions/m-1/messages")

    assert upstream.calls == [
        ("GET", f"{UPSTREAM}/api/hub/missions/m-1/session", None, None),
        ("GET", f"{UPSTREAM}/api/hub/missions/m-1/messages", None, None),
    ]
    assert session.status_code == messages.status_code == 200
    assert session.json() == {"ok": True}


def test_get_proxy_still_rewrites_html(upstream):
    upstream.response = FakeResponse(b'<script src="/api/hub.js"></script>', "text/html")
    with TestClient(module.app) as client:
        r = client.get("/mission-control/")
    assert r.status_code == 200
    assert '"/mission-control/api/hub.js"' in r.text
    assert upstream.calls == [("GET", f"{UPSTREAM}/", None, None)]


@pytest.fixture()
def tracker(tmp_path, monkeypatch):
    target = tmp_path / "job-applications.yml"
    target.write_text(
        "active_applications:\n"
        "  - company: Acme Health\n"
        "    role: Systems Administrator\n"
        "    status: applied\n"
        "    priority: high\n"
        "    job_url: https://example.com/job/123?x=1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "JOBS_FILE", target)
    return target


def interviews_page(host: str) -> str:
    with TestClient(module.app) as client:
        r = client.get("/", headers={"Host": host})
    assert r.status_code == 200
    page = r.text
    return page[page.index('id="page-interviews"'):]


def test_mission_link_only_on_local_hosts(tracker, upstream):
    for host in ("localhost", "127.0.0.1:8000"):
        page = interviews_page(host)
        assert ">Mission</a>" in page, host
        assert "http://localhost:8787/#session-prepare?company=Acme%20Health" in page
        assert "role=Systems%20Administrator" in page
        assert "url=https%3A//example.com/job/123%3Fx%3D1" in page

    page = interviews_page(TAILNET_HOST)
    assert "session-prepare" not in page
    assert ">Mission</a>" not in page
