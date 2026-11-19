#!/usr/bin/env python3
"""Separate Calendar consent and bounded dashboard Google operations.

Only ``calendar-login`` starts consent. JSON stdin operations never start OAuth.
Calendar credentials live in calendar/events; the legacy Tasks grant is unchanged.
"""
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from calendar_google import _atomic_json, _load_state as legacy_state, _read_json, _scope_set, build_service as tasks_service
from calendar_model import CalendarError, _body
from kb_privacy import redact
from kb_runtime import ingest_lock

ROOT = Path(__file__).resolve().parent
RUNTIME = Path.home() / ".local-routines" / "personal-kb" / "calendar"
CALENDAR_SCOPES = (
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/calendar.events.owned",
)
MAX_PAGES = 10
MAX_ITEMS = 1000


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def safe_link(value):
    if not isinstance(value, str) or len(value) > 2048:
        return ""
    try:
        parsed = urlsplit(value)
        if parsed.scheme == "https" and parsed.hostname in {"calendar.google.com", "www.google.com", "tasks.google.com"} and not parsed.username and not parsed.password and parsed.port in {None, 443}:
            return value
    except ValueError:
        pass
    return ""


def failure(exc):
    code = getattr(getattr(exc, "resp", None), "status", None)
    if code in {401, 403}:
        return "reconnect"
    if code == 429:
        return "deferred"
    if isinstance(exc, CalendarError):
        return "reconnect" if "authorization" in str(exc).lower() or "owner-only calendar JSON" in str(exc) else "needs_review"
    return "deferred"


def calendar_login(runtime=RUNTIME, credentials=None):
    directory = Path(runtime) / "events"
    client_path = Path(credentials).expanduser() if credentials else directory / "credentials.json"
    if not client_path.is_file():
        raise CalendarError(f"A Calendar Desktop OAuth client is required at {client_path}; save the downloaded client JSON there, owner-only, with mode 600.")
    try:
        client = _read_json(client_path)
    except CalendarError:
        raise CalendarError(
            f"Calendar client at {client_path} is not readable. Ensure it is an owner-only nonsymlink regular file with mode 600.") from None
    if not isinstance(client.get("installed"), dict):
        raise CalendarError("Calendar requires a Desktop OAuth client.")
    from google_auth_oauthlib.flow import InstalledAppFlow
    try:
        with ingest_lock(directory):
            flow = InstalledAppFlow.from_client_config(client, list(CALENDAR_SCOPES))
            authorized = flow.run_local_server(port=0, prompt="consent", include_granted_scopes="false")
            scopes = authorized.granted_scopes if authorized.granted_scopes is not None else authorized.scopes
            if set(scopes or ()) != set(CALENDAR_SCOPES):
                raise CalendarError("Calendar authorization must contain exactly the three documented Calendar scopes.")
            _atomic_json(directory / "token.json", json.loads(authorized.to_json()))
    except CalendarError:
        raise
    except Exception:
        raise CalendarError("Calendar authorization failed; existing Tasks and Gmail grants were not changed.") from None


def calendar_service(runtime):
    token = Path(runtime) / "events" / "token.json"
    info = _read_json(token)
    if _scope_set(info) != set(CALENDAR_SCOPES):
        raise CalendarError("Calendar authorization has incorrect scopes; explicitly reconnect Calendar.")
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        credentials = Credentials.from_authorized_user_info(info, list(CALENDAR_SCOPES))
        if not credentials.valid:
            if not credentials.expired or not credentials.refresh_token:
                raise CalendarError("Calendar authorization requires explicit reconnection.")
            credentials.refresh(Request())
            scopes = credentials.granted_scopes if credentials.granted_scopes is not None else credentials.scopes
            if set(scopes or ()) != set(CALENDAR_SCOPES):
                raise CalendarError("Calendar authorization scope changed; explicitly reconnect Calendar.")
            _atomic_json(token, json.loads(credentials.to_json()))
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)
    except CalendarError:
        raise
    except Exception:
        raise CalendarError("Saved Calendar authorization is unavailable; reconnect explicitly.") from None


def pages(resource, **options):
    items, seen, token = [], set(), None
    for _ in range(MAX_PAGES):
        response = resource.list(**options, **({"pageToken": token} if token else {})).execute(num_retries=0)
        if not isinstance(response, dict) or not isinstance(response.get("items", []), list):
            raise CalendarError("Invalid Google list response.")
        items.extend(response.get("items", []))
        if len(items) > MAX_ITEMS:
            return items[:MAX_ITEMS], True
        token = response.get("nextPageToken")
        if not token:
            return items, False
        if not isinstance(token, str) or token in seen:
            raise CalendarError("Invalid Google pagination response.")
        seen.add(token)
    return items, True


class GoogleProvider:
    def __init__(self, runtime=RUNTIME, calendar=None, tasks=None):
        self.runtime = Path(runtime)
        self._calendar = calendar
        self._tasks = tasks

    def calendar(self):
        if self._calendar is None:
            self._calendar = calendar_service(self.runtime)
        return self._calendar

    def tasks(self):
        if self._tasks is None:
            self._tasks = tasks_service(self.runtime)
        return self._tasks

    def choices(self):
        result = {"calendars": [], "tasklists": [], "errors": {}, "truncated": False}
        try:
            entries, truncated = pages(self.calendar().calendarList(), maxResults=100, showDeleted=False)
            result["truncated"] |= truncated
            for entry in entries:
                if isinstance(entry, dict) and isinstance(entry.get("id"), str) and not entry.get("deleted") and entry.get("accessRole") in {"owner", "writer", "reader"}:
                    result["calendars"].append({"id": entry["id"], "name": redact(str(entry.get("summary", "Unnamed calendar")))[:1024], "writable": entry.get("accessRole") == "owner"})
        except Exception as exc:
            result["errors"]["calendar"] = failure(exc)
        try:
            entries, truncated = pages(self.tasks().tasklists(), maxResults=100)
            result["truncated"] |= truncated
            for entry in entries:
                if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                    result["tasklists"].append({"id": entry["id"], "name": redact(str(entry.get("title", "Unnamed list")))[:1024]})
        except Exception as exc:
            result["errors"]["tasks"] = failure(exc)
        return result

    def _state(self):
        path = self.runtime / "dashboard-publish.json"
        if not path.exists() and not path.is_symlink():
            return {"version": 1, "entries": {}}
        state = _read_json(path)
        if state.get("version") != 1 or not isinstance(state.get("entries"), dict):
            raise CalendarError("Invalid dashboard publication state; preserve it for recovery.")
        for identity, entry in state["entries"].items():
            if not isinstance(entry, dict) or entry.get("kind") not in {"event", "task"} or entry.get("status") not in {"pending", "uncertain", "published", "deferred", "reconnect", "needs_review"}:
                raise CalendarError("Invalid dashboard outcome; preserve it without retrying creation.")
            if not all(isinstance(entry.get(key), str) and entry[key] for key in ("key", "destination")) or not isinstance(entry.get("body"), dict):
                raise CalendarError("Invalid dashboard identity; preserve it for recovery.")
            if identity != digest([entry["kind"], entry["destination"], entry["key"]]) or entry["status"] == "published" and (not isinstance(entry.get("remote_id"), str) or not entry["remote_id"]):
                raise CalendarError("Invalid dashboard mapping; preserve it for recovery.")
        return state

    def agenda(self, config, now):
        zone = ZoneInfo(config["timezone"])
        now = datetime.fromisoformat(now) if isinstance(now, str) else now
        start = datetime.combine(now.astimezone(zone).date(), time.min, zone)
        end = datetime.combine(start.date() + timedelta(days=7), time.min, zone)
        result = {"items": [], "state": "ready", "updated": now.isoformat(), "timezone": config["timezone"], "errors": {}, "truncated": False}
        names = {item["id"]: item["name"] for item in config.get("calendar_names", [])}
        for calendar_id in config["calendars"]:
            try:
                events, truncated = pages(self.calendar().events(), calendarId=calendar_id, singleEvents=True, showDeleted=False, timeMin=start.isoformat(), timeMax=end.isoformat(), timeZone=config["timezone"], orderBy="startTime", maxResults=100)
                result["truncated"] |= truncated
                for event in events:
                    item = self._event(event, calendar_id, names.get(calendar_id, calendar_id), zone, start, end)
                    if item:
                        result["items"].append(item)
            except Exception as exc:
                result["errors"][calendar_id] = failure(exc)
        try:
            tracked = [entry for entry in self._state()["entries"].values() if entry.get("kind") == "task" and entry.get("status") == "published" and entry.get("destination") == config["tasklist"]]
            if tracked:
                tasks, truncated = pages(self.tasks().tasks(), tasklist=config["tasklist"], maxResults=100, showCompleted=False, showHidden=False, showDeleted=False)
                result["truncated"] |= truncated
                identities = {entry["remote_id"] for entry in tracked}
                for task in tasks:
                    due = task.get("due", "")[:10]
                    if task.get("id") in identities and not task.get("deleted") and task.get("status") != "completed" and due and start.date().isoformat() <= due < end.date().isoformat():
                        result["items"].append({"id": task["id"], "kind": "task", "title": redact(str(task.get("title") or "Untitled task"))[:1024], "date": due, "start": due, "end": "", "all_day": True, "source": config.get("tasklist_name", "Google Tasks"), "calendar": "tasks", "url": safe_link(task.get("webViewLink", ""))})
        except Exception as exc:
            result["errors"]["tasks"] = failure(exc)
        result["items"].sort(key=lambda item: (item["date"], not item["all_day"], item["start"], item["id"]))
        if len(result["items"]) > MAX_ITEMS:
            result["items"] = result["items"][:MAX_ITEMS]
            result["truncated"] = True
        if result["errors"]:
            result["state"] = "partial" if result["items"] else "unavailable"
        elif not result["items"]:
            result["state"] = "empty"
        return result

    @staticmethod
    def _event(event, calendar_id, name, zone, start, end):
        if not isinstance(event, dict) or event.get("status") == "cancelled" or not isinstance(event.get("id"), str):
            return None
        first, last = event.get("start", {}), event.get("end", {})
        if first.get("date") and last.get("date"):
            begin, finish = date.fromisoformat(first["date"]), date.fromisoformat(last["date"])
            if finish <= start.date() or begin >= end.date():
                return None
            stamp, ending, day, all_day = begin.isoformat(), finish.isoformat(), max(begin, start.date()).isoformat(), True
        else:
            try:
                begin = datetime.fromisoformat(first["dateTime"].replace("Z", "+00:00"))
                finish = datetime.fromisoformat(last["dateTime"].replace("Z", "+00:00"))
                if begin.tzinfo is None or finish.tzinfo is None or finish <= start or begin >= end:
                    return None
                stamp, ending = begin.astimezone(zone).isoformat(), finish.astimezone(zone).isoformat()
                day, all_day = max(begin.astimezone(zone).date(), start.date()).isoformat(), False
            except (KeyError, TypeError, ValueError):
                return None
        return {"id": event["id"], "kind": "event", "title": redact(str(event.get("summary") or "Untitled event"))[:1024], "date": day, "start": stamp, "end": ending, "all_day": all_day, "source": name, "calendar": calendar_id, "url": safe_link(event.get("htmlLink", ""))}

    def publish(self, item, config):
        # Recheck ownership/list membership at the provider boundary, not just in the UI.
        choices = self.choices()
        schedule = item["schedule"]
        kind = "task" if "date" in schedule else "event"
        destination = config["tasklist"] if kind == "task" else config["event_calendar"]
        allowed = {choice["id"] for choice in choices["tasklists"]} if kind == "task" else {choice["id"] for choice in choices["calendars"] if choice["writable"]}
        if destination not in allowed:
            return {"status": choices["errors"].get("tasks" if kind == "task" else "calendar", "needs_review")}
        sys.path.insert(0, str(ROOT / "dashboard-app"))
        from core.calendar_sources import validate_schedule
        schedule = validate_schedule(schedule)
        if not schedule or not re.fullmatch(r"[0-9a-f]{64}", item.get("key", "")):
            raise CalendarError("Publication requires an explicit valid schedule and opaque source identity.")
        title = _body(item["title"], schedule.get("date", "2000-01-01"), item["key"])["title"]
        identity = digest([kind, destination, item["key"]])
        body = _body(title, schedule["date"], item["key"]) if kind == "task" else {"id": identity, "summary": title, "start": {"dateTime": datetime.fromisoformat(schedule["start"]).replace(tzinfo=ZoneInfo(schedule["timezone"])).isoformat(), "timeZone": schedule["timezone"]}, "end": {"dateTime": datetime.fromisoformat(schedule["end"]).replace(tzinfo=ZoneInfo(schedule["timezone"])).isoformat(), "timeZone": schedule["timezone"]}, "extendedProperties": {"private": {"cloudtransition": identity}}}
        try:
            with ingest_lock(self.runtime):
                state = self._state()
                entry = state["entries"].get(identity)
                if entry and entry.get("body") != body:
                    return {"status": "needs_review", "url": entry.get("url", "")}
                if entry and entry.get("status") == "needs_review":
                    return {"status": "needs_review", "url": entry.get("url", "")}
                if entry and entry.get("status") == "published":
                    return {"status": "published", "id": entry["remote_id"], "url": entry.get("url", "")}
                if entry and entry.get("status") in {"pending", "uncertain"}:
                    return self._recover(entry, state, identity)
                if entry is None and kind == "task":
                    legacy = legacy_state(self.runtime / "state.json")["entries"].values()
                    candidates = [record for record in legacy if record["tasklist"] == destination and record["status"] != "failed" and record["body"]["title"] == title]
                    exact = [record for record in candidates if record["key"] == item["key"] and record["body"] == body]
                    if candidates and len(exact) != 1:
                        # A title alone cannot prove cross-CLI identity. Refuse a
                        # duplicate instead of silently merging unrelated sources.
                        return {"status": "needs_review", "url": "https://tasks.google.com/"}
                    if exact:
                        previous = exact[0]
                        entry = {"kind": kind, "destination": destination, "key": item["key"], "body": body, "status": previous["status"], "remote_id": previous["task_id"], "url": "https://tasks.google.com/"}
                        state["entries"][identity] = entry
                        _atomic_json(self.runtime / "dashboard-publish.json", state)
                        if previous["status"] == "published":
                            return {"status": "published", "id": previous["task_id"], "url": entry["url"]}
                        return self._recover(entry, state, identity)
                entry = {"kind": kind, "destination": destination, "key": item["key"], "body": body, "status": "pending", "remote_id": None, "url": ""}
                state["entries"][identity] = entry
                _atomic_json(self.runtime / "dashboard-publish.json", state)
                try:
                    if kind == "task":
                        remote = self.tasks().tasks().insert(tasklist=destination, body=deepcopy(body)).execute(num_retries=0)
                    else:
                        remote = self.calendar().events().insert(calendarId=destination, body=deepcopy(body), sendUpdates="none").execute(num_retries=0)
                    if not isinstance(remote, dict) or not isinstance(remote.get("id"), str) or not remote["id"]:
                        entry["status"] = "uncertain"
                    else:
                        entry.update(status="published", remote_id=remote["id"], url=safe_link(remote.get("htmlLink", remote.get("webViewLink", ""))))
                except Exception as exc:
                    code = getattr(getattr(exc, "resp", None), "status", None)
                    state_name = failure(exc)
                    entry["status"] = "deferred" if code == 429 else "reconnect" if code in {401, 403} else "needs_review" if type(code) is int and 400 <= code < 500 and code not in {408, 409} else "uncertain"
                    if state_name == "reconnect":
                        entry["status"] = "reconnect"
                _atomic_json(self.runtime / "dashboard-publish.json", state)
                return {"status": entry["status"], "id": entry["remote_id"], "url": entry["url"]}
        except RuntimeError:
            return {"status": "busy"}

    def _recover(self, entry, state, identity):
        outcome = None
        try:
            if entry["kind"] == "event":
                remote = self.calendar().events().get(calendarId=entry["destination"], eventId=identity).execute(num_retries=0)
                body = entry["body"]
                valid = remote.get("status") != "cancelled" and remote.get("extendedProperties", {}).get("private", {}).get("cloudtransition") == identity and remote.get("summary") == body["summary"] and all(datetime.fromisoformat(remote[field]["dateTime"].replace("Z", "+00:00")) == datetime.fromisoformat(body[field]["dateTime"]) for field in ("start", "end"))
                found = remote if valid else None
            else:
                tasks, truncated = pages(self.tasks().tasks(), tasklist=entry["destination"], maxResults=100, showCompleted=True, showHidden=True, showDeleted=False)
                matches = [task for task in tasks if task.get("notes") == entry["body"]["notes"]]
                found = matches[0] if len(matches) == 1 and not truncated else None
                if found and (found.get("deleted") or any(found.get(key) != entry["body"][key] for key in ("title", "notes", "status")) or found.get("due", "")[:10] != entry["body"]["due"][:10]):
                    found = None
            if found and isinstance(found.get("id"), str) and found["id"]:
                entry.update(status="published", remote_id=found["id"], url=safe_link(found.get("htmlLink", found.get("webViewLink", ""))))
            else:
                entry["status"] = "uncertain"
        except Exception as exc:
            entry["status"] = "uncertain"
            outcome = "reconnect" if failure(exc) == "reconnect" else "uncertain"
        _atomic_json(self.runtime / "dashboard-publish.json", state)
        return {"status": outcome or entry["status"], "id": entry["remote_id"], "url": entry["url"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("calendar-login", "choices", "agenda", "publish"))
    parser.add_argument("--credentials", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "calendar-login":
            calendar_login(credentials=args.credentials)
            result = {"status": "connected"}
        else:
            payload = json.loads(sys.stdin.read(131073))
            if not isinstance(payload, dict):
                raise CalendarError("Invalid bridge request.")
            provider = GoogleProvider()
            if args.command == "choices":
                result = provider.choices()
            elif args.command == "agenda":
                result = provider.agenda(payload["config"], payload["now"])
            else:
                result = provider.publish(payload["item"], payload["config"])
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except CalendarError as exc:
        # Login and JSON-service errors both raise CalendarError — report the
        # actual safe message so missing credentials or wrong permissions are
        # actionable rather than hidden behind the fallback message.
        if args.command == "calendar-login":
            print(json.dumps({"status": "unavailable", "error": str(exc)}))
        else:
            print(json.dumps({"status": "unavailable", "error": "Google operation unavailable; check connection and private runtime permissions."}))
        return 1
    except Exception:
        print(json.dumps({"status": "unavailable", "error": "Google operation unavailable; check connection and private runtime permissions."}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
