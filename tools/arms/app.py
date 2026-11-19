#!/usr/bin/env python3
"""ARMS weekly review micro app — loopback-only, standard library only.

Run:   python3 tools/arms/app.py [--port 8790] [--data-dir DIR] [--root DIR]

What it does (and only this):
  * shows the routine report written by tools/arms/routines.py (<data-dir>/routines.json)
  * queries / saves memories through the fixed argv contract of second-brain/brain.py
  * parks feedback for a target skill (durable JSON); it NEVER edits skill files
  * keeps a suggestion cart and renders the selection as Markdown to copy
  * offers one run button: the deterministic `routines.py run` refresh (fixed argv)

Security boundary: binds 127.0.0.1 only; Host and Origin must be this server;
mutations must be application/json with a bounded Content-Length; every input is
validated; subprocesses are launched from fixed argument arrays with shell=False
and no text from the browser is ever interpreted as a command or flag.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX
    fcntl = None  # type: ignore[assignment]
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

APP_VERSION = "1"
DEFAULT_PORT = 8790
LOOPBACK = "127.0.0.1"

HERE = Path(__file__).resolve().parent
STATIC_DIR = HERE / "static"
REPO_ROOT = HERE.parent.parent
DEFAULT_DATA_DIR = HERE / "data"

MAX_BODY_BYTES = 64 * 1024
MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_SUBPROCESS_OUTPUT = 1024 * 1024
BRAIN_TIMEOUT_S = 30
ROUTINES_TIMEOUT_S = 120

LIMITS = {
    "question": 500,
    "title": 120,
    "summary": 500,
    "body": 8000,
    "target_skill": 80,
    "principle": 300,
    "comments": 4000,
    "cart_comment": 2000,
    "cart_items": 100,
    "feedback_items": 1000,
}
FEEDBACK_STATUSES = ("parked", "reviewed", "dismissed")  # web-settable; 'resolved' is CLI-only
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SKILL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,79}$")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SINGLE_LINE_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")

STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/static/style.css": ("style.css", "text/css; charset=utf-8"),
}
ARTIFACT_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
    ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8", ".json": "application/json",
    ".pdf": "application/pdf",
}
ARTIFACT_CSP = (
    "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self' data:; connect-src 'none'; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'"
)

CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


class ApiError(Exception):
    def __init__(self, status: int, message: str, **extra):
        super().__init__(message)
        self.status = status
        self.message = message
        self.extra = extra


# ───────────────────────── validation helpers ─────────────────────────


def _text(body: dict, key: str, *, required: bool, single_line: bool = False,
          max_len: int | None = None) -> str:
    value = body.get(key, "")
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ApiError(400, f"'{key}' must be a string")
    value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    limit = max_len or LIMITS[key]
    if len(value) > limit:
        raise ApiError(400, f"'{key}' is longer than {limit} characters")
    bad = SINGLE_LINE_CONTROL_RE if single_line else CONTROL_RE
    if bad.search(value):
        raise ApiError(400, f"'{key}' contains control characters")
    if required and not value:
        raise ApiError(400, f"'{key}' is required")
    return value


def _only_keys(body: dict, allowed: set[str]) -> None:
    extra = sorted(set(body) - allowed)
    if extra:
        raise ApiError(400, "unknown field(s): " + ", ".join(extra[:5]))


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _atomic_write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_json_file(path: Path, default: object, max_bytes: int = MAX_REPORT_BYTES) -> object:
    try:
        if path.stat().st_size > max_bytes:
            raise ApiError(500, f"{path.name} is larger than {max_bytes} bytes")
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (OSError, ValueError) as exc:
        raise ApiError(500, f"{path.name} is unreadable: {exc}") from exc


# ───────────────────────── application state ─────────────────────────


class StoreLock:
    """Thread lock plus an advisory file lock, so the server and the CLI never interleave writes."""

    def __init__(self, path: Path):
        self._path = path
        self._thread = threading.RLock()
        self._fh = None
        self._depth = 0

    def __enter__(self):
        self._thread.acquire()
        if self._depth == 0:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(self._path, "a+")  # noqa: SIM115 - closed in __exit__
            if fcntl is not None:
                fcntl.flock(self._fh, fcntl.LOCK_EX)
        self._depth += 1
        return self

    def __exit__(self, *exc):
        self._depth -= 1
        if self._depth == 0 and self._fh is not None:
            try:
                if fcntl is not None:
                    fcntl.flock(self._fh, fcntl.LOCK_UN)
            finally:
                self._fh.close()
                self._fh = None
        self._thread.release()


class ReviewApp:
    """Everything the handler needs; separated from HTTP for testability."""

    def __init__(self, root: Path, data_dir: Path, brain_script: Path | None = None,
                 routines_script: Path | None = None):
        self.root = root.resolve()
        self.data_dir = data_dir.resolve()
        self.brain_script = (brain_script or REPO_ROOT / "second-brain" / "brain.py").resolve()
        self.routines_script = (routines_script or HERE / "routines.py").resolve()
        self.report_path = self.data_dir / "routines.json"
        self.feedback_path = self.data_dir / "feedback.json"
        self.cart_path = self.data_dir / "cart.json"
        self.store_lock = StoreLock(self.data_dir / ".store.lock")
        self.artifacts_dir = REPO_ROOT / "artifacts"
        self.managed_skills_dir = Path.home() / ".omp" / "agent" / "managed-skills"
        self.refresh_lock = threading.Lock()
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # ── subprocess: fixed argv only ──
    def _child_env(self) -> dict[str, str]:
        env = {"PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8"}
        for key in ("PATH", "HOME", "TMPDIR", "LC_ALL"):
            if key in os.environ:
                env[key] = os.environ[key]
        return env

    def _run(self, argv: list[str], timeout: int) -> tuple[int, str, str]:
        try:
            proc = subprocess.run(  # noqa: S603 - fixed argv, shell=False
                argv, cwd=str(self.root), env=self._child_env(), stdin=subprocess.DEVNULL,
                capture_output=True, timeout=timeout, shell=False, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ApiError(504, f"command timed out after {timeout}s") from exc
        except OSError as exc:
            raise ApiError(502, f"could not start command: {exc.strerror or exc}") from exc
        if len(proc.stdout) > MAX_SUBPROCESS_OUTPUT:
            raise ApiError(502, "command output exceeded the size limit")
        return (proc.returncode, proc.stdout.decode("utf-8", "replace"),
                proc.stderr.decode("utf-8", "replace")[-600:])

    def _brain(self, *args: str) -> tuple[int, dict]:
        if not self.brain_script.is_file():
            raise ApiError(503, "second-brain/brain.py is not available", code="brain_missing")
        argv = [sys.executable, str(self.brain_script), "--root", str(self.root), *args]
        code, out, err = self._run(argv, BRAIN_TIMEOUT_S)
        try:
            obj = json.loads(out)
        except ValueError:
            obj = None
        if not isinstance(obj, dict):
            raise ApiError(502, "memory CLI returned non-JSON output", exit_code=code,
                           stderr=err.strip())
        return code, obj

    # ── memory ──
    def memory_query(self, body: dict) -> dict:
        _only_keys(body, {"question"})
        question = _text(body, "question", required=True, single_line=True)
        if question.startswith("-"):
            raise ApiError(400, "question must not start with '-'")
        code, obj = self._brain("query", question)
        return self._brain_result(code, obj, ok_codes=(0, 3))

    def memory_remember(self, body: dict) -> dict:
        _only_keys(body, {"title", "summary", "body"})
        title = _text(body, "title", required=True, single_line=True)
        summary = _text(body, "summary", required=True, single_line=True)
        text = _text(body, "body", required=True)
        code, obj = self._brain("remember", f"--title={title}", f"--summary={summary}",
                                f"--body={text}")
        return self._brain_result(code, obj, ok_codes=(0,))

    @staticmethod
    def _brain_result(code: int, obj: dict, ok_codes: tuple[int, ...]) -> dict:
        if code in ok_codes:
            return obj
        if code == 4:
            raise ApiError(503, "memory writer is busy; retry in a moment", code="busy", brain=obj)
        if code == 2:
            raise ApiError(400, str(obj.get("message") or obj.get("error") or "invalid input"),
                           brain=obj)
        raise ApiError(502, str(obj.get("message") or "memory CLI failed"), exit_code=code,
                       brain=obj)

    # ── report ──
    def report(self) -> dict:
        try:
            st = self.report_path.stat()
        except FileNotFoundError:
            return {"status": "missing", "path": str(self.report_path)}
        try:
            data = _read_json_file(self.report_path, None)
        except ApiError as exc:
            return {"status": "invalid", "message": exc.message, "path": str(self.report_path)}
        if not isinstance(data, dict):
            return {"status": "invalid", "message": "report is not a JSON object",
                    "path": str(self.report_path)}
        return {
            "status": "ok",
            "path": str(self.report_path),
            "modified": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds"),
            "report": data,
        }

    def refresh_report(self) -> dict:
        if not self.routines_script.is_file():
            raise ApiError(503, "tools/arms/routines.py is not available", code="routines_missing")
        if not self.refresh_lock.acquire(blocking=False):
            raise ApiError(409, "a refresh is already running")
        try:
            argv = [sys.executable, str(self.routines_script), "run", "--root", str(self.root),
                    "--output", str(self.report_path)]
            code, _out, err = self._run(argv, ROUTINES_TIMEOUT_S)
        finally:
            self.refresh_lock.release()
        if code != 0:
            raise ApiError(502, "routines.py failed", exit_code=code, stderr=err.strip())
        return self.report()

    # ── feedback store ──
    def _feedback(self) -> dict:
        data = _read_json_file(self.feedback_path, {"version": 1, "items": []}, 4 * 1024 * 1024)
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise ApiError(500, "feedback.json has an unexpected shape")
        return data

    def feedback_list(self) -> dict:
        with self.store_lock:
            return {"items": self._feedback()["items"]}

    def feedback_create(self, body: dict) -> dict:
        _only_keys(body, {"target_skill", "principle", "comments"})
        skill = _text(body, "target_skill", required=True, single_line=True)
        if not SKILL_RE.match(skill):
            raise ApiError(400, "'target_skill' may use letters, digits and . _ : / - only")
        principle = _text(body, "principle", required=False, single_line=True)
        comments = _text(body, "comments", required=False)
        if not principle and not comments:
            raise ApiError(400, "provide a principle or comments")
        now = _now()
        item = {
            "id": "fb-" + secrets.token_hex(6),
            "created_at": now,
            "updated_at": now,
            "target_skill": skill,
            "principle": principle,
            "comments": comments,
            "status": "parked",
            "applied": False,
            "user_approved": False,
            "resolution": "",
            "applied_principle": "",
            "resolved_at": None,
        }
        with self.store_lock:
            data = self._feedback()
            if len(data["items"]) >= LIMITS["feedback_items"]:
                raise ApiError(409, "feedback store is full; dismiss or archive old items")
            data["version"] = 1
            data["items"].append(item)
            _atomic_write_json(self.feedback_path, data)
        return item

    def feedback_status(self, body: dict) -> dict:
        """Web-UI triage only. 'resolved' is reachable solely via feedback_resolve (CLI)."""
        _only_keys(body, {"id", "status"})
        fid = _text(body, "id", required=True, single_line=True, max_len=64)
        status = body.get("status")
        if status not in FEEDBACK_STATUSES:
            raise ApiError(400, "'status' must be one of: " + ", ".join(FEEDBACK_STATUSES))
        with self.store_lock:
            data = self._feedback()
            for item in data["items"]:
                if isinstance(item, dict) and item.get("id") == fid:
                    if item.get("status") == "resolved":
                        raise ApiError(409, "resolved feedback is a closed record")
                    item["status"] = status
                    item["updated_at"] = _now()
                    _atomic_write_json(self.feedback_path, data)
                    return item
        raise ApiError(404, "feedback item not found")

    def feedback_resolve(self, fid: str, outcome: str, resolution: str,
                         applied_principle: str, user_approved: bool) -> dict:
        """Record the outcome of an explicit, user-approved review. Edits no skill file."""
        fid = _text({"id": fid}, "id", required=True, single_line=True, max_len=64)
        if outcome not in ("applied", "dismissed"):
            raise ApiError(400, "outcome must be 'applied' or 'dismissed'")
        if outcome == "applied" and not user_approved:
            raise ApiError(400, "an applied resolution requires explicit user approval (--user-approved)")
        resolution = _text({"resolution": resolution}, "resolution", required=True, max_len=LIMITS["comments"])
        applied_principle = _text({"principle": applied_principle}, "principle", required=False,
                                  single_line=True)
        with self.store_lock:
            data = self._feedback()
            for item in data["items"]:
                if isinstance(item, dict) and item.get("id") == fid:
                    if item.get("status") in ("resolved", "dismissed") and item.get("resolved_at"):
                        raise ApiError(409, "feedback is already resolved")
                    now = _now()
                    item["status"] = "resolved" if outcome == "applied" else "dismissed"
                    item["applied"] = outcome == "applied"
                    item["user_approved"] = bool(user_approved)
                    item["resolution"] = resolution
                    item["applied_principle"] = (applied_principle or item.get("principle", "")
                                                 ) if outcome == "applied" else ""
                    item["resolved_at"] = now
                    item["updated_at"] = now
                    _atomic_write_json(self.feedback_path, data)
                    return item
        raise ApiError(404, "feedback item not found")

    # ── cart store ──
    def _cart(self) -> dict:
        data = _read_json_file(self.cart_path, {"version": 1, "items": []}, 1024 * 1024)
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise ApiError(500, "cart.json has an unexpected shape")
        return data

    def cart_get(self) -> dict:
        with self.store_lock:
            return {"items": self._cart()["items"]}

    def cart_put(self, body: dict) -> dict:
        _only_keys(body, {"items"})
        items = body.get("items")
        if not isinstance(items, list):
            raise ApiError(400, "'items' must be a list")
        if len(items) > LIMITS["cart_items"]:
            raise ApiError(400, f"cart holds at most {LIMITS['cart_items']} items")
        clean, seen = [], set()
        for raw in items:
            if not isinstance(raw, dict):
                raise ApiError(400, "each cart item must be an object")
            _only_keys(raw, {"suggestion_id", "comment"})
            sid = _text(raw, "suggestion_id", required=True, single_line=True, max_len=128)
            if not ID_RE.match(sid):
                raise ApiError(400, "invalid suggestion_id")
            if sid in seen:
                raise ApiError(400, "duplicate suggestion_id")
            seen.add(sid)
            clean.append({"suggestion_id": sid,
                          "comment": _text(raw, "comment", required=False, max_len=LIMITS["cart_comment"])})
        with self.store_lock:
            _atomic_write_json(self.cart_path, {"version": 1, "updated_at": _now(), "items": clean})
        return {"items": clean}

    def cart_markdown(self, include_feedback: bool) -> dict:
        rep = self.report()
        report = rep.get("report") if rep.get("status") == "ok" else None
        sugg_block = (report or {}).get("suggestions") if isinstance(report, dict) else None
        sugg_items = sugg_block.get("items", []) if isinstance(sugg_block, dict) else []
        by_id = {s.get("id"): s for s in sugg_items if isinstance(s, dict)}
        generated = sugg_block.get("generated_at") if isinstance(sugg_block, dict) else None
        cart = self.cart_get()["items"]

        def clip(value: object) -> str:
            return str(value).replace("\r", " ").strip()

        lines = ["# ARMS weekly review — selected suggestions", ""]
        lines.append(f"Exported {_now()}; suggestions generated {clip(generated) if generated else 'unknown'}.")
        lines.append("Suggestions are proposals only. Nothing here has been executed or applied.")
        lines.append("")
        if not cart:
            lines += ["_No suggestions selected._", ""]
        for index, entry in enumerate(cart, 1):
            sid = entry.get("suggestion_id", "")
            sug = by_id.get(sid)
            lines.append(f"## {index}. {clip(sug.get('title')) if sug else sid}")
            lines.append(f"- id: `{sid}`")
            if sug is None:
                lines.append("- note: not present in the current report")
            else:
                if sug.get("summary"):
                    lines.append(f"- why: {clip(sug['summary'])}")
                if sug.get("evidence_count") is not None:
                    days = ", ".join(clip(d) for d in (sug.get("days") or [])[:14])
                    lines.append(f"- evidence: {sug['evidence_count']} observation(s)"
                                 + (f" on {days}" if days else ""))
                if sug.get("proposed_action"):
                    lines.append(f"- proposed action (not executed): {clip(sug['proposed_action'])}")
            comment = (entry.get("comment") or "").strip()
            if comment:
                lines.append("- comment:")
                lines += ["  > " + ln for ln in comment.split("\n")]
            lines.append("")
        if include_feedback:
            parked = [f for f in self.feedback_list()["items"]
                      if isinstance(f, dict) and f.get("status") == "parked"]
            lines.append("# Parked feedback (not applied)")
            lines.append("")
            if not parked:
                lines += ["_No parked feedback._", ""]
            for fb in parked:
                lines.append(f"## {clip(fb.get('target_skill'))} — {clip(fb.get('id'))}")
                if fb.get("principle"):
                    lines.append(f"- principle: {clip(fb['principle'])}")
                if fb.get("comments"):
                    lines.append("- comments:")
                    lines += ["  > " + ln for ln in str(fb["comments"]).split("\n")]
                lines.append("")
        return {"markdown": "\n".join(lines).rstrip() + "\n", "selected": len(cart)}

    # ── artifacts: read-only, explicit, extension-whitelisted ──
    def artifact(self, rel: str) -> tuple[bytes, str]:
        rel = rel or "index.html"
        parts = rel.split("/")
        if any(not p or p.startswith(".") or "\\" in p or "\x00" in p for p in parts):
            raise ApiError(404, "not found")
        ctype = ARTIFACT_TYPES.get(Path(rel).suffix.lower())
        if ctype is None:
            raise ApiError(404, "not found")
        base = self.artifacts_dir.resolve()
        target = (base / rel).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ApiError(404, "not found") from exc
        if not target.is_file() or target.stat().st_size > 20 * 1024 * 1024:
            raise ApiError(404, "not found")
        return target.read_bytes(), ctype

    # ── status ──
    def known_skills(self) -> list[str]:
        """Skill directory names only (never contents), for the target-skill suggestions."""
        names: set[str] = set()
        for base in (self.root / ".claude/skills", self.root / ".agents/skills", self.managed_skills_dir):
            try:
                for child in base.iterdir():
                    if (child / "SKILL.md").is_file() and SKILL_RE.match(child.name):
                        names.add(child.name)
            except OSError:
                continue
        return sorted(names)[:500]

    def status(self) -> dict:
        return {
            "app": "arms-review",
            "version": APP_VERSION,
            "root": str(self.root),
            "data_dir": str(self.data_dir),
            "brain_available": self.brain_script.is_file(),
            "routines_available": self.routines_script.is_file(),
            "known_skills": self.known_skills(),
            "feedback_statuses": list(FEEDBACK_STATUSES),
            "artifacts_available": (self.artifacts_dir / "index.html").is_file(),
            "limits": LIMITS,
        }


# ───────────────────────── HTTP layer ─────────────────────────


class Handler(BaseHTTPRequestHandler):
    _consumed = False
    server_version = "ARMSReview/" + APP_VERSION
    sys_version = ""
    timeout = 15
    _csp = CSP

    # -- responses --
    def _headers(self, status: int, ctype: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", self._csp)
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")

    def _send(self, status: int, ctype: str, payload: bytes, extra: dict | None = None) -> None:
        self._headers(status, ctype, len(payload))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status: int, obj: object) -> None:
        self._send(status, "application/json; charset=utf-8",
                   json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    # -- boundary checks --
    @property
    def _origins(self) -> set[str]:
        port = self.server.server_address[1]
        return {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}

    def _check_boundary(self) -> None:
        host = self.headers.get("Host", "")
        if host not in {o[len("http://"):] for o in self._origins}:
            raise ApiError(403, "foreign Host header rejected")
        origin = self.headers.get("Origin")
        if origin is not None and origin not in self._origins:
            raise ApiError(403, "foreign Origin rejected")
        site = self.headers.get("Sec-Fetch-Site")
        if site is not None and site not in ("same-origin", "none"):
            raise ApiError(403, "cross-site request rejected")

    def _read_json_body(self) -> dict:
        ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if ctype != "application/json":
            raise ApiError(415, "Content-Type must be application/json")
        if self.headers.get("Transfer-Encoding"):
            raise ApiError(411, "chunked bodies are not accepted; send Content-Length")
        raw_len = self.headers.get("Content-Length")
        if raw_len is None or not raw_len.isdigit():
            raise ApiError(411, "Content-Length required")
        length = int(raw_len)
        if length > MAX_BODY_BYTES:
            raise ApiError(413, f"body larger than {MAX_BODY_BYTES} bytes")
        raw = self.rfile.read(length)
        self._consumed = True
        if len(raw) != length:
            raise ApiError(400, "truncated body")
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ApiError(400, "body is not valid JSON") from exc
        if not isinstance(body, dict):
            raise ApiError(400, "body must be a JSON object")
        return body

    # -- dispatch --
    def _dispatch(self, method: str) -> None:
        try:
            self._check_boundary()
            path = urlsplit(self.path).path
            query = urlsplit(self.path).query
            app: ReviewApp = self.server.app  # type: ignore[attr-defined]
            if method == "GET" and path in STATIC_FILES:
                name, ctype = STATIC_FILES[path]
                try:
                    payload = (STATIC_DIR / name).read_bytes()
                except OSError as exc:
                    raise ApiError(404, "asset missing") from exc
                self._send(200, ctype, payload)
                return
            if method == "GET" and path.startswith("/artifacts/"):
                payload, ctype = app.artifact(path[len("/artifacts/"):])
                self._csp = "frame-ancestors 'none'" if ctype == "application/pdf" else ARTIFACT_CSP
                self._send(200, ctype, payload)
                return
            if method == "GET" and path == "/favicon.ico":
                self._send(204, "image/x-icon", b"")
                return
            if not path.startswith("/api/"):
                raise ApiError(404, "not found")
            routes = {
                ("GET", "/api/status"): lambda: app.status(),
                ("GET", "/api/report"): lambda: app.report(),
                ("POST", "/api/report/refresh"): lambda: app.refresh_report(),
                ("POST", "/api/memory/query"): lambda: app.memory_query(self._read_json_body()),
                ("POST", "/api/memory/remember"): lambda: app.memory_remember(self._read_json_body()),
                ("GET", "/api/feedback"): lambda: app.feedback_list(),
                ("POST", "/api/feedback"): lambda: app.feedback_create(self._read_json_body()),
                ("POST", "/api/feedback/status"): lambda: app.feedback_status(self._read_json_body()),
                ("GET", "/api/cart"): lambda: app.cart_get(),
                ("PUT", "/api/cart"): lambda: app.cart_put(self._read_json_body()),
                ("GET", "/api/cart/markdown"): lambda: app.cart_markdown("feedback=1" in query.split("&")),
            }
            handler = routes.get((method, path))
            if handler is None:
                known = {p for (_m, p) in routes}
                if path in known:
                    raise ApiError(405, "method not allowed")
                raise ApiError(404, "not found")
            if method in ("POST", "PUT") and path == "/api/report/refresh":
                # Body is ignored, but must still be a bounded JSON request.
                self._read_json_body()
            result = handler()
            self._json(201 if (method == "POST" and path == "/api/feedback") else 200, result)
        except ApiError as exc:
            self._json(exc.status, {"error": exc.message, **exc.extra})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # noqa: BLE001 - never leak a traceback to the client
            sys.stderr.write(f"internal error: {type(exc).__name__}: {exc}\n")
            self._json(500, {"error": "internal error"})
        finally:
            self._drain_body()

    def _drain_body(self) -> None:
        """Discard an unread (rejected) request body so closing never resets the client's read."""
        if self._consumed or self.command not in ("POST", "PUT"):
            return
        raw_len = self.headers.get("Content-Length", "")
        if not raw_len.isdigit():
            return
        remaining = min(int(raw_len), 1 << 20)
        try:
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 65536))
                if not chunk:
                    break
                remaining -= len(chunk)
        except OSError:
            pass

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def do_PUT(self) -> None:  # noqa: N802
        self._dispatch("PUT")

    def _method_not_allowed(self) -> None:
        self._send(405, "application/json; charset=utf-8", b'{"error":"method not allowed"}',
                   {"Allow": "GET, POST, PUT"})

    do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _method_not_allowed  # noqa: N815

    def log_message(self, fmt: str, *args) -> None:
        # An idle keep-alive socket can time out before a request line is parsed, when the
        # handler has no `command` or `path` yet; log that without raising in the handler thread.
        command = getattr(self, "command", None)
        if command is None:
            sys.stderr.write("[arms-app] %s\n" % (fmt % args))
            return
        sys.stderr.write("[arms-app] %s %s\n" % (command, urlsplit(getattr(self, "path", "")).path))


class ReviewServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, app: ReviewApp):
        self.app = app
        super().__init__(address, handler)


def create_server(root: Path, data_dir: Path, port: int = DEFAULT_PORT,
                  brain_script: Path | None = None,
                  routines_script: Path | None = None) -> ReviewServer:
    app = ReviewApp(root, data_dir, brain_script, routines_script)
    return ReviewServer((LOOPBACK, port), Handler, app)


def _build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data-dir", type=Path, default=argparse.SUPPRESS,
                        help="store directory (default tools/arms/data)")
    parser = argparse.ArgumentParser(
        description="ARMS weekly review app (loopback only) and its feedback-store CLI.",
        epilog="Without a subcommand the server starts. note/notes/resolve only read and write "
               "<data-dir>/feedback.json; they never edit skill files.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="TCP port (default 8790; 0 = any free port)")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                        help="where routines.json, feedback.json and cart.json live (default tools/arms/data)")
    parser.add_argument("--root", type=Path, default=REPO_ROOT,
                        help="workspace root handed to brain.py and routines.py (default: this repo)")
    sub = parser.add_subparsers(dest="cmd")
    note = sub.add_parser("note", parents=[common], help="park feedback for a skill")
    note.add_argument("--target", required=True, help="target skill name, e.g. frontend-design")
    note.add_argument("--body", default="", help="feedback comments")
    note.add_argument("--principle", default="", help="one-line principle (optional)")
    notes = sub.add_parser("notes", parents=[common], help="list feedback as JSON")
    notes.add_argument("--status", default="parked", choices=(*FEEDBACK_STATUSES, "resolved", "all"))
    notes.add_argument("--target", default="", help="only this target skill")
    res = sub.add_parser("resolve", parents=[common],
                         help="record the outcome of a reviewed note (does not edit any file)")
    res.add_argument("id", help="feedback id, e.g. fb-0123456789ab")
    res.add_argument("--resolution", required=True, help="what was decided or applied")
    res.add_argument("--outcome", choices=("applied", "dismissed"), default="applied")
    res.add_argument("--applied-principle", default="",
                     help="principle actually applied (defaults to the note's principle)")
    res.add_argument("--user-approved", action="store_true",
                     help="REQUIRED for outcome=applied: the user explicitly approved applying it")
    return parser


def _cli_output(obj: object, code: int = 0) -> int:
    print(json.dumps(obj, indent=2, ensure_ascii=False))
    return code


def _run_cli(args: argparse.Namespace) -> int:
    app = ReviewApp(args.root, args.data_dir)
    try:
        if args.cmd == "note":
            if not args.body.strip() and not args.principle.strip():
                raise ApiError(400, "provide --body and/or --principle")
            item = app.feedback_create({"target_skill": args.target, "principle": args.principle,
                                        "comments": args.body})
            return _cli_output({"status": "parked", "item": item})
        if args.cmd == "notes":
            items = [i for i in app.feedback_list()["items"] if isinstance(i, dict)
                     and (args.status == "all" or i.get("status") == args.status)
                     and (not args.target or i.get("target_skill") == args.target)]
            return _cli_output({"status": "ok", "count": len(items), "items": items})
        item = app.feedback_resolve(args.id, args.outcome, args.resolution,
                                    args.applied_principle, args.user_approved)
        return _cli_output({"status": item["status"], "item": item})
    except ApiError as exc:
        return _cli_output({"status": "error", "error": exc.message, **exc.extra}, 2)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    if args.cmd:
        return _run_cli(args)
    server = create_server(args.root, args.data_dir, args.port)
    host, port = server.server_address[:2]
    print(f"ARMS review app: http://{host}:{port}/  (data: {server.app.data_dir})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopped", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
