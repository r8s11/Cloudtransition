"""Isolated provider/policy contracts; no OAuth, network, or real worker service."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dashboard-app"))
import calendar_bridge as bridge
from calendar_google import TASKS_SCOPES, _atomic_json, _read_json
from calendar_model import CalendarError
from core.calendar_sources import annotate
from calendar_tests.fake_google import FakeTasksService, HttpFailure, Request
from core.google_calendar import CalendarService, SubprocessProvider

NOW = datetime(2026, 11, 14, 15, tzinfo=timezone.utc)
CONFIG = {"calendars": ["owned", "reader"], "event_calendar": "owned", "tasklist": "chosen-list", "timezone": "America/New_York", "sources": ["main"]}


class CalendarAPI:
    def __init__(self):
        self.rows = {"owned": [], "reader": []}
        self.remote = {}
        self.inserts = 0
        self.options = []
        self.fail_reads = set()
        self.timeout_create = False
        self.get_error = None

    def calendarList(self):
        class Lists:
            def list(self, **options):
                return Request(lambda: {"items": [{"id": "owned", "summary": "Personal", "accessRole": "owner"}, {"id": "reader", "summary": "Shared", "accessRole": "reader"}, {"id": "writer", "summary": "Not owned", "accessRole": "writer"}]})
        return Lists()

    def events(self):
        outer = self
        class Events:
            def list(self, **options):
                outer.options.append(options)
                def action():
                    if options["calendarId"] in outer.fail_reads:
                        raise HttpFailure(503)
                    offset = int(options.get("pageToken", "0"))
                    rows = outer.rows[options["calendarId"]]
                    response = {"items": deepcopy(rows[offset:offset + 1])}
                    if offset + 1 < len(rows):
                        response["nextPageToken"] = str(offset + 1)
                    return response
                return Request(action)

            def insert(self, *, calendarId, body, **options):
                def action():
                    assert options == {"sendUpdates": "none"}
                    assert "attendees" not in body and "description" not in body
                    outer.inserts += 1
                    if body["id"] in outer.remote:
                        raise HttpFailure(409)
                    remote = {**deepcopy(body), "htmlLink": "https://calendar.google.com/calendar/event?eid=synthetic"}
                    outer.remote[body["id"]] = remote
                    if outer.timeout_create:
                        outer.timeout_create = False
                        raise TimeoutError("provider-private-canary")
                    return remote
                return Request(action)

            def get(self, *, calendarId, eventId):
                def action():
                    if outer.get_error:
                        raise outer.get_error
                    if eventId not in outer.remote:
                        raise HttpFailure(404)
                    return deepcopy(outer.remote[eventId])
                return Request(action)
        return Events()


class PolicyProvider:
    def __init__(self):
        self.sent = []
        self.choice_reads = 0
        self.callback = None
        self.results = []

    def choices(self):
        self.choice_reads += 1
        return {"calendars": [{"id": "owned", "name": "Personal", "writable": True}, {"id": "reader", "name": "Shared", "writable": False}], "tasklists": [{"id": "chosen-list", "name": "Actions"}], "errors": {}}

    def agenda(self, config, now):
        return {"items": [], "errors": {}, "updated": now.isoformat()}

    def publish(self, item, config):
        self.sent.append(deepcopy(item))
        if self.callback:
            self.callback()
        return self.results.pop(0) if self.results else {"status": "published", "id": "remote-" + item["key"], "url": "https://tasks.google.com/"}


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "TASKS.md"
    path.write_text("# Actions\n- [ ] " + annotate("Dated action", {"date": "2026-11-16"}) + "\n- [ ] " + annotate("Timed action", {"start": "2026-11-17T14:00", "end": "2026-11-17T15:00", "timezone": "America/New_York"}) + "\n- [ ] Undated action\n")
    (tmp_path / "extra.md").write_text("- [ ] " + annotate("Unselected canary", {"date": "2026-11-18"}) + "\n")
    realms = [{"id": "main", "name": "Tasks", "file": "TASKS.md"}, {"id": "extra", "name": "Extra", "file": "extra.md"}, {"id": "college", "name": "College", "file": "College Planning/records.md"}]
    jobs = "interviews/job-applications.yml"
    return tmp_path, path, realms, jobs


def service(source, provider=None):
    root, _, realms, jobs = source
    return CalendarService(root, realms, jobs, runtime=root / "private-runtime", provider=provider or PolicyProvider(), clock=lambda: NOW)


def activate(instance):
    preview = instance.preview(CONFIG)
    instance.enable(CONFIG, preview["review"])
    return preview


def test_agenda(tmp_path, monkeypatch):
    calendar, tasks = CalendarAPI(), FakeTasksService()
    calendar.rows["owned"] = [
        {"id": "all-day", "summary": "All day", "start": {"date": "2026-11-14"}, "end": {"date": "2026-11-16"}, "htmlLink": "https://calendar.google.com/calendar/event?eid=one"},
        {"id": "instance", "recurringEventId": "series", "summary": "<img src=x onerror=alert(1)>", "start": {"dateTime": "2026-11-15T00:30:00Z"}, "end": {"dateTime": "2026-11-15T01:30:00Z"}, "htmlLink": "javascript:alert(1)"},
        {"id": "missing-title", "start": {"dateTime": "2026-11-16T14:00:00-05:00"}, "end": {"dateTime": "2026-11-16T15:00:00-05:00"}},
        {"id": "cancelled", "status": "cancelled", "start": {"date": "2026-11-15"}, "end": {"date": "2026-11-16"}},
    ]
    provider = bridge.GoogleProvider(tmp_path / "private", calendar=calendar, tasks=tasks)
    published = provider.publish({"key": "a" * 64, "title": "Mapped task", "schedule": {"date": "2026-11-16"}}, CONFIG)
    assert published["status"] == "published"
    tasks.remote.append({"id": "unrelated", "tasklist": "chosen-list", "title": "Do not import", "due": "2026-11-16T00:00:00Z"})
    result = provider.agenda(CONFIG, NOW)
    assert result["state"] == "ready" and result["errors"] == {}
    assert [item["id"] for item in result["items"]] == ["all-day", "instance", published["id"], "missing-title"]
    all_day, occurrence = result["items"][:2]
    assert all_day["start"] == "2026-11-14" and all_day["end"] == "2026-11-16" and all_day["all_day"]
    assert occurrence["start"] == "2026-11-14T19:30:00-05:00"
    assert occurrence["title"].startswith("<img") and occurrence["url"] == ""
    assert result["items"][-1]["title"] == "Untitled event"
    assert result["items"][2]["kind"] == "task"
    assert all(options["singleEvents"] and not options["showDeleted"] for options in calendar.options)
    assert calendar.options[0]["timeMin"] == "2026-11-14T00:00:00-05:00"
    assert calendar.options[0]["timeMax"] == "2026-11-21T00:00:00-05:00"
    calendar.fail_reads.add("reader")
    partial = provider.agenda(CONFIG, NOW)
    assert partial["state"] == "partial" and partial["items"]
    assert partial["errors"] == {"reader": "deferred"}
    assert "canary" not in json.dumps(partial)
    monkeypatch.setattr(bridge, "MAX_PAGES", 1)
    assert provider.agenda(CONFIG, NOW)["truncated"]
    assert calendar.inserts == 0 and tasks.insert_attempts == 1


def test_automatic_policy(source):
    provider = PolicyProvider()
    instance = service(source, provider)
    assert instance.snapshot()["enabled"] is False
    assert not instance.runtime.exists()
    assert instance.run_once()["status"] == "paused" and provider.choice_reads == 0
    preview = instance.preview(CONFIG)
    assert not instance.runtime.exists() and provider.sent == []
    assert {item["title"] for item in preview["backlog"]} == {"Dated action", "Timed action", "Undated action"}
    assert "Unselected canary" not in json.dumps(preview)
    instance.enable(CONFIG, preview["review"])
    instance.run_once()
    assert len(provider.sent) == 2
    assert all(set(item) == {"key", "title", "schedule"} for item in provider.sent)
    assert ["date" in item["schedule"] for item in provider.sent] == [True, False]
    instance.run_once()
    assert len(provider.sent) == 2
    root, path, _, _ = source
    path.write_text("Unrelated line\n" + path.read_text() + "- [ ] " + annotate("Future action", {"date": "2026-11-19"}) + "\n")
    restarted = service(source, provider)
    assert restarted.snapshot()["enabled"]
    restarted.run_once()
    assert len(provider.sent) == 3 and provider.sent[-1]["title"] == "Future action"
    assert (root / "private-runtime" / "policy.json").stat().st_mode & 0o777 == 0o600
    assert instance.runtime.stat().st_mode & 0o777 == 0o700
    assert "Unselected canary" not in (instance.runtime / "policy.json").read_text()
    class StopAfterInterval:
        def __init__(self):
            self.done = False
            self.intervals = []
        def is_set(self):
            return self.done
        def wait(self, seconds):
            self.intervals.append(seconds)
            self.done = True
    restarted._stop = StopAfterInterval()
    restarted._worker()
    assert restarted._stop.intervals == [60] and len(provider.sent) == 3


def test_agenda_service_stale_sources(source):
    provider = PolicyProvider()
    instance = service(source, provider)
    instance.configure(CONFIG)
    event = {"id": "one", "kind": "event", "title": "<b>Text only</b>", "date": "2026-11-15",
             "start": "2026-11-15T10:00:00-05:00", "end": "2026-11-15T11:00:00-05:00",
             "calendar": "owned", "source": "Personal", "all_day": False,
             "url": "javascript:private-canary"}
    provider.agenda = lambda config, now: {"items": [event], "errors": {}, "updated": now.isoformat()}
    first = instance.refresh()
    assert first["agenda"]["state"] == "ready" and first["agenda"]["items"][0]["url"] == ""
    saved = (instance.runtime / "policy.json").read_bytes()
    provider.agenda = lambda config, now: {"items": [], "errors": {"owned": "reconnect"}}
    stale = instance.refresh()
    assert stale["agenda"]["state"] == "stale"
    assert stale["agenda"]["items"][0]["stale"] is True
    assert stale["agenda"]["updated"] == first["agenda"]["updated"]
    assert (instance.runtime / "policy.json").read_bytes() == saved
    assert provider.sent == []


def test_authorization_pauses_only_affected_provider(source):
    provider = PolicyProvider()
    provider.results = [{"status": "reconnect"}, {"status": "published", "id": "event-one"}]
    instance = service(source, provider)
    activate(instance)
    instance.run_once()
    assert len(provider.sent) == 2
    assert {value["kind"]: value["status"] for value in instance.snapshot()["outcomes"]} == {"task": "reconnect", "event": "published"}
    instance.run_once()
    assert len(provider.sent) == 2
    activate(instance)
    instance.run_once()
    assert len(provider.sent) == 3
    assert all(value["status"] == "published" for value in instance.snapshot()["outcomes"])


def test_automatic_policy_pins_legacy_identity(source):
    root, path, realms, jobs = source
    path.write_text('- [ ] Legacy dated <!-- calendar: {"date":"2026-11-16"} -->\n')
    from core.calendar_sources import collect
    before = collect(root, realms, jobs, ["main"])[0]
    assert before["binding"]["identity"] is None
    provider = PolicyProvider()
    instance = service(source, provider)
    activate(instance)
    instance.run_once()
    pinned = collect(root, realms, jobs, ["main"])[0]
    assert pinned["key"] == before["key"] and pinned["binding"]["identity"] == before["key"]
    path.write_text("Moved line\n" + path.read_text().replace("Legacy dated", "Renamed legacy"))
    instance.run_once()
    assert len(provider.sent) == 1
    assert instance.snapshot()["backlog"][0]["status"] == "needs_review"


def test_publication_recovery_preserves_legacy_cli_state(tmp_path):
    from calendar_google import publish as legacy_publish
    from calendar_model import make_preview
    path = tmp_path / "TASKS.md"
    path.write_text("- [ ] Legacy task\n")
    runtime = tmp_path / "private"
    tasks = FakeTasksService()
    preview = make_preview(path, [("1", "2026-11-16")], "chosen-list")
    legacy_publish(preview, preview["approval"], runtime, tasks)
    original = (runtime / "state.json").read_bytes()
    provider = bridge.GoogleProvider(runtime, calendar=CalendarAPI(), tasks=tasks)
    renamed_identity = {"key": "a" * 64, "title": "Legacy task", "schedule": {"date": "2026-11-16"}}
    assert provider.publish(renamed_identity, CONFIG)["status"] == "needs_review"
    same_identity = {**renamed_identity, "key": preview["items"][0]["key"]}
    result = provider.publish(same_identity, CONFIG)
    assert result["status"] == "published" and result["id"] == tasks.remote[0]["id"]
    assert tasks.insert_attempts == 1
    assert (runtime / "state.json").read_bytes() == original


def test_authorization(source, tmp_path, monkeypatch):
    provider = PolicyProvider()
    instance = service(source, provider)
    for changes in ({"sources": ["../../TASKS.md"]}, {"sources": ["college"]}, {"event_calendar": "reader"}, {"event_calendar": "forged"}, {"tasklist": "forged"}, {"timezone": "Not/AZone"}, {"calendars": ["forged"]}):
        with pytest.raises(CalendarError):
            instance.preview({**CONFIG, **changes})
    assert provider.sent == [] and not instance.runtime.exists()
    reviewed = instance.preview(CONFIG)
    with pytest.raises(CalendarError):
        instance.enable(CONFIG, "forged")
    source[1].write_text(source[1].read_text() + "- [ ] Added during review\n")
    with pytest.raises(CalendarError):
        instance.enable(CONFIG, reviewed["review"])
    instance.configure(CONFIG)
    assert not instance.snapshot()["enabled"]
    instance.refresh()
    assert provider.sent == []
    token = tmp_path / "grant" / "events" / "token.json"
    _atomic_json(token, {"scopes": list(TASKS_SCOPES)})
    with pytest.raises(CalendarError, match="incorrect scopes"):
        bridge.calendar_service(tmp_path / "grant")
    assert set(bridge.CALENDAR_SCOPES).isdisjoint(TASKS_SCOPES)
    assert not (tmp_path / "grant" / "token.json").exists()
    calls = []
    def process(argv, **options):
        calls.append((argv, options))
        return SimpleNamespace(returncode=0, stdout='{"calendars":[],"tasklists":[]}', stderr="provider-private-canary")
    monkeypatch.setattr("core.google_calendar.subprocess.run", process)
    SubprocessProvider().choices()
    assert calls[0][0] == [str(ROOT / ".kb-venv/bin/python"), str(ROOT / "calendar_bridge.py"), "choices"]
    assert calls[0][1]["timeout"] == 40 and "shell" not in calls[0][1]
    assert bridge.safe_link("https://calendar.google.com.evil.test/") == ""
    assert bridge.safe_link("https://user@calendar.google.com/") == ""


def test_publication_recovery(tmp_path, monkeypatch):
    calendar, tasks = CalendarAPI(), FakeTasksService()
    provider = bridge.GoogleProvider(tmp_path / "private", calendar=calendar, tasks=tasks)
    dated = {"key": "b" * 64, "title": "Recover task", "schedule": {"date": "2026-11-16"}}
    tasks.timeout_after_create.add(1)
    assert provider.publish(dated, CONFIG)["status"] == "uncertain"
    assert provider.publish(dated, CONFIG)["status"] == "published"
    assert tasks.insert_attempts == 1
    timed = {"key": "c" * 64, "title": "Recover event", "schedule": {"start": "2026-11-17T14:00", "end": "2026-11-17T15:00", "timezone": "America/New_York"}}
    calendar.timeout_create = True
    assert provider.publish(timed, CONFIG)["status"] == "uncertain"
    calendar.get_error = HttpFailure(401)
    assert provider.publish(timed, CONFIG)["status"] == "reconnect"
    state = _read_json(tmp_path / "private" / "dashboard-publish.json")
    event_record = next(value for value in state["entries"].values() if value["kind"] == "event")
    assert event_record["status"] == "uncertain"
    calendar.get_error = None
    assert provider.publish(timed, CONFIG)["status"] == "published" and calendar.inserts == 1
    assert len(next(iter(calendar.remote))) == 64
    ambiguous = {**dated, "key": "d" * 64}
    tasks.timeout_after_create.add(2)
    assert provider.publish(ambiguous, CONFIG)["status"] == "uncertain"
    tasks.remote.append({**deepcopy(tasks.remote[-1]), "id": "ambiguous-other"})
    assert provider.publish(ambiguous, CONFIG)["status"] == "uncertain" and tasks.insert_attempts == 2
    rate_limited = {**dated, "key": "e" * 64}
    tasks.failures[3] = HttpFailure(429)
    assert provider.publish(rate_limited, CONFIG)["status"] == "deferred"
    assert provider.publish(rate_limited, CONFIG)["status"] == "published"
    original = bridge._atomic_json
    writes = 0
    def fail_success(path, state):
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("local-private-canary")
        return original(path, state)
    pending = {**dated, "key": "f" * 64}
    with patch.object(bridge, "_atomic_json", side_effect=fail_success):
        with pytest.raises(OSError):
            provider.publish(pending, CONFIG)
    attempts = tasks.insert_attempts
    restarted = bridge.GoogleProvider(tmp_path / "private", calendar=calendar, tasks=tasks)
    assert restarted.publish(pending, CONFIG)["status"] == "published"
    assert tasks.insert_attempts == attempts


def test_pause_conflicts(source):
    provider = PolicyProvider()
    instance = service(source, provider)
    activate(instance)
    provider.callback = instance.pause
    instance.run_once()
    assert len(provider.sent) == 1
    assert not service(source, provider).snapshot()["enabled"]
    assert service(source, provider).run_once()["status"] == "paused"
    provider.callback = None
    activate(instance)
    instance.run_once()
    assert len(provider.sent) == 2
    original = source[1].read_text()
    source[1].write_text("Line movement\n" + original)
    instance.run_once()
    assert len(provider.sent) == 2
    source[1].write_text(source[1].read_text().replace("Dated action", "Changed title").replace("2026-11-16", "2026-11-20"))
    instance.run_once()
    assert len(provider.sent) == 2
    changed = next(item for item in instance.snapshot()["backlog"] if item["title"] == "Changed title")
    assert changed["status"] == "needs_review" and changed["url"] == "https://tasks.google.com/"
    source[1].write_text(source[1].read_text().replace("- [ ]", "- [x]"))
    instance.run_once()
    assert len(provider.sent) == 2
    instance._pass.acquire()
    try:
        assert instance.run_once()["status"] == "busy"
    finally:
        instance._pass.release()
    instance.configure({**CONFIG, "sources": ["main", "extra"]})
    assert not instance.snapshot()["enabled"]
    instance.run_once()
    assert len(provider.sent) == 2


def test_agenda_calendar_view_without_tasks_grant(source):
    provider = PolicyProvider()
    provider.choices = lambda: {
        "calendars": [{"id": "owned", "name": "Personal", "writable": True}],
        "tasklists": [], "errors": {"tasks": "reconnect"}}
    instance = service(source, provider)
    config = {**CONFIG, "calendars": ["owned"], "tasklist": ""}
    instance.configure(config)
    view = instance.refresh()
    assert view["agenda"]["state"] == "empty"
    assert view["connection"] == {"calendar": "connected", "tasks": "reconnect"}
    assert not view["enabled"] and provider.sent == []
    with pytest.raises(CalendarError):
        instance.preview(config)


def test_automatic_policy_view_save_pauses(source):
    instance = service(source)
    activate(instance)
    assert instance.snapshot()["enabled"] is True
    instance.configure(CONFIG)
    assert instance.snapshot()["enabled"] is False
    assert instance.run_once()["status"] == "paused"


def test_pause_conflicts_visible_without_worker(source):
    _, path, _, _ = source
    provider = PolicyProvider()
    instance = service(source, provider)
    activate(instance)
    instance.run_once()
    instance.pause()
    path.write_text(path.read_text().replace("2026-11-16", "2026-11-18"))
    before = len(provider.sent)
    view = instance.snapshot()
    changed = next(item for item in view["outcomes"] if item["title"] == "Dated action")
    assert changed["status"] == "needs_review" and changed["url"] == "https://tasks.google.com/"
    assert len(provider.sent) == before


@pytest.mark.parametrize("problem", ["missing", "unsafe_permissions"])
def test_authorization_login_reports_setup_prerequisite(tmp_path, capsys, problem):
    client = tmp_path / "calendar-client.json"
    if problem == "unsafe_permissions":
        client.write_text('{"installed":{"client_secret":"private-client-canary"}}')
        client.chmod(0o644)
    result = bridge.main(["calendar-login", "--credentials", str(client)])
    response = json.loads(capsys.readouterr().out)
    assert result == 1 and response["status"] == "unavailable"
    if problem == "missing":
        assert str(client) in response["error"]
    else:
        assert "600" in response["error"]
    assert "private-client-canary" not in json.dumps(response)
    assert not (tmp_path / "token.json").exists()
