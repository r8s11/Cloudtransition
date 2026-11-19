"""Opt-in, create-only calendar policy and browser-independent reconciliation."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from calendar_bridge import digest, failure, safe_link
from calendar_google import _atomic_json, _read_json
from calendar_model import CalendarError, _body
from core.calendar_sources import collect, pin_item, source_choices, validate_schedule
from kb_runtime import ingest_lock

RUNTIME = Path.home() / ".local-routines" / "personal-kb" / "calendar" / "dashboard"
DISCLOSURE = ("Enable create-only automation for the named source files and destinations. "
              "Eligible sanitized titles and schedules, including this exact backlog and future qualifying items, "
              "will leave this Mac for Google. Tailnet dashboard viewers can see the selected agenda. "
              "Edits and completion do not update or delete Google items. Calendar's owned-event scope also "
              "permits modification and deletion, but this integration only creates.")


class SubprocessProvider:
    """Fixed interpreter/entrypoint; no caller-supplied paths, shell, or OAuth action."""
    def _call(self, command, payload):
        try:
            result = subprocess.run([str(ROOT / ".kb-venv" / "bin" / "python"), str(ROOT / "calendar_bridge.py"), command], input=json.dumps(payload, allow_nan=False), text=True, capture_output=True, timeout=40, cwd=ROOT, check=False)
            if result.returncode or len(result.stdout) > 2_000_000:
                raise CalendarError("Google operation unavailable; check connection.")
            value = json.loads(result.stdout)
            if not isinstance(value, dict):
                raise CalendarError("Google operation returned an invalid result.")
            return value
        except subprocess.TimeoutExpired:
            # The child may have created the item. Its durable intent must reconcile.
            raise TimeoutError("Google operation timed out; outcome requires reconciliation.") from None
        except (OSError, ValueError):
            raise CalendarError("Google operation unavailable; check connection and private runtime permissions.") from None

    def choices(self):
        return self._call("choices", {})

    def agenda(self, config, now):
        return self._call("agenda", {"config": config, "now": now.isoformat()})

    def publish(self, item, config):
        return self._call("publish", {"item": item, "config": config})

def atomic_source(path, text):
    """Default writer for isolated use; the dashboard injects its locked writer."""
    path = Path(path)
    if path.is_symlink():
        raise CalendarError("Calendar source must not be a symlink.")
    mode = path.stat().st_mode & 0o777
    fd, temporary = tempfile.mkstemp(prefix=".calendar-source-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)



class CalendarService:
    def __init__(self, workspace, realms, jobs_file, runtime=None, provider=None, clock=None, source_lock=None, write_source=None):
        self.workspace = Path(workspace)
        self.realms = realms
        self.jobs_file = jobs_file
        self.runtime = Path(runtime) if runtime is not None else RUNTIME
        self.provider = provider if provider is not None else SubprocessProvider()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._source_lock = source_lock if source_lock is not None else threading.RLock()
        self._write_source = write_source if write_source is not None else atomic_source
        self._guard = threading.RLock()
        self._pass = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._choices = {"calendars": [], "tasklists": [], "errors": {}}
        self._connection = {"calendar": "disconnected", "tasks": "disconnected"}
        self._agenda = {"items": [], "state": "disconnected", "updated": None, "timezone": "", "errors": {}, "truncated": False}

    def _now(self):
        value = self.clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise CalendarError("Calendar clock must provide an aware datetime.")
        return value

    def _load(self):
        path = self.runtime / "policy.json"
        if not path.exists() and not path.is_symlink():
            return {"version": 1, "enabled": False, "config": {}, "records": {}, "blocked": [], "review": None}
        state = _read_json(path)
        if state.get("version") != 1 or type(state.get("enabled")) is not bool or not isinstance(state.get("config"), dict) or not isinstance(state.get("records"), dict) or not isinstance(state.get("blocked"), list):
            raise CalendarError("Calendar policy is invalid; preserve private state for recovery.")
        if any(group not in {"calendar", "tasks"} for group in state["blocked"]):
            raise CalendarError("Calendar authorization state is invalid; preserve it for recovery.")
        for key, record in state["records"].items():
            if not isinstance(record, dict) or record.get("key") != key or not isinstance(record.get("binding"), dict) or not isinstance(record.get("source"), str) or record.get("kind") not in {"task", "event"} or record.get("status") not in {"pending", "published", "uncertain", "needs_review", "deferred", "reconnect", "busy"}:
                raise CalendarError("Calendar outcome is invalid; preserve it without retrying creation.")
            if record["status"] == "published" and (not isinstance(record.get("id"), str) or not record["id"]):
                raise CalendarError("Calendar success mapping is invalid; preserve it for recovery.")
        return state

    @contextmanager
    def _transaction(self):
        with self._guard:
            try:
                with ingest_lock(self.runtime / "policy-lock"):
                    state = self._load()
                    yield state
                    _atomic_json(self.runtime / "policy.json", state)
            except RuntimeError:
                raise CalendarError("Another calendar settings operation is running; retry shortly.") from None

    def _read_choices(self):
        try:
            supplied = self.provider.choices()
            if not isinstance(supplied, dict):
                raise ValueError
            result = {"calendars": [], "tasklists": [], "errors": {}, "truncated": bool(supplied.get("truncated"))}
            errors = supplied.get("errors", {})
            for group, kind in (("calendars", "calendar"), ("tasklists", "tasks")):
                error = errors.get(kind)
                if error:
                    result["errors"][kind] = error if error in {"reconnect", "deferred", "needs_review", "unavailable"} else "unavailable"
                values = supplied.get(group, [])
                if not isinstance(values, list) or len(values) > 1000:
                    raise ValueError
                for value in values:
                    if not isinstance(value, dict) or not isinstance(value.get("id"), str) or not value["id"] or len(value["id"]) > 1024:
                        raise ValueError
                    choice = {"id": value["id"], "name": str(value.get("name", value.get("title", "Unnamed destination")))[:1024]}
                    if group == "calendars":
                        choice["writable"] = value.get("writable") is True
                    result[group].append(choice)
                self._connection[kind] = "connected" if not error else "reconnect" if error == "reconnect" else "unavailable"
            self._choices = result
        except Exception as exc:
            status = failure(exc)
            self._choices = {"calendars": [], "tasklists": [], "errors": {"calendar": status, "tasks": status}}
            self._connection = {"calendar": "reconnect" if status == "reconnect" else "unavailable", "tasks": "reconnect" if status == "reconnect" else "unavailable"}
        return deepcopy(self._choices)

    def _config(self, config, choices, publishing=True):
        required = {"calendars", "event_calendar", "tasklist", "timezone", "sources"}
        if not isinstance(config, dict) or set(config) != required:
            raise CalendarError("Choose calendars, an owned event calendar, a Tasks list, timezone and named sources.")
        result = {}
        for key in ("calendars", "sources"):
            values = config[key]
            if not isinstance(values, list) or len(values) > (10 if key == "calendars" else 100) or not all(isinstance(value, str) and value and len(value) <= 1024 for value in values) or len(set(values)) != len(values):
                raise CalendarError("Calendar and source selections must be distinct allowed identifiers.")
            result[key] = sorted(values)
        for key in ("event_calendar", "tasklist", "timezone"):
            if not isinstance(config[key], str) or (not config[key] and (publishing or key == "timezone")) or len(config[key]) > 1024:
                raise CalendarError("Choose an existing owned calendar, Tasks list and IANA timezone.")
            result[key] = config[key]
        try:
            ZoneInfo(result["timezone"])
        except (ValueError, ZoneInfoNotFoundError):
            raise CalendarError("Choose a valid IANA display timezone.") from None
        calendars = {choice["id"]: choice for choice in choices["calendars"]}
        if not set(result["calendars"]) <= set(calendars) or result["event_calendar"] and (result["event_calendar"] not in calendars or not calendars[result["event_calendar"]]["writable"]):
            raise CalendarError("Select accessible read calendars and a verified owned event destination; reconnect if unavailable.")
        if result["tasklist"] and result["tasklist"] not in {choice["id"] for choice in choices["tasklists"]}:
            raise CalendarError("Select an existing accessible Google Tasks list; reconnect if unavailable.")
        sources = {choice["id"]: choice for choice in source_choices(self.workspace, self.realms, self.jobs_file)}
        if not set(result["sources"]) <= {key for key, value in sources.items() if value["available"]}:
            raise CalendarError("Select only named available nonprivate source files.")
        return result

    def _items(self, config):
        items = collect(self.workspace, self.realms, self.jobs_file, config.get("sources", []))
        if len(items) > 1000:
            raise CalendarError("Selected source backlog exceeds 1000 items; narrow the named source selection.")
        return items

    @staticmethod
    def _kind(item):
        return "task" if "date" in item["schedule"] else "event" if "start" in item["schedule"] else "local"

    def _backlog(self, config, state, items=None):
        result = []
        items = self._items(config) if items is None else items
        active_keys = {item["key"] for item in items}
        for item in items:
            kind = self._kind(item)
            previous = state["records"].get(item["key"])
            status = item["status"]
            if previous:
                status = previous["status"] if previous["binding"] == item["binding"] else "needs_review"
            elif self._conflict(item, state["records"], active_keys):
                status = "needs_review"
            row = {"key": item["key"], "title": item["title"], "schedule": item["schedule"], "source": item["source"], "status": status, "kind": kind, "destination": config.get("tasklist" if kind == "task" else "event_calendar", "") if kind != "local" else ""}
            if previous and previous.get("url"):
                row["url"] = previous["url"]
            result.append(row)
        return result

    def snapshot(self):
        # No network, runtime creation, policy write, or publication on a GET.
        with self._guard:
            state = self._load()
            try:
                backlog = self._backlog(state["config"], state) if state["config"] else []
                source_error = None
            except (ValueError, OSError):
                backlog, source_error = [], "Selected source unavailable; no publication is inferred."
            outcomes = [{name: record.get(name) for name in ("key", "title", "source", "status", "id", "url", "kind")} for record in state["records"].values() if record.get("source") in state["config"].get("sources", [])]
            current = {item["key"]: item["status"] for item in backlog}
            for outcome in outcomes:
                outcome["status"] = current.get(outcome["key"], outcome["status"])
            return {"enabled": state["enabled"], "config": deepcopy(state["config"]), "sources": source_choices(self.workspace, self.realms, self.jobs_file), "choices": deepcopy(self._choices), "connection": deepcopy(self._connection), "status": "reconnect" if state["blocked"] else "enabled" if state["enabled"] else "paused" if state.get("review") else "disabled", "agenda": deepcopy(self._agenda), "backlog": backlog, "outcomes": outcomes, "source_error": source_error, "pause_note": "Pause prevents queued creates. An already-started request may finish.", "disclosure": DISCLOSURE}

    def refresh(self):
        choices = self._read_choices()
        config = self._load()["config"]
        if not config:
            return self.snapshot()
        expanded = {**config, "calendar_names": choices["calendars"], "tasklist_name": next((value["name"] for value in choices["tasklists"] if value["id"] == config["tasklist"]), "Google Tasks")}
        previous = self._agenda
        try:
            agenda = self.provider.agenda(expanded, self._now())
            if not isinstance(agenda, dict) or not isinstance(agenda.get("items"), list) or len(agenda["items"]) > 11000 or not isinstance(agenda.get("errors", {}), dict):
                raise ValueError
            normalized = []
            for item in agenda["items"]:
                if not isinstance(item, dict) or item.get("kind") not in {"task", "event"}:
                    raise ValueError
                row = {key: item.get(key, "") for key in ("id", "kind", "title", "date", "start", "end", "source", "calendar")}
                if not all(isinstance(value, str) for value in row.values()):
                    raise ValueError
                row.update(url=safe_link(item.get("url", "")), all_day=bool(item.get("all_day")))
                normalized.append(row)
            errors = {str(key): value if value in {"reconnect", "deferred", "needs_review", "unavailable"} else "unavailable" for key, value in agenda.get("errors", {}).items()}
            for item in previous["items"]:
                if (item.get("calendar") in errors or item.get("kind") == "task" and "tasks" in errors) and not any(value["id"] == item["id"] and value.get("calendar") == item.get("calendar") for value in normalized):
                    normalized.append({**item, "stale": True})
            normalized.sort(key=lambda item: (item["date"], not item["all_day"], item["start"], item["id"]))
            state = "partial" if errors and any(not item.get("stale") for item in normalized) else "stale" if errors and normalized else "unavailable" if errors else "ready" if normalized else "empty"
            self._agenda = {"items": normalized, "state": state, "updated": previous["updated"] if state in {"stale", "unavailable"} else agenda.get("updated", self._now().isoformat()), "timezone": config["timezone"], "errors": errors, "truncated": bool(agenda.get("truncated"))}
        except Exception:
            self._agenda = {**previous, "items": [{**item, "stale": True} for item in previous["items"]], "state": "stale" if previous["items"] else "unavailable", "timezone": config["timezone"], "errors": {"provider": "unavailable"}}
        return self.snapshot()

    def configure(self, config):
        value = self._config(config, self._read_choices(), publishing=False)
        with self._transaction() as state:
            if state["config"] != value:
                self._agenda = {"items": [], "state": "not_refreshed", "updated": None, "timezone": value["timezone"], "errors": {}, "truncated": False}
            state.update(config=value, enabled=False, review=None, blocked=[])
        return self.snapshot()

    def preview(self, config):
        value = self._config(config, self._read_choices())
        state = self._load()
        items = self._items(value)
        backlog = self._backlog(value, state, items)
        # Includes local bindings and all outcomes: source/queue changes invalidate review.
        review = digest({"config": value, "items": [{"key": item["key"], "binding": item["binding"], "status": item["status"]} for item in items], "records": state["records"], "blocked": state["blocked"]})
        return {"config": value, "backlog": backlog, "review": review, "disclosure": DISCLOSURE}

    def enable(self, config, review):
        reviewed = self.preview(config)
        if not isinstance(review, str) or review != reviewed["review"]:
            raise CalendarError("Backlog or policy changed; review the exact current backlog before enabling.")
        with self._transaction() as state:
            current_items = self._items(reviewed["config"])
            current = digest({"config": reviewed["config"], "items": [{"key": item["key"], "binding": item["binding"], "status": item["status"]} for item in current_items], "records": state["records"], "blocked": state["blocked"]})
            if current != review:
                raise CalendarError("Backlog changed during review; refresh the preview before enabling.")
            state.update(config=reviewed["config"], enabled=True, review=review, blocked=[])
        return self.snapshot()

    def pause(self):
        with self._transaction() as state:
            state["enabled"] = False
        return self.snapshot()

    def _conflict(self, item, records, active_keys):
        previous = records.get(item["key"])
        if previous:
            return previous["binding"] != item["binding"]
        # Legacy records from before identity pinning require conservative review.
        if item["binding"].get("identity"):
            return False
        for record in records.values():
            if record["key"] not in active_keys and record["source"] == item["source"] and not record["binding"].get("identity"):
                return True
        return False

    def run_once(self):
        if not self._pass.acquire(blocking=False):
            return {"status": "busy", "results": []}
        try:
            if not self._load()["enabled"]:
                return {"status": "paused", "results": []}
            try:
                with ingest_lock(self.runtime / "worker-lock"):
                    return self._run_locked()
            except RuntimeError:
                return {"status": "busy", "results": []}
        finally:
            self._pass.release()

    def _run_locked(self):
        state = self._load()
        config = state["config"]
        choices = self._read_choices()
        try:
            items = self._items(config)
        except (ValueError, OSError):
            return {"status": "needs_review", "results": []}
        allowed_calendars = {value["id"] for value in choices["calendars"] if value["writable"]}
        allowed_lists = {value["id"] for value in choices["tasklists"]}
        active_keys = {item["key"] for item in items}
        results = []
        for item in items:
            kind = self._kind(item)
            if item["status"] != "eligible" or kind == "local":
                continue
            group = "tasks" if kind == "task" else "calendar"
            destination = config["tasklist"] if kind == "task" else config["event_calendar"]
            allowed = allowed_lists if kind == "task" else allowed_calendars
            with self._source_lock, self._transaction() as state:
                if not state["enabled"] or state["config"] != config:
                    break
                if group in state["blocked"]:
                    continue
                if destination not in allowed:
                    status = choices["errors"].get(group, "needs_review")
                    if status == "reconnect":
                        state["blocked"].append(group)
                    results.append({"key": item["key"], "status": status})
                    continue
                previous = state["records"].get(item["key"])
                if self._conflict(item, state["records"], active_keys):
                    if previous:
                        previous["status"] = "needs_review"
                    results.append({"key": item["key"], "status": "needs_review"})
                    continue
                if previous and (previous.get("destination") != destination or previous.get("kind") != kind):
                    previous["status"] = "needs_review"
                    results.append({"key": item["key"], "status": "needs_review"})
                    continue
                if previous and (previous["status"] in {"published", "needs_review"} or previous["status"] == "reconnect" and group in state["blocked"]):
                    continue
                # Re-read immediately before intent: an external edit is not consent
                # to publish stale content captured at the start of this pass.
                latest = {value["key"]: value for value in self._items(config)}.get(item["key"])
                if latest is None or latest["binding"] != item["binding"] or latest["status"] != "eligible":
                    results.append({"key": item["key"], "status": "needs_review"})
                    continue
                if not latest["binding"].get("identity"):
                    path, text = pin_item(self.workspace, self.realms, self.jobs_file, latest)
                    self._write_source(path, text)
                    pinned = {value["key"]: value for value in self._items(config)}.get(item["key"])
                    if pinned is None or any(pinned[field] != latest[field] for field in ("title", "schedule", "source")) or pinned["status"] != "eligible":
                        raise CalendarError("Source changed while preserving identity; review before publishing.")
                    item = pinned
                schedule = validate_schedule(item["schedule"])
                title = _body(item["title"], schedule.get("date", "2000-01-01"), item["key"])["title"]
                if not previous:
                    state["records"][item["key"]] = {"key": item["key"], "title": title, "schedule": schedule, "source": item["source"], "binding": deepcopy(item["binding"]), "location": deepcopy(item.get("location", {})), "status": "pending", "id": None, "url": "", "kind": kind, "destination": destination}
            # The provider receives no source location, notes, category, or contacts.
            try:
                result = self.provider.publish({"key": item["key"], "title": title, "schedule": schedule}, config)
                if not isinstance(result, dict) or result.get("status") not in {"published", "uncertain", "needs_review", "deferred", "reconnect", "busy"}:
                    result = {"status": "uncertain"}
                if result["status"] == "published" and (not isinstance(result.get("id"), str) or not result["id"]):
                    result = {"status": "uncertain"}
            except Exception as exc:
                result = {"status": "reconnect" if failure(exc) == "reconnect" else "uncertain"}
            with self._transaction() as state:
                record = state["records"][item["key"]]
                record.update(status=result["status"], id=result.get("id"), url=safe_link(result.get("url", "")))
                if result["status"] == "reconnect" and group not in state["blocked"]:
                    state["blocked"].append(group)
            results.append({"key": item["key"], "status": result["status"], "id": result.get("id")})
        return {"status": "complete", "results": results}

    def start(self):
        with self._guard:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._worker, name="dashboard-calendar", daemon=True)
            self._thread.start()

    def _worker(self):
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception:
                # Durable intents remain pending; do not log source text or bodies.
                pass
            self._stop.wait(60)

    def stop(self):
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1)
