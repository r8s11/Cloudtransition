"""Source connectors for the personal knowledge base: Claude Code sessions and Gmail.

Design rules (see docs/plans/personal-knowledge-base/):
- Everything is sanitized (secret masking) BEFORE it is hashed, chunked or stored.
- One source item = (source, source_id). Items are replaced atomically with kb_store.replace_rows.
- Raw text is stored in exact 4,000-character chunks (the last one may be shorter); short items
  (<= 4,000 characters) also get one `short` search row. Long items are marked
  metadata.summary_status = "pending"; this module NEVER calls a paid API.
- Source files are only ever read. Memory use is bounded by one source file / one Gmail thread at a time.
- Google libraries are imported lazily, only when a real Gmail client has to be built.
"""

from __future__ import annotations

import base64
import calendar
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable

import kb_privacy
import kb_store
from kb_privacy import (
    contains_private_key,
    diagnostic,
    exclusion_fingerprint,
    is_excluded_path,
    is_secret_path,
    is_security_email,
    load_exclusion_patterns,
    redact,
    redact_obj,
    safe_error,
)

SOURCE_CLAUDE = "claude"
SOURCE_GMAIL = "gmail"
CHUNK_SIZE = 4000
SHORT_LIMIT = CHUNK_SIZE
STORE_VERSION = "2"  # bump when extraction/redaction changes so items are re-stored
SUMMARY_PENDING = "pending"

GMAIL_SCOPES = ("https://www.googleapis.com/auth/gmail.readonly",)
GMAIL_OVERLAP_DAYS = 3
GMAIL_FIRST_RUN_MONTHS = 12
GMAIL_MAX_ATTEMPTS = 3
GMAIL_PAGE_SIZE = 500
GMAIL_UNITS_PER_SECOND = 80.0  # 4,800/min, below Google's 6,000/user/min.
GMAIL_LOGIN_HINT = "Run the interactive Gmail login once (ingest_all.py --gmail-login); scheduled runs never open a browser."

MAX_WARNINGS = 20


# --------------------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------------------


class ConnectorError(Exception):
    """A connector failed. `category` is a safe label for logs/stats; message is already sanitized."""

    category = "error"

    def __init__(self, message: str, *, category: str | None = None, counts: dict[str, Any] | None = None):
        super().__init__(message)
        if category:
            self.category = category
        self.counts = counts or {}


class GmailAuthError(ConnectorError):
    category = "auth"


class GmailQuotaError(ConnectorError):
    category = "quota"


class GmailServerError(ConnectorError):
    category = "server"


class GmailError(ConnectorError):
    category = "gmail"


class SourceUnavailableError(ConnectorError):
    category = "source-unavailable"


class SourceChangedError(ConnectorError):
    category = "changed-during-read"


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(value: Any, default: str | None = None) -> str | None:
    """Normalize datetime / epoch / ISO-8601 string to 'YYYY-MM-DDTHH:MM:SSZ' (UTC)."""
    dt: datetime | None = None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            seconds = float(value) / 1000.0 if value > 1e11 else float(value)
            dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            dt = None
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            dt = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text)
        except ValueError:
            dt = None
    if dt is None:
        return default
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def months_ago(moment: datetime, months: int) -> datetime:
    index = moment.year * 12 + (moment.month - 1) - months
    year, month = divmod(index, 12)
    month += 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def chunk_text(text: str, size: int = CHUNK_SIZE) -> list[str]:
    """Exact fixed-size chunks; ''.join(chunks) == text. The final chunk may be shorter."""
    return [text[i : i + size] for i in range(0, len(text), size)]


def content_hash(title: str, content: str) -> str:
    h = hashlib.sha256()
    h.update(STORE_VERSION.encode())
    h.update(b"\0")
    h.update(title.encode("utf-8", "surrogatepass"))
    h.update(b"\0")
    h.update(content.encode("utf-8", "surrogatepass"))
    return h.hexdigest()


def _row_to_dict(row: Any) -> dict[str, Any]:
    meta = row["metadata"]
    try:
        meta = json.loads(meta) if isinstance(meta, str) else dict(meta or {})
    except ValueError:
        meta = {}
    return {"kind": row["kind"], "ts": row["ts"], "title": row["title"], "content": row["content"], "metadata": meta}


def read_item_rows(conn, source: str, source_id: str) -> list[dict[str, Any]]:
    cur = conn.execute(
        "SELECT kind, ts, title, content, metadata FROM docs WHERE source=? AND source_id=? ORDER BY id",
        (source, source_id),
    )
    return [_row_to_dict(r) for r in cur.fetchall()]


def stored_hash(conn, source: str, source_id: str) -> str | None:
    row = conn.execute(
        "SELECT metadata FROM docs WHERE source=? AND source_id=? AND kind='raw' ORDER BY id LIMIT 1",
        (source, source_id),
    ).fetchone()
    if row is None:
        return None
    try:
        return json.loads(row["metadata"]).get("item_hash")
    except (ValueError, AttributeError, TypeError):
        return None


def rewrite_item(conn, source: str, source_id: str, mutate: Callable[[dict[str, Any]], None]) -> int:
    """Re-write an item's existing rows (e.g. metadata flag changes) through the atomic replace."""
    rows = read_item_rows(conn, source, source_id)
    if not rows:
        return 0
    for row in rows:
        mutate(row)
    kb_store.replace_rows(conn, source, source_id, rows)
    return len(rows)


def purge_item(conn, source: str, source_id: str) -> None:
    kb_store.replace_rows(conn, source, source_id, [])


# --------------------------------------------------------------------------------------
# Core store helper
# --------------------------------------------------------------------------------------


def store_item(
    conn,
    source: str,
    source_id: str,
    ts: Any,
    title: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sanitize, hash, chunk and atomically write one source item.

    Returns {"status": new|updated|unchanged|empty, "item_hash", "chunks", "chars", "long", "pending"}.
    Unchanged items (same sanitized content hash) are not rewritten, so existing summaries stay.
    """
    clean_title = redact(title or "").strip().replace("\n", " ")[:300] or "(untitled)"
    clean = redact(content or "")
    if not clean.strip():
        return {"status": "empty", "item_hash": None, "chunks": 0, "chars": 0, "long": False, "pending": False}
    stamp = to_iso(ts)
    if stamp is None:
        raise ValueError("store_item requires a valid timestamp")
    digest = content_hash(clean_title, clean)
    previous = stored_hash(conn, source, source_id)
    if previous == digest:
        return {"status": "unchanged", "item_hash": digest, "chunks": 0, "chars": len(clean), "long": len(clean) > SHORT_LIMIT, "pending": False}

    chunks = chunk_text(clean)
    is_long = len(clean) > SHORT_LIMIT
    base = redact_obj(dict(metadata or {}))
    base.update({"item_hash": digest, "chunk_count": len(chunks), "chunk_size": CHUNK_SIZE, "chars": len(clean)})
    rows: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        meta = dict(base)
        meta.update({"chunk_index": index, "chunk_start": index * CHUNK_SIZE, "chunk_end": index * CHUNK_SIZE + len(chunk)})
        if is_long:
            meta["summary_status"] = SUMMARY_PENDING
        rows.append({"kind": "raw", "ts": stamp, "title": clean_title, "content": chunk, "metadata": meta})
    if not is_long:
        rows.append({"kind": "short", "ts": stamp, "title": clean_title, "content": clean, "metadata": dict(base)})
    kb_store.replace_rows(conn, source, source_id, rows)
    return {
        "status": "new" if previous is None else "updated",
        "item_hash": digest,
        "chunks": len(chunks),
        "chars": len(clean),
        "long": is_long,
        "pending": is_long,
    }


# --------------------------------------------------------------------------------------
# State helpers
# --------------------------------------------------------------------------------------


def _merge_skipped(conn, source: str, additions: dict[str, str], removals: Iterable[str] = ()) -> dict[str, Any]:
    current = kb_store.get_state(conn, source, "skipped", None) or {}
    items = dict(current.get("items") or {})
    items.update(additions)
    for key in removals:
        items.pop(key, None)
    reasons: dict[str, int] = {}
    for reason in items.values():
        reasons[reason] = reasons.get(reason, 0) + 1
    value = {"count": len(items), "reasons": reasons, "items": items}
    kb_store.set_state(conn, source, "skipped", value)
    return value


def _hid(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()[:12]


def _finish_ok(conn, source: str, when: str, counts: dict[str, Any]) -> None:
    kb_store.set_state(conn, source, "last_counts", counts)
    kb_store.set_state(conn, source, "last_error", {})
    kb_store.set_state(conn, source, "last_success", when)


def _finish_error(conn, source: str, when: str, category: str, message: str, counts: dict[str, Any]) -> None:
    kb_store.set_state(conn, source, "last_counts", counts)
    record = {"at": when, "category": category, "message": redact(message), "notice": kb_privacy.MASKING_NOTICE}
    kb_store.set_state(conn, source, "last_error", record)


# --------------------------------------------------------------------------------------
# Claude Code sessions
# --------------------------------------------------------------------------------------


def default_claude_root() -> Path:
    override = os.environ.get("CLAUDE_PROJECTS_DIR")
    return Path(override).expanduser() if override else Path.home() / ".claude" / "projects"


def _read_file_bytes(path: Path) -> bytes:  # indirection so tests can simulate a file that changes mid-read
    return path.read_bytes()


def read_stable(path: Path, attempts: int = 3) -> tuple[bytes, dict[str, Any]]:
    """Read a whole file and return (bytes, signature). Retries when the file changed while being read
    (stat/size/hash mismatch) and raises SourceChangedError rather than returning a misleading signature.
    Signature = size + sha256 of the bytes actually read (mtime is informational, so same-mtime edits are caught)."""
    last = None
    for _ in range(attempts):
        before = path.stat()
        data = _read_file_bytes(path)
        after = path.stat()
        stable = (
            before.st_size == after.st_size
            and before.st_mtime_ns == after.st_mtime_ns
            and len(data) == after.st_size
        )
        if stable:
            return data, {"size": len(data), "mtime_ns": after.st_mtime_ns, "sha256": hashlib.sha256(data).hexdigest()}
        last = after
    raise SourceChangedError("source file kept changing while being read; will retry on the next run")



_TOOL_FIELDS = ("command", "file_path", "path", "pattern", "url", "query", "description", "prompt", "subagent_type")


def _tool_lines(name: str, tool_input: Any) -> tuple[str | None, bool]:
    """(text, is_secret). Only whitelisted, useful fields of a tool call are kept."""
    if not isinstance(tool_input, dict):
        return f"[tool {name}]", False
    strings = [v for v in tool_input.values() if isinstance(v, str)]
    if any(is_secret_path(v) or is_excluded_path(v) for v in strings):
        return None, True
    fields = []
    for key in _TOOL_FIELDS:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            fields.append(f"{key}: {value.strip()}")
    return f"[tool {name}] " + "\n".join(fields) if fields else f"[tool {name}]", False


def _result_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                out.append(block["text"])
            elif isinstance(block, str):
                out.append(block)
        return "\n".join(out)
    return ""


def parse_session(data: bytes) -> dict[str, Any]:
    """Extract sanitized-later conversation text from JSONL bytes.

    Keeps user/assistant text, whitelisted tool-call fields and complete eligible tool outcomes.
    Drops thinking blocks, credential/private-source tool traffic and records holding private keys.
    Tolerates malformed interior lines and an unfinished trailing line."""
    text = data.decode("utf-8", errors="replace")
    lines = text.split("\n")
    ends_with_newline = text.endswith("\n")
    pieces: list[str] = []
    stamps: list[str] = []
    result: dict[str, Any] = {
        "records": 0, "messages": 0, "malformed": 0, "incomplete_tail": False, "secret_records": 0,
        "warnings": [], "session_id": None, "cwd": None, "summary": None, "first_user": None,
    }
    tools: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()

    def warn(message: str) -> None:
        if len(result["warnings"]) < MAX_WARNINGS:
            result["warnings"].append(message)

    def add(piece: str | None) -> None:
        if piece is None:
            return
        if contains_private_key(piece):
            result["secret_records"] += 1
            return
        pieces.append(piece)
        result["messages"] += 1

    for index, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            if index == len(lines) - 1 and not ends_with_newline:
                result["incomplete_tail"] = True
            else:
                result["malformed"] += 1
                warn(f"line {index + 1}: malformed JSON record skipped")
            continue
        if not isinstance(record, dict):
            result["malformed"] += 1
            warn(f"line {index + 1}: unexpected JSON value skipped")
            continue
        result["records"] += 1
        uuid = record.get("uuid")
        if isinstance(uuid, str):
            key = f"{record.get('type')}:{uuid}"
            if key in seen:
                continue
            seen.add(key)
        stamp = to_iso(record.get("timestamp"))
        if stamp:
            stamps.append(stamp)
        if isinstance(record.get("sessionId"), str) and not result["session_id"]:
            result["session_id"] = record["sessionId"]
        if isinstance(record.get("cwd"), str) and not result["cwd"]:
            result["cwd"] = record["cwd"]
        kind = record.get("type")
        if kind == "summary":
            if isinstance(record.get("summary"), str) and not result["summary"]:
                result["summary"] = record["summary"]
            continue
        if kind not in ("user", "assistant") or record.get("isMeta"):
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        role = message.get("role") if isinstance(message.get("role"), str) else kind
        content = message.get("content")
        if isinstance(content, str):
            if content.strip():
                if role == "user" and not result["first_user"]:
                    result["first_user"] = content.strip()
                add(f"[{role}] {content.strip()}")
            continue
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text" and isinstance(block.get("text"), str) and block["text"].strip():
                if role == "user" and not result["first_user"]:
                    result["first_user"] = block["text"].strip()
                add(f"[{role}] {block['text'].strip()}")
            elif btype == "tool_use":
                name = str(block.get("name") or "tool")
                line_text, secret = _tool_lines(name, block.get("input"))
                if isinstance(block.get("id"), str):
                    tools[block["id"]] = {"name": name, "secret": secret}
                if secret:
                    result["secret_records"] += 1
                else:
                    add(line_text)
            elif btype == "tool_result":
                info = tools.get(block.get("tool_use_id")) if isinstance(block.get("tool_use_id"), str) else None
                if info and info["secret"]:
                    result["secret_records"] += 1
                    continue
                body = _result_text(block.get("content")).strip()
                if not body:
                    continue
                if block.get("is_error"):
                    add(f"[tool error{' ' + info['name'] if info else ''}] {body}")
                else:
                    add(f"[tool result{' ' + info['name'] if info else ''}] {body}")
    result["text"] = "\n\n".join(pieces)
    result["first_ts"] = min(stamps) if stamps else None
    result["last_ts"] = max(stamps) if stamps else None
    return result


def ingest_claude(conn, root: str | os.PathLike[str] | None = None, *, exclude_patterns: Iterable[str] | None = None) -> dict[str, Any]:
    """Ingest Claude Code session JSONL files under `root` (default ~/.claude/projects). Read-only on sources."""
    started = utcnow()
    now_iso = to_iso(started)
    base = Path(root).expanduser() if root else default_claude_root()
    if not base.is_dir():
        # never treat a missing mount/dir as "everything was deleted"
        message = "Claude projects directory is not available"
        _finish_error(conn, SOURCE_CLAUDE, now_iso, SourceUnavailableError.category, message, {})
        raise SourceUnavailableError(message)

    patterns = load_exclusion_patterns(exclude_patterns)
    fingerprint = STORE_VERSION + ":" + exclusion_fingerprint(patterns)
    force = kb_store.get_state(conn, SOURCE_CLAUDE, "exclusion_fingerprint", None) != fingerprint
    known: dict[str, dict[str, Any]] = dict(kb_store.get_state(conn, SOURCE_CLAUDE, "files", None) or {})

    counts: dict[str, Any] = {
        "files": 0, "parsed": 0, "unchanged_files": 0, "new": 0, "updated": 0, "unchanged_items": 0,
        "empty": 0, "excluded": 0, "pending_summaries": 0, "malformed_records": 0, "incomplete_tails": 0,
        "secret_records": 0, "missing_sources": 0, "errors": 0, "unstable": 0, "warnings": [],
    }
    skipped_add: dict[str, str] = {}
    skipped_remove: list[str] = []
    seen: set[str] = set()
    failures: list[str] = []

    def warn(message: str) -> None:
        if len(counts["warnings"]) < MAX_WARNINGS:
            counts["warnings"].append(redact(message))

    for path in sorted(base.rglob("*.jsonl")):
        if path.is_symlink() or not path.is_file():
            continue
        rel = path.relative_to(base).as_posix()
        source_id = rel[: -len(".jsonl")]
        seen.add(rel)
        counts["files"] += 1
        prior = known.get(rel) or {}
        hid = _hid(rel)

        def exclude(reason: str, signature: dict[str, Any] | None = None) -> None:
            counts["excluded"] += 1
            skipped_add[hid] = reason
            if prior.get("status") == "ingested" or stored_hash(conn, SOURCE_CLAUDE, source_id):
                purge_item(conn, SOURCE_CLAUDE, source_id)
            entry = {"status": "excluded", "source_id": source_id}
            if signature:
                entry.update(signature)
            known[rel] = entry

        try:
            if is_excluded_path(rel, patterns):
                exclude("excluded_path")
                continue
            data, signature = read_stable(path)
            if (
                not force
                and prior.get("sha256") == signature["sha256"]
                and prior.get("size") == signature["size"]
                and prior.get("status") in ("ingested", "excluded", "empty")
            ):
                counts["unchanged_files"] += 1
                known[rel] = {**prior, "mtime_ns": signature["mtime_ns"]}
                continue
            parsed = parse_session(data)
            del data
            counts["parsed"] += 1
            counts["malformed_records"] += parsed["malformed"]
            counts["incomplete_tails"] += 1 if parsed["incomplete_tail"] else 0
            counts["secret_records"] += parsed["secret_records"]
            for w in parsed["warnings"]:
                warn(f"{hid}: {w}")
            if parsed["incomplete_tail"]:
                warn(f"{hid}: unfinished trailing line ignored until the file changes")
            if is_excluded_path(parsed["cwd"], patterns):
                exclude("excluded_cwd", signature)
                continue
            mtime_iso = to_iso(datetime.fromtimestamp(signature["mtime_ns"] / 1e9, tz=timezone.utc))
            last_ts = parsed["last_ts"] or mtime_iso
            parts = rel.split("/")
            first_line = (parsed["first_user"] or "").strip().splitlines()
            title = parsed["summary"] or (first_line[0][:100] if first_line else "") or f"Claude session {parts[-1][:-6]}"
            metadata = {
                "path": str(path),
                "pointer": str(path),
                "relative_path": rel,
                "project": parts[0],
                "session_id": parsed["session_id"] or parts[-1][:-6],
                "subagent": "subagents" in parts[:-1],
                "first_ts": parsed["first_ts"] or mtime_iso,
                "last_ts": last_ts,
                "ts_source": "records" if parsed["last_ts"] else "file_mtime",
                "message_count": parsed["messages"],
                "malformed_records": parsed["malformed"],
                "incomplete_tail": parsed["incomplete_tail"],
                "original": "available",
            }
            outcome = store_item(conn, SOURCE_CLAUDE, source_id, last_ts, title, parsed["text"], metadata)
            status = outcome["status"]
            if status == "empty":
                counts["empty"] += 1
                known[rel] = {"status": "empty", "source_id": source_id, **signature}
                continue
            if status == "unchanged":
                counts["unchanged_items"] += 1
                if prior.get("status") == "missing":
                    def restore(row: dict[str, Any]) -> None:
                        row["metadata"]["original"] = "available"
                        row["metadata"].pop("original_missing_since", None)

                    rewrite_item(conn, SOURCE_CLAUDE, source_id, restore)
            else:
                counts[status] += 1
            if outcome["pending"]:
                counts["pending_summaries"] += 1
            known[rel] = {"status": "ingested", "source_id": source_id, **signature}
        except SourceChangedError as exc:
            counts["unstable"] += 1
            counts["errors"] += 1
            failures.append(f"{hid}: {safe_error(exc)}")
        except Exception as exc:  # isolate one bad file from the rest
            counts["errors"] += 1
            failures.append(f"{hid}: {safe_error(exc)}")

    # sources deleted after ingestion keep their archive and get a truthful pointer status
    for rel, entry in list(known.items()):
        if rel in seen or entry.get("status") != "ingested":
            continue
        source_id = entry.get("source_id") or rel[: -len(".jsonl")]

        def mark(row: dict[str, Any], when=now_iso) -> None:
            row["metadata"]["original"] = "missing"
            row["metadata"]["original_missing_since"] = row["metadata"].get("original_missing_since") or when

        try:
            rewrite_item(conn, SOURCE_CLAUDE, source_id, mark)
            known[rel] = {**entry, "status": "missing"}
            counts["missing_sources"] += 1
        except Exception as exc:
            counts["errors"] += 1
            failures.append(f"{_hid(rel)}: {safe_error(exc)}")

    kb_store.set_state(conn, SOURCE_CLAUDE, "files", known)
    kb_store.set_state(conn, SOURCE_CLAUDE, "exclusion_fingerprint", fingerprint)
    _merge_skipped(conn, SOURCE_CLAUDE, skipped_add, skipped_remove)
    if failures:
        counts["failures"] = failures[:MAX_WARNINGS]
        message = f"{len(failures)} session file(s) failed: " + "; ".join(failures[:3])
        _finish_error(conn, SOURCE_CLAUDE, now_iso, "partial", message, counts)
        raise ConnectorError(redact(message), category="partial", counts=counts)
    _finish_ok(conn, SOURCE_CLAUDE, now_iso, counts)
    return counts


# --------------------------------------------------------------------------------------
# Gmail
# --------------------------------------------------------------------------------------


def gmail_token_path() -> Path:
    override = os.environ.get("KB_GMAIL_TOKEN")
    return Path(override).expanduser() if override else kb_privacy.private_dir() / "gmail-token.json"


def gmail_credentials_path() -> Path:
    override = os.environ.get("KB_GMAIL_CREDENTIALS")
    return Path(override).expanduser() if override else kb_privacy.private_dir() / "gmail-credentials.json"


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(path, 0o600)


def build_gmail_service(token_path: str | os.PathLike[str] | None = None):
    """Official Gmail API client from a saved readonly token. NEVER opens a browser or prompts."""
    token = Path(token_path).expanduser() if token_path else gmail_token_path()
    if not token.is_file():
        raise GmailAuthError(f"Gmail is not authorized. {GMAIL_LOGIN_HINT}")
    try:
        info = json.loads(token.read_text(encoding="utf-8"))
        granted = set(info.get("scopes") or ([info["scope"]] if info.get("scope") else []))
    except (OSError, ValueError, AttributeError, KeyError, TypeError):
        raise GmailAuthError(f"Gmail token file is unreadable. {GMAIL_LOGIN_HINT}") from None
    if granted != set(GMAIL_SCOPES):
        raise GmailAuthError(f"Gmail token scope is not exactly gmail.readonly. {GMAIL_LOGIN_HINT}")
    try:
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise GmailError(f"Google client libraries are not installed in the ingest virtualenv ({type(exc).__name__}).") from None
    try:
        creds = Credentials.from_authorized_user_info(info, list(GMAIL_SCOPES))
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                _write_private(token, creds.to_json())
            else:
                raise GmailAuthError(f"Gmail authorization expired. {GMAIL_LOGIN_HINT}")
    except GmailAuthError:
        raise
    except RefreshError:
        raise GmailAuthError(f"Gmail authorization was revoked or expired. {GMAIL_LOGIN_HINT}") from None
    except Exception as exc:
        raise GmailError(f"Could not load Gmail credentials ({type(exc).__name__}).") from None
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def authorize_gmail_interactive(
    credentials_path: str | os.PathLike[str] | None = None,
    token_path: str | os.PathLike[str] | None = None,
) -> Path:
    """Explicit, user-run OAuth consent (browser). Scope: gmail.readonly only. Saves the token privately (0600)."""
    credentials = Path(credentials_path).expanduser() if credentials_path else gmail_credentials_path()
    token = Path(token_path).expanduser() if token_path else gmail_token_path()
    if not credentials.is_file():
        raise GmailAuthError(f"OAuth client file not found at {credentials}. Create a Desktop OAuth client in Google Cloud and save its JSON there.")
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise GmailError("google-auth-oauthlib is not installed in the ingest virtualenv.") from None
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials), list(GMAIL_SCOPES))
    creds = flow.run_local_server(port=0)
    _write_private(token, creds.to_json())
    return token


def classify_gmail_error(exc: BaseException) -> str:
    """auth | quota | server | notfound | other (duck-typed so google libraries are not imported)."""
    if type(exc).__name__ == "RefreshError":
        return "auth"
    if isinstance(exc, (TimeoutError, ConnectionError)) or type(exc).__name__ in ("timeout", "ServerNotFoundError", "ReadTimeout"):
        return "server"
    status = getattr(getattr(exc, "resp", None), "status", None)
    if status is None:
        status = getattr(exc, "status_code", None)
    if status is None:
        return "other"
    try:
        status = int(status)
    except (TypeError, ValueError):
        return "other"
    reasons: set[str] = set()
    content = getattr(exc, "content", b"")
    try:
        payload = json.loads(content.decode("utf-8") if isinstance(content, (bytes, bytearray)) else content or "{}")
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        if isinstance(error, dict):
            reasons.update(str(e.get("reason", "")) for e in error.get("errors", []) if isinstance(e, dict))
            if error.get("status"):
                reasons.add(str(error["status"]))
    except (ValueError, AttributeError):
        pass
    if status == 401:
        return "auth"
    if status == 429 or reasons & {"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded", "RESOURCE_EXHAUSTED", "dailyLimitExceeded"}:
        return "quota"
    if status == 403:
        return "auth"
    if status == 404:
        return "notfound"
    if status >= 500:
        return "server"
    return "other"


def _gmail_api_details(exc: BaseException) -> dict[str, Any]:
    """Whitelist status/reason/quota labels, never exception text or request URLs."""
    status = getattr(getattr(exc, "resp", None), "status", None)
    result = {"http_status": status if isinstance(status, int) else None}
    try:
        error = json.loads(getattr(exc, "content", b"{}")).get("error", {})
        result["reasons"] = [
            redact(str(row["reason"]))[:100] for row in error.get("errors", [])
            if isinstance(row, dict) and isinstance(row.get("reason"), str)
        ]
        message = str(error.get("message", ""))
        for field, pattern in (
            ("quota_metric", r"quota metric '([^']{1,120})'"),
            ("quota_limit", r"limit '([^']{1,120})'"),
        ):
            match = re.search(pattern, message)
            if match:
                result[field] = redact(match.group(1))
    except (ValueError, TypeError, AttributeError):
        pass
    return result


class _GmailPacer:
    """Spread method costs over time instead of bursting through a minute quota."""
    def __init__(self, sleep):
        self.sleep = sleep
        self.next_request = time.monotonic()

    def call(self, units, fn):
        delay = self.next_request - time.monotonic()
        if delay > 0:
            self.sleep(delay)
        self.next_request = max(self.next_request, time.monotonic()) + units / GMAIL_UNITS_PER_SECOND
        return fn()


def _gmail_call(fn: Callable[[], Any], sleep: Callable[[float], None]) -> Any:
    """Run one API request with bounded retries for quota/server errors. Never retried: auth, other."""
    for attempt in range(1, GMAIL_MAX_ATTEMPTS + 1):
        try:
            return fn()
        except Exception as exc:
            if isinstance(exc, ConnectorError):
                raise
            category = classify_gmail_error(exc)
            if category in ("quota", "server") and attempt < GMAIL_MAX_ATTEMPTS:
                if category == "quota":
                    # Minute quota cannot recover with only 1-2 seconds of delay.
                    delay = 60.0 * attempt
                    try:
                        delay = max(delay, min(300.0, float(exc.resp.get("retry-after", 0))))
                    except (AttributeError, TypeError, ValueError):
                        pass
                    sleep(delay)
                else:
                    sleep(min(2 ** (attempt - 1), 8))
                continue
            if category == "auth":
                raise GmailAuthError(f"Gmail rejected the credentials ({safe_error(exc)}). {GMAIL_LOGIN_HINT}") from None
            if category == "quota":
                details = _gmail_api_details(exc)
                failure = GmailQuotaError(f"Gmail rate/quota rejection after {attempt} attempts: {json.dumps(details)}")
                failure.api_details = details
                raise failure from None
            if category == "server":
                raise GmailServerError(f"Gmail server/network error persisted after {attempt} attempts ({safe_error(exc)}).") from None
            if category == "notfound":
                raise  # caller decides (thread deleted between list and get)
            raise GmailError(f"Gmail request failed ({safe_error(exc)}).") from None
    raise GmailError("Gmail request failed.")  # pragma: no cover


class _HTMLText(HTMLParser):
    BLOCK = {"p", "div", "br", "tr", "li", "ul", "ol", "table", "section", "article", "blockquote", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "pre"}
    SKIP = {"script", "style", "head", "title", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_to_text(html: str) -> str:
    parser = _HTMLText()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)
    text = "".join(parser.out).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _decode_b64(data: str, charset: str | None) -> str:
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    for enc in (charset, "utf-8"):
        if not enc:
            continue
        try:
            return raw.decode(enc, errors="replace")
        except LookupError:
            continue
    return raw.decode("utf-8", errors="replace")


def _headers(part: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for h in part.get("headers") or []:
        if isinstance(h, dict) and isinstance(h.get("name"), str):
            out.setdefault(h["name"].lower(), str(h.get("value") or ""))
    return out


def _decode_header_value(value: str) -> str:
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return value.strip()


def _charset(part: dict[str, Any]) -> str | None:
    match = re.search(r"charset=\"?([\w\-]+)", _headers(part).get("content-type", ""), re.IGNORECASE)
    return match.group(1) if match else None


def mime_text(part: dict[str, Any]) -> str:
    """Readable text of a Gmail MIME payload: text/plain preferred over its HTML twin inside
    multipart/alternative, HTML-only mail converted to text, attachments noted by name only."""
    mime = str(part.get("mimeType") or "").lower()
    children = part.get("parts") or []
    if mime.startswith("multipart/") or children:
        texts = [(str(c.get("mimeType") or "").lower(), mime_text(c)) for c in children if isinstance(c, dict)]
        if mime == "multipart/alternative":
            for child_mime, text in texts:
                if child_mime == "text/plain" and text.strip():
                    return text
            for _, text in texts:
                if text.strip():
                    return text
            return ""
        return "\n\n".join(text for _, text in texts if text.strip())
    filename = part.get("filename")
    if filename:
        return f"[attachment: {_decode_header_value(str(filename))}]"
    data = (part.get("body") or {}).get("data")
    if not data:
        return ""
    decoded = _decode_b64(data, _charset(part))
    if mime == "text/plain":
        return decoded.strip()
    if mime == "text/html":
        return html_to_text(decoded)
    return ""


def _message_datetime(message: dict[str, Any]) -> str | None:
    value = _headers(message.get("payload") or {}).get("date")
    if value:
        try:
            parsed = parsedate_to_datetime(value)
            if parsed is not None:
                return to_iso(parsed)
        except (TypeError, ValueError, IndexError):
            pass
    internal = message.get("internalDate")
    try:
        return to_iso(int(internal)) if internal is not None else None
    except (TypeError, ValueError):
        return None


def gmail_thread_url(thread_id: str) -> str:
    return f"https://mail.google.com/mail/u/0/#all/{thread_id}"


def build_thread_item(thread: dict[str, Any], window_start: datetime | None = None, fallback_ts: str | None = None) -> dict[str, Any]:
    """Turn a full Gmail thread resource into (title, text, ts, metadata); security mail messages are dropped."""
    thread_id = str(thread.get("id"))
    blocks: list[str] = []
    stamps: list[str] = []
    message_meta: list[dict[str, Any]] = []
    skipped_security = 0
    subject_first = None
    for message in thread.get("messages") or []:
        if not isinstance(message, dict):
            continue
        payload = message.get("payload") or {}
        headers = _headers(payload)
        subject = _decode_header_value(headers.get("subject", ""))
        body = mime_text(payload)
        if is_security_email(subject, body):
            skipped_security += 1
            continue
        stamp = _message_datetime(message)
        if stamp:
            stamps.append(stamp)
        if subject_first is None and subject:
            subject_first = subject
        header_lines = [f"From: {_decode_header_value(headers.get('from', ''))}"]
        for name in ("to", "cc"):
            if headers.get(name):
                header_lines.append(f"{name.capitalize()}: {_decode_header_value(headers[name])}")
        header_lines.append(f"Date: {stamp or headers.get('date', '')}")
        header_lines.append(f"Subject: {subject}")
        blocks.append("\n".join(header_lines) + "\n\n" + body.strip())
        message_meta.append({"id": message.get("id"), "date": stamp})
    older = 0
    if window_start is not None:
        older = sum(1 for m in message_meta if m["date"] and _parse_iso(m["date"]) < window_start)
    ts = max(stamps) if stamps else fallback_ts
    metadata = {
        "url": gmail_thread_url(thread_id),
        "pointer": gmail_thread_url(thread_id),
        "thread_id": thread_id,
        "subject": subject_first or "",
        "message_count": len(message_meta),
        "first_message_date": min(stamps) if stamps else None,
        "last_message_date": max(stamps) if stamps else None,
        "messages": message_meta,
        "window_start": to_iso(window_start) if window_start else None,
        "older_context_messages": older,
        "context_note": (
            f"{older} message(s) older than the discovery window are included because the thread matched it"
            if older else ""
        ),
    }
    return {
        "title": subject_first or "(no subject)",
        "text": "\n\n---\n\n".join(blocks),
        "ts": ts,
        "metadata": metadata,
        "skipped_security": skipped_security,
        "kept_messages": len(message_meta),
    }


def ingest_gmail(
    conn,
    service=None,
    *,
    now: datetime | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Read-only, rate-paced Gmail ingest; persist each page/item before advancing.

    A resumed run retains its original discovery window and start watermark.
    The watermark advances only after the entire window finishes; the next
    overlapping run catches mail arriving while a long backfill was running.
    """
    started = now or utcnow()
    now_iso = to_iso(started)
    counts: dict[str, Any] = {
        "pages": 0, "discovered": 0, "fetched": 0, "new": 0, "updated": 0, "unchanged": 0, "empty": 0,
        "skipped_security": 0, "vanished": 0, "pending_summaries": 0, "failed": 0, "window_start": None,
    }
    watermark = kb_store.get_state(conn, SOURCE_GMAIL, "watermark", None)
    checkpoint = kb_store.get_state(conn, SOURCE_GMAIL, "pending_run", None)
    limiter = _GmailPacer(sleep)
    try:
        if service is None:
            service = build_gmail_service()
        if checkpoint is None:
            window_start = (
                _parse_iso(to_iso(watermark)) - timedelta(days=GMAIL_OVERLAP_DAYS)
                if watermark and to_iso(watermark) else months_ago(started, GMAIL_FIRST_RUN_MONTHS)
            )
            checkpoint = {
                "started": now_iso, "window_start": to_iso(window_start),
                "page_token": None, "seen_tokens": [],
            }
            with kb_store.transaction(conn):
                kb_store.set_state(conn, SOURCE_GMAIL, "pending_run", checkpoint)
                kb_store.set_state(conn, SOURCE_GMAIL, "page_index", 0)
        else:
            window_start = _parse_iso(checkpoint["window_start"])
        counts["window_start"] = checkpoint["window_start"]
        query = f"after:{int(window_start.timestamp())}"

        while True:
            if "ids" not in checkpoint:
                request_args = {"userId": "me", "q": query, "maxResults": GMAIL_PAGE_SIZE}
                if checkpoint["page_token"]:
                    request_args["pageToken"] = checkpoint["page_token"]
                response = _gmail_call(
                    lambda: limiter.call(10, lambda: service.users().threads().list(**request_args).execute()), sleep
                )
                counts["pages"] += 1
                checkpoint["ids"] = list(dict.fromkeys(
                    str(item["id"]) for item in (response or {}).get("threads", [])
                    if isinstance(item, dict) and item.get("id")
                ))
                checkpoint["next_page_token"] = (response or {}).get("nextPageToken")
                with kb_store.transaction(conn):
                    kb_store.set_state(conn, SOURCE_GMAIL, "pending_run", checkpoint)
                    kb_store.set_state(conn, SOURCE_GMAIL, "page_index", 0)
            index = kb_store.get_state(conn, SOURCE_GMAIL, "page_index", 0)
            for position in range(index, len(checkpoint["ids"])):
                tid = checkpoint["ids"][position]
                done_key = f"pending_thread:{tid}"
                if kb_store.get_state(conn, SOURCE_GMAIL, done_key) == checkpoint["started"]:
                    kb_store.set_state(conn, SOURCE_GMAIL, "page_index", position + 1)
                    continue
                counts["discovered"] += 1
                thread = None
                try:
                    thread = _gmail_call(
                        lambda: limiter.call(120, lambda: service.users().threads().get(
                            userId="me", id=tid, format="full"
                        ).execute()), sleep
                    )
                except ConnectorError:
                    raise
                except Exception as exc:
                    if classify_gmail_error(exc) != "notfound":
                        raise
                    counts["vanished"] += 1
                with kb_store.transaction(conn):
                    if thread is not None:
                        counts["fetched"] += 1
                        item = build_thread_item(thread, window_start, fallback_ts=now_iso)
                        counts["skipped_security"] += item["skipped_security"]
                        if not item["kept_messages"] or not item["text"].strip():
                            if item["skipped_security"]:
                                purge_item(conn, SOURCE_GMAIL, tid)
                                _merge_skipped(conn, SOURCE_GMAIL, {tid: "security_email"})
                            else:
                                counts["empty"] += 1
                        else:
                            _merge_skipped(conn, SOURCE_GMAIL, {}, [tid])
                            outcome = store_item(
                                conn, SOURCE_GMAIL, tid, item["ts"], item["title"], item["text"], item["metadata"]
                            )
                            counts[outcome["status"]] += 1
                            if outcome["pending"]:
                                counts["pending_summaries"] += 1
                    kb_store.set_state(conn, SOURCE_GMAIL, done_key, checkpoint["started"])
                    kb_store.set_state(conn, SOURCE_GMAIL, "page_index", position + 1)
                # Safe progress remains inspectable without reading mail bodies.
                kb_store.set_state(conn, SOURCE_GMAIL, "last_counts", counts)
            next_token = checkpoint.get("next_page_token")
            if not next_token:
                break
            if next_token == checkpoint["page_token"] or next_token in checkpoint["seen_tokens"]:
                raise GmailError("Gmail pagination did not advance; stopping to avoid a loop.")
            checkpoint["seen_tokens"].append(next_token)
            checkpoint["page_token"] = next_token
            checkpoint.pop("ids", None)
            checkpoint.pop("next_page_token", None)
            with kb_store.transaction(conn):
                kb_store.set_state(conn, SOURCE_GMAIL, "pending_run", checkpoint)
                kb_store.set_state(conn, SOURCE_GMAIL, "page_index", 0)
        with kb_store.transaction(conn):
            kb_store.set_state(conn, SOURCE_GMAIL, "watermark", checkpoint["started"])
            kb_store.set_state(conn, SOURCE_GMAIL, "pending_run", None)
            conn.execute("DELETE FROM ingest_state WHERE source=? AND key LIKE 'pending_thread:%'", (SOURCE_GMAIL,))
            _finish_ok(conn, SOURCE_GMAIL, now_iso, counts)
    except ConnectorError as exc:
        _finish_error(conn, SOURCE_GMAIL, now_iso, exc.category, str(exc), counts)
        if getattr(exc, "api_details", None):
            record = kb_store.get_state(conn, SOURCE_GMAIL, "last_error")
            record["api"] = exc.api_details
            kb_store.set_state(conn, SOURCE_GMAIL, "last_error", record)
        exc.counts = counts
        raise
    except Exception as exc:
        message = safe_error(exc)
        _finish_error(conn, SOURCE_GMAIL, now_iso, "error", message, counts)
        raise GmailError(message, counts=counts) from None
    return counts


# --------------------------------------------------------------------------------------
# CLI: explicit interactive Gmail login only (ingest itself is driven by ingest_all.py)
# --------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["gmail-login"]:
        try:
            path = authorize_gmail_interactive()
        except ConnectorError as exc:
            print(f"gmail-login failed: {exc}", file=sys.stderr)
            return 1
        print(f"Gmail read-only token saved to {path} (owner-only). Scope: {GMAIL_SCOPES[0]}")
        return 0
    print("usage: connectors.py gmail-login   (interactive Google consent, gmail.readonly only)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
