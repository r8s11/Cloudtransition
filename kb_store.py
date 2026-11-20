"""Personal knowledge base storage and search (standard library only).

One SQLite file holds `docs` (every searchable row), `docs_fts` (FTS5 index
kept in sync by triggers) and `ingest_state` (per-source JSON watermarks).

Item identity is `(source, source_id)`.  An item is stored as one or more rows
(`raw`, `short`, `segment`, `atom`).  Items are always replaced as a whole and
atomically through `replace_rows`.

Reserved `ingest_state` keys read by `stats`/`search` freshness reporting:
  last_success  ISO timestamp string of the last fully successful run
  last_attempt  ISO timestamp string of the last run start (newer than
                last_success without last_error = interrupted/incomplete run)
  last_error    {} / None when the last run was fine, else a dict with
                "category"/"message"/"at" (truthy means the last run failed)
  skipped       {"count": n, ...} items deliberately not stored
"""

import contextlib
import itertools
import json
import math
import os
import re
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.realpath(__file__)))
DEFAULT_DB = ROOT / "kb.sqlite"

# Keep disk-backed SQLite spill files with the archive, not on a full system disk.
os.environ.setdefault("SQLITE_TMPDIR", str(ROOT))

SCHEMA_VERSION = 2
RAW_KIND = "raw"
SHORT_KIND = "short"
SUMMARY_KINDS = ("short", "segment", "atom")
PENDING_STATUSES = ("pending", "oversized", "failed")

RRF_K = 60
SUMMARY_WEIGHT = 1.0
RAW_WEIGHT = 0.5
RECENCY_BONUS = 0.1
RECENCY_DAYS = 180.0
SUPERSEDED_FACTOR = 0.5
STALE_HOURS = 12.0
CANDIDATES_PER_LIST = 500
MAX_TERMS = 24
MAX_LIMIT = 1000

_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TERM = re.compile(r"[^\W_]+", re.UNICODE)
_savepoints = itertools.count(1)

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS docs (
        id INTEGER PRIMARY KEY,
        kind TEXT NOT NULL,
        source TEXT NOT NULL,
        source_id TEXT NOT NULL,
        ts TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        content TEXT NOT NULL DEFAULT '',
        metadata TEXT NOT NULL DEFAULT '{}',
        superseded_by INTEGER REFERENCES docs(id) ON DELETE SET NULL
    )""",
    "CREATE INDEX IF NOT EXISTS docs_item ON docs(source, source_id)",
    "CREATE INDEX IF NOT EXISTS docs_ts ON docs(ts)",
    "CREATE INDEX IF NOT EXISTS docs_superseded ON docs(superseded_by) WHERE superseded_by IS NOT NULL",
    """CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
        title, content, content='docs', content_rowid='id',
        tokenize='porter unicode61'
    )""",
    """CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON docs BEGIN
        INSERT INTO docs_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
    END""",
    """CREATE TRIGGER IF NOT EXISTS docs_ad AFTER DELETE ON docs BEGIN
        INSERT INTO docs_fts(docs_fts, rowid, title, content) VALUES ('delete', old.id, old.title, old.content);
    END""",
    """CREATE TRIGGER IF NOT EXISTS docs_au AFTER UPDATE OF title, content ON docs BEGIN
        INSERT INTO docs_fts(docs_fts, rowid, title, content) VALUES ('delete', old.id, old.title, old.content);
        INSERT INTO docs_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
    END""",
    """CREATE TABLE IF NOT EXISTS ingest_state (
        source TEXT NOT NULL,
        key TEXT NOT NULL,
        watermark TEXT,
        PRIMARY KEY (source, key)
    )""",
)

# Exact header counts stay inside the same SQLite transaction as their docs.
# Avoid scanning large indexes from the USB volume on every search.
_HEADER_COUNTS_SCHEMA = (
    """CREATE TABLE source_counts (
        source TEXT PRIMARY KEY,
        rows INTEGER NOT NULL CHECK(rows >= 0),
        items INTEGER NOT NULL CHECK(items >= 0)
    ) WITHOUT ROWID""",
    """INSERT INTO source_counts(source, rows, items)
       SELECT source, COUNT(*), COUNT(DISTINCT source_id) FROM docs GROUP BY source""",
    """CREATE TRIGGER docs_counts_insert AFTER INSERT ON docs BEGIN
        INSERT INTO source_counts(source, rows, items)
        VALUES(new.source, 1, NOT EXISTS(
            SELECT 1 FROM docs WHERE source=new.source AND source_id=new.source_id AND id<>new.id
        )) ON CONFLICT(source) DO UPDATE SET rows=rows+1, items=items+excluded.items;
    END""",
    """CREATE TRIGGER docs_counts_delete AFTER DELETE ON docs BEGIN
        UPDATE source_counts SET rows=rows-1, items=items-NOT EXISTS(
            SELECT 1 FROM docs WHERE source=old.source AND source_id=old.source_id
        ) WHERE source=old.source;
        DELETE FROM source_counts WHERE source=old.source AND rows=0;
    END""",
    """CREATE TRIGGER docs_counts_move AFTER UPDATE OF source,source_id ON docs
       WHEN old.source<>new.source OR old.source_id<>new.source_id BEGIN
        UPDATE source_counts SET rows=rows-1, items=items-NOT EXISTS(
            SELECT 1 FROM docs WHERE source=old.source AND source_id=old.source_id
        ) WHERE source=old.source;
        DELETE FROM source_counts WHERE source=old.source AND rows=0;
        INSERT INTO source_counts(source, rows, items)
        VALUES(new.source, 1, NOT EXISTS(
            SELECT 1 FROM docs WHERE source=new.source AND source_id=new.source_id AND id<>new.id
        )) ON CONFLICT(source) DO UPDATE SET rows=rows+1, items=items+excluded.items;
    END""",
)

# The superseded set is normally empty. Without the hint SQLite (no ANALYZE statistics) walks docs_item
# and probes every content row, which reads the whole multi-hundred-MB docs table on each search/stats.
_SUPERSEDED_ITEMS_SQL = (
    "SELECT DISTINCT source, source_id FROM docs INDEXED BY docs_superseded WHERE superseded_by IS NOT NULL"
)


# --------------------------------------------------------------------------- time


def _utcnow():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(value):
    """Parse an ISO date or datetime into an aware UTC datetime (naive = UTC)."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("ts must be a non-empty ISO date or datetime string")
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(f"ts is not an ISO date/datetime: {value!r}") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_day(value):
    """Validate a strict YYYY-MM-DD string; returns the string."""
    if not isinstance(value, str) or not _DAY.match(value):
        raise ValueError(f"expected a date as YYYY-MM-DD, got {value!r}")
    try:
        date(int(value[:4]), int(value[5:7]), int(value[8:10]))
    except ValueError:
        raise ValueError(f"not a real calendar date: {value!r}") from None
    return value


# ----------------------------------------------------------------------- connect


def _secure(path):
    """Owner-only permissions for the DB and its WAL/SHM sidecars."""
    for suffix in ("", "-wal", "-shm"):
        p = path + suffix
        try:
            if os.stat(p).st_mode & 0o077:
                os.chmod(p, 0o600)
        except FileNotFoundError:
            pass


def _init_schema(conn):
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise sqlite3.DatabaseError(f"database schema {version} is newer than this code")
    if version == SCHEMA_VERSION:
        return
    with transaction(conn):
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise sqlite3.DatabaseError(f"database schema {version} is newer than this code")
        if version < 1:
            for statement in _SCHEMA:
                conn.execute(statement)
        if version < 2:
            for statement in _HEADER_COUNTS_SCHEMA:
                conn.execute(statement)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def connect(path=None, *, create=True):
    """Open (and initialise) the KB database.

    Default path is `kb.sqlite` in the workspace root, independent of cwd.
    The connection is autocommit (`isolation_level=None`) with Row factory,
    WAL journaling and foreign keys.  `create=False` raises FileNotFoundError
    rather than creating a missing database.
    """
    target = os.path.abspath(os.fspath(path)) if path is not None else str(DEFAULT_DB)
    memory = target.endswith(":memory:")
    if not memory and not os.path.exists(target):
        if not create:
            raise FileNotFoundError(f"knowledge base not found: {target}")
        os.close(os.open(target, os.O_RDWR | os.O_CREAT, 0o600))
    if not memory:
        _secure(target)
    conn = sqlite3.connect(":memory:" if memory else target, timeout=30, isolation_level=None)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA foreign_keys = ON")
        if not memory:
            if conn.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
                conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        _init_schema(conn)
    except BaseException:
        conn.close()
        raise
    if not memory:
        _secure(target)
    return conn


@contextlib.contextmanager
def transaction(conn):
    """Re-entrant write transaction: BEGIN IMMEDIATE, or a SAVEPOINT when nested."""
    if conn.in_transaction:
        name = f"kb_sp_{next(_savepoints)}"
        conn.execute(f"SAVEPOINT {name}")
        try:
            yield conn
        except BaseException:
            conn.execute(f"ROLLBACK TO {name}")
            conn.execute(f"RELEASE {name}")
            raise
        conn.execute(f"RELEASE {name}")
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


# ------------------------------------------------------------------------- state


def get_state(conn, source, key, default=None):
    row = conn.execute(
        "SELECT watermark FROM ingest_state WHERE source = ? AND key = ?", (source, key)
    ).fetchone()
    if row is None or row[0] is None:
        return default
    try:
        return json.loads(row[0])
    except ValueError:
        return default


def set_state(conn, source, key, value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True)
    conn.execute(
        "INSERT INTO ingest_state(source, key, watermark) VALUES (?, ?, ?) "
        "ON CONFLICT(source, key) DO UPDATE SET watermark = excluded.watermark",
        (source, key, payload),
    )


# ---------------------------------------------------------------------- replace


def _prepare(row):
    if not isinstance(row, dict):
        raise TypeError("each row must be a dict")
    kind, title, content, metadata = row.get("kind"), row.get("title", ""), row.get("content", ""), row.get("metadata", {})
    if not isinstance(kind, str) or not kind:
        raise ValueError("row kind must be a non-empty string")
    if not isinstance(title, str) or not isinstance(content, str):
        raise TypeError("row title and content must be strings")
    if not isinstance(metadata, dict):
        raise TypeError("row metadata must be a dict")
    parse_ts(row.get("ts"))
    return (kind, row["ts"], title, content, json.dumps(metadata, ensure_ascii=False, sort_keys=True))


def replace_rows(conn, source, source_id, rows):
    """Atomically replace every row of item (source, source_id) with `rows`.

    Rows are dicts with kind/ts/title/content/metadata(dict).  An empty list
    deletes the item.  Validation happens before any write.  `superseded_by`
    stays coherent: rows of other items that pointed at this item's old rows are
    re-pointed at the matching new row (same kind and position, else first row of
    the kind, else first row), or cleared when the item is deleted; a superseded
    item stays superseded after being refreshed.  Returns
    {"deleted": n, "inserted": m}.
    """
    if not isinstance(source, str) or not source or not isinstance(source_id, str) or not source_id:
        raise ValueError("source and source_id must be non-empty strings")
    prepared = [_prepare(r) for r in rows]
    with transaction(conn):
        old = conn.execute(
            "SELECT id, kind, superseded_by FROM docs WHERE source = ? AND source_id = ? ORDER BY id",
            (source, source_id),
        ).fetchall()
        old_ids = {r["id"] for r in old}
        inbound = conn.execute(
            "SELECT c.id AS child, c.superseded_by AS target FROM docs c "
            "JOIN docs t ON t.id = c.superseded_by "
            "WHERE t.source = ? AND t.source_id = ? AND NOT (c.source = ? AND c.source_id = ?)",
            (source, source_id, source, source_id),
        ).fetchall()
        outgoing = next(
            (r["superseded_by"] for r in old if r["superseded_by"] is not None and r["superseded_by"] not in old_ids),
            None,
        )
        conn.execute("DELETE FROM docs WHERE source = ? AND source_id = ?", (source, source_id))
        new_ids = []
        for kind, ts, title, content, metadata in prepared:
            cur = conn.execute(
                "INSERT INTO docs(kind, source, source_id, ts, title, content, metadata, superseded_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (kind, source, source_id, ts, title, content, metadata, outgoing),
            )
            new_ids.append((cur.lastrowid, kind))
        if inbound and new_ids:
            by_kind = {}
            for rid, kind in new_ids:
                by_kind.setdefault(kind, []).append(rid)
            position = {}
            for r in old:
                position[r["id"]] = (r["kind"], sum(1 for p in position.values() if p[0] == r["kind"]))
            for r in inbound:
                kind, index = position.get(r["target"], (None, 0))
                pool = by_kind.get(kind)
                target = pool[index] if pool and index < len(pool) else (pool[0] if pool else new_ids[0][0])
                conn.execute("UPDATE docs SET superseded_by = ? WHERE id = ?", (target, r["child"]))
    return {"deleted": len(old), "inserted": len(prepared)}


# -------------------------------------------------------------------- freshness


def _as_dt(value):
    try:
        return parse_ts(value)
    except (ValueError, TypeError):
        return None


def _error_text(value):
    if isinstance(value, dict):
        if not value:
            return None
        return str(value.get("category") or value.get("type") or value.get("message") or "error")[:120]
    return str(value)[:120] if value else None


def freshness(conn, now=None):
    """Per-source freshness plus the overall last successful ingest time."""
    now = now or _utcnow()
    names = {r[0] for r in conn.execute("SELECT source FROM source_counts")}
    names |= {
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT source FROM ingest_state WHERE key IN ('last_success', 'last_error', 'last_attempt')"
        )
    }
    sources = {}
    best = None
    for name in sorted(names):
        success = get_state(conn, name, "last_success")
        success_dt = _as_dt(success)
        attempt_dt = _as_dt(get_state(conn, name, "last_attempt"))
        error = _error_text(get_state(conn, name, "last_error"))
        age = (now - success_dt).total_seconds() / 3600 if success_dt else None
        if error:
            status = "failed"
        elif attempt_dt and (success_dt is None or attempt_dt > success_dt):
            status = "incomplete"
        elif success_dt is None:
            status = "never"
        elif age > STALE_HOURS:
            status = "stale"
        else:
            status = "fresh"
        sources[name] = {
            "status": status,
            "last_success": _iso(success_dt) if success_dt else None,
            "last_attempt": _iso(attempt_dt) if attempt_dt else None,
            "age_hours": round(age, 2) if age is not None else None,
            "last_error": error,
        }
        if success_dt and (best is None or success_dt > best):
            best = success_dt
    age = (now - best).total_seconds() / 3600 if best else None
    return {
        "last_ingest": _iso(best) if best else None,
        "last_ingest_age_hours": round(age, 2) if age is not None else None,
        "stale": age is None or age > STALE_HOURS or any(s["status"] != "fresh" for s in sources.values()),
        "stale_hours": STALE_HOURS,
        "sources": sources,
    }


# ------------------------------------------------------------------------ stats


def _count_state(value):
    if isinstance(value, dict):
        value = value.get("count")
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def stats(conn, now=None):
    """JSON-compatible overview: rows vs items, per source/kind, coverage, pending, freshness."""
    fresh = freshness(conn, now)
    rows = conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
    items = conn.execute("SELECT COUNT(*) FROM (SELECT DISTINCT source, source_id FROM docs)").fetchone()[0]
    by_source = {name: {"items": 0, "rows": 0, "kinds": {}, "first_ts": None, "last_ts": None} for name in fresh["sources"]}
    by_kind = {}
    for r in conn.execute("SELECT source, kind, COUNT(*) n, MIN(ts) lo, MAX(ts) hi FROM docs GROUP BY source, kind"):
        s = by_source.setdefault(r["source"], {"items": 0, "rows": 0, "kinds": {}, "first_ts": None, "last_ts": None})
        s["kinds"][r["kind"]] = r["n"]
        s["rows"] += r["n"]
        s["first_ts"] = r["lo"] if s["first_ts"] is None else min(s["first_ts"], r["lo"])
        s["last_ts"] = r["hi"] if s["last_ts"] is None else max(s["last_ts"], r["hi"])
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + r["n"]
    for r in conn.execute("SELECT source, COUNT(*) n FROM (SELECT DISTINCT source, source_id FROM docs) GROUP BY source"):
        by_source[r["source"]]["items"] = r["n"]
    placeholders = ",".join("?" * len(PENDING_STATUSES))
    pending = {
        r["source"]: r["n"]
        for r in conn.execute(
            "SELECT source, COUNT(*) n FROM (SELECT DISTINCT source, source_id FROM docs "
            f"WHERE kind = 'raw' AND json_extract(metadata, '$.summary_status') IN ({placeholders})) GROUP BY source",
            PENDING_STATUSES,
        )
    }
    superseded = conn.execute(f"SELECT COUNT(*) FROM ({_SUPERSEDED_ITEMS_SQL})").fetchone()[0]
    skipped_total = 0
    for name, s in by_source.items():
        s["pending_summaries"] = pending.get(name, 0)
        s["skipped"] = _count_state(get_state(conn, name, "skipped"))
        s.update(fresh["sources"].get(name, {"status": "never", "last_success": None, "age_hours": None, "last_error": None}))
        skipped_total += s["skipped"]
    return {
        "rows": rows,
        "items": items,
        "by_kind": by_kind,
        "by_source": by_source,
        "pending_summaries": sum(pending.values()),
        "skipped": skipped_total,
        "superseded_items": superseded,
        "last_ingest": fresh["last_ingest"],
        "last_ingest_age_hours": fresh["last_ingest_age_hours"],
        "stale": fresh["stale"],
        "stale_hours": STALE_HOURS,
    }


# ----------------------------------------------------------------------- search


def match_terms(query):
    """Distinct lowercase word tokens of `query` (at most MAX_TERMS)."""
    seen = []
    for token in _TERM.findall(query or ""):
        token = token.lower()
        if token not in seen:
            seen.append(token)
        if len(seen) >= MAX_TERMS:
            break
    return seen


def fts_query(terms):
    """OR of quoted terms; tokens are alphanumeric only, so no FTS syntax survives."""
    return " OR ".join(f'"{t}"' for t in terms)


def _ranked(conn, match, raw, after, source):
    clauses = ["docs_fts MATCH :match", "d.kind = 'raw'" if raw else "d.kind != 'raw'"]
    params = {"match": match, "cap": CANDIDATES_PER_LIST}
    if after is not None:
        clauses.append("d.ts >= :after")
        params["after"] = after
    if source is not None:
        clauses.append("d.source = :source")
        params["source"] = source
    sql = f"""
        WITH hits AS MATERIALIZED (
            SELECT d.id AS id, d.source AS source, d.source_id AS source_id, bm25(docs_fts) AS s
            FROM docs_fts JOIN docs d ON d.id = docs_fts.rowid
            WHERE {' AND '.join(clauses)}
        ), best AS (
            SELECT id, source, source_id, s,
                   ROW_NUMBER() OVER (PARTITION BY source, source_id ORDER BY s, id) AS rn
            FROM hits
        )
        SELECT id, source, source_id, s FROM best WHERE rn = 1
        ORDER BY s, source, source_id LIMIT :cap"""
    return [(r["source"], r["source_id"], r["id"], r["s"]) for r in conn.execute(sql, params)]


def item_score(summary_rank, raw_rank, age_days, superseded):
    """Weighted RRF (k=60) x recency multiplier, halved when superseded."""
    score = 0.0
    if summary_rank is not None:
        score += SUMMARY_WEIGHT / (RRF_K + summary_rank)
    if raw_rank is not None:
        score += RAW_WEIGHT / (RRF_K + raw_rank)
    score *= 1 + RECENCY_BONUS * math.exp(-max(0.0, age_days) / RECENCY_DAYS)
    return score * SUPERSEDED_FACTOR if superseded else score


def _header(conn, now):
    fresh = freshness(conn, now)
    counts = conn.execute("SELECT COALESCE(SUM(rows),0),COALESCE(SUM(items),0) FROM source_counts").fetchone()
    return {
        "rows": counts[0],
        "items": counts[1],
        **fresh,
    }


def search(conn, query, after=None, source=None, limit=10, now=None):
    """Keyword search: two bm25 passes (summaries / raw), weighted RRF, recency, superseded.

    Returns {"query","terms","after","source","limit","header","results"}; each
    result has rank, id, source, source_id, kind, ts, title, snippet, pointer,
    metadata, score, superseded and lists ({"summary": rank|None, "raw": rank|None}).
    Items are collapsed per (source, source_id) in each list before fusion; ties
    break on (source, source_id).  `now` (aware datetime) is for deterministic tests.
    """
    if after is not None:
        after = parse_day(after)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be an integer from 1 to {MAX_LIMIT}")
    if source is not None and not isinstance(source, str):
        raise ValueError("source must be a string")
    now = now or _utcnow()
    terms = match_terms(query)
    out = {
        "query": query,
        "terms": terms,
        "after": after,
        "source": source,
        "limit": limit,
        "header": _header(conn, now),
        "results": [],
    }
    if not terms:
        return out
    match = fts_query(terms)
    lists = {
        "summary": _ranked(conn, match, False, after, source),
        "raw": _ranked(conn, match, True, after, source),
    }
    ranks = {}
    evidence = {}
    for name, hits in lists.items():
        for rank, (src, sid, rowid, s) in enumerate(hits, 1):
            key = (src, sid)
            ranks.setdefault(key, {"summary": None, "raw": None})[name] = rank
            if key not in evidence or s < evidence[key][1]:
                evidence[key] = (rowid, s)
    if not ranks:
        return out
    superseded = {(r["source"], r["source_id"]) for r in conn.execute(_SUPERSEDED_ITEMS_SQL)}
    scored = []
    for key, r in ranks.items():
        ts = conn.execute("SELECT ts FROM docs WHERE id = ?", (evidence[key][0],)).fetchone()[0]
        age = (now - parse_ts(ts)).total_seconds() / 86400
        scored.append((-item_score(r["summary"], r["raw"], age, key in superseded), key[0], key[1], key))
    scored.sort()
    for position, (neg, _, _, key) in enumerate(scored[:limit], 1):
        rowid = evidence[key][0]
        row = conn.execute(
            "SELECT id, kind, source, source_id, ts, title, content, metadata FROM docs WHERE id = ?", (rowid,)
        ).fetchone()
        snip = conn.execute(
            "SELECT snippet(docs_fts, -1, '[', ']', ' ... ', 24) FROM docs_fts WHERE docs_fts MATCH ? AND rowid = ?",
            (match, rowid),
        ).fetchone()
        try:
            metadata = json.loads(row["metadata"])
        except ValueError:
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        out["results"].append(
            {
                "rank": position,
                "id": row["id"],
                "source": row["source"],
                "source_id": row["source_id"],
                "kind": row["kind"],
                "ts": row["ts"],
                "title": row["title"],
                "snippet": (snip[0] if snip and snip[0] else row["content"][:200]),
                "pointer": metadata.get("url") or metadata.get("path"),
                "metadata": metadata,
                "score": -neg,
                "superseded": key in superseded,
                "lists": ranks[key],
            }
        )
    return out
