#!/usr/bin/env python3
"""ARMS routines: read-only routine inventory, session usage, repeated-job suggestions, passive checks.

Standard library only. Makes no network or model calls: every run costs
0 API tokens and 0 API dollars. It only reads local files and runs three
read-only subprocess families with fixed argument lists (launchctl list,
crontab -l, git ls-files) and, for compressed Codex logs on Pythons older than
3.14, `zstd -dc`.

Report (JSON, exactly four top-level keys): inventory, usage, suggestions, checks.
Default run writes <root>/tools/arms/data/routines.json.

    python3 tools/arms/routines.py                 # same as `run`
    python3 tools/arms/routines.py run --stdout
    python3 tools/arms/routines.py schedule        # print the weekly launchd plist
    python3 tools/arms/routines.py schedule --write

Raw prompts, assistant text and credential values are never emitted: only
counts, fixed taxonomy labels, session ids, dates and path:line locations.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import hmac
import io
import json
import os
import plistlib
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote

SCHEMA_VERSION = 1
LABEL = "com.cloudtransition.arms-routines"
WINDOW_DAYS = 30
SUGGEST_DAYS = 7
THRESHOLD = 3
COLD_MINUTES = 60
ROUTER_FILES = ["CLAUDE.md", "OPERATIONS.md", "CODE.md", "MONEY.md", "LEARNING.md", "HEALTH.md"]
STATE_FILES = ["TASKS.md", "DASHBOARD.md", "routine.md"]
SCRIPT = Path(__file__).resolve()
DEFAULT_ROOT = SCRIPT.parents[2]

# ----------------------------------------------------------------- helpers

CRED_PATTERNS = [
    ("openai-style-key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}")),
    ("aws-access-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghs|ghu|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{30,}")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("private-key-block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----")),
]
GENERIC_CRED = re.compile(
    r"""(?i)\b(?:api[_-]?key|secret|token|passw(?:or)?d)\b["']?\s*[:=]\s*["'][^"'\s]{16,}["']"""
)
REDACT_RE = re.compile("|".join(p.pattern for _, p in CRED_PATTERNS))


def now_local(override=None):
    if override:
        return parse_ts(override)
    return dt.datetime.now().astimezone()


def parse_ts(value):
    """ISO string / epoch seconds / epoch millis -> aware local datetime, or None."""
    try:
        if isinstance(value, (int, float)):
            v = float(value)
            if v > 1e11:
                v /= 1000.0
            return dt.datetime.fromtimestamp(v).astimezone()
        if not isinstance(value, str) or not value:
            return None
        s = value.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        s = re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", s)
        d = dt.datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d.astimezone()
    except (ValueError, OverflowError, OSError):
        return None


def iso(d):
    return d.isoformat(timespec="seconds") if d else None


def norm(p):
    return os.path.normpath(str(p))


def in_root(cwd, roots):
    if not isinstance(cwd, str) or not cwd:
        return False
    c = norm(cwd)
    return any(c == r or c.startswith(r + os.sep) for r in roots)


def root_variants(root):
    out = {norm(root)}
    with contextlib.suppress(OSError):
        out.add(norm(Path(root).resolve()))
    return sorted(out)


def run_fixed(args, timeout=15):
    """Run a fixed argument list (never a shell). Returns (rc, stdout) or (None, '')."""
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return p.returncode, p.stdout
    except (OSError, subprocess.SubprocessError):
        return None, ""


def read_text(path, limit=262144):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return None


def short(path, home, root):
    s = str(path)
    h = str(home)
    r = str(root)
    if s.startswith(r + os.sep):
        return "<root>/" + s[len(r) + 1:]
    if s.startswith(h + os.sep):
        return "~/" + s[len(h) + 1:]
    return s


# ------------------------------------------------------------ session parse


class Session:
    def __init__(self, tool, sid):
        self.tool = tool
        self.id = sid
        self.events = []  # (ts, input_uncached, output, cache_read, cache_creation)
        self.prompts = []  # (ts, text) - held in memory only, never emitted
        self.messages = 0
        self.skills = Counter()
        self.days = set()
        self.first = None
        self.last = None

    def touch(self, ts):
        self.days.add(ts.date().isoformat())
        if self.first is None or ts < self.first:
            self.first = ts
        if self.last is None or ts > self.last:
            self.last = ts

    @property
    def key(self):
        return "%s:%s" % (self.tool, self.id)


def _text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") in ("text", "input_text") and isinstance(b.get("text"), str):
                parts.append(b["text"])
        return "\n".join(parts)
    return ""


def parse_claude_file(path, roots, since, until):
    s = Session("claude", path.stem)
    msgs = {}
    skill_calls = {}
    inside = None
    try:
        fh = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return None, "unreadable"
    with fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            if inside is None and d.get("cwd"):
                inside = in_root(d["cwd"], roots)
                if not inside:
                    return None, "other-project"
            if d.get("sessionId"):
                s.id = d["sessionId"]
            ts = parse_ts(d.get("timestamp"))
            if ts is None or ts < since or ts > until:
                continue
            kind = d.get("type")
            m = d.get("message") if isinstance(d.get("message"), dict) else {}
            if kind == "assistant":
                s.touch(ts)
                u = m.get("usage") if isinstance(m.get("usage"), dict) else None
                mid = m.get("id") or d.get("uuid") or str(len(msgs))
                if u is not None:
                    msgs[mid] = (
                        ts,
                        int(u.get("input_tokens") or 0),
                        int(u.get("output_tokens") or 0),
                        int(u.get("cache_read_input_tokens") or 0),
                        int(u.get("cache_creation_input_tokens") or 0),
                    )
                else:
                    msgs.setdefault(mid, None)
                content = m.get("content")
                if isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Skill":
                            inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                            if isinstance(inp.get("skill"), str):
                                skill_calls[b.get("id") or len(skill_calls)] = inp["skill"][:80]
            elif kind == "user" and not d.get("isMeta"):
                content = m.get("content")
                if isinstance(content, list) and any(
                    isinstance(b, dict) and b.get("type") == "tool_result" for b in content
                ):
                    continue
                text = _text_of(content).strip()
                if not text or text.startswith("<"):
                    continue
                s.touch(ts)
                s.messages += 1
                s.prompts.append((ts, text))
    if inside is not True:
        return None, "no-cwd" if inside is None else "other-project"
    s.messages += len(msgs)
    s.events = sorted((v for v in msgs.values() if v), key=lambda e: e[0])
    s.skills = Counter(skill_calls.values())
    if not s.days:
        return None, "outside-window"
    return s, "ok"


@contextlib.contextmanager
def open_text(path):
    if path.suffix != ".zst":
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            yield fh
        return
    try:
        from compression import zstd  # Python 3.14+
    except ImportError:
        zstd = None
    if zstd is not None:
        with zstd.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            yield fh
        return
    proc = subprocess.Popen(["zstd", "-dc", "-q", str(path)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        yield io.TextIOWrapper(proc.stdout, encoding="utf-8", errors="replace")
    finally:
        proc.kill()
        proc.wait()


SKILL_PATH_RE = re.compile(r"/skills/([A-Za-z0-9_.\-]{1,80})/SKILL\.md")
CODEX_SKIP_PREFIXES = ("<", "# AGENTS.md instructions", "# Context from my IDE")


def codex_meta(path):
    try:
        with open_text(path) as fh:
            first = fh.readline()
        d = json.loads(first)
        p = d.get("payload") if isinstance(d, dict) else None
        if isinstance(p, dict) and d.get("type") == "session_meta":
            return p
    except (OSError, ValueError, ImportError, EOFError, RuntimeError):
        pass
    return None


def parse_codex_file(path, since, until):
    s = Session("codex", path.stem)
    prev = None
    try:
        with open_text(path) as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(d, dict):
                    continue
                p = d.get("payload") if isinstance(d.get("payload"), dict) else {}
                if d.get("type") == "session_meta" and p.get("id"):
                    s.id = p["id"]
                    continue
                ts = parse_ts(d.get("timestamp"))
                if ts is None:
                    continue
                kind, ptype = d.get("type"), p.get("type")
                if kind == "event_msg" and ptype == "token_count":
                    info = p.get("info") if isinstance(p.get("info"), dict) else None
                    tot = info.get("total_token_usage") if info and isinstance(info.get("total_token_usage"), dict) else None
                    if tot is None:
                        continue
                    cur = (
                        int(tot.get("input_tokens") or 0),
                        int(tot.get("cached_input_tokens") or 0),
                        int(tot.get("output_tokens") or 0),
                        int(tot.get("cache_write_input_tokens") or 0),
                    )
                    if prev is None:
                        delta = cur
                    elif any(c < q for c, q in zip(cur, prev)):
                        delta = cur  # counter reset
                    else:
                        delta = tuple(c - q for c, q in zip(cur, prev))
                    prev = cur
                    if since <= ts <= until and any(delta):
                        s.touch(ts)
                        inp, cached, out, cw = delta
                        s.events.append((ts, max(inp - cached, 0), out, cached, cw))
                    continue
                if ts < since or ts > until:
                    continue
                if kind == "response_item" and ptype == "message":
                    role = p.get("role")
                    if role == "user":
                        text = _text_of(p.get("content")).strip()
                        if text and not text.startswith(CODEX_SKIP_PREFIXES):
                            s.touch(ts)
                            s.messages += 1
                            s.prompts.append((ts, text))
                    elif role == "assistant":
                        s.touch(ts)
                        s.messages += 1
                elif kind == "response_item" and ptype in ("function_call", "custom_tool_call"):
                    blob = p.get("arguments") if isinstance(p.get("arguments"), str) else p.get("input")
                    if isinstance(blob, str):
                        for name in set(SKILL_PATH_RE.findall(blob)):
                            s.skills[name] += 1
    except (OSError, ImportError, EOFError, RuntimeError):
        return None
    return s if s.days else None


FILE_DATE_RE = re.compile(r"rollout-(\d{4})-(\d{2})-(\d{2})T")


def collect_sessions(home, roots, since, until):
    """Return (sessions, sources). Only project dirs/date dirs inside the window are touched."""
    sessions = []
    sources = []

    # ---- Claude transcripts: ~/.claude/projects/<encoded root>*
    cproj = home / ".claude" / "projects"
    src = {"id": "claude-transcripts", "tool": "claude", "available": cproj.is_dir(),
           "sessions": None, "reason": None, "files_scanned": 0, "dirs_matched": 0}
    if not cproj.is_dir():
        src["reason"] = "~/.claude/projects not found"
    else:
        n = 0
        enc = {re.sub(r"[^A-Za-z0-9]", "-", r) for r in roots}
        try:
            dirs = [d for d in cproj.iterdir() if d.is_dir() and any(d.name == e or d.name.startswith(e + "-") for e in enc)]
        except OSError:
            dirs = []
        src["dirs_matched"] = len(dirs)
        cutoff = since.timestamp()
        for d in dirs:
            for f in sorted(d.glob("*.jsonl")):
                try:
                    if f.stat().st_mtime < cutoff:
                        continue
                except OSError:
                    continue
                src["files_scanned"] += 1
                sess, why = parse_claude_file(f, roots, since, until)
                if sess:
                    sessions.append(sess)
                    n += 1
        src["sessions"] = n
        if not dirs:
            src["reason"] = "no Claude project directory exists for this root (no retained transcripts)"
    sources.append(src)

    # ---- Claude history index (counts only; prompt text never read)
    hist = home / ".claude" / "history.jsonl"
    hs = {"id": "claude-history", "tool": "claude", "available": hist.is_file(), "sessions": None,
          "reason": None}
    if hist.is_file():
        ids = set()
        try:
            with open(hist, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(d, dict) or not in_root(d.get("project"), roots):
                        continue
                    ts = parse_ts(d.get("timestamp"))
                    if ts and since <= ts <= until and d.get("sessionId"):
                        ids.add(d["sessionId"])
        except OSError:
            hs["reason"] = "unreadable"
        have = {s.id for s in sessions if s.tool == "claude"}
        hs["sessions"] = len(ids)
        hs["history_only_sessions"] = len(ids - have)
        hs["reason"] = hs["reason"] or "session ids/timestamps only; prompt text is not read; history has no token data"
    else:
        hs["reason"] = "~/.claude/history.jsonl not found"
    sources.append(hs)

    # ---- Codex rollout files (sessions/YYYY/MM/DD + archived_sessions), date-bounded
    cdx = home / ".codex"
    cs = {"id": "codex-sessions", "tool": "codex", "available": (cdx / "sessions").is_dir() or (cdx / "archived_sessions").is_dir(),
          "sessions": None, "reason": None, "files_considered": 0, "window_sessions_other_projects": 0,
          "unreadable": 0}
    if not cs["available"]:
        cs["reason"] = "~/.codex/sessions not found"
    else:
        floor = (since - dt.timedelta(days=3)).date()
        cands = []
        base = cdx / "sessions"
        day = floor
        while day <= until.date():
            dd = base / ("%04d" % day.year) / ("%02d" % day.month) / ("%02d" % day.day)
            if dd.is_dir():
                cands.extend(sorted(dd.glob("rollout-*.jsonl*")))
            day += dt.timedelta(days=1)
        arch = cdx / "archived_sessions"
        if arch.is_dir():
            for f in sorted(arch.glob("rollout-*.jsonl*")):
                m = FILE_DATE_RE.match(f.name)
                if m and floor <= dt.date(int(m[1]), int(m[2]), int(m[3])) <= until.date():
                    cands.append(f)
        seen = set()
        n = 0
        for f in cands:
            cs["files_considered"] += 1
            meta = codex_meta(f)
            if meta is None:
                cs["unreadable"] += 1
                continue
            sid = meta.get("id") or f.name
            if sid in seen:
                continue
            seen.add(sid)
            if not in_root(meta.get("cwd"), roots):
                cs["window_sessions_other_projects"] += 1
                continue
            sess = parse_codex_file(f, since, until)
            if sess:
                sessions.append(sess)
                n += 1
        cs["sessions"] = n
        if n == 0:
            cs["reason"] = "no Codex session for this root in the window (other projects excluded by cwd)"
    sources.append(cs)
    return sessions, sources


# -------------------------------------------------------------- usage block


def tally(events):
    t = {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_creation_tokens": 0}
    for _, i, o, cr, cc in events:
        t["input_tokens"] += i
        t["output_tokens"] += o
        t["cache_read_tokens"] += cr
        t["cache_creation_tokens"] += cc
    return t


RATE_KEYS = {"input": "input_tokens", "output": "output_tokens", "cache_read": "cache_read_tokens",
             "cache_write": "cache_creation_tokens"}


def load_rates(path):
    if not path:
        return None
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for tool, spec in d.items():
        if tool not in ("claude", "codex") or not isinstance(spec, dict):
            continue
        per = spec.get("per_million_tokens", {})
        if not all(isinstance(per.get(k), (int, float)) for k in RATE_KEYS):
            raise SystemExit("rates file: %s needs numeric per_million_tokens for %s" % (tool, ", ".join(RATE_KEYS)))
        out[tool] = {"currency": spec.get("currency", "USD"), "source": str(spec.get("source", ""))[:200],
                     "per_million_tokens": {k: float(per[k]) for k in RATE_KEYS}}
    if not out:
        raise SystemExit("rates file has no claude/codex entries")
    return out


def cost(tally_, rates):
    return sum(tally_[RATE_KEYS[k]] * rates["per_million_tokens"][k] / 1e6 for k in RATE_KEYS)


def build_usage(sessions, sources, now, since, rates, cold_minutes):
    usage = {"schema_version": SCHEMA_VERSION, "generated_at": iso(now), "window_days": WINDOW_DAYS,
             "window_start": iso(since), "window_end": iso(now), "sources": sources}
    has = [s for s in sessions]
    notes = []
    avail = [s for s in sources if s["available"]]
    if not has:
        usage["status"] = "unknown"
        usage["totals"] = {k: None for k in ("sessions", "messages", "input_tokens", "output_tokens",
                                             "cache_read_tokens", "cache_creation_tokens")}
        usage["by_tool"] = {}
        usage["by_day"] = []
        usage["cache"] = {"read_ratio": None, "observations": [
            "No project sessions with token telemetry were found, so cache behaviour is unknown (not zero)."],
            "cold": None}
        usage["skills"] = {"status": "unknown", "items": [], "most_used": None,
                           "reason": "no project sessions available to count skill invocations"}
        notes.append("No Claude or Codex session for this root was found in the last %d days. Retained local "
                     "transcripts may have been pruned, and other harnesses (for example omp) are not parsed, so "
                     "usage and cost are UNKNOWN rather than zero." % WINDOW_DAYS)
    else:
        all_events = [e for s in has for e in s.events]
        tot = {"sessions": len(has), "messages": sum(s.messages for s in has)}
        tot.update(tally(all_events) if all_events else {k: None for k in RATE_KEYS.values()})
        usage["totals"] = tot
        by_tool = {}
        for tool in sorted({s.tool for s in has}):
            ss = [s for s in has if s.tool == tool]
            ev = [e for s in ss for e in s.events]
            row = {"sessions": len(ss), "messages": sum(s.messages for s in ss)}
            row.update(tally(ev) if ev else {k: None for k in RATE_KEYS.values()})
            by_tool[tool] = row
        usage["by_tool"] = by_tool
        days = defaultdict(lambda: {"sessions": set(), "input_tokens": 0, "output_tokens": 0,
                                    "cache_read_tokens": 0, "cache_creation_tokens": 0})
        for s in has:
            for dday in s.days:
                days[dday]["sessions"].add(s.key)
            for ts, i, o, cr, cc in s.events:
                row = days[ts.date().isoformat()]
                row["input_tokens"] += i
                row["output_tokens"] += o
                row["cache_read_tokens"] += cr
                row["cache_creation_tokens"] += cc
        usage["by_day"] = [dict(date=k, sessions=len(v["sessions"]), **{x: v[x] for x in v if x != "sessions"})
                           for k, v in sorted(days.items())]
        usage["status"] = "ok" if all_events else "partial"
        if not all_events:
            notes.append("Sessions were found but none carried token telemetry; token totals are unknown.")
        # cache
        cache = {"read_ratio": None, "observations": [], "cold": None}
        if all_events:
            t = tally(all_events)
            den = t["input_tokens"] + t["cache_read_tokens"] + t["cache_creation_tokens"]
            cache["read_ratio"] = round(t["cache_read_tokens"] / den, 4) if den else None
            cache["observations"].append(
                "cache_read / (uncached input + cache_read + cache_creation) = %s over %d token-bearing turns/updates."
                % (cache["read_ratio"], len(all_events)))
        claude_sessions = [s for s in has if s.tool == "claude" and s.events]
        if claude_sessions:
            gaps = reloads = reload_tokens = sessions_hit = 0
            max_idle = 0.0
            for s in claude_sessions:
                hit = False
                for a, b in zip(s.events, s.events[1:]):
                    idle = (b[0] - a[0]).total_seconds() / 60.0
                    max_idle = max(max_idle, idle)
                    if idle >= cold_minutes:
                        gaps += 1
                        if b[4] > 0:
                            reloads += 1
                            reload_tokens += b[4]
                            hit = True
                sessions_hit += 1 if hit else 0
            cold = {"threshold_minutes": cold_minutes, "analysed_tool": "claude",
                    "idle_gaps_over_threshold": gaps, "cold_reloads": reloads,
                    "reload_cache_creation_tokens": reload_tokens, "sessions_with_cold_reload": sessions_hit,
                    "max_idle_minutes": round(max_idle, 1),
                    "reload_cost_usd": None,
                    "keepalive_savings": {"status": "unavailable",
                                          "reason": "requires the actual cache TTL, billing plan and per-ping cost; not "
                                                    "observable from transcripts. No keep-warm pings are sent."}}
            if rates and "claude" in rates:
                delta = rates["claude"]["per_million_tokens"]["cache_write"] - rates["claude"]["per_million_tokens"]["cache_read"]
                cold["reload_cost_usd"] = round(reload_tokens * delta / 1e6, 4)
                cold["reload_cost_basis"] = "reload tokens x (supplied cache_write - cache_read) rate: premium over a warm read"
            cache["cold"] = cold
            cache["observations"].append(
                "Claude: %d idle gaps >= %d min; %d turns after such gaps re-created cache (%d tokens)."
                % (gaps, cold_minutes, reloads, reload_tokens))
        else:
            cache["observations"].append("Idle-gap / cold-cache analysis needs Claude per-turn timing; none available. Unknown.")
        if any(s.tool == "codex" for s in has):
            cache["observations"].append("Codex cache read = cached_input_tokens from cumulative token_count deltas; "
                                         "idle-gap analysis is not defined for Codex logs.")
        usage["cache"] = cache
        # skills
        sk = Counter()
        for s in has:
            for name, c in s.skills.items():
                sk[(s.tool, name)] += c
        items = [{"name": n, "tool": t, "count": c} for (t, n), c in sk.most_common(25)]
        usage["skills"] = {"status": "ok", "items": items, "most_used": items[0]["name"] if items else None,
                           "reason": None if items else "no skill invocations visible in the scanned sessions",
                           "method": "Claude: Skill tool_use blocks; Codex: reads of .../skills/<name>/SKILL.md (inferred)"}
    # estimate
    if rates:
        est = {"status": "supplied-rates", "usd": None, "by_tool": {}, "rates": rates,
               "reason": "tokens x user-supplied per-million rates; not a bill. Plan/subscription usage is not API-billed."}
        total = 0.0
        ok = False
        for tool, row in usage.get("by_tool", {}).items():
            if tool in rates and row.get("input_tokens") is not None:
                c = round(cost(row, rates[tool]), 4)
                est["by_tool"][tool] = c
                total += c
                ok = True
        est["usd"] = round(total, 4) if ok else None
        if not ok:
            est["reason"] += " No token-bearing sessions matched the supplied tools."
        usage["estimate"] = est
    else:
        usage["estimate"] = {"status": "unavailable", "usd": None, "by_tool": {}, "rates": None,
                             "reason": "No rates supplied (--rates FILE). Prices are never guessed. Per-run cost of "
                                       "scheduled routines is unknown without recorded token telemetry."}
    for s in avail:
        if s.get("unreadable"):
            notes.append("%s: %d files unreadable." % (s["id"], s["unreadable"]))
    if any(s["id"] == "claude-history" and s.get("history_only_sessions") for s in sources):
        notes.append("Some Claude sessions appear in history.jsonl without a retained transcript; their tokens are unknown.")
    notes.append("Window uses session timestamps; Codex sessions that started more than 3 days before the window "
                 "are not discovered by filename.")
    usage["notes"] = notes
    return usage


# ------------------------------------------------------------ suggestions

TAXONOMY = [
    ("weekly-review", r"weekly review|week(?:'s)? review|review (?:the|my) week",
     "Weekly review prep", "Local passive check that lists stale TASKS.md/DASHBOARD.md/routine.md items and recent git "
     "activity, written to a local file; the narrative review stays manual.", True, "none"),
    ("tasks-tidy", r"\btasks\.md\b|tidy (?:the )?tasks|update (?:the )?tasks",
     "TASKS.md tidy", "Passive check that flags checked-off or stale entries in TASKS.md; edits stay manual.", True, "none"),
    ("dashboard-refresh", r"\bdashboard\.md\b|refresh (?:the )?dashboard",
     "DASHBOARD.md refresh", "Passive freshness check on DASHBOARD.md with a flag when older than 14 days.", True, "none"),
    ("work-log", r"work[- ]?log",
     "Daily work-log nudge", "Passive reminder when no work-log entry exists for the day; entry content is yours.", True, "none"),
    ("git-summary", r"\bgit (?:status|diff|log)\b|what changed|recent commits",
     "Git change summary", "Local read-only `git status`/`git log` digest.", True, "none"),
    ("money-check", r"\bdebt\b|\bbudget\b|\bpayment\b|\bfinance\b",
     "Money check-in", "Passive reminder to open MONEY.md on the weekly cadence; no financial data is read or stored.", True, "none"),
    ("study-notes", r"md-102|az-900|az-104|study (?:notes|plan)|flashcards?",
     "Study session prep", "Passive reminder pointing at LEARNING.md and the next study item.", True, "none"),
    ("career-docs", r"\bresume\b|cover letter|job (?:search|application)",
     "Career document refresh", "Model-assisted drafting is a separate approval; a deterministic freshness check is possible now.", False, "unknown"),
    ("graft-refresh", r"graft (?:build|ask|map)|refresh (?:the )?graft",
     "Code-graph refresh", "Local `graft build` after substantial edits (deterministic, $0 per graft docs).", True, "none"),
    ("second-brain", r"second[- ]brain|brain\.py|\bmemory (?:index|check)\b",
     "Second-brain index check", "Run `python3 second-brain/brain.py check` on a schedule (deterministic, no model calls).", True, "none"),
]
TAXO_RE = [(k, re.compile(p, re.I), t, a, safe, spend) for k, p, t, a, safe, spend in TAXONOMY]


def norm_prompt(text):
    t = re.sub(r"\s+", " ", text.strip().lower())
    return re.sub(r"\d+", "#", t)


def load_salt(data_dir, persist):
    f = data_dir / ".routines-salt"
    try:
        v = f.read_text(encoding="utf-8").strip()
        if len(v) >= 32:
            return v
    except OSError:
        pass
    v = secrets.token_hex(24)
    if persist:
        data_dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(f), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(v)
    return v


def build_suggestions(sessions, now, threshold, salt):
    since = now - dt.timedelta(days=SUGGEST_DAYS)
    out = {"schema_version": SCHEMA_VERSION, "generated_at": iso(now), "window_days": SUGGEST_DAYS,
           "window_start": iso(since), "threshold": threshold, "items": [], "notes": []}
    taxo = defaultdict(list)  # key -> [(session, ts)]
    verb = defaultdict(list)
    sess_with_prompts = set()
    for s in sessions:
        for ts, text in s.prompts:
            if ts < since:
                continue
            sess_with_prompts.add(s.key)
            for key, rx, *_ in TAXO_RE:
                if rx.search(text):
                    taxo[key].append((s, ts))
            n = norm_prompt(text)
            if len(n) >= 20 and not n.startswith("/"):
                h = hmac.new(salt.encode(), n.encode("utf-8", "replace"), hashlib.sha256).hexdigest()[:10]
                verb[h].append((s, ts))
    items = []

    def pack(sid, title, summary, action, occ, safe, spend, kind):
        sess = sorted({s.key for s, _ in occ})
        return {"id": sid, "kind": kind, "title": title, "summary": summary, "evidence_count": len(occ),
                "session_ids": sess, "days": sorted({ts.date().isoformat() for _, ts in occ}),
                "tool": ",".join(sorted({s.tool for s, _ in occ})), "proposed_action": action,
                "safe_to_schedule": safe, "model_spend": spend, "status": "suggested",
                "requires_approval": True}

    for key, rx, title, action, safe, spend in TAXO_RE:
        occ = taxo.get(key, [])
        if len(occ) >= threshold:
            items.append(pack("sug-" + key, title,
                              "%d prompts in the past %d days matched the fixed '%s' job category (text not stored)."
                              % (len(occ), SUGGEST_DAYS, key), action, occ, safe, spend, "taxonomy"))
    for h, occ in verb.items():
        if len(occ) >= threshold:
            items.append(pack("sug-rep-" + h, "Identical prompt repeated %d times" % len(occ),
                              "The same normalised prompt was sent %d times in %d days. Its text is deliberately not "
                              "shown; look the session ids up in your own transcripts." % (len(occ), SUGGEST_DAYS),
                              "Review the listed sessions and decide whether it deserves a saved prompt, skill or routine. "
                              "Nothing is scheduled automatically.", occ, False, "unknown", "verbatim"))
    items.sort(key=lambda i: (-i["evidence_count"], i["id"]))
    out["items"] = items
    if not sess_with_prompts:
        out["notes"].append("No project prompts were available for the past %d days, so repeated-job detection has "
                            "no evidence (unknown, not 'no repeated jobs')." % SUGGEST_DAYS)
    else:
        out["notes"].append("Evaluated %d project sessions with prompts in the past %d days; threshold is %d "
                            "occurrences." % (len(sess_with_prompts), SUGGEST_DAYS, threshold))
    out["notes"].append("Suggestions are proposals only. Session text is never executed or copied; actions come from a "
                        "fixed taxonomy. Nothing is installed or enabled without explicit approval.")
    return out


# ---------------------------------------------------------------- inventory

LOG_LINE = re.compile(r"^(\S+)\s+([A-Z_]+)\s+\S+\s")
NETWORK_RE = re.compile(r"(?i)\b(curl|wget|https?://|openai|anthropic|gemini)\b")


def analyse_script(path):
    text = read_text(path, 65536)
    if text is None:
        return None
    info = {"model_invoking": False, "network": False, "model": None, "workspace": None}
    if re.search(r'(?i)(\$\{?CLAUDE\}?|\bclaude\b|\bcodex\b)[^\n]*(\s-p\b|--print|\bexec\b)', text):
        info["model_invoking"] = True
    elif NETWORK_RE.search(text):
        info["network"] = True
    m = re.search(r'(?m)^MODEL="?([A-Za-z0-9._\-]+)"?', text)
    if m:
        info["model"] = m.group(1)
    m = re.search(r'(?m)^WORKSPACE="?([^"\n]+)"?', text)
    if m:
        info["workspace"] = m.group(1).strip()
    return info


def recent_outcomes(log_path, since):
    text = read_text(log_path, 1048576)
    if text is None:
        return None
    oc = Counter()
    last = None
    for line in text.splitlines():
        m = LOG_LINE.match(line)
        if not m:
            continue
        ts = parse_ts(m.group(1))
        if ts and ts >= since:
            oc[m.group(2)] += 1
            last = ts if last is None or ts > last else last
    return {"window_days": WINDOW_DAYS, "outcomes": dict(oc), "last_run": iso(last)}


def launchd_items(home, root, now, notes_unknown):
    items = []
    agents = home / "Library" / "LaunchAgents"
    rc, out = run_fixed(["launchctl", "list"])
    loaded = set()
    if rc == 0:
        for line in out.splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) == 3:
                loaded.add(parts[2])
    else:
        notes_unknown.append("launchctl list unavailable; loaded state of launch agents is unknown.")
    if not agents.is_dir():
        notes_unknown.append("~/Library/LaunchAgents not found.")
        return items, loaded
    other = 0
    since = now - dt.timedelta(days=WINDOW_DAYS)
    for pl in sorted(agents.glob("*.plist")):
        try:
            with open(pl, "rb") as fh:
                d = plistlib.load(fh)
        except Exception:
            notes_unknown.append("Could not parse %s." % pl.name)
            continue
        label = d.get("Label") or pl.stem
        args = [str(a) for a in (d.get("ProgramArguments") or ([d["Program"]] if d.get("Program") else []))]
        joined = " ".join(args) + " " + str(d.get("WorkingDirectory", ""))
        relevant = (str(root) in joined or ".local-routines" in joined or "Cloudtransition" in joined
                    or label == LABEL or re.search(r"(?i)\b(claude|codex)\b", joined))
        if not relevant:
            other += 1
            continue
        sched = None
        sci = d.get("StartCalendarInterval")
        if isinstance(sci, dict):
            sched = "calendar %s" % ",".join("%s=%s" % (k, sci[k]) for k in sorted(sci))
        elif isinstance(sci, list):
            sched = "calendar x%d entries" % len(sci)
        elif d.get("StartInterval"):
            sched = "every %ss" % d["StartInterval"]
        if d.get("RunAtLoad"):
            sched = (sched + "; " if sched else "") + "run at load"
        script = next((a for a in args if a.endswith((".sh", ".py")) and os.path.isfile(a)), None)
        info = analyse_script(script) if script else None
        item = {"id": "launchd:" + label, "name": label, "kind": "launchd", "source": short(pl, home, root),
                "schedule": sched, "status": "installed-loaded" if label in loaded else "installed-not-loaded",
                "external": False, "review_mode": "unknown", "token_telemetry": "none-recorded",
                "script": short(script, home, root) if script else None}
        if label == LABEL:
            item.update(classification="local-deterministic", model_spend="none-by-design", review_mode="passive",
                        token_telemetry="zero-by-design",
                        notes="ARMS deterministic generator. Zero API tokens and dollars.")
        elif info and info["model_invoking"]:
            item.update(classification="model-invoking", model_spend="possible", external=True)
            item["model"] = info["model"]
            item["notes"] = ("Static scan: script invokes a model CLI non-interactively. Billing basis (plan vs API) and "
                             "per-run tokens are not recorded anywhere readable, so cost is unknown.")
        elif info and info["network"]:
            item.update(classification="external", model_spend="unknown", external=True,
                        notes="Static scan found network references; behaviour not verified.")
        elif info:
            item.update(classification="local-deterministic", model_spend="none-by-design",
                        notes="Static scan found no model/network calls (heuristic, not a proof).")
        else:
            item.update(classification="unknown", model_spend="unknown", notes="Script not readable or not found.")
        if script and info:
            ws = info.get("workspace")
            if ws:
                item["workspace"] = ws
            rr = recent_outcomes(Path(script).parent / "routine.log", since)
            if rr:
                item["recent_runs"] = rr
                item["review_mode"] = "active" if rr["outcomes"].get("SUCCESS") or rr["outcomes"].get("SUCCESS_NO_INPUT") else item["review_mode"]
        item["summary"] = "%s (%s)" % (item.get("classification"), item["status"])
        items.append(item)
    if other:
        notes_unknown.append("%d other user LaunchAgents are unrelated vendor/system helpers and are not routines; not listed." % other)
    return items, loaded


def cron_items(home, root, notes_unknown):
    rc, out = run_fixed(["crontab", "-l"])
    if rc is None:
        notes_unknown.append("crontab not runnable; cron entries unknown.")
        return []
    if rc != 0:
        return []  # "no crontab for user"
    items = []
    for i, line in enumerate(out.splitlines()):
        t = line.strip()
        if not t or t.startswith("#") or "=" in t.split()[0]:
            continue
        parts = t.split(None, 5)
        if len(parts) < 6:
            continue
        cmd = parts[5]
        spend = "possible" if re.search(r"(?i)\b(claude|codex)\b", cmd) else "unknown"
        items.append({"id": "cron:%d" % i, "name": "cron entry %d" % i, "kind": "cron", "source": "crontab -l",
                      "schedule": " ".join(parts[:5]), "status": "installed-loaded",
                      "classification": "model-invoking" if spend == "possible" else "unknown",
                      "model_spend": spend, "external": spend == "possible", "review_mode": "unknown",
                      "token_telemetry": "none-recorded", "summary": "cron entry (command not shown)",
                      "notes": "Command text intentionally not emitted."})
    return items


def dir_items(base, kind, label, home, root, classification):
    items = []
    if base.is_dir():
        for d in sorted(base.iterdir()):
            if d.is_dir() and not d.name.startswith("."):
                items.append({"id": "%s:%s" % (kind, d.name), "name": d.name, "kind": kind, "source": short(d, home, root),
                              "schedule": None, "status": "unknown", "classification": classification,
                              "model_spend": "possible", "external": True, "review_mode": "unknown",
                              "token_telemetry": "none-recorded", "summary": label,
                              "notes": "Directory exists; schedule and cost fields are not parsed."})
    return items


def build_inventory(home, root, now, notes_extra=None):
    unknown = []
    items, _ = launchd_items(home, root, now, unknown)
    items += cron_items(home, root, unknown)
    items += dir_items(home / ".claude" / "scheduled-tasks", "claude-scheduled", "Claude scheduled task", home, root, "model-invoking")
    items += dir_items(home / ".codex" / "automations", "codex-automation", "Codex automation", home, root, "model-invoking")
    if not (home / ".claude" / "scheduled-tasks").is_dir():
        unknown.append("No ~/.claude/scheduled-tasks directory: Claude Desktop schedules not present locally. "
                       "Claude cloud Routines (claude.ai) cannot be enumerated offline: unknown.")
    if not (home / ".codex" / "automations").is_dir():
        unknown.append("No ~/.codex/automations directory: no local Codex automations found. Cloud automations unknown.")

    rm = root / "routine.md"
    if rm.is_file():
        items.append({"id": "workspace:routine.md", "name": "Human weekly rhythm", "kind": "workspace-file",
                      "source": "<root>/routine.md", "schedule": "manual weekly rhythm (per file)", "status": "unknown",
                      "classification": "manual", "model_spend": "none-by-design", "external": False,
                      "review_mode": "active", "token_telemetry": "not-applicable",
                      "summary": "Manual routine described in routine.md; nothing runs automatically.",
                      "notes": "Source of truth for the human work rhythm; not parsed into tasks."})
    br = root / "button-runner" / "server.js"
    if br.is_file():
        rl = root / "runs.log"
        n = len(read_text(rl, 1048576).splitlines()) if rl.is_file() and read_text(rl, 1048576) else 0
        items.append({"id": "workspace:button-runner", "name": "button-runner", "kind": "on-demand-app",
                      "source": "<root>/button-runner/server.js", "schedule": None, "status": "on-demand",
                      "classification": "model-invoking", "model_spend": "possible", "external": True,
                      "review_mode": "active", "token_telemetry": "none-recorded",
                      "summary": "On-demand local HTTP button UI that forwards prompts to a local router API.",
                      "notes": "Not scheduled. Posts prompts to a local proxy (localhost); downstream model and billing "
                               "unknown. <root>/runs.log has %d logged entries (content not read into this report)." % n})
    artifact = SCRIPT.parent / "launchd" / (LABEL + ".plist")
    installed = home / "Library" / "LaunchAgents" / (LABEL + ".plist")
    if not any(i["id"] == "launchd:" + LABEL for i in items):
        items.append({"id": "arms:" + LABEL, "name": LABEL, "kind": "arms-managed",
                      "source": short(artifact, home, root) if artifact.is_file() else "run `routines.py schedule --write`",
                      "schedule": "calendar Weekday=5,Hour=9,Minute=0 (Friday 09:00 local)",
                      "status": "installed-not-loaded" if installed.is_file() else "available-not-installed",
                      "classification": "local-deterministic", "model_spend": "none-by-design", "external": False,
                      "review_mode": "passive", "token_telemetry": "zero-by-design",
                      "summary": "Weekly local generation of this report; available, not installed.",
                      "notes": "Artifact only. Nothing is installed by this tool; see tools/arms/routines-README.md."})
    counts = Counter(i["classification"] for i in items)
    return {"schema_version": SCHEMA_VERSION, "generated_at": iso(now), "root": str(root), "items": items,
            "counts": dict(counts), "unknown": unknown + (notes_extra or [])}


# ------------------------------------------------------------------- checks

LINK_RE = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
STAMP_RE = re.compile(r"(?i)(?:last[ _]updated|updated)[:\s_*]*(\d{4}-\d{2}-\d{2})")
BINARY_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".zip", ".gz", ".zst", ".xlsx", ".docx",
              ".pptx", ".woff", ".woff2", ".ttf", ".mp4", ".mov", ".mp3", ".mhtml", ".svgz", ".sqlite", ".db"}


def chk(cid, title, status, message, evidence=None):
    return {"id": cid, "title": title, "status": status, "message": message, "detail": message,
            "evidence": (evidence or [])[:20]}


def check_core_files(root):
    want = ROUTER_FILES + STATE_FILES
    missing = [f for f in want if not (root / f).is_file()]
    return chk("core-files", "Root routers and operational files present",
               "pass" if not missing else "fail",
               "All %d expected files present." % len(want) if not missing else "%d of %d expected files missing." % (len(missing), len(want)),
               ["missing: " + m for m in missing])


def check_freshness(root, now):
    ev, worst = [], "pass"
    for f in STATE_FILES:
        p = root / f
        if not p.is_file():
            continue
        text = read_text(p, 4096) or ""
        m = STAMP_RE.search(text)
        if m:
            when = parse_ts(m.group(1) + "T00:00:00")
            basis = "stamp"
        else:
            when = dt.datetime.fromtimestamp(p.stat().st_mtime).astimezone()
            basis = "file mtime"
        age = (now - when).days
        ev.append("%s: %d days old (%s)" % (f, age, basis))
        if age > 14:
            worst = "warn"
    if not ev:
        return chk("state-freshness", "TASKS/DASHBOARD/routine freshness", "unknown", "No state files found.")
    return chk("state-freshness", "TASKS/DASHBOARD/routine freshness", worst,
               "All state files updated within 14 days." if worst == "pass" else "One or more state files are older than 14 days.", ev)


def check_links(root):
    broken, total = [], 0
    for f in ROUTER_FILES + STATE_FILES:
        p = root / f
        text = read_text(p)
        if text is None:
            continue
        fenced = False
        for n, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("```"):
                fenced = not fenced
                continue
            if fenced:
                continue
            for m in LINK_RE.finditer(line):
                tgt = m.group(1)
                if re.match(r"(?i)^(https?:|mailto:|#|tel:)", tgt):
                    continue
                total += 1
                rel = unquote(tgt.split("#", 1)[0])
                if rel and not (p.parent / rel).exists():
                    broken.append("%s:%d -> %s" % (f, n, rel))
    return chk("router-links", "Router and state-file relative links resolve",
               "pass" if not broken else "warn",
               "%d relative links checked; %d broken." % (total, len(broken)), broken)


def check_drafts(root, now):
    d = root / "drafts"
    files = sorted(d.glob("weekly-review-*.md")) if d.is_dir() else []
    if not files:
        return chk("weekly-review-drafts", "Recent weekly-review draft exists", "warn",
                   "No drafts/weekly-review-*.md in this root.")
    m = re.search(r"(\d{4}-\d{2}-\d{2})", files[-1].name)
    when = parse_ts(m.group(1) + "T00:00:00") if m else None
    age = (now - when).days if when else None
    return chk("weekly-review-drafts", "Recent weekly-review draft exists", "pass" if age is not None and age <= 10 else "warn",
               "Latest draft is %s days old (%d drafts)." % (age, len(files)), [files[-1].name])


def check_launchd_workspace(inv, root):
    bad = []
    for it in inv["items"]:
        ws = it.get("workspace")
        if it["kind"] == "launchd" and ws and norm(ws) not in root_variants(root):
            oc = (it.get("recent_runs") or {}).get("outcomes", {})
            bad.append("%s targets %s (not this root); recent outcomes: %s" % (it["name"], ws, json.dumps(oc, sort_keys=True)))
    if not any(it.get("workspace") for it in inv["items"] if it["kind"] == "launchd"):
        return chk("launchd-workspace", "Scheduled routines target this workspace", "unknown", "No launchd routine declares a workspace.")
    return chk("launchd-workspace", "Scheduled routines target this workspace", "warn" if bad else "pass",
               "A scheduled routine points at a different directory than this root." if bad else "Scheduled routine workspaces match this root.", bad)


def check_credentials(root):
    rc, out = run_fixed(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"], timeout=30)
    if rc != 0:
        return chk("credential-scan", "Workspace files free of credential-like strings", "unknown",
                   "Not a readable git repository; scan skipped.")
    hits, name_hits, scanned = [], [], 0
    for rel in out.split("\0"):
        if not rel:
            continue
        low = rel.lower()
        base = os.path.basename(low)
        if base == ".env" or base.startswith(".env.") and not base.endswith(".example") or low.endswith((".pem", ".p12", ".pfx")) or base in ("id_rsa", "id_ed25519"):
            name_hits.append("sensitive-looking filename: " + rel)
        ext = os.path.splitext(low)[1]
        if ext in BINARY_EXT or "_files/" in low or ext in (".html", ".htm"):
            continue  # binaries and saved third-party web pages
        p = root / rel
        try:
            if not p.is_file() or p.stat().st_size > 524288:
                continue
        except OSError:
            continue
        text = read_text(p, 524288)
        if text is None:
            continue
        scanned += 1
        for n, line in enumerate(text.splitlines(), 1):
            if len(line) > 2000:
                continue
            for kind, rx in CRED_PATTERNS:
                if rx.search(line):
                    hits.append("%s:%d %s" % (rel, n, kind))
                    break
            else:
                if GENERIC_CRED.search(line):
                    hits.append("%s:%d generic-credential-assignment" % (rel, n))
    ev = name_hits + hits
    specific = any("generic-credential" not in h for h in hits) or bool(name_hits)
    status = "fail" if specific else ("warn" if hits else "pass")
    return chk("credential-scan", "Workspace files free of credential-like strings", status,
               "%d text files scanned (tracked + untracked, git-ignored excluded); %d credential-like locations. Values never shown."
               % (scanned, len(ev)), ev)


def check_disk(root):
    try:
        u = shutil.disk_usage(str(root))
    except OSError:
        return chk("disk-space", "Workspace volume free space", "unknown", "disk usage unavailable")
    pct = 100.0 * u.free / u.total
    gb = u.free / 1e9
    return chk("disk-space", "Workspace volume free space", "pass" if pct >= 10 and gb >= 2 else "warn",
               "%.1f GB free (%.1f%%)." % (gb, pct))


def check_tools(home):
    found = []
    for name, extra in (("claude", [Path("/opt/homebrew/bin/claude"), home / ".local" / "bin" / "claude"]),
                        ("codex", [home / ".local" / "bin" / "codex", Path("/opt/homebrew/bin/codex")])):
        p = shutil.which(name) or next((str(x) for x in extra if x.exists()), None)
        found.append("%s: %s" % (name, "present" if p else "not found"))
    return chk("agent-clis", "Agent CLIs present (not invoked)", "pass" if all("present" in f for f in found) else "unknown",
               "Presence only; auth, plan and billing basis are not queried.", found)


def check_usage(usage):
    if usage["status"] == "unknown":
        return chk("session-data", "Project session telemetry available", "unknown",
                   "No Claude/Codex session data for this root in the last %d days; usage is unknown." % WINDOW_DAYS,
                   ["%s: %s" % (s["id"], s.get("reason") or "no data") for s in usage["sources"]])
    return chk("session-data", "Project session telemetry available", "pass" if usage["status"] == "ok" else "warn",
               "%d project sessions with %s token data." % (usage["totals"]["sessions"], "usable" if usage["status"] == "ok" else "no"))


def check_zero_cost():
    return chk("zero-model-spend", "This report makes no model or network calls", "pass",
               "Deterministic: reads local files; subprocesses limited to launchctl list, crontab -l, git ls-files "
               "(and zstd -dc fallback). API tokens: 0. API dollars: 0.")


def build_checks(root, home, now, inv, usage):
    items = [check_zero_cost(), check_core_files(root), check_freshness(root, now), check_links(root),
             check_drafts(root, now), check_launchd_workspace(inv, root), check_credentials(root), check_disk(root),
             check_tools(home), check_usage(usage)]
    summ = Counter(i["status"] for i in items)
    return {"schema_version": SCHEMA_VERSION, "generated_at": iso(now),
            "summary": {k: summ.get(k, 0) for k in ("pass", "warn", "fail", "unknown")},
            "cost": {"api_tokens": 0, "api_usd": 0,
                     "note": "Checks are deterministic local reads; no model or network calls."},
            "items": items}


# ------------------------------------------------------------ report + CLI


def scrub(obj):
    """Last-line defence: mask anything credential-shaped in the serialised report."""
    s = json.dumps(obj, indent=2, ensure_ascii=False)
    return REDACT_RE.sub("[redacted]", s)


def build_report(root, home, now, rates=None, threshold=THRESHOLD, cold_minutes=COLD_MINUTES, persist_salt=False):
    roots = root_variants(root)
    since = now - dt.timedelta(days=WINDOW_DAYS)
    sessions, sources = collect_sessions(home, roots, since, now)
    usage = build_usage(sessions, sources, now, since, rates, cold_minutes)
    salt = load_salt(root / "tools" / "arms" / "data", persist_salt)
    sugg = build_suggestions(sessions, now, threshold, salt)
    inv = build_inventory(home, root, now)
    checks = build_checks(root, home, now, inv, usage)
    return {"inventory": inv, "usage": usage, "suggestions": sugg, "checks": checks}


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".routines-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        os.replace(tmp, str(path))
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def log_dir(home):
    return Path(home) / ".local-routines" / "arms-report"


def build_plist(root, python, home, weekday=5, hour=9, minute=0):
    """WorkingDirectory and log files live under $HOME so launchd never touches the external volume before spawn."""
    logs = log_dir(home)
    return plistlib.dumps({
        "Label": LABEL,
        "ProgramArguments": [str(python), str(root / "tools" / "arms" / "routines.py"), "--root", str(root), "run"],
        "StartCalendarInterval": {"Weekday": weekday, "Hour": hour, "Minute": minute},
        "WorkingDirectory": str(home),
        "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"},
        "StandardOutPath": str(logs / "routines.launchd.out.log"),
        "StandardErrorPath": str(logs / "routines.launchd.err.log"),
        "ProcessType": "Background",
        "Nice": 10,
        "LowPriorityIO": True,
    })


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cmd", nargs="?", choices=["run", "schedule"], default="run",
                    help="run: generate the report (default); schedule: print/write the weekly Friday launchd plist (never installs)")
    ap.add_argument("--root", default=None, help="workspace root (default: repo root of this file)")
    ap.add_argument("--home", default=None, help="home holding ~/.claude, ~/.codex, ~/Library (default: $HOME)")
    ap.add_argument("--output", default=None, help="report path (default <root>/tools/arms/data/routines.json)")
    ap.add_argument("--stdout", action="store_true", help="print the report instead of writing it")
    ap.add_argument("--rates", default=None, help="JSON file of user-supplied per-million-token rates (see README)")
    ap.add_argument("--threshold", type=int, default=THRESHOLD, help="repeat count for suggestions (default 3)")
    ap.add_argument("--cold-minutes", type=int, default=COLD_MINUTES, help="idle minutes treated as a cold cache")
    ap.add_argument("--now", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--write", action="store_true", help="with schedule: write tools/arms/launchd/%s.plist" % LABEL)
    ap.add_argument("--python", default=sys.executable, help="with schedule: interpreter path to embed")
    args = ap.parse_args(argv)
    root = Path(args.root).expanduser() if args.root else DEFAULT_ROOT
    root = Path(os.path.abspath(str(root)))
    home = Path(args.home).expanduser() if args.home else Path.home()

    if args.cmd == "schedule":
        data = build_plist(root, args.python, home)
        if args.write:
            out = root / "tools" / "arms" / "launchd" / (LABEL + ".plist")
            out.parent.mkdir(parents=True, exist_ok=True)
            log_dir(home).mkdir(parents=True, exist_ok=True)  # launchd will not create the log directory
            tmp = out.with_suffix(".tmp")
            tmp.write_bytes(data)
            os.replace(str(tmp), str(out))
            print(str(out))
        else:
            sys.stdout.write(data.decode("utf-8"))
        return 0

    now = now_local(getattr(args, "now", None))
    rates = load_rates(args.rates)
    report = build_report(root, home, now, rates, args.threshold, args.cold_minutes, persist_salt=not args.stdout)
    text = scrub(report)
    if args.stdout:
        print(text)
        return 0
    out = Path(args.output).expanduser() if args.output else root / "tools" / "arms" / "data" / "routines.json"
    atomic_write(out, text)
    c = report["checks"]["summary"]
    u = report["usage"]
    print("wrote %s | sessions(30d)=%s usage=%s suggestions=%d checks pass=%d warn=%d fail=%d unknown=%d"
          % (out, u["totals"]["sessions"], u["status"], len(report["suggestions"]["items"]),
             c["pass"], c["warn"], c["fail"], c["unknown"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
