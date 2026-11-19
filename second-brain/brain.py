#!/usr/bin/env python3
"""Second Brain: deterministic, model-free retrieval over a curated workspace.

Commands (all print exactly one JSON object on stdout):

    brain.py [--root ROOT] index
    brain.py [--root ROOT] query QUESTION
    brain.py [--root ROOT] remember --title T --summary S --body B
    brain.py [--root ROOT] check
    brain.py [--root ROOT] benchmark [--questions FILE] [--repeat N] [--baseline-files K]

Retrieval ladder (no model calls anywhere):
    1. strip the question to keywords
    2. score every catalogue entry with field-boosted BM25 over the generated postings index
       (term counts recorded at index time); no source file is opened
    3. open exactly one best source
    4. extract one bounded section
    5. follow at most one safe local pointer when the section only points elsewhere

Standard library only. Python 3.9+.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import posixpath
import re
import statistics
import sys
import tempfile
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import quote, unquote

try:  # POSIX advisory locks; released by the kernel if the process dies.
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback uses O_EXCL lock files
    fcntl = None  # type: ignore[assignment]

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

BRAIN_DIRNAME = "second-brain"
CATALOGUE_NAME = "catalogue.md"
MEMORIES_DIRNAME = "memories"
POSTINGS_NAME = "postings.json"
POSTINGS_VERSION = 3
LOCK_NAME = ".lock"
MEMORY_INDEX_NAME = "memory.md"   # generated short index of memories, at the workspace root
MEMORY_INDEX_MARKER = "<!-- brain-memory-index v1 -->"
TMP_PREFIX = ".brain-"
TMP_SUFFIX = ".tmp"
FORMAT_MARKER = "<!-- brain-catalogue v1 -->"
DEFAULT_QUESTIONS_NAME = "benchmark-questions.json"

TITLE_MAX = 120
SUMMARY_MAX = 500
BODY_MAX = 8000
QUESTION_MAX = 500

MAX_FILE_BYTES = 300_000          # larger files are not indexed
MAX_EVIDENCE_LINES = 40           # hard bound for one evidence block
MAX_EVIDENCE_CHARS = 3000         # hard bound for one evidence block
THIN_PROSE_CHARS = 200            # below this a section "just points elsewhere"
CAT_SUMMARY_CHARS = 160
CAT_HEADING_CHARS = 40
CAT_MAX_HEADINGS = 24            # upper bound; see heading_budget()
CAT_MAX_KEYWORDS = 40            # upper bound; see kw_budget()
SUPERSEDED_FACTOR = 0.5           # a memory another memory supersedes scores at half
SUPERSEDES_MAX = 5
RECENCY_BONUS = 0.1               # newest memory gets at most +10%: breaks ties, never overrides relevance
RECENCY_DAYS = 180.0
DURATION_MARK = "~dur"            # synthetic section term; `~` cannot occur in a real term
DURATION_SECTION_BOOST = 1.6
DURATION_DOC_BOOST = 1.25
MIN_SCORE = 0.5                   # BM25 floor; coverage (>=40% of known terms) does the real filtering
LOCK_TIMEOUT_DEFAULT = 10.0

ALLOWED_EXT = {".md", ".yml", ".yaml", ".txt"}

EXIT_OK = 0
EXIT_PROBLEMS = 1
EXIT_INVALID = 2
EXIT_STALE = 3
EXIT_LOCKED = 4

ROUTER_FILES = {
    "operations.md": "operations",
    "code.md": "code",
    "money.md": "money",
    "learning.md": "learning",
    "health.md": "health",
    "content.md": "content",
}

# Directory names that are vendored, generated, or tool-owned. Any dot-directory
# is skipped as well.
VENDOR_DIR_NAMES = {
    "node_modules", "venv", ".venv", "env", "__pycache__", "dist", "build",
    "site-packages", "vendor", "runs", "graft", "coverage", "target", "out",
    "tests", "test", "testdata", "__snapshots__", "playwright-report", "test-results",
}
ARCHIVE_DIR_NAMES = {"archive", "archives"}
PRIVATE_DIR_RE = re.compile(r"private|employer|secret|credential", re.I)

# Root-relative (lowercase) directories that are curated out of content ingestion.
CURATED_EXCLUDED_DIRS = {
    "college planning": "personal_academic_records",
    "shared": "synced_folder",
    "projects/rendercv": "vendored_third_party",
    "andrej-karpathy-skills": "vendored_third_party",
}
# Directories whose *subdirectories* are skipped (only top-level files indexed).
TOP_FILES_ONLY_DIRS = {"resume": "variants_and_archive"}

# Agent instruction / context files are routing inputs for tools, not knowledge.
INSTRUCTION_NAMES = {
    "claude.md", "agents.md", "gemini.md", "cursor.md", "skill.md",
    "copilot-instructions.md", "claude.local.md", "codex.md", ".cursorrules",
}
INSTRUCTION_RE = re.compile(r"^agent[-_]?(contract|instructions?)", re.I)
# Root-relative (lowercase) files kept out of ingestion: agent design context and the build plan
# for this very system (it must not outrank the authoritative sources it describes).
ROOT_EXCLUDED_FILES = {
    "product.md": "agent_design_context",
    "docs/plans/2026-10-28-second-brain-arms.md": "implementation_plan",
    "docs/plans/2026-11-09-second-brain-improvements.md": "implementation_plan",
    MEMORY_INDEX_NAME: "generated_memory_index",
}
SECRET_NAME_RE = re.compile(
    r"(^|[-_.])(env|secret|secrets|credential|credentials|token|password|"
    r"passwords|passwd|apikey|api-key|id_rsa|service-account|client_secret|private)"
    r"([-_.]|$)", re.I)
SECRET_EXT = {".pem", ".key", ".p12", ".pfx", ".pickle", ".kdbx"}
GENERATED_NAME_RE = re.compile(r"(\.min\.|\.lock$|package-lock|_report\.md$|_summary\.txt$|^requirements.*\.txt$)", re.I)

STOPWORDS = frozenset("""
a about above after again all also am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further get gets
give had has have having he her here hers him his how i if in into is it its itself just let
list me more most my need no nor not now of off on once only or other our ours out over own
please same she should show so some such tell than that the their theirs them then there these
they this those through to too under until up us use used using very want was we were what when
where which while who whom why will with would you your yours find tells find
""".split())

# --------------------------------------------------------------------------- #
# Errors and small helpers
# --------------------------------------------------------------------------- #


class BrainError(Exception):
    def __init__(self, code: int, error: str, message: str):
        super().__init__(message)
        self.code = code
        self.error = error
        self.message = message


def now_ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000.0, 2)


def relposix(root: Path, path: str) -> str:
    rel = os.path.relpath(path, str(root))
    return "" if rel == "." else rel.replace(os.sep, "/")


def brain_dir(root: Path) -> Path:
    return root / BRAIN_DIRNAME


def catalogue_path(root: Path) -> Path:
    return brain_dir(root) / CATALOGUE_NAME


def postings_path(root: Path) -> Path:
    return brain_dir(root) / POSTINGS_NAME


def memories_dir(root: Path) -> Path:
    return brain_dir(root) / MEMORIES_DIRNAME


def memory_index_path(root: Path) -> Path:
    return root / MEMORY_INDEX_NAME


def sha8(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()[:8]


def inside(root_real: str, target: str) -> bool:
    real = os.path.realpath(target)
    return real == root_real or real.startswith(root_real + os.sep)


def clean_cell(s: str) -> str:
    s = s.replace("‖", "/").replace("[", "(").replace("]", ")")
    return re.sub(r"\s+", " ", s).strip()


def truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    cut = s[: n - 1].rsplit(" ", 1)[0] if " " in s[: n - 1] else s[: n - 1]
    return cut.rstrip(" ,;:-") + "…"


# --------------------------------------------------------------------------- #
# Redaction and secret detection
# --------------------------------------------------------------------------- #

HARD_SECRET_RES = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
]
_KV_RE = re.compile(
    r"(?i)\b(pass(?:word|wd)?|pwd|secret|token|api[_-]?key|bearer)\b(\s*[:=]\s*)([\"']?)([^\s\"'`,;)]{8,})")
_BACKTICK_RE = re.compile(r"`([A-Za-z0-9!@#$%^&*+=?~-]{8,64})`")
_DN_RE = re.compile(r"\b(?:DC|OU|CN)=[^,\s`)]+(?:,\s*(?:DC|OU|CN)=[^,\s`)]+)*")


def has_hard_secret(text: str) -> bool:
    return any(rx.search(text) for rx in HARD_SECRET_RES)


def _looks_secret_value(v: str) -> bool:
    return (len(v) >= 8 and any(c.isdigit() for c in v)
            and any(c.isalpha() for c in v))


def _backtick_secret(m: "re.Match[str]") -> str:
    v = m.group(1)
    if (any(c.isupper() for c in v) and any(c.islower() for c in v)
            and any(c.isdigit() for c in v) and any(c in "!@#$%^&*" for c in v)):
        return "`[redacted]`"
    return m.group(0)


def redact(text: str) -> Tuple[str, int]:
    """Line-preserving redaction of credential-looking tokens. Returns (text, count)."""
    count = 0

    def sub_count(rx, repl, s):
        nonlocal count
        s, n = rx.subn(repl, s)
        count += n
        return s

    out = []
    for line in text.split("\n"):
        for rx in HARD_SECRET_RES:
            line = sub_count(rx, "[redacted]", line)

        def kv(m: "re.Match[str]") -> str:
            nonlocal count
            if _looks_secret_value(m.group(4)):
                count += 1
                return f"{m.group(1)}{m.group(2)}{m.group(3)}[redacted]"
            return m.group(0)

        line = _KV_RE.sub(kv, line)
        before = line
        line = _BACKTICK_RE.sub(_backtick_secret, line)
        if line != before:
            count += 1
        line = sub_count(_DN_RE, "[redacted-dn]", line)
        out.append(line)
    return "\n".join(out), count


# --------------------------------------------------------------------------- #
# Tokenisation
# --------------------------------------------------------------------------- #


def stem(w: str) -> str:
    """Light, consistent suffix folding. Stems need only agree between corpus and question."""
    if w.isdigit() or len(w) <= 3:
        return w
    if w.endswith("ly") and len(w) >= 6:
        w = w[:-2]  # weekly -> week, locally -> local, manually -> manual
    if w.endswith("ies") and len(w) > 4:
        w = w[:-3] + "y"
    elif w.endswith(("sses", "shes", "ches", "xes", "zes")):
        w = w[:-2]
    elif w.endswith("ing") and len(w) > 5:
        w = w[:-3]
        if len(w) > 2 and w[-1] == w[-2] and w[-1] not in "lsz":
            w = w[:-1]
    elif w.endswith("ed") and len(w) > 4:
        w = w[:-2]
        if len(w) > 2 and w[-1] == w[-2] and w[-1] not in "lsz":
            w = w[:-1]
    elif w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    if w.endswith("er") and len(w) >= 6:
        w = w[:-2]  # server -> serv, matching serve -> serv; computer -> comput
    if w.endswith("ation") and len(w) > 8:
        w = w[:-5]  # configuration -> configur, matching configure -> configur
    if w.endswith("e") and len(w) > 4:
        w = w[:-1]
    return w


_DURATION_RE = re.compile(
    r"(?<![\w.])\d+(?:\.\d+)?(?:\s*[\u2013\u2014-]\s*\d+(?:\.\d+)?)?\s*"
    r"(?:sec(?:ond)?s?|min(?:ute)?s?|h(?:ou)?rs?|h|days?|weeks?|wks?|months?|years?|yrs?)\b", re.I)
_HOW_LONG_RE = re.compile(r"\bhow\s+long\b", re.I)
_DURATION_Q_RE = re.compile(
    r"\bhow\s+long\b|\bhow\s+much\s+time\b|\bduration\b|"
    r"\bhow\s+many\s+(?:seconds|minutes|hours|days|weeks|months|years)\b", re.I)


def tokens(text: str) -> List[str]:
    text = text.lower()
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    return re.findall(r"[a-z0-9]+", text)


def terms(text: str) -> List[str]:
    out = []
    for t in tokens(text):
        if t in STOPWORDS:
            continue
        if len(t) < 2:
            continue
        out.append(stem(t))
    return out


def question_terms(question: str) -> Tuple[List[str], str]:
    """Keywords plus an intent marker. "How long ..." asks for a duration: `long` is then filler,
    and sections that state a duration are preferred."""
    qterms = unique(terms(question))
    if not _DURATION_Q_RE.search(question):
        return qterms, ""
    drop = {stem("long")} if _HOW_LONG_RE.search(question) else set()
    return [t for t in qterms if t not in drop], DURATION_MARK


def unique(seq: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


_URL_RE = re.compile(r"https?://\S+")


def strip_md(s: str) -> str:
    s = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"`+", "", s)
    s = re.sub(r"(\*\*|__|\*|~~)", "", s)
    s = re.sub(r"^\s*(?:[#>]+|[-*+]\s+(?:\[[ xX]\]\s*)?|\d+[.)]\s+)", "", s)
    return re.sub(r"\s+", " ", s).strip()


def slug(s: str) -> str:
    s = strip_md(s).lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"[\s]+", "-", s).strip("-")


# --------------------------------------------------------------------------- #
# Source policy (what is allowed into the brain)
# --------------------------------------------------------------------------- #


def dir_exclusion(rel: str, name: str) -> Optional[str]:
    low = name.lower()
    if low in {".kb-private", ".kb-venv", "personal-kb", "eval-evidence"}:
        return "private_kb"
    if name.startswith("."):
        return "hidden_dir"
    if low in VENDOR_DIR_NAMES:
        return "vendor_or_generated"
    if low.endswith("_files"):
        return "saved_web_page"
    if low in ARCHIVE_DIR_NAMES:
        return "archived"
    if PRIVATE_DIR_RE.search(low):
        return "private_or_employer"
    rl = rel.lower()
    if rl in CURATED_EXCLUDED_DIRS:
        return CURATED_EXCLUDED_DIRS[rl]
    parent = posixpath.dirname(rl)
    if parent in TOP_FILES_ONLY_DIRS:
        return TOP_FILES_ONLY_DIRS[parent]
    if parent == BRAIN_DIRNAME or rl.startswith(BRAIN_DIRNAME + "/"):
        return "brain_internal"
    return None


def file_exclusion(rel: str, name: str, size: int) -> Optional[str]:
    low = name.lower()
    if low == "kb.sqlite" or low.startswith("kb.sqlite-") or low.startswith(
        ("kb-ingest.log", "kb-approval")
    ):
        return "private_kb"
    ext = os.path.splitext(low)[1]
    if ext in SECRET_EXT:
        return "secret_file"
    if ext not in ALLOWED_EXT:
        return "not_text_source"
    if low in INSTRUCTION_NAMES or INSTRUCTION_RE.match(low):
        return "instruction_file"
    if rel.lower() in ROOT_EXCLUDED_FILES:
        return ROOT_EXCLUDED_FILES[rel.lower()]
    if low == "product.md":
        return "agent_design_context"
    stem_part = os.path.splitext(low)[0]
    if SECRET_NAME_RE.search(stem_part) or low.startswith(".env"):
        return "secret_file"
    if PRIVATE_DIR_RE.search(low):
        return "private_or_employer"
    if "work-log" in low or "worklog" in low:
        return "employer_work_log"
    if GENERATED_NAME_RE.search(low):
        return "generated_or_report"
    if stem_part in {"license", "licence", "notice"}:
        return "license_boilerplate"
    if rel.lower().startswith(BRAIN_DIRNAME + "/") and rel.lower() != BRAIN_DIRNAME + "/readme.md":
        return "brain_internal"
    if size == 0:
        return "empty"
    if size > MAX_FILE_BYTES:
        return "too_large"
    return None


@dataclass
class Candidate:
    rel: str
    abs: str
    size: int


def scan_candidates(root: Path) -> Tuple[List[Candidate], Dict[str, int]]:
    """Walk the workspace applying the exclusion policy. Does not open files."""
    found: List[Candidate] = []
    skipped: Counter = Counter()
    root_s = str(root)
    for dirpath, dirnames, filenames in os.walk(root_s, followlinks=False):
        rel_dir = relposix(root, dirpath)
        keep = []
        for d in sorted(dirnames):
            full = os.path.join(dirpath, d)
            rel = f"{rel_dir}/{d}" if rel_dir else d
            if os.path.islink(full):
                skipped["symlink"] += 1
                continue
            reason = dir_exclusion(rel, d)
            if reason:
                skipped[reason] += 1
                continue
            keep.append(d)
        dirnames[:] = keep
        for f in sorted(filenames):
            full = os.path.join(dirpath, f)
            rel = f"{rel_dir}/{f}" if rel_dir else f
            ext = os.path.splitext(f.lower())[1]
            if os.path.islink(full):
                if ext in ALLOWED_EXT:
                    skipped["symlink"] += 1
                continue
            try:
                size = os.stat(full).st_size
            except OSError:
                skipped["unreadable"] += 1
                continue
            reason = file_exclusion(rel, f, size)
            if reason:
                if reason != "not_text_source":
                    skipped[reason] += 1
                continue
            found.append(Candidate(rel, full, size))
    return found, dict(sorted(skipped.items()))


# --------------------------------------------------------------------------- #
# Router map (areas and one-line descriptions come from the existing routers)
# --------------------------------------------------------------------------- #


def load_router_map(root: Path) -> Dict[str, Tuple[str, str]]:
    """{lowercase path: (area, description)} parsed from the root router tables."""
    mapping: Dict[str, Tuple[str, str]] = {}
    for lower_name, area in ROUTER_FILES.items():
        fname = lower_name[:-3].upper() + ".md"
        p = root / fname
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.split("\n"):
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 2:
                continue
            paths = re.findall(r"`([^`]+)`", cells[0])
            desc = clean_cell(strip_md(redact(" — ".join(c for c in cells[1:] if c))[0]))
            for raw in paths:
                raw = raw.strip().rstrip("/").strip()
                if not raw or " " in raw and not raw.lower().endswith(tuple(ALLOWED_EXT)) and "/" not in raw:
                    continue
                mapping.setdefault(raw.lower(), (area, desc))
    return mapping


def area_for(rel: str, router_map: Dict[str, Tuple[str, str]]) -> Tuple[str, str]:
    low = rel.lower()
    base = posixpath.basename(low)
    if "/" not in low and base in ROUTER_FILES:
        return ROUTER_FILES[base], ""
    if low in router_map:
        return router_map[low]
    best = None
    for p in router_map:
        if low.startswith(p + "/") and (best is None or len(p) > len(best)):
            best = p
    if best:
        return router_map[best][0], ""
    top = low.split("/", 1)[0]
    if top in {"second-brain", "tools", "docs"}:
        return "code", ""
    return "other", ""


# --------------------------------------------------------------------------- #
# Catalogue model, rendering, parsing
# --------------------------------------------------------------------------- #


@dataclass
class Entry:
    path: str
    title: str
    kind: str          # source | router | memory
    area: str
    size: int
    sha: str
    summary: str
    keywords: List[str] = field(default_factory=list)
    headings: List[str] = field(default_factory=list)

    @property
    def sig(self) -> str:
        return f"{self.size}-{self.sha}"


_ENTRY_RE = re.compile(
    r"^- \[(?P<title>[^\]]*)\]\((?P<link>[^)]*)\) · (?P<kind>source|router|memory) · "
    r"(?P<area>[a-z0-9-]+) · sig:(?P<size>\d+)-(?P<sha>[0-9a-f]{8}) · "
    r"(?P<summary>.*?) ‖ k: (?P<kw>.*?) ‖ h: (?P<h>.*)$")


def render_entry(e: Entry) -> str:
    link = "../" + quote(e.path, safe="/")
    kw = " ".join(e.keywords)
    hd = " | ".join(clean_cell(h).replace("|", "/") for h in e.headings)
    return (f"- [{clean_cell(e.title)}]({link}) · {e.kind} · {e.area} · sig:{e.sig} · "
            f"{clean_cell(e.summary)} ‖ k: {kw} ‖ h: {hd}")


def parse_entry(line: str) -> Optional[Entry]:
    m = _ENTRY_RE.match(line.rstrip("\n"))
    if not m:
        return None
    link = unquote(m.group("link"))
    if not link.startswith("../"):
        return None
    path = link[3:]
    parts = path.split("/")
    if not path or path.startswith("/") or ".." in parts or "" in parts:
        return None
    return Entry(
        path=path, title=m.group("title"), kind=m.group("kind"), area=m.group("area"),
        size=int(m.group("size")), sha=m.group("sha"), summary=m.group("summary"),
        keywords=m.group("kw").split(), headings=[h for h in m.group("h").split(" | ") if h])


def render_catalogue(entries: Sequence[Entry]) -> str:
    mem = sorted((e for e in entries if e.kind == "memory"), key=lambda e: e.path)
    src = [e for e in entries if e.kind != "memory"]
    by_area: Dict[str, List[Entry]] = {}
    for e in sorted(src, key=lambda e: (e.area, e.path)):
        by_area.setdefault(e.area, []).append(e)
    out = [
        "# Second Brain Catalogue", "",
        FORMAT_MARKER,
        "Check this index first, open files second. One line per entry: "
        "`[title](link) · kind · area · sig · summary ‖ k: keywords ‖ h: headings`. "
        "Generated by `python3 second-brain/brain.py index`; `remember` appends memory lines. "
        "Do not hand-edit.", "",
        f"Sources: {len(src)} · Memories: {len(mem)}", "",
        "## Memories", "",
    ]
    out.extend(render_entry(e) for e in mem)
    if not mem:
        out.append("_No memories saved yet._")
    out.append("")
    out.append("## Sources")
    for area in sorted(by_area):
        out.extend(["", f"### {area}", ""])
        out.extend(render_entry(e) for e in by_area[area])
    out.append("")
    return "\n".join(out)


@dataclass
class Catalogue:
    entries: List[Entry]
    bad_lines: List[Tuple[int, str]]
    size: int


def load_catalogue(root: Path) -> Optional[Catalogue]:
    p = catalogue_path(root)
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if FORMAT_MARKER not in text:
        return None
    entries, bad = [], []
    for i, line in enumerate(text.split("\n"), 1):
        if line.startswith("- ["):
            e = parse_entry(line)
            if e is None:
                bad.append((i, line[:120]))
            else:
                entries.append(e)
    return Catalogue(entries, bad, len(text.encode("utf-8")))


# --------------------------------------------------------------------------- #
# Document parsing: sections, summaries, headings
# --------------------------------------------------------------------------- #

_HEAD_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_YAML_KEY_RE = re.compile(r"^([A-Za-z0-9_\"'][^:#\n]*):(\s|$)")


@dataclass
class Section:
    start: int            # 1-based line of heading / first line
    end: int              # 1-based inclusive, trimmed of trailing blanks
    heading: str
    level: int
    ancestors: Tuple[str, ...]
    body_start: int       # first 1-based line counted as body text


def decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def _trim_end(lines: List[str], start: int, end: int) -> int:
    while end > start and not lines[end - 1].strip():
        end -= 1
    return end


def parse_sections(lines: List[str], suffix: str) -> List[Section]:
    n = len(lines)
    if n == 0:
        return []
    if suffix == ".md":
        heads = []
        fence = None
        for i, l in enumerate(lines, 1):
            s = l.lstrip()
            if s.startswith("```") or s.startswith("~~~"):
                mark = s[:3]
                if fence is None:
                    fence = mark
                elif fence == mark:
                    fence = None
                continue
            if fence:
                continue
            m = _HEAD_RE.match(l)
            if m:
                heads.append((i, len(m.group(1)), strip_md(m.group(2))))
        sections: List[Section] = []
        first = heads[0][0] if heads else n + 1
        if first > 1 and any(x.strip() for x in lines[: first - 1]):
            sections.append(Section(1, _trim_end(lines, 1, first - 1), "", 0, (), 1))
        stack: List[Tuple[int, str]] = []
        for idx, (ln, lvl, text) in enumerate(heads):
            nxt = heads[idx + 1][0] if idx + 1 < len(heads) else n + 1
            while stack and stack[-1][0] >= lvl:
                stack.pop()
            anc = tuple(t for _, t in stack)
            stack.append((lvl, text))
            sections.append(Section(ln, _trim_end(lines, ln, nxt - 1), text, lvl, anc, ln + 1))
        return sections
    if suffix in (".yml", ".yaml"):
        keys = [i for i, l in enumerate(lines, 1)
                if l and l[0] not in " \t#-" and _YAML_KEY_RE.match(l)]
        if keys:
            sections = []
            if keys[0] > 1 and any(x.strip() for x in lines[: keys[0] - 1]):
                sections.append(Section(1, _trim_end(lines, 1, keys[0] - 1), "", 0, (), 1))
            for idx, ln in enumerate(keys):
                nxt = keys[idx + 1] if idx + 1 < len(keys) else n + 1
                key = _YAML_KEY_RE.match(lines[ln - 1]).group(1).strip("\"'")
                sections.append(Section(ln, _trim_end(lines, ln, nxt - 1), key, 1, (), ln + 1))
            return sections
    # plain text (and yaml without top-level keys): paragraphs
    sections = []
    i = 1
    while i <= n:
        if not lines[i - 1].strip():
            i += 1
            continue
        j = i
        while j + 1 <= n and lines[j].strip():
            j += 1
        sections.append(Section(i, j, truncate(strip_md(lines[i - 1]), 60), 1, (), i))
        i = j + 1
    return sections


def section_stats(lines: List[str], sections: List[Section]) -> List[Tuple[int, int, set, set, Counter]]:
    """Per-section term statistics: (start, end, heading terms, ancestor terms, body counts).

    A section that states a duration ("45-60 min", "3 weeks") also carries DURATION_MARK, so a
    "how long" question can prefer it from the index alone.
    """
    out = []
    for sec in sections:
        text = " ".join(lines[sec.body_start - 1: sec.end])
        body = Counter(terms(text))
        if _DURATION_RE.search(text):
            body[DURATION_MARK] = 1
        out.append((sec.start, sec.end, set(terms(sec.heading)),
                    set(terms(" ".join(sec.ancestors))), body))
    return out


def rank_sections(stats: Sequence[Tuple[int, int, set, set, Counter]], qset: set,
                  bonus: str = "") -> Tuple[Optional[int], float, int]:
    """Pick the section that best answers the question: (index, score, question terms it holds).

    Terms are weighted by how rare they are *within this file's sections*, so a word that
    appears everywhere (the document's own topic) does not outvote the discriminating words.
    Works identically on freshly parsed lines and on the statistics stored in the postings index.
    `bonus` is an intent marker (DURATION_MARK): it lifts a section that already matches a question
    term and holds the marker; it never makes a section match on its own.
    """
    sdf: Counter = Counter()
    seen_by = []
    for _, _, head, anc, body in stats:
        seen = qset & (head | anc | set(body))
        sdf.update(seen)
        seen_by.append(seen)
    active = [t for t in qset if sdf[t]]
    if not active:
        return None, 0.0, 0
    # The document title is every section's ancestor. Its own (preamble) section must not win on
    # the title words alone: score a heading made only of shared ancestor words as an ancestor.
    ancs = [anc for _, _, _, anc, _ in stats if anc]
    shared = set.intersection(*ancs) if ancs else set()
    total = len(stats)
    weight = {t: math.log(1.0 + total / sdf[t]) + 0.3 for t in active}
    best, best_s, best_n = None, 0.0, 0
    for i, ((start, end, head, anc, body), seen) in enumerate(zip(stats, seen_by)):
        if not seen:
            continue
        head_w = 1.5 if head and head <= shared else 3.0
        raw = 0.0
        for t in seen:
            raw += weight[t] * ((head_w if t in head else 0.0) + (1.5 if t in anc else 0.0)
                                + ((2.0 + 0.25 * min(body[t], 3)) if t in body else 0.0))
        cov = len(seen) / len(active)
        nlines = end - start + 1
        s = raw * (0.3 + 0.7 * cov) / (1.0 + 0.15 * math.log(1.0 + nlines / 10.0))
        if bonus and bonus in body:
            s *= DURATION_SECTION_BOOST
        if s > best_s:
            best, best_s, best_n = i, s, len(seen)
    return best, best_s, best_n


def best_section(lines: List[str], sections: List[Section], qset: set, bonus: str = ""
                 ) -> Tuple[Optional[Section], float]:
    idx, score, _ = rank_sections(section_stats(lines, sections), qset, bonus)
    return (sections[idx], score) if idx is not None else (None, 0.0)


def bound_window(lines: List[str], s: int, e: int, qset: set, dur: bool = False
                 ) -> Optional[Tuple[int, int, str]]:
    """Bound a section to MAX_EVIDENCE_LINES / MAX_EVIDENCE_CHARS around question hits."""
    while s <= e and not lines[s - 1].strip():
        s += 1
    while e >= s and not lines[e - 1].strip():
        e -= 1
    if s > e:
        return None

    def line_score(i: int) -> int:
        return len(qset & set(terms(lines[i - 1]))) + (
            1 if dur and _DURATION_RE.search(lines[i - 1]) else 0)

    if e - s + 1 > MAX_EVIDENCE_LINES:
        scores = {i: line_score(i) for i in range(s, e + 1)}
        window = sum(scores[i] for i in range(s, s + MAX_EVIDENCE_LINES))
        best_start, best_sum = s, window
        for start in range(s + 1, e - MAX_EVIDENCE_LINES + 2):
            window += scores[start + MAX_EVIDENCE_LINES - 1] - scores[start - 1]
            if window > best_sum:
                best_start, best_sum = start, window
        s, e = best_start, best_start + MAX_EVIDENCE_LINES - 1
    while sum(len(l.rstrip()) + 1 for l in lines[s - 1:e]) > MAX_EVIDENCE_CHARS and e > s:
        if line_score(e) <= line_score(s):
            e -= 1
        else:
            s += 1
    while s <= e and not lines[s - 1].strip():
        s += 1
    while e >= s and not lines[e - 1].strip():
        e -= 1
    if s > e:
        return None
    text = "\n".join(l.rstrip() for l in lines[s - 1:e])
    if len(text) > MAX_EVIDENCE_CHARS:
        text = text[: MAX_EVIDENCE_CHARS - 1] + "…"
    return s, e, text


def first_title(lines: List[str], suffix: str, fallback: str) -> str:
    fence = None
    for l in lines:
        s = l.lstrip()
        if s.startswith("```") or s.startswith("~~~"):
            fence = None if fence else s[:3]
            continue
        if fence:
            continue
        m = re.match(r"^#\s+(.*?)\s*#*\s*$", l)
        if m:
            return strip_md(m.group(1)) or fallback
    if suffix in (".yml", ".yaml"):
        for l in lines:
            m = re.match(r"^(?:title|name):\s*(.+)$", l)
            if m:
                return m.group(1).strip().strip("\"'") or fallback
    return fallback


def humanize(name: str) -> str:
    stem_part = os.path.splitext(name)[0]
    return re.sub(r"[-_]+", " ", stem_part).strip() or name


def first_summary(lines: List[str], suffix: str) -> str:
    if suffix == ".md":
        i, n, fence = 0, len(lines), None
        if n and lines[0].strip() == "---":  # front matter
            j = 1
            while j < n and lines[j].strip() != "---":
                j += 1
            i = j + 1
        buf: List[str] = []
        for l in lines[i:]:
            s = l.strip()
            if s.startswith("```") or s.startswith("~~~"):
                fence = None if fence else s[:3]
                if buf:
                    break
                continue
            if fence:
                continue
            if not s:
                if buf:
                    break
                continue
            if (s.startswith(("#", "|", "<", "---", "***", "!")) or re.match(r"^_?\(?(last )?updated", s, re.I)
                    or re.match(r"^[-*+]\s", s) and not buf):
                if buf:
                    break
                continue
            buf.append(s)
        text = strip_md(redact(" ".join(buf))[0])
        return truncate(text, CAT_SUMMARY_CHARS)
    if suffix in (".yml", ".yaml"):
        for l in lines:
            s = l.strip()
            if s.startswith("#") and len(s.strip("# ")) > 3 and not s.startswith("#!"):
                return truncate(s.strip("# ").strip(), CAT_SUMMARY_CHARS)
        keys = [m.group(1) for l in lines if (m := _YAML_KEY_RE.match(l)) and l[0] not in " -#"]
        return truncate("YAML data; top-level keys: " + ", ".join(keys[:6]), CAT_SUMMARY_CHARS) if keys else ""
    for l in lines:
        if l.strip():
            return truncate(strip_md(l), CAT_SUMMARY_CHARS)
    return ""


def kw_budget(size: int) -> int:
    """Keywords scale with document size: a 1 KB note keeps 8, a 12 KB README ~26, capped at 40."""
    return int(min(CAT_MAX_KEYWORDS, max(8, 6 * math.log2(1 + size / 600))))


def heading_budget(size: int) -> int:
    return int(min(CAT_MAX_HEADINGS, max(8, 6 + size // 1500)))


def doc_headings(lines: List[str], suffix: str, limit: int) -> List[str]:
    secs = parse_sections(lines, suffix)
    heads = [s for s in secs if s.heading]
    if suffix == ".md":
        pool = [s for s in heads if s.level <= 4]
    elif suffix in (".yml", ".yaml"):
        pool = heads
    else:
        pool = []
    out = unique(truncate(clean_cell(s.heading), CAT_HEADING_CHARS) for s in pool)
    return out[:limit]


def body_terms(text: str) -> Counter:
    text = _URL_RE.sub(" ", strip_md_block(text))
    return Counter(t for t in terms(text) if _keyword_ok(t))


def strip_md_block(text: str) -> str:
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return text


def _keyword_ok(t: str) -> bool:
    if len(t) < 3 and not t.isdigit():
        return False
    if len(t) >= 10 and any(c.isdigit() for c in t) and any(c.isalpha() for c in t):
        return False  # id/token-like
    if t.isdigit() and len(t) < 4:
        return False
    return True


# --------------------------------------------------------------------------- #
# Locking and atomic writes
# --------------------------------------------------------------------------- #


class WriterLock:
    """Exclusive advisory lock on <brain>/.lock. Kernel releases it if the process dies."""

    def __init__(self, bdir: Path, timeout: Optional[float] = None):
        self.path = bdir / LOCK_NAME
        env = os.environ.get("BRAIN_LOCK_TIMEOUT")
        self.timeout = timeout if timeout is not None else (
            float(env) if env else LOCK_TIMEOUT_DEFAULT)
        self.fd: Optional[int] = None

    def __enter__(self) -> "WriterLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout
        if fcntl is not None:
            fd = os.open(str(self.path), os.O_CREAT | os.O_RDWR, 0o644)
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.fd = fd
                    return self
                except OSError:
                    if time.monotonic() >= deadline:
                        os.close(fd)
                        raise BrainError(EXIT_LOCKED, "locked",
                                         "another brain.py writer holds the lock; retry shortly")
                    time.sleep(0.02)
        while True:  # pragma: no cover - fallback
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o644)
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise BrainError(EXIT_LOCKED, "locked",
                                     "another brain.py writer holds the lock; retry shortly")
                time.sleep(0.02)

    def __exit__(self, *exc) -> None:
        if self.fd is None:
            return
        if fcntl is not None:
            with contextlib.suppress(OSError):
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
        else:  # pragma: no cover
            os.close(self.fd)
            with contextlib.suppress(OSError):
                os.unlink(self.path)
        self.fd = None


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=TMP_PREFIX, suffix=TMP_SUFFIX)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, str(path))
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    with contextlib.suppress(OSError):
        dfd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)


def stray_tmp_files(root: Path) -> List[Path]:
    out: List[Path] = []
    for d in (root, brain_dir(root), memories_dir(root)):
        if d.is_dir():
            out.extend(sorted(p for p in d.iterdir()
                              if p.name.startswith(TMP_PREFIX) and p.name.endswith(TMP_SUFFIX)))
    return out


def recover_tmp(root: Path) -> int:
    """Delete leftovers of interrupted writes. Caller MUST hold the writer lock."""
    n = 0
    for p in stray_tmp_files(root):
        with contextlib.suppress(OSError):
            p.unlink()
            n += 1
    return n


# --------------------------------------------------------------------------- #
# Building entries
# --------------------------------------------------------------------------- #


def build_entry(rel: str, data: bytes, kind: str, area: str, router_desc: str,
                idf: Optional[Dict[str, float]] = None) -> Entry:
    text = decode(data)
    lines = text.split("\n")
    suffix = os.path.splitext(rel.lower())[1]
    title = first_title(lines, suffix, humanize(posixpath.basename(rel)))
    summary = router_desc or first_summary(lines, suffix)
    if not router_desc and not summary:
        summary = truncate(title, CAT_SUMMARY_CHARS)
    summary = redact(summary)[0]
    tf = body_terms(text)
    seen = set(terms(title))
    ranked = sorted(
        tf.items(),
        key=lambda kv: (-(1.0 + math.log(kv[1])) * (idf.get(kv[0], 1.0) if idf else 1.0), kv[0]))
    keywords = []
    for t, _ in ranked:
        if t in seen:
            continue
        keywords.append(t)
        if len(keywords) >= kw_budget(len(data)):
            break
    headings = [redact(h)[0] for h in doc_headings(lines, suffix, heading_budget(len(data)))]
    return Entry(rel, redact(title)[0], kind, area, len(data), sha8(data), summary,
                 keywords, headings)


def doc_postings(rel: str, data: bytes) -> dict:
    """Term counts recorded at index time, per document and per section, so a query can choose
    both the file and the section that answers without opening any source."""
    text = decode(data)
    tf = body_terms(text)
    lines = text.split("\n")
    suffix = os.path.splitext(rel.lower())[1]
    secs = [[start, end, sorted(head), sorted(anc), dict(sorted(body.items()))]
            for start, end, head, anc, body in section_stats(lines, parse_sections(lines, suffix))]
    return {"sha": sha8(data), "len": sum(tf.values()), "tf": dict(sorted(tf.items())), "sec": secs}


def stored_sections(post: object) -> Optional[List[Tuple[int, int, set, set, Counter]]]:
    """Section statistics from a postings entry, or None when absent or malformed."""
    secs = post.get("sec") if isinstance(post, dict) else None
    if not isinstance(secs, list):
        return None
    out = []
    for s in secs:
        if not (isinstance(s, list) and len(s) == 5 and isinstance(s[4], dict)):
            return None
        out.append((int(s[0]), int(s[1]), set(s[2]), set(s[3]), Counter(s[4])))
    return out


def write_postings(root: Path, docs: Dict[str, dict]) -> None:
    """Caller MUST hold the writer lock. Written next to the catalogue; never hand-edited."""
    payload = {"version": POSTINGS_VERSION, "docs": dict(sorted(docs.items()))}
    atomic_write(postings_path(root), json.dumps(payload, separators=(",", ":"), ensure_ascii=False))


def load_postings(root: Path) -> Dict[str, dict]:
    """Index file, loaded like the catalogue. Missing or corrupt postings mean metadata-only scoring."""
    try:
        with open(postings_path(root), encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(payload, dict) or payload.get("version") != POSTINGS_VERSION:
        return {}
    docs = payload.get("docs")
    return docs if isinstance(docs, dict) else {}


def build_source_entries(root: Path) -> Tuple[List[Entry], Dict[str, int], List[str], Dict[str, dict]]:
    cands, skipped = scan_candidates(root)
    router_map = load_router_map(root)
    skipped = Counter(skipped)
    secret_paths: List[str] = []
    loaded: List[Tuple[Candidate, bytes]] = []
    seen_hash: Dict[str, str] = {}
    for c in cands:
        try:
            data = Path(c.abs).read_bytes()
        except OSError:
            skipped["unreadable"] += 1
            continue
        if b"\x00" in data:
            skipped["binary"] += 1
            continue
        text = decode(data)
        if has_hard_secret(text):
            skipped["secret_content"] += 1
            secret_paths.append(c.rel)
            continue
        h = hashlib.sha1(data).hexdigest()
        if h in seen_hash:
            skipped["duplicate_content"] += 1
            continue
        seen_hash[h] = c.rel
        loaded.append((c, data))
    # corpus document frequency for keyword selection
    df: Counter = Counter()
    for c, data in loaded:
        df.update(set(body_terms(decode(data))))
    n = max(1, len(loaded))
    idf = {t: math.log(1.0 + n / (1.0 + d)) for t, d in df.items()}
    entries: List[Entry] = []
    postings: Dict[str, dict] = {}
    for c, data in loaded:
        area, desc = area_for(c.rel, router_map)
        base = posixpath.basename(c.rel).lower()
        kind = "router" if "/" not in c.rel and base in ROUTER_FILES else "source"
        entries.append(build_entry(c.rel, data, kind, area, desc if kind == "source" else "", idf))
        postings[c.rel] = doc_postings(c.rel, data)
    return entries, dict(sorted(skipped.items())), sorted(secret_paths), postings


def memory_files(root: Path) -> List[Path]:
    d = memories_dir(root)
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir()
                  if p.is_file() and p.suffix.lower() == ".md" and not p.name.startswith("."))


_MEMORY_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
_SUPERSEDES_RE = re.compile(r"^_Supersedes: ([a-z0-9, -]+)_\s*$")
_MEMORY_HEADER_LINES = 8


def memory_supersedes(lines: Sequence[str]) -> List[str]:
    """Memory ids named on the `_Supersedes: id, id_` header line written by `remember`."""
    for l in lines[:_MEMORY_HEADER_LINES]:
        m = _SUPERSEDES_RE.match(l)
        if m:
            return sorted({i for i in (x.strip() for x in m.group(1).split(",")) if _MEMORY_ID_RE.match(i)})
    return []


def superseded_by(entries: Sequence[Entry], postings: Dict[str, dict]) -> Dict[str, str]:
    """Memory path -> id of the memory that supersedes it. Read from the index only; a postings
    entry whose signature differs from the catalogue is not trusted."""
    prefix = f"{BRAIN_DIRNAME}/{MEMORIES_DIRNAME}/"
    out: Dict[str, str] = {}
    for e in entries:
        if e.kind != "memory":
            continue
        post = postings.get(e.path)
        if not (isinstance(post, dict) and post.get("sha") == e.sha):
            continue
        for mid in post.get("supersedes") or []:
            if isinstance(mid, str) and _MEMORY_ID_RE.match(mid) and prefix + mid + ".md" != e.path:
                out[prefix + mid + ".md"] = posixpath.basename(e.path)[:-3]
    return out


def memory_entry(root: Path, p: Path) -> Tuple[Entry, dict]:
    data = p.read_bytes()
    rel = relposix(root, str(p))
    text = decode(data)
    lines = text.split("\n")
    title = first_title(lines, ".md", humanize(p.name))
    summary = ""
    for l in lines:
        if l.startswith("> "):
            summary = strip_md(redact(l[2:])[0])
            break
    if not summary:
        summary = first_summary(lines, ".md") or title
    tf = body_terms(text)
    seen = set(terms(title))
    kws = [t for t, _ in sorted(tf.items(), key=lambda kv: (-kv[1], kv[0])) if t not in seen]
    post = doc_postings(rel, data)
    sup = memory_supersedes(lines)
    if sup:
        post["supersedes"] = sup
    return Entry(rel, redact(title)[0], "memory", "memory", len(data), sha8(data),
                 truncate(redact(summary)[0], CAT_SUMMARY_CHARS), kws[:kw_budget(len(data))],
                 [redact(h)[0] for h in doc_headings(lines, ".md", heading_budget(len(data)))]
                 ), post


_MD_CTRL_RE = re.compile(r"[\x00-\x1f\x7f\u2028\u2029]+")
_MD_ESCAPE_RE = re.compile(r"([\\`*_\[\]<>~|&])")


def md_label(s: str, limit: int) -> str:
    """Single-line, length-capped text that cannot open or close Markdown constructs."""
    s = re.sub(r"\s+", " ", _MD_CTRL_RE.sub(" ", s)).strip()
    return _MD_ESCAPE_RE.sub(r"\\\1", truncate(s, limit))


def render_memory_index(entries: Sequence[Entry], superseded: Optional[Dict[str, str]] = None) -> str:
    """One linked line per memory. Reuses Entry title/summary (already redacted); never the body."""
    mem = sorted((e for e in entries if e.kind == "memory"), key=lambda e: e.path, reverse=True)
    out = [
        "# Memory", "",
        MEMORY_INDEX_MARKER,
        "Short index of saved memories: one line each, open the link for the full text. "
        "Generated by `python3 second-brain/brain.py index` and `remember`. Do not hand-edit.", "",
    ]
    for e in mem:
        title = md_label(e.title, TITLE_MAX) or md_label(humanize(posixpath.basename(e.path)), TITLE_MAX)
        line = f"- [{title}]({quote(e.path, safe='/')})"
        summary = md_label(e.summary, CAT_SUMMARY_CHARS)
        if summary and summary != title:
            line += f" — {summary}"
        if superseded and e.path in superseded:
            line += f" _(superseded by {superseded[e.path]})_"
        out.append(line)
    if not mem:
        out.append("_No memories saved yet._")
    out.append("")
    return "\n".join(out)


def memory_index_text(root: Path) -> str:
    """What memory.md must contain right now, derived from the memory files on disk."""
    pairs = [memory_entry(root, p) for p in memory_files(root)]
    entries = [e for e, _ in pairs]
    return render_memory_index(entries, superseded_by(entries, {e.path: post for e, post in pairs}))


def _read_memory_index(root: Path) -> Optional[str]:
    try:
        return memory_index_path(root).read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None


def ensure_memory_index_writable(root: Path) -> None:
    """Refuse to overwrite a hand-written memory.md. Call before any write of a writer command."""
    cur = _read_memory_index(root)
    if cur is None and not os.path.lexists(memory_index_path(root)):
        return
    if cur is not None and (not cur.strip() or MEMORY_INDEX_MARKER in cur):
        return
    raise BrainError(EXIT_INVALID, "memory_index_foreign",
                     f"{MEMORY_INDEX_NAME} exists but was not generated by brain.py; move or delete it first")


def write_memory_index(root: Path, text: str) -> None:
    """Caller MUST hold the writer lock and have called ensure_memory_index_writable."""
    if _read_memory_index(root) != text:
        atomic_write(memory_index_path(root), text)


# --------------------------------------------------------------------------- #
# index
# --------------------------------------------------------------------------- #


def _index_locked(root: Path) -> Dict[str, object]:
    ensure_memory_index_writable(root)
    recovered = recover_tmp(root)
    entries, skipped, secret_paths, postings = build_source_entries(root)
    mems = []
    for p in memory_files(root):
        entry, post = memory_entry(root, p)
        mems.append(entry)
        postings[entry.path] = post
    text = render_catalogue(entries + mems)
    # Postings first: a crash between the writes leaves extra postings, which queries ignore by sig.
    write_postings(root, postings)
    atomic_write(catalogue_path(root), text)
    write_memory_index(root, render_memory_index(mems, superseded_by(mems, postings)))
    return {
        "status": "indexed",
        "catalogue": relposix(root, str(catalogue_path(root))),
        "memory_index": MEMORY_INDEX_NAME,
        "catalogue_bytes": len(text.encode("utf-8")),
        "sources": len(entries),
        "memories": len(mems),
        "entries": len(entries) + len(mems),
        "skipped": skipped,
        "excluded_secret_paths": secret_paths,
        "recovered_tmp_files": recovered,
    }


def cmd_index(root: Path) -> Tuple[dict, int]:
    t0 = time.perf_counter()
    with WriterLock(brain_dir(root)):
        payload = _index_locked(root)
    payload["elapsed_ms"] = now_ms(t0)
    return payload, EXIT_OK


# --------------------------------------------------------------------------- #
# query
# --------------------------------------------------------------------------- #

# Catalogue fields add pseudo-occurrences on top of the recorded body counts (BM25F-lite).
_FIELD_BOOSTS = {"name": 3.0, "title": 3.0, "head": 2.0, "path": 1.0, "sum": 1.0, "meta": 1.5}
_BM25_K1 = 1.2
_BM25_B = 0.5  # milder length normalisation: buried facts in long living docs must stay findable
_SNAPSHOT_DIRS = {"superpowers", "specs", "briefs", "drafts"}
_DATED_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


@dataclass
class Scored:
    entry: Entry
    score: float
    matched: int


RERANK_DEPTH = 5


def rerank_by_section(ranked: List[Scored], qterms: List[str], postings: Dict[str, dict],
                      bonus: str = "") -> List[Scored]:
    """Prefer the candidate whose single best section holds the most question terms.

    Uses section statistics from the postings index only (no source is opened). A document that
    mentions every term in different places loses to one that answers in one section, because only
    one bounded section is ever handed to the model.
    """
    head = ranked[:RERANK_DEPTH]
    if len(head) < 2:
        return ranked
    qset = set(qterms)
    active = {t for t in qset if any(isinstance(postings.get(s.entry.path), dict)
                                     and t in postings[s.entry.path].get("tf", {}) for s in head)}
    if not active:
        return ranked
    rescored = []
    for s in head:
        post = postings.get(s.entry.path)
        stats = stored_sections(post) if isinstance(post, dict) and post.get("sha") == s.entry.sha else None
        if stats is None:
            rescored.append(s)  # no trustworthy section data: keep the document score unchanged
            continue
        idx, _, held = rank_sections(stats, qset, bonus)
        held = min(held, len(active))
        mult = 0.4 + 0.6 * held / len(active)
        if bonus and idx is not None and bonus in stats[idx][4]:
            mult *= DURATION_DOC_BOOST
        rescored.append(Scored(s.entry, s.score * mult, s.matched))
    rescored.sort(key=lambda s: (-s.score, s.entry.path))
    return rescored + ranked[RERANK_DEPTH:]


def _today() -> date:
    return datetime.now(timezone.utc).date()


def authority(e: Entry) -> float:
    """Path-derived prior: living docs outrank dated design snapshots on equal evidence."""
    if e.kind == "memory":
        # Memories carry their save date in the file name. A bounded bonus lets the newer of two
        # equally relevant memories win; sources have no trustworthy date and get none.
        m = _DATED_NAME_RE.match(posixpath.basename(e.path))
        try:
            age = (_today() - date.fromisoformat(m.group(0))).days if m else None
        except ValueError:
            age = None
        if age is None:
            return 1.0
        return 1.0 + RECENCY_BONUS * math.exp(-max(0, age) / RECENCY_DAYS)
    parts = e.path.lower().split("/")
    mult = 1.0
    if any(p in _SNAPSHOT_DIRS for p in parts[:-1]):
        mult *= 0.8
    if _DATED_NAME_RE.match(parts[-1]):
        mult *= 0.9
    if len(parts) == 1 or parts[-1] == "readme.md":
        mult *= 1.1
    return mult


def score_entries(entries: Sequence[Entry], qterms: List[str],
                  postings: Optional[Dict[str, dict]] = None) -> List[Scored]:
    """Rank every catalogue entry with field-boosted BM25. Opens no source file.

    Body counts come from the postings index written at index time. An entry whose postings are
    missing or whose signature differs falls back to its catalogue keywords, so a drifted postings
    file degrades ranking instead of answering from content the catalogue never vouched for.
    """
    postings = postings or {}
    qset = set(qterms)
    sup = superseded_by(entries, postings)
    docs = []
    df: Counter = Counter()
    lengths = []
    for e in entries:
        post = postings.get(e.path)
        if isinstance(post, dict) and post.get("sha") == e.sha and isinstance(post.get("tf"), dict):
            body = post["tf"]
            tf = Counter({t: float(body[t]) for t in qset if t in body})
            dl = float(post.get("len") or 0)
        else:
            tf = Counter({t: 1.0 for t in qset & set(e.keywords)})
            dl = None
        fields = {
            "name": set(terms(os.path.splitext(posixpath.basename(e.path))[0])),
            "path": set(terms(posixpath.dirname(e.path))),
            "title": set(terms(e.title)),
            "head": set(terms(" ".join(e.headings))),
            "sum": set(terms(e.summary)),
            "meta": set(terms(f"{e.kind} {e.area}")),  # catalogue `kind · area` columns
        }
        for f, boost in _FIELD_BOOSTS.items():
            for t in fields[f] & qset:
                tf[t] += boost
        docs.append((e, tf, dl))
        df.update(t for t in tf if tf[t] > 0)
        if dl:
            lengths.append(dl)
    n = max(1, len(entries))
    avgdl = (sum(lengths) / len(lengths)) if lengths else 1.0
    active = [t for t in qterms if df[t]]
    if not active or len(active) < math.ceil(0.3 * len(qterms)):
        return []
    need = max(1, math.ceil(0.4 * len(active)))
    idf = {t: math.log(1.0 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in active}
    out: List[Scored] = []
    for e, tf, dl in docs:
        matched = sum(1 for t in active if tf[t] > 0)
        if matched < need:
            continue
        norm = _BM25_K1 * (1.0 - _BM25_B + _BM25_B * ((dl or avgdl) / avgdl))
        total = sum(idf[t] * tf[t] * (_BM25_K1 + 1.0) / (tf[t] + norm) for t in active if tf[t] > 0)
        cov = matched / len(active)
        score = total * (0.5 + 0.5 * cov) * authority(e)
        if e.path in sup:
            score *= SUPERSEDED_FACTOR
        if score >= MIN_SCORE:
            out.append(Scored(e, score, matched))
    out.sort(key=lambda s: (-s.score, s.entry.path))
    return out


class _Stale(Exception):
    pass


def read_entry(root: Path, root_real: str, e: Entry) -> Tuple[str, List[str], int]:
    """Open one catalogue entry's file, verifying containment and signature."""
    p = root / e.path
    if not p.is_file() or p.is_symlink() or not inside(root_real, str(p)):
        raise _Stale(f"{e.path}: missing, symlinked, or outside root")
    try:
        if os.stat(p).st_size > MAX_FILE_BYTES:
            raise _Stale(f"{e.path}: grew beyond size cap since indexing")
        data = p.read_bytes()
    except OSError as exc:
        raise _Stale(f"{e.path}: unreadable ({exc.__class__.__name__})")
    if len(data) != e.size or sha8(data) != e.sha:
        raise _Stale(f"{e.path}: content changed since indexing")
    text = decode(data)
    return text, text.split("\n"), len(data)


_MD_LINK_RE = re.compile(r"\[([^\]\n]*)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_TICK_RE = re.compile(r"`([^`\n]{2,200})`")
_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def resolve_pointer(raw: str, src_rel: str, known: set) -> Optional[Tuple[str, str]]:
    """Map a link to a catalogue path. Purely lexical: filesystem state is checked at read time,
    so a pointer that was swapped (e.g. for a symlink) after indexing is reported stale, not hidden."""
    raw = unquote(raw.strip())
    if not raw or raw.startswith(("#", "~", "$")) or _SCHEME_RE.match(raw) or "\x00" in raw:
        return None
    path, _, frag = raw.partition("#")
    if not path or path.endswith("/"):
        return None
    for cand in (posixpath.join(posixpath.dirname(src_rel), path), path):
        cand = posixpath.normpath(cand)
        if cand.startswith("/") or cand == ".." or cand.startswith("../") or cand == ".":
            continue
        if cand in known and cand != src_rel:
            return cand, frag
    return None


def _prose_len(text: str) -> int:
    t = _MD_LINK_RE.sub(" ", text)
    t = _TICK_RE.sub(" ", t)
    keep = []
    for l in t.split("\n"):
        s = l.strip()
        if not s or s.startswith("#") or re.match(r"^\|?[\s:|-]+\|?$", s):
            continue
        keep.append(re.sub(r"[|*_>#\-]+", " ", s))
    return len(re.sub(r"\s+", " ", " ".join(keep)).strip())


def choose_pointer(ev_text: str, src_rel: str, known: set, qset: set, router: bool
                   ) -> Optional[Tuple[str, str]]:
    thin = _prose_len(ev_text) < THIN_PROSE_CHARS
    if not (thin or router):
        return None
    best: Optional[Tuple[float, int, str, str]] = None
    order = 0
    for line in ev_text.split("\n"):
        line_terms = set(terms(strip_md(line)))
        raws: List[Tuple[str, str]] = [(m.group(1), m.group(2)) for m in _MD_LINK_RE.finditer(line)]
        for m in _TICK_RE.finditer(line):
            v = m.group(1).strip()
            if re.search(r"\.(md|yml|yaml|txt)(#[^\s]*)?$", v, re.I) and "*" not in v:
                raws.append((v, v))
        for label, target in raws:
            res = resolve_pointer(target, src_rel, known)
            if res is None:
                continue
            hit = len(qset & (set(terms(label)) | set(terms(res[0])) | line_terms))
            if router and hit == 0:
                continue
            order += 1
            cand = (float(hit), -order, res[0], res[1])
            if best is None or cand[:2] > best[:2]:
                best = cand
    return (best[2], best[3]) if best else None


def extract_evidence(lines: List[str], suffix: str, qset: set, frag: str = "", bonus: str = ""
                     ) -> Optional[Tuple[int, int, str, float]]:
    sections = parse_sections(lines, suffix)
    sec, sc = None, 0.0
    if frag:
        want = slug(frag)
        for s in sections:
            if s.heading and slug(s.heading) == want:
                sec, sc = s, 1.0
                break
    if sec is None:
        sec, sc = best_section(lines, sections, qset, bonus)
    if sec is None:
        return None
    win = bound_window(lines, sec.start, sec.end, qset, bool(bonus))
    if win is None:
        return None
    return win[0], win[1], win[2], sc


def _fallback_section(lines: List[str], suffix: str, qset: set) -> Optional[Tuple[int, int, str, float]]:
    for s in parse_sections(lines, suffix):
        win = bound_window(lines, s.start, s.end, qset)
        if win and (len(lines[win[0] - 1:win[1]]) > 1 or not s.heading):
            return win[0], win[1], win[2], 0.0
    return None


def run_query(root: Path, question: str, heal: bool = True) -> Tuple[dict, int]:
    """Answer from the index. When the index is missing or has drifted from the source the answer
    would come from, rebuild it once under the writer lock and answer again (`reindexed: true`).
    A changed file is never answered from its old index; `heal=False` reports the drift instead."""
    t0 = time.perf_counter()
    payload, code = _query_once(root, question)
    if not (payload.pop("_drift", False) and heal):
        return payload, code
    try:
        cmd_index(root)
    except BrainError as exc:  # lock busy or foreign memory.md: report the drift, do not hide it
        payload["reindex_error"] = exc.error
        return payload, code
    payload, code = _query_once(root, question)
    payload.pop("_drift", None)
    payload["reindexed"] = True
    payload["elapsed_ms"] = now_ms(t0)
    return payload, code


def _query_once(root: Path, question: str) -> Tuple[dict, int]:
    t0 = time.perf_counter()
    payload: dict = {"status": "ok", "question": question, "evidence": [], "files_opened": 0,
                     "elapsed_ms": 0.0, "keywords": [], "source": None, "pointer": None,
                     "candidates": [], "opened": [], "bytes_opened": 0, "redactions": 0}

    def done(status: str, code: int, message: str = "") -> Tuple[dict, int]:
        payload["status"] = status
        if message:
            payload["message"] = message
        payload["elapsed_ms"] = now_ms(t0)
        return payload, code

    if len(question) > QUESTION_MAX:
        raise BrainError(EXIT_INVALID, "invalid_input", f"question exceeds {QUESTION_MAX} characters")
    if "\x00" in question:
        raise BrainError(EXIT_INVALID, "invalid_input", "question contains NUL")
    qterms, bonus = question_terms(question)
    payload["keywords"] = qterms
    if bonus:
        payload["intent"] = "duration"
    if not qterms:
        return done("empty_question", EXIT_OK, "no searchable keywords after stripping filler words")
    cat = load_catalogue(root)
    if cat is None:
        payload["_drift"] = True
        return done("not_indexed", EXIT_STALE, "catalogue missing or unreadable; run `brain.py index`")
    postings = load_postings(root)
    if cat.entries and not postings:
        payload["_drift"] = True  # postings missing or written by an older version
    ranked = rerank_by_section(score_entries(cat.entries, qterms, postings), qterms, postings, bonus)
    payload["candidates"] = [{"path": s.entry.path, "score": round(s.score, 3)} for s in ranked[:3]]
    if not ranked:
        return done("no_match", EXIT_OK, "no catalogue entry matched the question keywords")
    best = ranked[0]
    root_real = os.path.realpath(str(root))
    payload["source"] = {"path": best.entry.path, "title": best.entry.title,
                         "kind": best.entry.kind, "area": best.entry.area,
                         "score": round(best.score, 3)}
    newer = superseded_by(cat.entries, postings).get(best.entry.path)
    if newer:
        payload["source"]["superseded_by"] = newer
    try:
        _, lines, nbytes = read_entry(root, root_real, best.entry)
    except _Stale as exc:
        payload["_drift"] = True
        payload["stale_paths"] = [best.entry.path]
        return done("stale", EXIT_STALE, f"{exc}; run `brain.py index`")
    payload["files_opened"] = 1
    payload["opened"] = [best.entry.path]
    payload["bytes_opened"] = nbytes
    qset = set(qterms)
    suffix = os.path.splitext(best.entry.path.lower())[1]
    ev = extract_evidence(lines, suffix, qset, "", bonus)
    if ev is None:
        return done("no_match", EXIT_OK,
                    f"{best.entry.path} matched on metadata but no section contains the keywords")
    s, e, text, _ = ev
    text, nred = redact(text)
    payload["redactions"] += nred
    payload["evidence"].append({"path": best.entry.path, "start_line": s, "end_line": e, "text": text})
    known = {x.path for x in cat.entries}
    ptr = choose_pointer("\n".join(lines[s - 1:e]), best.entry.path, known, qset,
                         best.entry.kind == "router")
    if ptr:
        target, frag = ptr
        tentry = next(x for x in cat.entries if x.path == target)
        try:
            _, tlines, tbytes = read_entry(root, root_real, tentry)
        except _Stale as exc:
            payload["_drift"] = True
            payload["pointer_status"] = "stale"
            payload["message"] = f"pointer skipped: {exc}"
        else:
            payload["files_opened"] = 2
            payload["opened"].append(target)
            payload["bytes_opened"] += tbytes
            tsuffix = os.path.splitext(target.lower())[1]
            tev = extract_evidence(tlines, tsuffix, qset, frag) or _fallback_section(tlines, tsuffix, qset)
            payload["pointer"] = target
            if tev:
                ptext, nred = redact(tev[2])
                payload["redactions"] += nred
                payload["evidence"].append({"path": target, "start_line": tev[0],
                                            "end_line": tev[1], "text": ptext})
                payload["pointer_status"] = "followed"
            else:
                payload["pointer_status"] = "empty"
    return done("ok", EXIT_OK)


# --------------------------------------------------------------------------- #
# remember
# --------------------------------------------------------------------------- #

_CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _line_field(name: str, value: str, limit: int) -> str:
    if not isinstance(value, str):
        raise BrainError(EXIT_INVALID, "invalid_input", f"{name} must be text")
    v = value.strip()
    if not v:
        raise BrainError(EXIT_INVALID, "invalid_input", f"{name} must not be empty")
    if "\n" in v or "\r" in v or _CTRL_RE.search(v):
        raise BrainError(EXIT_INVALID, "invalid_input", f"{name} must be a single line without control characters")
    if len(v) > limit:
        raise BrainError(EXIT_INVALID, "invalid_input", f"{name} exceeds {limit} characters")
    return v


def validate_memory(title: str, summary: str, body: str) -> Tuple[str, str, str]:
    t = _line_field("title", title, TITLE_MAX)
    s = _line_field("summary", summary, SUMMARY_MAX)
    if not isinstance(body, str):
        raise BrainError(EXIT_INVALID, "invalid_input", "body must be text")
    b = body.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not b:
        raise BrainError(EXIT_INVALID, "invalid_input", "body must not be empty")
    if _CTRL_RE.search(b):
        raise BrainError(EXIT_INVALID, "invalid_input", "body contains control characters")
    if len(b) > BODY_MAX:
        raise BrainError(EXIT_INVALID, "invalid_input", f"body exceeds {BODY_MAX} characters")
    for label, v in (("title", t), ("summary", s), ("body", b)):
        if has_hard_secret(v):
            raise BrainError(EXIT_INVALID, "secret_refused",
                             f"{label} looks like it contains a credential; refusing to store it")
    return t, s, b


def make_slug(title: str) -> str:
    s = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:48].strip("-")
    return s or "memory"


def _memory_text(title: str, summary: str, body: str, stamp: str, supersedes: Sequence[str] = ()) -> str:
    sup = f"_Supersedes: {', '.join(supersedes)}_\n" if supersedes else ""
    return f"# {title}\n\n> {summary}\n\n_Saved: {stamp}_\n{sup}\n{body}\n"


def validate_supersedes(ids: Sequence[str]) -> List[str]:
    out = sorted(set(ids))
    if len(out) > SUPERSEDES_MAX:
        raise BrainError(EXIT_INVALID, "invalid_input", f"at most {SUPERSEDES_MAX} --supersedes ids")
    for mid in out:
        if not _MEMORY_ID_RE.match(mid):
            raise BrainError(EXIT_INVALID, "invalid_input",
                             "--supersedes takes a memory id such as 2026-11-09-nebulizer-settings")
    return out


def cmd_remember(root: Path, title: str, summary: str, body: str,
                 supersedes: Sequence[str] = ()) -> Tuple[dict, int]:
    t0 = time.perf_counter()
    title, summary, body = validate_memory(title, summary, body)
    sup = validate_supersedes(supersedes)
    now = datetime.now(timezone.utc)
    with WriterLock(brain_dir(root)):
        ensure_memory_index_writable(root)
        recovered = recover_tmp(root)
        if load_catalogue(root) is None:
            _index_locked(root)  # first use: build the full catalogue in the same critical section
        cat = load_catalogue(root)
        assert cat is not None
        postings = load_postings(root)
        mdir = memories_dir(root)
        mdir.mkdir(parents=True, exist_ok=True)
        for mid in sup:
            if not (mdir / f"{mid}.md").is_file():
                raise BrainError(EXIT_INVALID, "invalid_input", f"--supersedes: no memory with id {mid}")
        base = f"{now:%Y-%m-%d}-{make_slug(title)}"
        name, n = f"{base}.md", 1
        while (mdir / name).exists():
            n += 1
            name = f"{base}-{n}.md"
        path = mdir / name
        atomic_write(path, _memory_text(title, summary, body, f"{now:%Y-%m-%dT%H:%M:%SZ}", sup))
        # Reconcile: adopt orphan memory files (crash between the two writes) and drop dangling lines.
        on_disk = {relposix(root, str(p)): p for p in memory_files(root)}
        entries = [e for e in cat.entries if e.kind != "memory" or e.path in on_disk]
        have = {e.path for e in entries if e.kind == "memory"}
        adopted = 0
        for rel, p in on_disk.items():
            if rel not in have:
                entry, post = memory_entry(root, p)
                entries.append(entry)
                postings[entry.path] = post
                adopted += 1
        text = render_catalogue(entries)
        kept = {e.path for e in entries}
        postings = {p: v for p, v in postings.items() if p in kept}
        write_postings(root, postings)
        atomic_write(catalogue_path(root), text)
        write_memory_index(root, memory_index_text(root))
    rel = relposix(root, str(path))
    return {
        "status": "saved", "id": path.stem, "path": rel,
        "catalogue": relposix(root, str(catalogue_path(root))), "memory_index": MEMORY_INDEX_NAME,
        "indexed": True, "supersedes": sup,
        "adopted_orphans": max(0, adopted - 1), "recovered_tmp_files": recovered,
        "elapsed_ms": now_ms(t0),
    }, EXIT_OK


# --------------------------------------------------------------------------- #
# check
# --------------------------------------------------------------------------- #


def cmd_check(root: Path) -> Tuple[dict, int]:
    t0 = time.perf_counter()
    problems: List[dict] = []

    def add(kind: str, path: str, detail: str) -> None:
        problems.append({"kind": kind, "path": path, "detail": detail})

    cat = load_catalogue(root)
    counts = {"sources": 0, "memories": 0, "catalogue_bytes": 0}
    if cat is None:
        add("not_indexed", relposix(root, str(catalogue_path(root))), "catalogue missing or unreadable")
        return {"status": "problems", "problems": problems, "counts": counts,
                "elapsed_ms": now_ms(t0)}, EXIT_PROBLEMS
    counts["sources"] = sum(1 for e in cat.entries if e.kind != "memory")
    counts["memories"] = sum(1 for e in cat.entries if e.kind == "memory")
    counts["catalogue_bytes"] = cat.size
    postings = load_postings(root)
    for e in cat.entries:
        post = postings.get(e.path)
        if not isinstance(post, dict) or post.get("sha") != e.sha:
            add("postings_drift", e.path, "postings index missing or out of date; run `brain.py index`")
    for ln, text in cat.bad_lines:
        add("bad_line", f"{relposix(root, str(catalogue_path(root)))}:{ln}", text)
    root_real = os.path.realpath(str(root))
    seen: Dict[str, int] = Counter()
    for e in cat.entries:
        seen[e.path] += 1
        try:
            read_entry(root, root_real, e)
        except _Stale as exc:
            kind = "dangling_entry" if not (root / e.path).exists() else "stale_sig"
            add(kind, e.path, str(exc))
    for path, n in seen.items():
        if n > 1:
            add("duplicate_entry", path, f"{n} catalogue lines")
    cands, _ = scan_candidates(root)
    router_known = {e.path for e in cat.entries}
    # Files eligible by policy but absent from the catalogue (duplicate-content files are expected absent).
    hashes = {}
    for e in cat.entries:
        hashes[(e.size, e.sha)] = e.path
    for c in cands:
        if c.rel in router_known:
            continue
        try:
            data = Path(c.abs).read_bytes()
        except OSError:
            continue
        if b"\x00" in data or has_hard_secret(decode(data)):
            continue
        if (len(data), sha8(data)) in hashes:
            continue
        add("unindexed_source", c.rel, "eligible file missing from catalogue; run `brain.py index`")
    for e in cat.entries:
        if e.kind == "memory":
            continue
        base = posixpath.basename(e.path)
        reason = file_exclusion(e.path, base, e.size)
        parts = e.path.split("/")
        d_reason = None
        for i in range(1, len(parts)):
            d_reason = dir_exclusion("/".join(parts[:i]), parts[i - 1])
            if d_reason:
                break
        if reason or d_reason:
            add("excluded_in_catalogue", e.path, f"policy now excludes this path ({reason or d_reason})")
    on_disk = {relposix(root, str(p)) for p in memory_files(root)}
    in_cat = {e.path for e in cat.entries if e.kind == "memory"}
    for rel in sorted(on_disk - in_cat):
        add("orphan_memory", rel, "memory file has no catalogue line; next `remember` or `index` adopts it")
    for rel in sorted(in_cat - on_disk):
        add("dangling_entry", rel, "catalogue line for a memory file that does not exist")
    for p in stray_tmp_files(root):
        add("stray_tmp", relposix(root, str(p)), "interrupted write; next writer command removes it")
    current = _read_memory_index(root)
    if current is None:
        add("memory_index_drift", MEMORY_INDEX_NAME, "memory index missing or unreadable; run `brain.py index`")
    elif current.strip() and MEMORY_INDEX_MARKER not in current:
        add("memory_index_foreign", MEMORY_INDEX_NAME, "not generated by brain.py; index and remember refuse to overwrite it")
    elif current != memory_index_text(root):
        add("memory_index_drift", MEMORY_INDEX_NAME, "memory index out of date; run `brain.py index`")
    return {"status": "problems" if problems else "ok", "problems": problems, "counts": counts,
            "elapsed_ms": now_ms(t0)}, (EXIT_PROBLEMS if problems else EXIT_OK)


# --------------------------------------------------------------------------- #
# benchmark
# --------------------------------------------------------------------------- #

BENCH_DISCLAIMER = (
    "PROXY MEASUREMENT ONLY. Sizes are UTF-8 bytes; 'token proxy' = ceil(bytes/4). This is NOT a Claude "
    "/context reading and NOT billing. The baseline is a deterministic keyword scan that reads the top-K "
    "files whole; it is not a real default Claude session. Elapsed times measure this Python process only, "
    "with no model latency on either side. Answer correctness means an expected string from the question "
    "file appears in the text each side would hand to a model.")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).casefold()


def baseline_scan(root: Path, qterms: List[str], top_k: int) -> dict:
    t0 = time.perf_counter()
    cands, _ = scan_candidates(root)
    paths = [(c.rel, c.abs) for c in cands]
    paths += [(relposix(root, str(p)), str(p)) for p in memory_files(root)]
    qset = set(qterms)
    scored = []
    scanned_bytes = 0
    for rel, ab in paths:
        try:
            data = Path(ab).read_bytes()
        except OSError:
            continue
        scanned_bytes += len(data)
        if b"\x00" in data:
            continue
        counts = Counter(terms(decode(data)))
        distinct = len(qset & set(counts))
        if distinct:
            scored.append((-distinct, -sum(counts[t] for t in qset), rel, data))
    scored.sort(key=lambda x: (x[0], x[1], x[2]))
    top = scored[:top_k]
    return {
        "files_opened": len(paths),
        "bytes_scanned": scanned_bytes,
        "files_read_whole": [t[2] for t in top],
        "model_context_bytes": sum(len(t[3]) for t in top),
        "text": "\n".join(decode(t[3]) for t in top),
        "elapsed_ms": now_ms(t0),
    }


def cmd_benchmark(root: Path, questions_file: Optional[str], repeat: int, top_k: int) -> Tuple[dict, int]:
    t0 = time.perf_counter()
    qpath = Path(questions_file) if questions_file else brain_dir(root) / DEFAULT_QUESTIONS_NAME
    if not qpath.is_file():
        raise BrainError(EXIT_INVALID, "invalid_input", f"question file not found: {qpath}")
    try:
        spec = json.loads(qpath.read_text(encoding="utf-8"))
        questions = spec["questions"] if isinstance(spec, dict) else spec
        assert isinstance(questions, list) and questions
        for q in questions:
            assert isinstance(q["id"], str) and isinstance(q["question"], str)
            assert isinstance(q["expect_any"], list) and q["expect_any"]
    except (OSError, ValueError, KeyError, TypeError, AssertionError):
        raise BrainError(EXIT_INVALID, "invalid_input",
                         "question file must be JSON {questions:[{id,question,expect_any:[...]}]}")
    if load_catalogue(root) is None:
        raise BrainError(EXIT_STALE, "not_indexed", "catalogue missing; run `brain.py index` first")
    results = []
    for q in questions:
        b_runs, d_runs = [], []
        b_payload, d_payload = None, None
        for _ in range(repeat):
            ts = time.perf_counter()
            bp, _code = run_query(root, q["question"])
            b_runs.append((time.perf_counter() - ts) * 1000.0)
            b_payload = b_payload or bp
            d = baseline_scan(root, unique(terms(q["question"])), top_k)
            d_runs.append(d["elapsed_ms"])
            d_payload = d_payload or d
        assert b_payload is not None and d_payload is not None
        expect = [_norm(x) for x in q["expect_any"]]
        b_text = _norm("\n".join(e["text"] for e in b_payload["evidence"]))
        d_text = _norm(d_payload.pop("text"))
        b_bytes = sum(len(e["text"].encode("utf-8")) for e in b_payload["evidence"])
        exp_paths = q.get("expected_paths") or []
        results.append({
            "id": q["id"], "question": q["question"], "technical": bool(q.get("technical", False)),
            "category": q.get("category", ""),
            "brain": {
                "status": b_payload["status"],
                "answer_found": any(x in b_text for x in expect),
                "files_opened": b_payload["files_opened"],
                "bytes_opened": b_payload["bytes_opened"],
                "model_context_bytes": b_bytes,
                "token_proxy": math.ceil(b_bytes / 4),
                "elapsed_ms_median": round(statistics.median(b_runs), 2),
                "source_path": (b_payload["source"] or {}).get("path"),
                "pointer": b_payload["pointer"],
                "expected_path_hit": (None if not exp_paths else
                                      any(e["path"] in exp_paths for e in b_payload["evidence"])),
            },
            "baseline": {
                "answer_found": any(x in d_text for x in expect),
                "files_opened": d_payload["files_opened"],
                "bytes_opened": d_payload["bytes_scanned"],
                "files_read_whole": d_payload["files_read_whole"],
                "model_context_bytes": d_payload["model_context_bytes"],
                "token_proxy": math.ceil(d_payload["model_context_bytes"] / 4),
                "elapsed_ms_median": round(statistics.median(d_runs), 2),
            },
        })

    def totals(rows: List[dict]) -> dict:
        if not rows:
            return {"questions": 0}
        bb = sum(r["brain"]["model_context_bytes"] for r in rows)
        db = sum(r["baseline"]["model_context_bytes"] for r in rows)
        return {
            "questions": len(rows),
            "brain_answer_found": sum(r["brain"]["answer_found"] for r in rows),
            "baseline_answer_found": sum(r["baseline"]["answer_found"] for r in rows),
            "brain_model_context_bytes": bb, "baseline_model_context_bytes": db,
            "brain_token_proxy": math.ceil(bb / 4), "baseline_token_proxy": math.ceil(db / 4),
            "context_ratio_baseline_over_brain": round(db / bb, 2) if bb else None,
            "brain_bytes_opened": sum(r["brain"]["bytes_opened"] for r in rows),
            "baseline_bytes_opened": sum(r["baseline"]["bytes_opened"] for r in rows),
            "brain_files_opened": sum(r["brain"]["files_opened"] for r in rows),
            "baseline_files_opened": sum(r["baseline"]["files_opened"] for r in rows),
            "brain_elapsed_ms_median_per_question": round(statistics.median(r["brain"]["elapsed_ms_median"] for r in rows), 2),
            "baseline_elapsed_ms_median_per_question": round(statistics.median(r["baseline"]["elapsed_ms_median"] for r in rows), 2),
            "brain_cheaper_questions": sum(
                1 for r in rows if r["brain"]["model_context_bytes"] < r["baseline"]["model_context_bytes"]),
        }

    return {
        "status": "ok", "disclaimer": BENCH_DISCLAIMER, "questions_file": str(qpath),
        "repeat": repeat, "baseline_files": top_k,
        "totals": totals(results),
        "totals_technical_only": totals([r for r in results if r["technical"]]),
        "results": results, "elapsed_ms": now_ms(t0),
    }, EXIT_OK


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):  # JSON-friendly, never prints usage to stdout
        raise BrainError(EXIT_INVALID, "invalid_arguments", message)


def default_root() -> Path:
    """Nearest ancestor of the working directory that holds second-brain/; else the script's parent."""
    cwd = Path.cwd().resolve()
    for d in (cwd, *cwd.parents):
        if (d / BRAIN_DIRNAME / "brain.py").is_file():
            return d
    return Path(__file__).resolve().parent.parent


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="brain.py", description="Deterministic second brain (JSON output).")
    p.add_argument("--root", default=None, help="workspace root (default: nearest ancestor of the cwd containing second-brain/, else the parent of this script's folder)")
    common = _Parser(add_help=False)
    common.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=_Parser)
    sub.add_parser("index", parents=[common], help="rebuild the catalogue from curated sources + memories")
    q = sub.add_parser("query", parents=[common], help="answer from the best single source")
    q.add_argument("question")
    q.add_argument("--no-reindex", action="store_true",
                   help="report a missing or drifted index (exit 3) instead of rebuilding it")
    r = sub.add_parser("remember", parents=[common], help="save a plain-markdown memory and index it")
    r.add_argument("--title", required=True)
    r.add_argument("--summary", required=True)
    r.add_argument("--body", required=True)
    r.add_argument("--supersedes", action="append", default=[], metavar="MEMORY_ID",
                   help="id of a memory this one replaces (repeatable); the old one then scores at half")
    sub.add_parser("check", parents=[common], help="verify catalogue, files, and memories agree")
    b = sub.add_parser("benchmark", parents=[common], help="proxy comparison vs deterministic file scan")
    b.add_argument("--questions", default=None)
    b.add_argument("--repeat", type=int, default=3)
    b.add_argument("--baseline-files", type=int, default=3)
    return p


_VALUE_OPTS = {"--title", "--summary", "--body", "--questions", "--root", "--supersedes"}


def _glue_values(argv: List[str]) -> List[str]:
    """Turn `--body -x` into `--body=-x` so values starting with '-' are accepted."""
    out, i = [], 0
    while i < len(argv):
        a = argv[i]
        if a in _VALUE_OPTS and i + 1 < len(argv):
            out.append(f"{a}={argv[i + 1]}")
            i += 2
            continue
        out.append(a)
        i += 1
    return out


def run(argv: Optional[Sequence[str]] = None) -> Tuple[dict, int]:
    args_in = _glue_values(list(sys.argv[1:] if argv is None else argv))
    try:
        ns = build_parser().parse_args(args_in)
        root = Path(ns.root).expanduser().resolve() if ns.root else default_root()
        if not root.is_dir():
            raise BrainError(EXIT_INVALID, "invalid_input", f"root is not a directory: {root}")
        if ns.cmd == "index":
            return cmd_index(root)
        if ns.cmd == "query":
            return run_query(root, ns.question, heal=not ns.no_reindex)
        if ns.cmd == "remember":
            return cmd_remember(root, ns.title, ns.summary, ns.body, ns.supersedes)
        if ns.cmd == "check":
            return cmd_check(root)
        if ns.repeat < 1 or ns.repeat > 20 or ns.baseline_files < 1 or ns.baseline_files > 10:
            raise BrainError(EXIT_INVALID, "invalid_input", "--repeat must be 1-20 and --baseline-files 1-10")
        return cmd_benchmark(root, ns.questions, ns.repeat, ns.baseline_files)
    except BrainError as exc:
        return {"status": "error", "error": exc.error, "message": exc.message}, exc.code
    except Exception as exc:  # noqa: BLE001 - CLI boundary: report, never traceback to the caller
        return {"status": "error", "error": "internal",
                "message": f"{exc.__class__.__name__}: {exc}"}, EXIT_PROBLEMS


def main(argv: Optional[Sequence[str]] = None) -> int:
    payload, code = run(argv)
    with contextlib.suppress(AttributeError, ValueError):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    sys.stdout.flush()
    return code


if __name__ == "__main__":
    sys.exit(main())
