"""Explicit Tasks OAuth and one-way, approval-bound publication; no auto-login."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

from calendar_model import CalendarError, validate_preview
from kb_privacy import redact
from kb_runtime import ingest_lock, private_directory

TASKS_SCOPES = ("https://www.googleapis.com/auth/tasks",)


def _read_json(path):
    path = Path(path).expanduser()
    try:
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise OSError("symlink")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise OSError("not an owner-only regular file")
            value = json.load(stream)
        if not isinstance(value, dict):
            raise ValueError("not an object")
        return value
    except (OSError, ValueError, UnicodeError):
        raise CalendarError("Cannot read an owner-only calendar JSON file; use a regular nonsymlink file with mode 600.") from None


def _atomic_json(path, value):
    path = Path(path)
    private_directory(path.parent)
    if path.is_symlink():
        raise CalendarError("Calendar runtime files must not be symlinks.")
    if path.exists():
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise CalendarError("Existing calendar runtime file is not owner-only.")
    fd, temporary = tempfile.mkstemp(prefix=".calendar-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _scope_set(info):
    scopes = info.get("scopes", info.get("scope", []))
    if isinstance(scopes, str):
        scopes = scopes.split()
    if not isinstance(scopes, (list, tuple)) or not all(isinstance(scope, str) for scope in scopes):
        return set()
    return set(scopes)


def _check_credentials_scope(credentials):
    scopes = credentials.granted_scopes
    if scopes is None:
        scopes = credentials.scopes
    if set(scopes or ()) != set(TASKS_SCOPES):
        raise CalendarError("Authorization scope must be exactly Google Tasks, not Gmail or Calendar.")


def login(runtime, credentials=None):
    """Only this explicitly invoked operation opens an OAuth consent flow."""
    runtime = Path(runtime).expanduser()
    client = _read_json(Path(credentials).expanduser() if credentials else runtime / "credentials.json")
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise CalendarError("Use the existing .kb-venv interpreter for Google Tasks authorization.") from None
    try:
        with ingest_lock(runtime):
            flow = InstalledAppFlow.from_client_config(client, list(TASKS_SCOPES))
            authorized = flow.run_local_server(port=0, prompt="consent", include_granted_scopes="false")
            _check_credentials_scope(authorized)
            _atomic_json(runtime / "token.json", json.loads(authorized.to_json()))
    except CalendarError:
        raise
    except Exception as exc:
        raise CalendarError(f"Tasks authorization failed ({type(exc).__name__}); no Gmail credentials were changed.") from None


def build_service(runtime):
    """Use only the separate saved Tasks token; never start authorization."""
    runtime = Path(runtime).expanduser()
    token = runtime / "token.json"
    info = _read_json(token)
    if _scope_set(info) != set(TASKS_SCOPES):
        raise CalendarError("Saved authorization must have exactly the Google Tasks scope; run the separate Tasks login.")
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        raise CalendarError("Use the existing .kb-venv interpreter for Google Tasks operations.") from None
    try:
        authorized = Credentials.from_authorized_user_info(info, list(TASKS_SCOPES))
        _check_credentials_scope(authorized)
        if not authorized.valid:
            if not authorized.expired or not authorized.refresh_token:
                raise CalendarError("Tasks authorization expired; explicitly run the separate Tasks login.")
            authorized.refresh(Request())
            _check_credentials_scope(authorized)
            _atomic_json(token, json.loads(authorized.to_json()))
        return build("tasks", "v1", credentials=authorized, cache_discovery=False)
    except CalendarError:
        raise
    except Exception as exc:
        raise CalendarError(f"Cannot use saved Tasks authorization ({type(exc).__name__}); login is never automatic.") from None


def _pages(resource, **options):
    token, seen = None, set()
    while True:
        response = resource.list(**options, **({"pageToken": token} if token else {})).execute(num_retries=0)
        if not isinstance(response, dict) or not isinstance(response.get("items", []), list):
            raise CalendarError("Invalid Tasks list response.")
        yield from response.get("items", [])
        token = response.get("nextPageToken")
        if not token:
            return
        if not isinstance(token, str) or token in seen:
            raise CalendarError("Invalid Tasks pagination response.")
        seen.add(token)


def list_tasklists(service):
    try:
        result = []
        for item in _pages(service.tasklists(), maxResults=100):
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"] or not isinstance(item.get("title", ""), str):
                raise CalendarError("Invalid task-list choice response.")
            result.append({"id": item["id"], "title": redact(item.get("title", ""))})
        return result
    except CalendarError:
        raise
    except Exception as exc:
        raise CalendarError(f"Cannot list Tasks destinations ({type(exc).__name__}).") from None


def _load_state(path):
    if not path.exists() and not path.is_symlink():
        return {"version": 1, "entries": {}}
    state = _read_json(path)
    if set(state) != {"version", "entries"} or type(state["version"]) is not int or state["version"] != 1 or not isinstance(state["entries"], dict):
        raise CalendarError("Invalid publication state; preserve it for explicit recovery, do not retry creation.")
    for identity, entry in state["entries"].items():
        if not isinstance(identity, str) or not isinstance(entry, dict) or set(entry) != {"tasklist", "key", "source", "binding", "body", "status", "task_id"}:
            raise CalendarError("Invalid publication record; preserve state for recovery.")
        if not all(isinstance(entry[name], str) for name in ("tasklist", "key", "source", "status")) or entry["status"] not in {"pending", "uncertain", "failed", "published"}:
            raise CalendarError("Invalid publication identity or outcome.")
        binding, body = entry["binding"], entry["body"]
        if not isinstance(binding, dict) or set(binding) != {"title", "heading", "line", "count", "occurrence"} or not all(isinstance(binding[name], str) for name in ("title", "heading")) or not all(type(binding[name]) is int for name in ("line", "count", "occurrence")):
            raise CalendarError("Invalid publication source binding.")
        if not isinstance(body, dict) or set(body) != {"title", "due", "status", "notes"} or not all(isinstance(value, str) for value in body.values()):
            raise CalendarError("Invalid publication body.")
        if entry["task_id"] is not None and (not isinstance(entry["task_id"], str) or not entry["task_id"]):
            raise CalendarError("Invalid published task identifier.")
        if entry["status"] == "published" and not entry["task_id"]:
            raise CalendarError("Missing published task identifier; preserve state for recovery.")
        if identity != _identity(entry["tasklist"], entry["key"]):
            raise CalendarError("Publication identity does not match its record.")
    return state


def _identity(tasklist, key):
    return hashlib.sha256(json.dumps([tasklist, key], separators=(",", ":")).encode()).hexdigest()


def _preflight(state, preview):
    for item in preview["items"]:
        previous = state["entries"].get(_identity(preview["tasklist"], item["key"]))
        if previous and previous["status"] != "failed" and previous["body"] != item["body"]:
            raise CalendarError("A recorded source already has a different approved payload; resolve it explicitly without another insert.")
        for record in state["entries"].values():
            if record["status"] == "failed" or record["tasklist"] != preview["tasklist"] or record["source"] != preview["source"]:
                continue
            binding = item["source"]
            if all(record["binding"][name] == binding[name] for name in ("heading", "title")):
                if record["binding"]["count"] != binding["count"]:
                    raise CalendarError("Recorded duplicate group changed; resolve its identity before publishing.")
                if previous is record and binding["count"] > 1 and record["binding"]["line"] != binding["line"]:
                    raise CalendarError("Recorded duplicate moved ambiguously; resolve its identity before publishing.")


def _reconcile(service, tasklist, body):
    matches = []
    for task in _pages(service.tasks(), tasklist=tasklist, maxResults=100, showCompleted=True, showHidden=True, showDeleted=False):
        if isinstance(task, dict) and task.get("notes") == body["notes"]:
            matches.append(task)
    if len(matches) != 1:
        return None
    task = matches[0]
    if task.get("deleted") or not isinstance(task.get("id"), str) or not task["id"]:
        return None
    # The API stores a day, not a time; tolerate its timestamp formatting only.
    if any(task.get(name) != body[name] for name in ("title", "notes", "status")) or not isinstance(task.get("due"), str) or task["due"][:10] != body["due"][:10]:
        return None
    return task["id"]


def _result(item, status, task_id=None):
    value = {"key": item["key"], "status": status}
    if task_id:
        value["task_id"] = task_id
    return value


def publish(preview, approval, runtime, service=None):
    validate_preview(preview)
    if not isinstance(approval, str) or approval != preview["approval"]:
        raise CalendarError("Publication requires the exact fingerprint of the reviewed batch.")
    runtime = Path(runtime).expanduser()
    try:
        with ingest_lock(runtime):
            state_path = runtime / "state.json"
            state = _load_state(state_path)
            _preflight(state, preview)
            results = []
            destination_checked = False
            for item in preview["items"]:
                identity = _identity(preview["tasklist"], item["key"])
                record = state["entries"].get(identity)
                if record and record["status"] == "published":
                    results.append(_result(item, "already_published", record["task_id"]))
                    continue
                if service is None:
                    service = build_service(runtime)
                if not destination_checked:
                    if preview["tasklist"] not in {choice["id"] for choice in list_tasklists(service)}:
                        raise CalendarError("The approved destination is not an accessible Tasks list.")
                    destination_checked = True
                if record and record["status"] in {"pending", "uncertain"}:
                    try:
                        task_id = _reconcile(service, preview["tasklist"], record["body"])
                    except Exception:
                        task_id = None
                    if not task_id:
                        results.append(_result(item, "uncertain"))
                        break
                    record.update(status="published", task_id=task_id)
                    _atomic_json(state_path, state)
                    results.append(_result(item, "published", task_id))
                    continue
                validate_preview(preview)
                record = {"tasklist": preview["tasklist"], "key": item["key"], "source": preview["source"], "binding": deepcopy(item["source"]), "body": deepcopy(item["body"]), "status": "pending", "task_id": None}
                state["entries"][identity] = record
                # Durable intent precedes the only non-idempotent operation.
                _atomic_json(state_path, state)
                try:
                    task = service.tasks().insert(tasklist=preview["tasklist"], body=deepcopy(item["body"])).execute(num_retries=0)
                    task_id = task.get("id") if isinstance(task, dict) else None
                    if not isinstance(task_id, str) or not task_id:
                        record["status"] = "uncertain"
                    else:
                        record.update(status="published", task_id=task_id)
                except Exception as exc:
                    code = getattr(getattr(exc, "resp", None), "status", None)
                    record["status"] = "failed" if type(code) is int and 400 <= code < 500 and code != 408 else "uncertain"
                # A write failure leaves the on-disk pending intent for reconciliation.
                _atomic_json(state_path, state)
                results.append(_result(item, record["status"], record["task_id"]))
                if record["status"] != "published":
                    break
            return {"results": results, "failed": sum(item["status"] == "failed" for item in results), "uncertain": sum(item["status"] == "uncertain" for item in results)}
    except RuntimeError:
        raise CalendarError("Another calendar operation is running; no concurrent publication is allowed.") from None
