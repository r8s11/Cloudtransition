"""
Career Dashboard — FastAPI app that reads workspace YAML/MD files directly.

Run:  uvicorn app:app --reload
Open: http://localhost:8000
"""

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import yaml
from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import interview_editor as ie
import workspace_content as wc
from agents import build_agents_view


def _load_env_file(path: Path, environ: dict[str, str] | None = None) -> None:
    """Load KEY=VALUE lines from a local .env without overriding real env vars.

    The dashboard runs under launchd with its own environment, so a
    gitignored dashboard-app/.env is where local keys such as
    OPENROUTER_API_KEY belong.
    """
    target = os.environ if environ is None else environ
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        target.setdefault(key, value)


_load_env_file(Path(__file__).resolve().parent / ".env")

# ── Paths ──────────────────────────────────────────────────────
WORKSPACE = Path(__file__).resolve().parent.parent  # Cloudtransition/
SKILLS_FILE = WORKSPACE / "skills" / "skills-inventory.yml"
GOALS_FILE = WORKSPACE / "goals" / "career-goals.yml"
JOBS_FILE = WORKSPACE / "interviews" / "job-applications.yml"
NETWORK_FILE = WORKSPACE / "networking" / "contacts.yml"
TASKS_FILE = WORKSPACE / "TASKS.md"
EDU_FILE = WORKSPACE / "College Planning" / "education-data.yml"
BOOKS_FILE = WORKSPACE / "Books" / "books-data.yml"

# ── Connected systems (dashboard-as-shell) ─────────────────────
SECOND_BRAIN_FILE = WORKSPACE / "robonugget-second-brain-app" / "index.html"
MISSION_CONTROL_UPSTREAM = "http://127.0.0.1:8787"
MISSION_CONTROL_TIMEOUT = 3  # seconds

# ── Verified washi palette ────────────────────────────────────
# Hues that hold WCAG AA text contrast on the paper surfaces. Data-supplied
# colors (books YAML, project metadata) are mapped onto these so tinted
# backgrounds, fills, and accents never fall back to an unchecked hex.
SAFE_HUES = {
    "vermilion": "#b3212e",
    "green": "#356844",
    "blue": "#38618c",
    "purple": "#6f58a8",
    "red": "#a8322c",
    "yellow": "#7b580e",
    "teal": "#27686a",
    "sage": "#3f7d54",
    "ink-muted": "#554d41",
}

SAFE_HUE_MAP = {
    "#d97757": SAFE_HUES["vermilion"],
    "#c87dff": SAFE_HUES["purple"],
    "#e05555": SAFE_HUES["red"],
    "#5cc98a": SAFE_HUES["green"],
    "#0078d4": SAFE_HUES["blue"],
    "#61dafb": SAFE_HUES["blue"],
    "#e0b840": SAFE_HUES["yellow"],
    "#9478d4": SAFE_HUES["purple"],
    "#7c5cbf": SAFE_HUES["purple"],
    "#3aa8c1": SAFE_HUES["teal"],
    "#4a7fb5": SAFE_HUES["blue"],
    "#5a9fd4": SAFE_HUES["blue"],
    "#4a9e6e": SAFE_HUES["green"],
    "#c9a227": SAFE_HUES["yellow"],
    "#c44d4d": SAFE_HUES["red"],
    "#888": SAFE_HUES["ink-muted"],
    "#888888": SAFE_HUES["ink-muted"],
}


def safe_hue(value: str | None) -> str:
    """Map a data-supplied color onto the verified washi palette."""
    return SAFE_HUE_MAP.get((value or "").strip().lower(), SAFE_HUES["ink-muted"])


# ── Realm Configuration ───────────────────────────────────────
REALMS = [
    {
        "id": "tasks",
        "name": "Tasks",
        "file": "TASKS.md",
        "color": SAFE_HUES["vermilion"],
        "icon": "📋",
    },
    {
        "id": "year-plan",
        "name": "Year Plan",
        "file": "plans/year-plan-2026-2027.md",
        "color": SAFE_HUES["purple"],
        "icon": "🗓️",
    },
    {
        "id": "eng190",
        "name": "ENG-190",
        "file": "College Planning/eng190-tracker.md",
        "color": SAFE_HUES["red"],
        "icon": "📝",
    },
    {
        "id": "regeneron",
        "name": "Regeneron",
        "file": "plans/regeneron-cloud-devops-roadmap_2.md",
        "color": SAFE_HUES["green"],
        "icon": "🔧",
    },
    {
        "id": "sc900",
        "name": "SC-900",
        "file": "plans/sc900-study-plan.md",
        "color": SAFE_HUES["blue"],
        "icon": "🛡️",
    },
    {
        "id": "azure",
        "name": "Azure AZ-204",
        "file": "plans/azure-az204-plan.md",
        "color": SAFE_HUES["blue"],
        "icon": "☁️",
    },
    {
        "id": "devops",
        "name": "DevOps Plan",
        "file": "plans/devops-learning-plan.md",
        "color": SAFE_HUES["green"],
        "icon": "⚙️",
    },
    {
        "id": "books",
        "name": "Books",
        "file": "plans/books-reading-plan.md",
        "color": SAFE_HUES["purple"],
        "icon": "📚",
    },
    {
        "id": "react",
        "name": "React",
        "file": "plans/react_plan.md",
        "color": SAFE_HUES["blue"],
        "icon": "⚛️",
    },
    {
        "id": "sql",
        "name": "SQL",
        "file": "plans/sql_plan.md",
        "color": SAFE_HUES["yellow"],
        "icon": "🗄️",
    },
    {
        "id": "prompts",
        "name": "Future Prompts",
        "file": "prompts/todo-prompts.md",
        "color": SAFE_HUES["purple"],
        "icon": "💡",
    },
    {
        "id": "az104",
        "name": "AZ-104",
        "file": "plans/az104-study-plan.md",
        "color": SAFE_HUES["red"],
        "icon": "🎓",
    },
    {
        "id": "college",
        "name": "College",
        "file": "College Planning/education-plan.md",
        "color": SAFE_HUES["teal"],
        "icon": "🏫",
    },
]

# ── App ────────────────────────────────────────────────────────
app = FastAPI(title="Career Dashboard")
app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


# ── YAML Loader ────────────────────────────────────────────────
def load_yaml(path: Path) -> dict:
    """Load a YAML file, return empty dict if missing or invalid."""
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


# ── Task Parser ────────────────────────────────────────────────
CHECKBOX_RE = re.compile(r"^(\s*- \[)([ xX])(\] .+)$")


def parse_tasks_from_file(path: Path, realm_id: str) -> list[dict]:
    """Parse checklist items from any markdown file, preserving line numbers."""
    if not path.exists():
        return []

    items = []
    current_category = ""
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        stripped = line.strip()

        # Track nearest heading (any level) as category
        if stripped.startswith("#"):
            current_category = stripped.lstrip("#").strip()
            # Remove emoji prefixes
            current_category = re.sub(
                r"^[\U0001F300-\U0001FAFF\u2600-\u27BF\u2702-\u27B0]+\s*",
                "",
                current_category,
            ).strip()
            continue

        m = CHECKBOX_RE.match(line)
        if m:
            done = m.group(2) in ("x", "X")
            text = m.group(3)[2:]  # strip "] " prefix
            items.append(
                {
                    "text": text,
                    "cat": current_category,
                    "done": done,
                    "realm": realm_id,
                    "line": lineno,
                }
            )

    return items


def parse_all_realms() -> dict:
    """Parse tasks across all realms, returning structured data."""
    all_items = []
    realm_stats = []

    for realm in REALMS:
        path = WORKSPACE / realm["file"]
        items = parse_tasks_from_file(path, realm["id"])
        active = [i for i in items if not i["done"]]
        done = [i for i in items if i["done"]]
        realm_stats.append(
            {
                **realm,
                "total": len(items),
                "done_count": len(done),
                "active_count": len(active),
                "pct": round(len(done) / len(items) * 100) if items else 0,
            }
        )
        all_items.extend(items)

    active = [i for i in all_items if not i["done"]]
    done = [i for i in all_items if i["done"]]
    return {
        "active": active,
        "done": done,
        "all": all_items,
        "realm_stats": realm_stats,
        "total": len(all_items),
        "total_done": len(done),
        "total_active": len(active),
    }


class ToggleRequest(BaseModel):
    realm: str
    line: int
    done: bool
    # Task text as rendered. Lines shift when a capture or an outside edit lands
    # after the page loaded; the text lets the server find the item again.
    text: str | None = None


# ── Inbox capture ─────────────────────────────────────────────
INBOX_HEADING = "## Inbox"
CAPTURE_MAX = 300


class CaptureRequest(BaseModel):
    text: str


def insert_inbox_item(source: str, item: str) -> tuple[str, int]:
    """Append `- [ ] item` to the `## Inbox` section of a markdown file.

    Creates the section just above `## Active` (or at the end) when missing.
    Returns the new text and the 1-based line number of the inserted item.
    """
    lines = source.splitlines()
    entry = f"- [ ] {item}"
    start = next((i for i, ln in enumerate(lines) if ln.strip() == INBOX_HEADING), None)
    if start is None:
        at = next(
            (i for i, ln in enumerate(lines) if ln.strip() == "## Active"), len(lines)
        )
        block = [INBOX_HEADING, "", entry, ""]
        if at and lines[at - 1].strip():
            block.insert(0, "")
        lines[at:at] = block
        return "\n".join(lines) + "\n", at + block.index(entry) + 1

    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("#")),
        len(lines),
    )
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    if end == start + 1:  # empty section: keep a blank line under the heading
        lines[end:end] = ["", entry]
        return "\n".join(lines) + "\n", end + 2
    lines.insert(end, entry)
    return "\n".join(lines) + "\n", end + 1


# One writer at a time for workspace markdown: toggle and capture both
# read-modify-write TASKS.md, and FastAPI runs sync handlers in a thread pool.
_FILE_WRITE_LOCK = threading.Lock()


def _atomic_write(target: Path, text: str) -> None:
    """Temp-file + os.replace: a crash mid-write never corrupts the source."""
    with tempfile.NamedTemporaryFile(
        "w", dir=target.parent, delete=False, suffix=".tmp"
    ) as tf:
        tf.write(text)
    os.replace(tf.name, target)


# ── Week Computation ──────────────────────────────────────────
def current_week_of_year(today: date | None = None) -> int:
    """Return the 1-indexed week of the current calendar year (1..53).

    Replaces the old DASHBOARD.md "(Week N)" parser. Now derived from the
    current date so progress bars stay correct without manual edits.
    """
    today = today or date.today()
    return today.isocalendar().week


# ── Routine Folds ────────────────────────────────────────────
WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

DEFAULT_ROUTINE = {
    "workday": "Job search + career portfolio",
    "project": "Alternating build",
    "devops": "Automation build",
    "weekend": "Money + review",
}


def parse_routine_slots() -> dict:
    """Extract the 'What' column of routine.md's working-rhythm table.

    Falls back to the default weekly plan if routine.md is missing or the
    markdown table cannot be read. The folds stay honest to the source file.
    """
    slots = dict(DEFAULT_ROUTINE)
    path = WORKSPACE / "routine.md"
    if not path.exists():
        return slots
    try:
        in_rhythm = False
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if "working rhythm" in stripped.lower():
                in_rhythm = True
                continue
            if in_rhythm and stripped.startswith("|"):
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                if len(cells) < 2:
                    continue
                slot = cells[0].lower()
                # skip header row and the separator row
                if slot == "slot" or all(ch in "-:" for ch in slot):
                    continue
                what = cells[1].strip()
                if not what or what.lower() == "what":
                    continue
                if "workday" in slot:
                    slots["workday"] = what
                elif "project" in slot:
                    slots["project"] = what
                elif "devops" in slot:
                    slots["devops"] = what
                elif "weekend" in slot:
                    slots["weekend"] = what
    except (OSError, UnicodeDecodeError):
        pass
    return slots


def _routine_sections(lines: list[str]) -> dict[str, list[tuple[int, str]]]:
    sections: dict[str, list[tuple[int, str]]] = {}
    current: str | None = None
    for line_number, line in enumerate(lines, start=1):
        heading = re.match(r"^##\s+(.+?)\s*$", line.strip())
        if heading:
            title = heading.group(1).strip()
            current = (
                "weekly review"
                if re.match(r"^Weekly Review(?:\s|\()", title, re.IGNORECASE)
                else title.casefold()
            )
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append((line_number, line))
    return sections


def _routine_plain_text(value: str) -> str:
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    return re.sub(r"\*\*|__|~~|`", "", value).strip()


def _routine_table(
    rows: list[tuple[int, str]], min_cells: int
) -> list[list[str]]:
    result = []
    for _, line in rows:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < min_cells or cells[0].casefold() in {"slot", "date"}:
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        result.append([_routine_plain_text(cell) for cell in cells])
    return result


def _routine_review_items(lines: list[str]) -> list[dict]:
    items = []
    for line_number, line in _routine_sections(lines).get("weekly review", []):
        match = CHECKBOX_RE.match(line.rstrip("\r\n"))
        if not match:
            continue
        text = match.group(3)[2:]
        items.append(
            {
                "text": text,
                "display_text": _routine_plain_text(text),
                "cat": "Weekly Review",
                "done": match.group(2) in ("x", "X"),
                "realm": "routine",
                "line": line_number,
            }
        )
    return items


def parse_routine_view(today: date, path: Path | None = None) -> dict:
    """Parse the Today routine panel from the live routine.md source."""
    path = path or WORKSPACE / "routine.md"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return {"available": False, "message": "routine.md was not found."}
    except (OSError, UnicodeDecodeError):
        return {"available": False, "message": "routine.md could not be read."}

    sections = _routine_sections(lines)
    rhythm_section = next(
        (
            rows
            for name, rows in sections.items()
            if name.endswith("working rhythm")
        ),
        [],
    )
    rhythm_rows = _routine_table(rhythm_section, 3)
    rhythm_summary = [
        _routine_plain_text(line.strip())
        for _, line in rhythm_section
        if line.strip()
        and not line.strip().startswith("|")
        and not re.match(r"^#{1,6}\s+", line.strip())
        and not re.fullmatch(r"(?:-{3,}|_{3,}|\*{3,})", line.strip())
    ]
    if today.weekday() < 5:
        today_slots = ("workday",)
    elif today.weekday() == 5:
        today_slots = ("project", "devops")
    else:
        today_slots = ("weekend",)
    rhythm = [
        {
            "slot": row[0],
            "what": row[1],
            "notes": row[2],
            "is_today": any(token in row[0].casefold() for token in today_slots),
        }
        for row in rhythm_rows
    ]

    updated = None
    context = ""
    for line in lines:
        if updated is None:
            match = re.match(r"^\s*_Last updated:\s*(.+?)_\s*$", line)
            if match:
                updated = match.group(1)
        match = re.match(r"^\s*\*\*Current context:\*\*\s*(.+)$", line)
        if match:
            context = _routine_plain_text(match.group(1))

    rules = []
    for _, line in sections.get("rules", []):
        match = re.match(r"^\s*\d+\.\s+(.+)$", line)
        if match:
            rules.append(_routine_plain_text(match.group(1)))

    return {
        "available": True,
        "updated": updated,
        "context": context,
        "rhythm": rhythm,
        "rhythm_summary": rhythm_summary,
        "review": _routine_review_items(lines),
        "rules": rules,
        "dates": _routine_table(sections.get("key dates ahead", []), 3),
    }


def parse_routine_folds(today: date | None = None) -> list[dict]:
    """Map this week's routine to numbered fold steps.

    Mon-Fri: Workday folds. Sat: project block (Week A/B by ISO parity) and
    DevOps block. Sun: weekend money + review. The gold dot marks today —
    the first fold whose weekday matches the current date is the active step.
    """
    today = today or date.today()
    week_no = today.isocalendar().week
    week_a = week_no % 2 == 1
    project_side = "Week A — IT Mgmt Playbook" if week_a else "Week B — Bogatyr"
    slots = parse_routine_slots()

    plan = [
        (0, f"Workday — {slots['workday']}"),
        (1, f"Workday — {slots['workday']}"),
        (2, f"Workday — {slots['workday']}"),
        (3, f"Workday — {slots['workday']}"),
        (4, f"Workday — {slots['workday']}"),
        (5, f"Project block — {project_side}"),
        (5, f"DevOps — {slots['devops']}"),
        (6, f"Weekend — {slots['weekend']}"),
    ]

    today_idx = today.weekday()  # Mon=0 .. Sun=6
    dot_placed = False
    steps = []
    for n, (day_idx, label) in enumerate(plan, start=1):
        is_today = (not dot_placed) and day_idx == today_idx
        if is_today:
            dot_placed = True
        steps.append(
            {
                "step_num": n,
                "day": WEEKDAY_NAMES[day_idx],
                "label": label,
                "is_today": is_today,
            }
        )
    return steps


# ── Today view ────────────────────────────────────────────────
NEXT_UP_COUNT = 3

# routine.md orders the work: income and the job search first (rule 1), debt is
# part of the routine (rule 6), and the bills lane — playbook/MD-102 — outranks
# DevOps extras (rule 3). TASKS.md's own security heading outranks all of it.
NEXT_UP_LANES = (
    ("security", 0),
    ("income", 1),
    ("monetization", 1),
    ("job search", 1),
    ("debt", 2),
    ("playbook", 3),
    ("md-102", 3),
    ("devops", 4),
    ("bogatyr", 5),
)
# Sections that are reference, not work: TASKS.md keeps the elapsed $3,000
# sprint as historical context, and routine.md already renders the weekly
# rhythm on this page.
NEXT_UP_REFERENCE = ("$3,000 income sprint",)
NEXT_UP_NON_WORK = ("inbox", "recurring", "someday", "waiting on")
_OTHER_LANE = 6


def _next_up_lane(category: str) -> int:
    folded = category.casefold()
    for keyword, lane in NEXT_UP_LANES:
        if keyword in folded:
            return lane
    return _OTHER_LANE


def _next_up_candidate(category: str) -> bool:
    folded = category.casefold()
    if any(folded.startswith(prefix) for prefix in NEXT_UP_NON_WORK):
        return False
    return not any(term in folded for term in NEXT_UP_REFERENCE)


def select_next_up(
    open_tasks: list[dict], today: date | None = None, count: int = NEXT_UP_COUNT
) -> list[dict]:
    """The highest-priority open TASKS.md items, ranked by routine.md's lanes.

    TASKS.md file order breaks ties. The live alternating week (routine.md:
    odd = Playbook, even = Bogatyr) decides which project leads; the other
    project waits behind DevOps.
    """
    today = today or date.today()
    week_a = today.isocalendar().week % 2 == 1
    live_project, waiting_project = ("playbook", "bogatyr") if week_a else ("bogatyr", "playbook")

    def rank(task: dict) -> int:
        folded = task["cat"].casefold()
        lane = _next_up_lane(task["cat"])
        if lane >= 3:
            if live_project in folded:
                lane = 3
            elif waiting_project in folded:
                lane = 5
        return lane

    candidates = [t for t in open_tasks if _next_up_candidate(t["cat"])]
    return sorted(candidates, key=rank)[:count]
# Run-tab tools surfaced as one-tap buttons on the Today page.
QUICK_TOOLS = ("plan-today", "triage-inbox", "brain-index")


def build_today_view(realm_tasks: dict, fold_steps: list[dict], today: date) -> dict:
    """Today page data: routine blocks, Inbox, and the top open TASKS.md items.

    TASKS.md is written in priority order, so file order is the ranking.
    """
    weekday = WEEKDAY_NAMES[today.weekday()]
    open_tasks = [t for t in realm_tasks["active"] if t["realm"] == "tasks"]
    return {
        "today_weekday": weekday,
        "today_blocks": [s["label"] for s in fold_steps if s["day"] == weekday],
        "routine": parse_routine_view(today),
        "inbox_items": [t for t in open_tasks if t["cat"] == "Inbox"],
        "next_up": select_next_up(open_tasks, today),
        "quick_tools": QUICK_TOOLS,
    }


# ── Command centre (Today): daily destinations, recent artifacts, map freshness ──
# Each source is read on its own; a failure blanks only its own section.
# To add a destination, append a row in command_centre(); to add a widget, add a
# key here and a card in templates/pages/today.html.
RECENT_ARTIFACTS = 8
INDEX_STALE_DAYS = 7
MAP_REFRESH_COMMAND = f'"{Path(__file__).parent / "venv" / "bin" / "python"}" "{wc.VIEWER_DIR / "refresh-index.py"}"'
ARTIFACT_KINDS = {
    "html": "HTML",
    "pdf": "PDF",
    "svg": "SVG",
    "png": "Image",
    "jpg": "Image",
    "jpeg": "Image",
}


def workspace_file_href(rel: str) -> str:
    return "/workspace-file/" + urllib.parse.quote(rel)


def map_index_summary(now: datetime) -> dict:
    """Snapshot facts for the Workspace map; never claims the index is live."""
    try:
        data = json.loads(wc.INDEX_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"ok": False, "reason": "Index unavailable"}
    if not isinstance(data, dict) or data.get("schemaVersion") != wc.INDEX_SCHEMA:
        return {"ok": False, "reason": "Index format outdated"}
    try:
        generated = datetime.fromisoformat(data["generated"])
        files = int(data["fileCount"])
        age_days = (now - generated).total_seconds() / 86400
    except (KeyError, TypeError, ValueError):
        return {"ok": False, "reason": "Index damaged"}
    return {
        "ok": True,
        "files": files,
        "generated": f"{generated.day} {generated:%b %Y, %H:%M}",
        "stale": age_days >= INDEX_STALE_DAYS,
    }


def recent_artifacts() -> dict:
    """Newest artifacts/ files by modification time (not authorship)."""
    try:
        rows = wc.artifact_entries()
    except OSError:
        return {"ok": False, "rows": [], "count": 0}
    items = []
    for row in rows[:RECENT_ARTIFACTS]:
        modified = datetime.fromisoformat(row["modified"])
        items.append(
            {
                **row,
                "href": workspace_file_href(row["relativePath"]),
                "kind": ARTIFACT_KINDS.get(row["extension"], row["extension"].upper()),
                "when": f"{modified.day} {modified:%b %Y}",
            }
        )
    return {"ok": True, "rows": items, "count": len(rows)}


def command_centre(
    realm_tasks: dict,
    today_view: dict,
    project_count: int,
    interview_action: dict | None = None,
) -> dict:
    now = datetime.now(timezone.utc).astimezone()
    index = map_index_summary(now)
    artifacts = recent_artifacts()
    open_count = realm_tasks["total_active"]
    blocks = today_view["today_blocks"]
    daily = []
    if interview_action:
        # Opens Interview mode for that application; the row itself carries the
        # key, so Today never has to re-read the tracker in the browser.
        daily.append(
            {
                "label": "Interview mode",
                "href": "#interviews",
                "interview_key": interview_action["key"],
                "note": interview_action["company"],
                "value": f"{interview_action['when']} \u00b7 {interview_action['date']}",
                "warn": interview_action["overdue"],
            }
        )
    daily += [
        {
            "label": "Tasks",
            "href": "#tasks",
            "value": f"{open_count} open · {len(today_view['inbox_items'])} in inbox",
        },
        {
            "label": "Routine",
            "href": workspace_file_href("routine.md"),
            "new_tab": True,
            "value": "; ".join(blocks) if blocks else "Nothing scheduled today",
            "note": "routine.md",
        },
        {
            "label": "Active projects",
            "href": "#projects",
            "value": f"{project_count} configured",
        },
        {
            "label": "Recent artifacts",
            "href": "#workspace-map",
            "map_query": "folder=artifacts",
            "value": f"{artifacts['count']} files in artifacts/"
            if artifacts["ok"]
            else "Unavailable",
        },
        {
            "label": "Workspace map",
            "href": "#workspace-map",
            "value": f"{index['files']} files · snapshot {index['generated']}"
            if index["ok"]
            else index["reason"],
            "warn": not index["ok"] or index["stale"],
        },
        {
            "label": "Metrics",
            "href": "#metrics",
            "value": "Not read here: open for live server readings",
            "placeholder": True,
        },
    ]
    return {
        "daily": daily,
        "artifacts": artifacts,
        "map_index": index,
        "map_refresh": MAP_REFRESH_COMMAND,
    }


# ── Money Data ────────────────────────────────────────────────
MONEY_CANDIDATES = [
    WORKSPACE / "finance" / "tracker.yml",
    WORKSPACE / "money" / "tracker.yml",
    WORKSPACE / "goals" / "money-goals.yml",
]


def money_available() -> bool:
    """True when a money/debt tracker exists in the workspace."""
    return any(p.exists() for p in MONEY_CANDIDATES)


# ── Build Context ─────────────────────────────────────────────
# ── Interview dashboard ───────────────────────────────────────
# interviews/job-applications.yml is the source of truth. Statuses the file
# uses today: interviewing | assessment | screening | applied | new_lead
# (rejected/withdrawn entries are closed and not shown as live work).
INTERVIEW_STATUS_ORDER = {
    "offer": 0,
    "onsite": 1,
    "interviewing": 2,
    "assessment": 3,
    "screening": 4,
    "applied": 5,
    "new_lead": 6,
}
INTERVIEW_STATUS_LABELS = {
    "offer": "Offer",
    "onsite": "Onsite",
    "interviewing": "Interviewing",
    "assessment": "Assessment",
    "screening": "Screening",
    "applied": "Applied",
    "new_lead": "New lead",
}
INTERVIEW_STATUS_BADGES = {
    "offer": "badge-done",
    "onsite": "badge-p2",
    "interviewing": "badge-status-active",
    "assessment": "badge-status-pending",
    "screening": "badge-status-planned",
    "applied": "badge-status-upcoming",
    "new_lead": "badge",
}
INTERVIEW_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
INTERVIEW_PRIORITY_BADGES = {
    "high": "badge-p1",
    "medium": "badge-p2",
    "low": "badge-p3",
}
# Everything except a bare lead has a live conversation to show first.
INTERVIEW_ACTIVE_STATUSES = ("offer", "onsite", "interviewing", "assessment", "screening", "applied")
# Closed threads stay in the file for history; Today must never point at one.
INTERVIEW_CLOSED_STATUSES = ("rejected", "withdrawn")


def _iso_text(value) -> str:
    """YAML unquoted dates parse as date objects; JSON and the template want text."""
    if not value:
        return ""
    return value.isoformat() if isinstance(value, date) else str(value)


def _inter_date(value) -> date | None:
    """An ISO date from YAML, or None — never guess from a human sentence."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _workspace_href(recorded: str) -> str:
    """A servable link for a workspace-relative file, or "" if it is missing.

    Absolute paths and `..` are refused: the tracker stores workspace paths, and
    a link should never reach outside it.
    """
    if not recorded:
        return ""
    rel = Path(str(recorded))
    if rel.is_absolute() or ".." in rel.parts:
        return ""
    if not (WORKSPACE / rel).is_file():
        return ""
    return workspace_file_href(rel.as_posix())


def _resume_href(recorded: str) -> str:
    """A servable link for a resume recorded as a path under resume/."""
    if not recorded:
        return ""
    rel = Path(str(recorded))
    if rel.is_absolute() or ".." in rel.parts:
        return ""
    if not (WORKSPACE / "resume" / rel).is_file():
        return ""
    return workspace_file_href(f"resume/{rel.as_posix()}")


def _prep_files(recorded) -> list[dict]:
    """Prep/JD files the tracker lists under `interview_prep:`.

    The tracker stores paths (interviews/Ground Up/prep.md). Only files that
    exist are linked; a recorded-but-missing path is reported, not invented.
    """
    if isinstance(recorded, str):
        recorded = [recorded]
    files = []
    for item in recorded or []:
        if not isinstance(item, str) or not item.strip():
            continue
        path = item.strip()
        files.append(
            {
                "path": path,
                "label": Path(path).name,
                "href": _workspace_href(path),
            }
        )
    return files


def _relative_day(when: date, today: date) -> str:
    """"today" / "tomorrow" / "in N days" / "overdue N days" for a date."""
    delta = (when - today).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "tomorrow"
    if delta > 1:
        return f"in {delta} days"
    if delta == -1:
        return "overdue 1 day"
    return f"overdue {-delta} days"


def next_interview_action(rows: list[dict], today: date) -> dict | None:
    """The application whose next action is nearest — Today's one-tap entry.

    Soonest upcoming date wins; when every recorded date has passed, the most
    recent one is offered and flagged overdue. Nothing is invented: a row with
    no next-step date is simply not a candidate.
    """
    dated = [
        r
        for r in rows
        if r.get("next_step")
        and _inter_date(r["next_step"].get("date"))
        and r.get("status") not in INTERVIEW_CLOSED_STATUSES
    ]
    if not dated:
        return None

    def sort_key(row: dict):
        when = _inter_date(row["next_step"].get("date"))
        return (
            when,
            INTERVIEW_STATUS_ORDER.get(row["status"], 9),
            INTERVIEW_PRIORITY_ORDER.get(row["priority"], 9),
        )

    upcoming = [r for r in dated if sort_key(r)[0] >= today]
    pick = min(upcoming, key=sort_key) if upcoming else max(dated, key=sort_key)
    when = _inter_date(pick["next_step"].get("date"))
    return {
        "company": pick["company"],
        "role": pick["role"],
        # company|role is the tracker's key and survives the pipe-free data here.
        "key": f"{pick['company']}|{pick['role']}",
        "date": when.isoformat(),
        "when": _relative_day(when, today),
        "overdue": when < today,
        "status_label": pick["status_label"],
        "task": pick["next_step"]["task"],
    }


def _interview_sheet_href(company: str, role: str) -> str:
    """A printable one-page sheet for one application."""
    query = urllib.parse.urlencode({"company": company, "role": role})
    return f"/interviews/sheet?{query}"


def build_interview_view(jobs_data: dict, today: date | None = None) -> dict:
    """Rows for the Interviews tab, read live from job-applications.yml.

    A row carries what the file actually records: status, priority, contacts,
    the latest timeline entry and the first next step. Missing fields stay
    blank rather than being filled in.
    """
    today = today or date.today()
    rows = []
    for entry in jobs_data.get("active_applications") or []:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "new_lead")
        priority = str(entry.get("priority") or "").casefold()
        timeline = entry.get("timeline") or []
        last = timeline[-1] if timeline else {}
        step = (entry.get("next_steps") or [{}])[0]
        step_date = _inter_date(step.get("date"))
        rows.append(
            {
                "company": entry.get("company") or "Company not recorded",
                "role": entry.get("role") or "Role not recorded",
                "status": status,
                "status_label": INTERVIEW_STATUS_LABELS.get(
                    status, status.replace("_", " ").capitalize()
                ),
                "status_badge": INTERVIEW_STATUS_BADGES.get(status, "badge"),
                "priority": priority,
                "priority_label": priority.capitalize() if priority else "",
                "priority_badge": INTERVIEW_PRIORITY_BADGES.get(priority, "badge"),
                "location": entry.get("location") or "",
                "salary": entry.get("salary_range") or "",
                "url": entry.get("job_url") or "",
                "resume": entry.get("resume") or "",
                "resume_href": _resume_href(entry.get("resume") or ""),
                "application_date": _iso_text(entry.get("application_date")),
                # Dashboard-owned blocks, each separate from the hand-written
                # job-fit `notes:` so the tracker's own prose survives edits.
                "notes": entry.get("interview_notes") or "",
                "questions": entry.get("interview_questions") or "",
                "preparation": entry.get("interview_preparation") or "",
                "fit_notes": str(entry.get("notes") or "").strip(),
                "prep_files": _prep_files(entry.get("interview_prep")),
                "contacts": [
                    {
                        "name": c.get("name") or "",
                        "role": c.get("role") or "",
                        "email": c.get("email") or "",
                    }
                    for c in (entry.get("contacts") or [])
                    if isinstance(c, dict)
                ],
                "history": [
                    {
                        "date": _iso_text(t.get("date")),
                        "stage": str(t.get("stage") or "").replace("_", " "),
                        "notes": t.get("notes") or "",
                    }
                    for t in timeline
                    if isinstance(t, dict)
                ][-4:][::-1],
                "last_event": (
                    {
                        "date": _iso_text(last.get("date")),
                        "stage": str(last.get("stage") or "").replace("_", " "),
                        "notes": last.get("notes") or "",
                    }
                    if last
                    else None
                ),
                "next_step": {
                    "task": step.get("task") or "",
                    "date": step_date.isoformat() if step_date else "",
                }
                if step.get("task")
                else None,
                "overdue": bool(step_date and step_date < today),
                "sheet_href": _interview_sheet_href(
                    entry.get("company") or "Company not recorded",
                    entry.get("role") or "Role not recorded",
                ),
            }
        )

    rows.sort(
        key=lambda r: (
            INTERVIEW_STATUS_ORDER.get(r["status"], 9),
            INTERVIEW_PRIORITY_ORDER.get(r["priority"], 9),
        )
    )
    # Closed threads (rejected/withdrawn) are kept for history but never shown
    # as live work: they get their own collapsed card and stay out of the counts.
    live = [r for r in rows if r["status"] not in INTERVIEW_CLOSED_STATUSES]
    closed = [r for r in rows if r["status"] in INTERVIEW_CLOSED_STATUSES]
    active = [r for r in live if r["status"] in INTERVIEW_ACTIVE_STATUSES]
    leads = [r for r in live if r["status"] not in INTERVIEW_ACTIVE_STATUSES]
    # Newest signal first, so the most recent rejection reads at the top.
    closed.sort(
        key=lambda r: (
            r["last_event"]["date"] if r["last_event"] else "",
            r["company"],
        ),
        reverse=True,
    )
    return {
        "interview_rows": rows,
        "interview_active": active,
        "interview_leads": leads,
        "interview_closed": closed,
        "interview_counts": {
            "tracked": len(live),
            "active": len(active),
            "leads": len(leads),
            "high": sum(1 for r in live if r["priority"] == "high"),
            "closed": len(closed),
        },
        "interview_active_statuses": list(INTERVIEW_ACTIVE_STATUSES),
        "interview_statuses": [
            {
                "value": status,
                "label": INTERVIEW_STATUS_LABELS.get(
                    status, status.replace("_", " ").capitalize()
                ),
            }
            for status in ie.STATUSES
        ],
        "interview_priorities": [
            {"value": priority, "label": priority.capitalize()}
            for priority in ie.PRIORITIES
        ],
    }


def build_context() -> dict:
    """Read all workspace files and return template context."""

    skills_data = load_yaml(SKILLS_FILE)
    goals_data = load_yaml(GOALS_FILE)
    jobs_data = load_yaml(JOBS_FILE)
    network_data = load_yaml(NETWORK_FILE)
    realm_tasks = parse_all_realms()
    today = date.today()
    current_week = current_week_of_year(today)

    # Skills — flatten for template
    technical_skills = []
    for cat in skills_data.get("technical_skills", []):
        category_name = cat.get("category", "Other")
        for sk in cat.get("skills", []):
            technical_skills.append(
                {
                    "name": sk.get("name", ""),
                    "category": category_name,
                    "proficiency": sk.get("proficiency", "beginner"),
                    "years": sk.get("years_experience", 0),
                    "last_used": sk.get("last_used", ""),
                }
            )

    soft_skills = []
    for sk in skills_data.get("soft_skills", []):
        soft_skills.append(
            {
                "name": sk.get("name", ""),
                "proficiency": sk.get("proficiency", "low"),
            }
        )

    certifications = []
    for cert in skills_data.get("certifications", []):
        certifications.append(
            {
                "name": cert.get("name", ""),
                "issuer": cert.get("issuer", ""),
                "obtained": cert.get("date_obtained"),
                "expires": cert.get("expires"),
                "credential_id": cert.get("credential_id"),
            }
        )

    # Job stats
    stats = jobs_data.get("statistics", {}).get("2026", {})
    job_stats = {
        "applied": stats.get("applications_sent", 0),
        "screening": stats.get("screening_calls", 0),
        "interviews": stats.get("technical_interviews", 0),
        "onsites": stats.get("onsites", 0),
        "offers": stats.get("offers", 0),
        "rejections": stats.get("rejections", 0),
        "pending": stats.get("pending", 0),
    }

    interview_view = build_interview_view(jobs_data, today)

    # Networking goals
    net_goals = []
    for g in network_data.get("networking_goals", []):
        net_goals.append(
            {
                "goal": g.get("goal", ""),
                "progress": g.get("progress", "0/0"),
            }
        )

    # Vision/goals
    vision = goals_data.get("vision", {})
    has_goals = bool(vision.get("title"))

    # Year/quarter progress
    year_pct = round((current_week / 52) * 100)
    q1_pct = min(100, round((current_week / 13) * 100))
    q2_pct = (
        max(0, min(100, round(((current_week - 13) / 13) * 100)))
        if current_week > 13
        else 0
    )
    q3_pct = (
        max(0, min(100, round(((current_week - 26) / 13) * 100)))
        if current_week > 26
        else 0
    )
    q4_pct = (
        max(0, min(100, round(((current_week - 39) / 13) * 100)))
        if current_week > 39
        else 0
    )  # noqa: used in template

    # Projects (deprioritized — maintenance only while school + job search + roadmap are priorities)
    projects = [
        {
            "name": "WODCard",
            "status": "Deprioritized — maintenance only",
            "q1_goal": "Resume after school stabilizes",
            "color": SAFE_HUES["vermilion"],
            "features": [
                "React + Vite + TypeScript frontend",
                "FastAPI backend structure",
                "Card component with flip animation",
                "Timer component, exercise data model",
            ],
        },
        {
            "name": "SalsaSegura",
            "status": "Deprioritized — maintenance only",
            "q1_goal": "Resume after school stabilizes",
            "color": SAFE_HUES["blue"],
            "features": [
                "React TypeScript app deployed to Azure",
                "Events display, header, footer, hero section",
                "Work in progress page",
            ],
        },
        {
            "name": "SalsaTD",
            "status": "Deprioritized — maintenance only",
            "q1_goal": "Resume after school stabilizes",
            "color": SAFE_HUES["purple"],
            "features": [
                "Game board with turn-based play (2-30 players)",
                "Truth & Dare decks with spiciness levels",
                "Dark mode, scroll indicator, mobile optimized",
                "Card UI with animations, deck reshuffling",
                "Penalty system, Azure Cosmos DB prototype",
            ],
        },
        {
            "name": "Capstone (genomics-style batch pipeline)",
            "status": "Planned — Phase 7 of roadmap, builds in 2027",
            "q1_goal": "Public GitHub repo by end of 2027",
            "color": SAFE_HUES["green"],
            "features": [
                "Terraform-managed VPC + EKS cluster",
                "Fan-out workflow: S3 → SQS → Karpenter worker pods",
                "Argo Workflows or AWS Batch (Fargate)",
                "Prometheus + Grafana + Loki + AWS X-Ray",
                "GitHub Actions CI/CD with Trivy + ArgoCD",
            ],
        },
    ]

    # Skill-project matrix
    learning_matrix = [
        {"skill": "React", "wod": True, "salsa": True, "td": True},
        {"skill": "FastAPI", "wod": True, "salsa": False, "td": True},
        {"skill": "Cosmos DB", "wod": True, "salsa": False, "td": True},
        {"skill": "Auth", "wod": True, "salsa": True, "td": True},
        {"skill": "CI/CD", "wod": True, "salsa": True, "td": True},
        {"skill": "Docker", "wod": True, "salsa": False, "td": False},
        {"skill": "K8s/AKS", "wod": True, "salsa": False, "td": False},
        {"skill": "Terraform", "wod": True, "salsa": False, "td": False},
    ]

    # Success metrics — aligned to plans/year-plan-2026-2027.md (Regeneron-class role by end of 2027)
    success_metrics = [
        {
            "category": "Career",
            "goal": "Stepping-stone role (IT eng / sysadmin / cloud-adjacent)",
            "metric": "Offer signed by end of 2026",
        },
        {
            "category": "Long-term Career",
            "goal": "Lead Cloud DevOps Engineer (Regeneron-class)",
            "metric": "Apply by Q4 2027",
        },
        {
            "category": "School",
            "goal": "SNHU CS BS (or Cybersecurity BS)",
            "metric": "1 course/term, on track each term",
        },
        {
            "category": "Roadmap",
            "goal": "Phases 1–7 + capstone complete",
            "metric": "End of 2027 — see year plan",
        },
        {
            "category": "Certifications",
            "goal": "CKA, Terraform Associate, AWS DOP",
            "metric": "Stack alongside roadmap phases",
        },
        {
            "category": "Projects",
            "goal": "Genomics-style batch pipeline (capstone)",
            "metric": "Public GitHub repo by end of 2027",
        },
    ]

    # Application checklist
    app_checklist = jobs_data.get("application_strategy", {}).get(
        "application_checklist", []
    )

    # Education data
    edu_data = load_yaml(EDU_FILE)
    edu_program = edu_data.get("program", {})
    edu_stats = edu_data.get("degree_stats", {})
    edu_sources = [
        {**s, "color": safe_hue(s.get("color"))}
        for s in edu_data.get("credit_sources", [])
    ]
    edu_phases = edu_data.get("transfer_phases", [])
    edu_timeline = edu_data.get("timeline", [])
    edu_cost = edu_data.get("cost", {})
    edu_actions = edu_data.get("actions", [])

    # Compute total credits by status for stacked bar
    credits_completed = sum(
        s.get("credits", 0) for s in edu_sources if s.get("status") == "completed"
    )
    credits_planned = sum(
        s.get("credits", 0) for s in edu_sources if s.get("status") != "completed"
    )

    # Books data
    books_data = load_yaml(BOOKS_FILE)
    books_list = books_data.get("books", [])
    books_categories = books_data.get("categories", [])

    # Build category lookup
    cat_meta = {c["name"]: c for c in books_categories}

    # Stats
    total_books = len(books_list)
    in_plan_count = sum(1 for b in books_list if b.get("in_plan"))
    new_picks = total_books - in_plan_count

    # Group books by category (preserve insertion order, O(n) via dict)
    cat_groups: dict[str, dict] = {}
    for b in books_list:
        cat = b.get("category", "Uncategorized")
        if cat not in cat_groups:
            meta = cat_meta.get(cat, {})
            cat_groups[cat] = {
                "name": cat,
                "icon": meta.get("icon", "📖"),
                "color": safe_hue(meta.get("color")),
                "books": [],
            }
        cat_groups[cat]["books"].append(b)
    books_by_category = list(cat_groups.values())

    # Quarter counts
    q_counts = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    for b in books_list:
        q = b.get("quarter", "Q1")
        if q in q_counts:
            q_counts[q] += 1

    # Routine folds
    fold_steps = parse_routine_folds(today)
    today_view = build_today_view(realm_tasks, fold_steps, today)

    return {
        "today": today.isoformat(),
        "fold_steps": fold_steps,
        **today_view,
        **command_centre(
            realm_tasks,
            today_view,
            len(projects),
            next_interview_action(interview_view["interview_rows"], today),
        ),
        "money_available": money_available(),
        "edu_program": edu_program,
        "edu_stats": edu_stats,
        "edu_sources": edu_sources,
        "edu_phases": edu_phases,
        "edu_timeline": edu_timeline,
        "edu_cost": edu_cost,
        "edu_actions": edu_actions,
        "credits_completed": credits_completed,
        "credits_planned": credits_planned,
        "current_week": current_week,
        "year_pct": year_pct,
        "q1_pct": q1_pct,
        "q2_pct": q2_pct,
        "q3_pct": q3_pct,
        "q4_pct": q4_pct,
        "realm_tasks": realm_tasks,
        "realms": REALMS,
        "technical_skills": technical_skills,
        "soft_skills": soft_skills,
        "certifications": certifications,
        "has_goals": has_goals,
        "vision": vision,
        "job_stats": job_stats,
        **interview_view,
        "net_goals": net_goals,
        "projects": projects,
        "learning_matrix": learning_matrix,
        "success_metrics": success_metrics,
        "app_checklist": app_checklist,
        "books_by_category": books_by_category,
        "total_books": total_books,
        "in_plan_count": in_plan_count,
        "new_picks": new_picks,
        "q_counts": q_counts,
        **build_agents_view(),
    }


# ── Markdown File Discovery ───────────────────────────────────
EXCLUDED_DIRS = {"node_modules", ".git", "venv", "__pycache__", "dashboard-app"}


def discover_md_files() -> list[dict]:
    """Walk workspace and return .md files grouped by directory."""
    files = []
    for md in sorted(WORKSPACE.rglob("*.md")):
        # Skip excluded directories and anything the privacy rules protect
        rel = md.relative_to(WORKSPACE)
        if md.is_symlink() or any(part in EXCLUDED_DIRS for part in rel.parts) or wc.privacy_violation(
            rel.as_posix()
        ):
            continue
        files.append(
            {
                "path": str(rel),
                "name": md.name,
                "folder": str(rel.parent) if str(rel.parent) != "." else "",
                "size": md.stat().st_size,
            }
        )
    return files


# ── Routes ────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    # The Run tab reads this catalogue; build it while the page renders.
    _warm_skill_catalog()
    ctx = build_context()
    return templates.TemplateResponse(request, "index.html", ctx)


@app.get("/reader", response_class=HTMLResponse)
def reader(request: Request):
    return templates.TemplateResponse(request, "reader.html")


@app.get("/second-brain", response_class=HTMLResponse)
def second_brain():
    return serve_second_brain()


# ── Workspace map (visual-second-brain) + safe file access ─────
# Read-only. Eligibility and privacy rules live in workspace_content.py.
@app.get("/workspace-map", include_in_schema=False)
def workspace_map_redirect():
    return RedirectResponse("/workspace-map/")


@app.get("/workspace-map/")
def workspace_map():
    return FileResponse(
        wc.VIEWER_HTML, media_type="text/html", headers={"Cache-Control": "no-cache"}
    )


@app.get("/workspace-map/workspace-index.json")
def workspace_map_index():
    if not wc.INDEX_FILE.is_file():
        return JSONResponse(
            {"error": "Workspace index missing; run refresh-index.py"}, status_code=503
        )
    # X-Workspace-Open tells the viewer where its Open/Download links point.
    return FileResponse(
        wc.INDEX_FILE,
        media_type="application/json",
        headers={"Cache-Control": "no-store", "X-Workspace-Open": "/workspace-file"},
    )


@app.get("/workspace-file/{path:path}")
def workspace_file(path: str, download: bool = False):
    """Serve one indexed file or live artifact; relative links inside artifacts resolve here too."""
    try:
        target = wc.resolve_file(WORKSPACE, wc.INDEX_FILE, path)
    except wc.ContentError as exc:
        return PlainTextResponse(
            str(exc),
            status_code=exc.status,
            headers={"X-Content-Type-Options": "nosniff"},
        )
    media, headers = wc.file_headers(target, download)
    return FileResponse(target, media_type=media, headers=headers)


@app.get("/api/workspace/artifacts")
def workspace_artifacts():
    try:
        return JSONResponse({"artifacts": wc.artifact_entries()})
    except OSError:
        return JSONResponse(
            {"error": "artifacts/ could not be read; is the drive mounted?"},
            status_code=503,
        )


@app.get("/mission-control")
@app.get("/mission-control/{path:path}", response_class=HTMLResponse)
def mission_control(path: str = ""):
    return proxy_mission_control(path)


@app.get("/api/files")
def api_files():
    return JSONResponse(discover_md_files())


@app.get("/api/file")
def api_file(path: str = Query(...)):
    # Resolve to absolute path and confirm it lives inside WORKSPACE.
    # Using Path.resolve() handles symlinks, "..", and absolute injections
    # (e.g. Path("/workspace") / Path("/etc/passwd") == Path("/etc/passwd")).
    workspace = WORKSPACE.resolve()
    target = (workspace / path).resolve()
    try:
        resolved_rel = target.relative_to(workspace).as_posix()
    except ValueError:
        return JSONResponse({"error": "Invalid path"}, status_code=400)
    # Same privacy rules as the Workspace map, on the requested and the real path.
    if wc.privacy_violation(path.strip("/")) or wc.privacy_violation(resolved_rel):
        return JSONResponse({"error": "File not available"}, status_code=403)
    if not target.exists() or not target.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)
    ALLOWED_EXTENSIONS = {
        ".md",
        ".txt",
        ".yaml",
        ".yml",
        ".json",
        ".csv",
        ".html",
        ".py",
    }
    if target.suffix.lower() not in ALLOWED_EXTENSIONS:
        return JSONResponse({"error": "File type not allowed"}, status_code=403)
    return JSONResponse({"path": path, "content": target.read_text(errors="replace")})


@app.post("/api/tasks/toggle")
def toggle_task(req: ToggleRequest, x_requested_with: str = Header(default="")):
    """Toggle a checkbox in the source markdown file."""
    if x_requested_with != "XMLHttpRequest":
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    if req.realm == "routine":
        target = WORKSPACE / "routine.md"
    else:
        realm_cfg = next((r for r in REALMS if r["id"] == req.realm), None)
        if not realm_cfg:
            return JSONResponse({"error": "Unknown realm"}, status_code=400)
        target = WORKSPACE / realm_cfg["file"]
    if not target.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)

    with _FILE_WRITE_LOCK:
        lines = target.read_text().splitlines(keepends=True)
        idx = req.line - 1  # convert to 0-based
        allowed_routine_lines = (
            {item["line"]: item["text"] for item in _routine_review_items(lines)}
            if req.realm == "routine"
            else None
        )
        if (
            allowed_routine_lines is not None
            and idx + 1 not in allowed_routine_lines
            and req.text not in allowed_routine_lines.values()
        ):
            return JSONResponse(
                {"error": "Only Weekly Review items can be changed here"},
                status_code=400,
            )

        def text_at(i: int) -> str | None:
            if not 0 <= i < len(lines):
                return None
            if allowed_routine_lines is not None:
                return allowed_routine_lines.get(i + 1)
            m = CHECKBOX_RE.match(lines[i].rstrip("\r\n"))
            return m.group(3)[2:] if m else None

        if req.text is not None and not (
            0 <= idx < len(lines) and text_at(idx) == req.text
        ):
            # The file moved under the page. Follow the text, but only if unique.
            hits = [i for i in range(len(lines)) if text_at(i) == req.text]
            if len(hits) != 1:
                return JSONResponse(
                    {"error": "Task moved or changed — reload the page"},
                    status_code=409,
                )
            idx = hits[0]

        if idx < 0 or idx >= len(lines):
            return JSONResponse({"error": "Line out of range"}, status_code=400)

        m = CHECKBOX_RE.match(lines[idx].rstrip("\n").rstrip("\r"))
        if not m:
            return JSONResponse({"error": "No checkbox on that line"}, status_code=400)
        if allowed_routine_lines is not None and idx + 1 not in allowed_routine_lines:
            return JSONResponse(
                {"error": "Only Weekly Review items can be changed here"},
                status_code=400,
            )

        new_mark = "x" if req.done else " "
        lines[idx] = m.group(1) + new_mark + m.group(3) + "\n"
        _atomic_write(target, "".join(lines))

    return JSONResponse(
        {"ok": True, "realm": req.realm, "line": idx + 1, "done": req.done}
    )


@app.post("/api/capture")
def capture(req: CaptureRequest, x_requested_with: str = Header(default="")):
    """Append one item to the Inbox section of TASKS.md."""
    if x_requested_with != "XMLHttpRequest":
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    # Collapse newlines/tabs: one capture is exactly one checkbox line.
    text = " ".join(req.text.split())
    if not text:
        return JSONResponse({"error": "Nothing to capture"}, status_code=400)
    if len(text) > CAPTURE_MAX:
        return JSONResponse(
            {"error": f"Keep it under {CAPTURE_MAX} characters"}, status_code=400
        )

    with _FILE_WRITE_LOCK:
        source = TASKS_FILE.read_text() if TASKS_FILE.exists() else "# Tasks\n"
        new_text, line = insert_inbox_item(source, text)
        _atomic_write(TASKS_FILE, new_text)

    return JSONResponse({"ok": True, "realm": "tasks", "line": line, "text": text})


# ── Second brain (second-brain/brain.py, deterministic, no model) ──
BRAIN_CLI = WORKSPACE / "second-brain" / "brain.py"
BRAIN_TIMEOUT = 60


class RememberRequest(BaseModel):
    title: str
    summary: str
    body: str


def _brain(*args: str) -> JSONResponse:
    """Run one brain.py subcommand and relay its JSON. Arguments go in as
    separate argv elements with no shell, so input cannot become a command."""
    try:
        proc = subprocess.run(
            [sys.executable, str(BRAIN_CLI), *args],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=BRAIN_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return JSONResponse({"error": f"brain.py failed: {exc}"}, status_code=500)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        detail = (proc.stderr or proc.stdout).strip()[-400:] or "no output"
        return JSONResponse({"error": detail}, status_code=500)
    return JSONResponse(data, status_code=200 if proc.returncode == 0 else 422)


@app.get("/api/brain/query")
def brain_query(q: str = Query(..., min_length=2, max_length=200)):
    return _brain("query", q)


@app.post("/api/brain/remember")
def brain_remember(req: RememberRequest, x_requested_with: str = Header(default="")):
    if x_requested_with != "XMLHttpRequest":
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    return _brain(
        "remember", "--title", req.title, "--summary", req.summary, "--body", req.body
    )


# ── Interview dashboard writes ─────────────────────────────────────────────
# Each endpoint edits only the lines it owns in interviews/job-applications.yml
# (see interview_editor.py), then answers with the rebuilt row so the page can
# update without a reload.
class InterviewFieldRequest(BaseModel):
    company: str
    role: str
    field: str
    value: str


class InterviewNextStepRequest(BaseModel):
    company: str
    role: str
    task: str
    date: str | None = None


class InterviewSignalRequest(BaseModel):
    company: str
    role: str
    date: str
    stage: str
    notes: str | None = None


class InterviewTextRequest(BaseModel):
    company: str
    role: str
    field: str
    text: str


class InterviewCreateRequest(BaseModel):
    company: str
    role: str
    status: str = "new_lead"
    priority: str = "medium"
    location: str | None = None
    salary_range: str | None = None
    job_url: str | None = None
    next_step: str | None = None
    date: str | None = None


def _interview_target(company: str, role: str) -> tuple[str, str] | None:
    company, role = company.strip(), role.strip()
    if not company or not role or len(company) > 200 or len(role) > 200:
        return None
    return company, role


def _interview_write(edit, company: str, role: str):
    """Apply one editor function under the file lock, then return the new row."""
    if not JOBS_FILE.exists():
        return JSONResponse({"error": "Application tracker not found"}, status_code=404)
    with _FILE_WRITE_LOCK:
        text = JOBS_FILE.read_text(encoding="utf-8")
        try:
            updated = edit(text)
        except ie.InterviewEditError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        _atomic_write(JOBS_FILE, updated)

    view = build_interview_view(load_yaml(JOBS_FILE), date.today())
    row = next(
        (
            r
            for r in view["interview_rows"]
            if r["company"] == company and r["role"] == role
        ),
        None,
    )
    return JSONResponse({"ok": True, "row": row, "counts": view["interview_counts"]})


def _csrf_ok(x_requested_with: str) -> bool:
    return x_requested_with == "XMLHttpRequest"


@app.post("/api/interviews/field")
def interview_field(
    req: InterviewFieldRequest, x_requested_with: str = Header(default="")
):
    if not _csrf_ok(x_requested_with):
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    target = _interview_target(req.company, req.role)
    if not target:
        return JSONResponse({"error": "Company and role are required"}, status_code=400)
    company, role = target
    return _interview_write(
        lambda text: ie.set_field(text, company, role, req.field, req.value),
        company,
        role,
    )


@app.post("/api/interviews/next-step")
def interview_next_step(
    req: InterviewNextStepRequest, x_requested_with: str = Header(default="")
):
    if not _csrf_ok(x_requested_with):
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    target = _interview_target(req.company, req.role)
    if not target:
        return JSONResponse({"error": "Company and role are required"}, status_code=400)
    company, role = target
    return _interview_write(
        lambda text: ie.set_next_step(text, company, role, req.task, req.date or ""),
        company,
        role,
    )


@app.post("/api/interviews/timeline")
def interview_timeline(
    req: InterviewSignalRequest, x_requested_with: str = Header(default="")
):
    if not _csrf_ok(x_requested_with):
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    target = _interview_target(req.company, req.role)
    if not target:
        return JSONResponse({"error": "Company and role are required"}, status_code=400)
    company, role = target
    return _interview_write(
        lambda text: ie.append_timeline(
            text, company, role, req.date, req.stage, req.notes or ""
        ),
        company,
        role,
    )


@app.get("/api/interviews/detail")
def interview_detail(
    company: str = Query(..., min_length=1, max_length=200),
    role: str = Query(..., min_length=1, max_length=200),
):
    """One application as the Interview mode dialog needs it."""
    view = build_interview_view(load_yaml(JOBS_FILE), date.today())
    row = next(
        (
            r
            for r in view["interview_rows"]
            if r["company"] == company.strip() and r["role"] == role.strip()
        ),
        None,
    )
    if row is None:
        return JSONResponse({"error": "Application not found"}, status_code=404)
    return JSONResponse({"ok": True, "row": row})


@app.get("/interviews/sheet", response_class=HTMLResponse)
def interview_sheet(
    request: Request,
    company: str = Query(..., min_length=1, max_length=200),
    role: str = Query(..., min_length=1, max_length=200),
):
    """Standalone printable prep sheet: browser Print → PDF for offline use."""
    view = build_interview_view(load_yaml(JOBS_FILE), date.today())
    row = next(
        (
            r
            for r in view["interview_rows"]
            if r["company"] == company.strip() and r["role"] == role.strip()
        ),
        None,
    )
    if row is None:
        return HTMLResponse("Application not found", status_code=404)
    return templates.TemplateResponse(
        request,
        "interview_sheet.html",
        {"row": row, "printed": date.today().isoformat(), "workspace": str(WORKSPACE)},
    )


@app.post("/api/interviews/text")
def interview_text(
    req: InterviewTextRequest, x_requested_with: str = Header(default="")
):
    if not _csrf_ok(x_requested_with):
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    target = _interview_target(req.company, req.role)
    if not target:
        return JSONResponse({"error": "Company and role are required"}, status_code=400)
    if req.field not in ie.TEXT_BLOCKS:
        return JSONResponse({"error": "Unknown field"}, status_code=400)
    company, role = target
    return _interview_write(
        lambda text: ie.set_text_block(text, company, role, req.field, req.text),
        company,
        role,
    )


@app.post("/api/interviews/create")
def interview_create(
    req: InterviewCreateRequest, x_requested_with: str = Header(default="")
):
    if not _csrf_ok(x_requested_with):
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)
    target = _interview_target(req.company, req.role)
    if not target:
        return JSONResponse({"error": "Company and role are required"}, status_code=400)
    company, role = target

    def edit(text: str) -> str:
        return ie.add_application(
            text,
            company=company,
            role=role,
            status=req.status,
            priority=req.priority,
            location=req.location or "",
            salary_range=req.salary_range or "",
            job_url=req.job_url or "",
            next_step=req.next_step or "",
            due=req.date or "",
        )

    return _interview_write(edit, company, role)


# ── Connected systems: Second Brain + Mission Control ──────────
def serve_second_brain():
    """Serve the static RoboNuggets second-brain reference page."""
    if not SECOND_BRAIN_FILE.exists():
        return HTMLResponse("Second brain not found.", status_code=404)
    return HTMLResponse(
        SECOND_BRAIN_FILE.read_text(errors="replace"), media_type="text/html"
    )


OFFLINE_CARD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Mission Control offline</title>
<style>
  body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
       background:#131722;color:#e6e9ef;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,sans-serif;}
  .card{max-width:420px;text-align:center;padding:2rem;border:1px solid #232838;border-radius:14px;}
  h1{font-size:1.15rem;margin:0 0 .5rem;color:#7c9eff;}
  p{color:#8b93a7;font-size:.9rem;line-height:1.5;margin:.4rem 0;}
  code{background:#1b2130;border:1px solid #232838;padding:.15em .45em;border-radius:6px;font-size:.85em;}
</style></head>
<body><div class="card">
  <h1>&#x1F6AB; Mission Control offline</h1>
  <p>Start the agentic-os server to open it:</p>
  <p><code>cd agentic-os/apps/api &amp;&amp; npm start</code></p>
  <p>Then this tab will load the live mission board.</p>
</div></body></html>"""


def proxy_mission_control(path: str = ""):
    """Reverse proxy to the agentic-os Mission Control server (:8787).

    HTML responses are rewritten so the dashboard's root-absolute /api/*
    fetches land back through this proxy. API routes forward byte-for-byte.
    """
    upstream = MISSION_CONTROL_UPSTREAM + "/" + path.lstrip("/")
    try:
        with urllib.request.urlopen(upstream, timeout=MISSION_CONTROL_TIMEOUT) as resp:
            ctype = resp.headers.get("Content-Type", "")
            body = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return HTMLResponse(OFFLINE_CARD, status_code=502)

    if path.startswith("api/"):
        return Response(content=body, media_type=ctype, status_code=200)

    html = body.decode(errors="replace")
    html = html.replace('"/api/', '"/mission-control/api/').replace(
        "'/api/", "'/mission-control/api/"
    )
    return HTMLResponse(html, status_code=200)


# ══════════════════════════════════════════════════════════════
# Skill runner — fire Claude Code skills headlessly from buttons
# ══════════════════════════════════════════════════════════════
# Security model: the browser sends a skill *id* from the allowlist below,
# never an arbitrary prompt or command. Inputs are validated and passed as
# subprocess arguments, without shell=True.

RUNS_DIR = Path(__file__).parent / "runs"
RUNS_LOG = WORKSPACE / "runs.log"
RUN_TIMEOUT = 1800  # 30 min — real skill passes take minutes, not seconds
MAX_RUNS_KEPT = 50

# ── Model providers for Run executions ───────────────────────────
# Claude keeps its existing aliases; Codex/OpenCode/OpenRouter are
# provider-labelled as "provider:model_id" (e.g. "codex:gpt-6.1-sol",
# "opencode:opencode/beam-free", "openrouter:nvidia/...:free").
PROVIDERS = ("claude", "codex", "opencode", "openrouter")

# `claude --model` takes an alias or a full name. Aliases stay valid as
# models are replaced; pinned full names rot.
ALLOWED_MODELS = ("sonnet", "opus", "fable")
ALLOWED_EFFORT = ("default", "low", "medium", "high")

# Local catalogue locations (no credentials, no network at build time).
CODEX_CACHE = Path.home() / ".codex" / "models_cache.json"
OPENROUTER_CATALOG = Path.home() / ".hermes.bak" / "cache" / "openrouter_curated_catalog.json"
OPENROUTER_METADATA = Path.home() / ".hermes.bak" / "cache" / "openrouter_model_metadata.json"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"

# Bounds for workspace text inlined into OpenRouter prompts (no file tools).
CONTEXT_MAX_FILE_CHARS = 80_000
CONTEXT_MAX_CHARS = 160_000


def _is_free_model_id(model_id: str) -> bool:
    """OpenCode/OpenRouter free models are marked with -free or :free."""
    return model_id.endswith(":free") or model_id.endswith("-free")


def _load_codex_models():
    """Visible Codex catalogue entries: [{id, label, efforts}], available, reason."""
    if _resolve_codex_exe() is None:
        return [], False, "codex executable not on PATH"
    try:
        raw = json.loads(CODEX_CACHE.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        return [], False, f"Codex catalogue unreadable: {exc}"
    entries = raw.get("models") if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        return [], False, "Codex catalogue has no model list"
    seen = set()
    models = []
    for m in entries:
        if not isinstance(m, dict):
            continue
        if m.get("visibility") != "list" or not m.get("supported_in_api"):
            continue
        slug = m.get("slug") or m.get("id")
        if not slug or slug in seen:
            continue
        seen.add(slug)
        levels = m.get("supported_reasoning_levels") or []
        efforts = ["default"]
        for lv in levels:
            if isinstance(lv, dict) and lv.get("effort") and lv["effort"] not in efforts:
                efforts.append(lv["effort"])
        models.append({"id": slug, "label": m.get("display_name") or slug, "efforts": efforts})
    models.sort(key=lambda x: x["label"])
    return (models, True, None) if models else ([], False, "Codex catalogue has no visible entries")


def _resolve_executable(name: str, fallbacks: tuple[Path, ...]) -> str | None:
    """Locate an executable on PATH, then at known install locations.

    launchd starts the dashboard with a minimal PATH that does not include
    per-user bin directories, so PATH alone is not enough.
    """
    try:
        proc = subprocess.run(["which", name], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip().splitlines()[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    for candidate in fallbacks:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _resolve_opencode_exe() -> str | None:
    """Locate the `opencode` executable, checking PATH then common install spots."""
    return _resolve_executable(
        "opencode",
        (
            Path.home() / ".opencode" / "bin" / "opencode",
            Path("/usr/local/bin/opencode"),
            Path("/opt/homebrew/bin/opencode"),
        ),
    )


def _resolve_codex_exe() -> str | None:
    """Locate the `codex` executable, checking PATH then common install spots."""
    return _resolve_executable(
        "codex",
        (
            Path.home() / ".local" / "bin" / "codex",
            Path("/opt/homebrew/bin/codex"),
            Path("/usr/local/bin/codex"),
        ),
    )


def _load_opencode_models():
    """Free OpenCode models from `opencode models`: [{id, label, efforts}], available, reason."""
    exe = _resolve_opencode_exe()
    if exe is None:
        return [], False, "opencode executable not on PATH"
    try:
        # --standalone runs a private server per call instead of depending on the
        # shared background service, whose stale registration can make this hang.
        proc = subprocess.run(
            [exe, "models", "--standalone"], capture_output=True, text=True, timeout=15
        )
    except subprocess.TimeoutExpired:
        return [], False, "opencode models timed out"
    except OSError as exc:
        return [], False, f"opencode models failed to start: {exc}"
    if proc.returncode != 0:
        return [], False, f"opencode models exited {proc.returncode}: {proc.stderr.strip()[:200]}"
    ids = [line.strip() for line in proc.stdout.splitlines() if "/" in line.strip() and _is_free_model_id(line.strip()) and "opus" not in line.strip().lower()]
    seen = set()
    models = []
    for mid in ids:
        if mid in seen:
            continue
        seen.add(mid)
        models.append({"id": mid, "label": mid, "efforts": ["default"]})
    models.sort(key=lambda x: x["id"])
    return (models, True, None) if models else ([], False, "opencode catalogue has no free entries")


def _load_openrouter_models():
    """Free OpenRouter models from the curated catalogue: [{id, label, efforts}], available, reason."""
    try:
        raw = json.loads(OPENROUTER_CATALOG.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        return [], False, f"OpenRouter catalogue unreadable: {exc}"
    curated = raw.get("curated") if isinstance(raw, dict) else None
    if not isinstance(curated, list):
        return [], False, "OpenRouter catalogue has no curated list"
    metadata = {}
    try:
        metadata = json.loads(OPENROUTER_METADATA.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        metadata = {}
    seen = set()
    models = []
    for entry in curated:
        if not isinstance(entry, (list, tuple)) or len(entry) < 1:
            continue
        mid = entry[0]
        label = entry[1] if len(entry) > 1 and entry[1] else ""
        is_free = label == "free" or _is_free_model_id(mid)
        # zero-price confirmation from metadata (listing is not entitlement).
        # Missing pricing is NOT treated as free: only explicitly zero-priced
        # models qualify.
        info = metadata.get(mid) or metadata.get(mid.split(":")[0]) or {}
        if not isinstance(info, dict):
            info = {}
        pricing = info.get("pricing") if isinstance(info.get("pricing"), dict) else None
        if pricing is not None:
            try:
                prompt_price = float(pricing.get("prompt", 0) or 0)
                comp_price = float(pricing.get("completion", 0) or 0)
            except (TypeError, ValueError):
                prompt_price = comp_price = 0
            if prompt_price == 0 and comp_price == 0:
                is_free = True
        if not is_free:
            continue
        if mid in seen:
            continue
        seen.add(mid)
        models.append({"id": mid, "label": mid, "efforts": ["default"]})
    models.sort(key=lambda x: x["id"])
    return (models, True, None) if models else ([], False, "OpenRouter catalogue has no free entries")


def _fetch_skill_catalog():
    """Assemble the full provider-labelled catalogue (fresh on each call)."""
    claude_models = [
        {"id": m, "label": m.capitalize(), "efforts": list(ALLOWED_EFFORT)} for m in ALLOWED_MODELS
    ]
    codex_models, codex_ok, codex_reason = _load_codex_models()
    opencode_models, opencode_ok, opencode_reason = _load_opencode_models()
    openrouter_models, openrouter_ok, openrouter_reason = _load_openrouter_models()
    return {
        "models": list(ALLOWED_MODELS),
        "effort": list(ALLOWED_EFFORT),
        "provider_models": {
            "claude": claude_models,
            "codex": codex_models,
            "opencode": opencode_models,
            "openrouter": openrouter_models,
        },
        "provider_available": {
            "claude": True,
            "codex": codex_ok,
            "opencode": opencode_ok,
            "openrouter": openrouter_ok,
        },
        "provider_unavailable_reason": {
            "codex": codex_reason,
            "opencode": opencode_reason,
            "openrouter": openrouter_reason,
        },
    }

# The catalogue is read by the Run tab on open. OpenCode listing spawns a
# private server (~4 s), so cache the assembled payload and warm it from any
# dashboard visit; "Refresh models" still forces a rebuild.
_SKILL_CATALOG_TTL = 300.0
_SKILL_CATALOG: dict[str, object] = {
    "payload": None,
    "built_at": 0.0,
    "building": False,
}
_SKILL_CATALOG_LOCK = threading.Lock()


def _skill_catalog_payload() -> dict:
    """The full catalogue response (provider models plus renderable skills)."""
    return {
        **_fetch_skill_catalog(),
        "skills": [
            {
                "id": sid,
                "label": cfg["label"],
                "blurb": cfg["blurb"],
                "icon": cfg["icon"],
                "kind": cfg["kind"],
                "model": cfg.get("model"),
                "options": cfg.get("options", cfg["kind"] == "claude"),
                "input_label": cfg.get("input_label"),
                "input_type": cfg.get("input_type", "url"),
                "providers": cfg.get("providers"),
            }
            for sid, cfg in SKILL_RUNNERS.items()
        ],
    }


def _cached_skill_catalog(force: bool = False) -> dict:
    """Return a cached catalogue, rebuilding it when stale or forced."""
    now = time.monotonic()
    with _SKILL_CATALOG_LOCK:
        cached = _SKILL_CATALOG["payload"]
        if (
            not force
            and cached is not None
            and now - float(_SKILL_CATALOG["built_at"]) < _SKILL_CATALOG_TTL
        ):
            return cached  # type: ignore[return-value]
        payload = _skill_catalog_payload()
        _SKILL_CATALOG["payload"] = payload
        _SKILL_CATALOG["built_at"] = time.monotonic()
        return payload


def _warm_skill_catalog() -> None:
    """Build the catalogue off the request path so the next Run visit is fast."""
    now = time.monotonic()
    with _SKILL_CATALOG_LOCK:
        cached = _SKILL_CATALOG["payload"]
        if (
            cached is not None
            and now - float(_SKILL_CATALOG["built_at"]) < _SKILL_CATALOG_TTL
        ):
            return
        if _SKILL_CATALOG["building"]:
            return
        _SKILL_CATALOG["building"] = True

    def build() -> None:
        try:
            # Not forced: if a page request filled the cache first, reuse it.
            _cached_skill_catalog()
        except Exception:  # noqa: BLE001 — a failed warm must not break the page
            pass
        finally:
            with _SKILL_CATALOG_LOCK:
                _SKILL_CATALOG["building"] = False

    threading.Thread(target=build, name="skill-catalog-warm", daemon=True).start()


SKILL_RUNNERS = {
    "impeccable-audit": {
        "label": "Audit dashboard",
        "blurb": "Five-dimension technical scan with a scored report. Read-only.",
        "icon": "◇",
        "kind": "claude",
        "prompt": "/impeccable audit dashboard-app. Report findings only; do not edit files.",
        "model": "sonnet",
        "options": True,
        "read_only": True,
    },
    "impeccable-polish": {
        "label": "Polish dashboard",
        "blurb": "Final quality pass over the Orizuru surface. Edits files.",
        "icon": "✦",
        "kind": "claude",
        "prompt": (
            "/impeccable polish dashboard-app. Keep changes scoped to the dashboard UI: "
            "edit only dashboard-app/templates/ and dashboard-app/static/, never app.py. "
            "Read .html files with the Read tool. The always-on server at "
            "http://127.0.0.1:8000 hot-reloads templates and static files; do not start "
            "another. See each tab with `sh dashboard-app/screenshot.sh <tab> <width>` "
            "(tabs are the nav ids, e.g. today, run, tasks; widths 390 and 1280), then "
            "Read the PNG path it prints; the script fails if the page does not return "
            "200. Before finishing, run "
            "`dashboard-app/venv/bin/python -m pytest dashboard-app/tests -q` and report "
            "its result."
        ),
        "model": "sonnet",
        "options": True,
        # dontAsk + this allowlist: everything else is denied, not prompted.
        "permissions": {
            "tools": ["Read", "Glob", "Grep", "Skill", "Edit", "Write", "Bash"],
            "allow": [
                "Read",
                "Glob",
                "Grep",
                "Skill",
                # Edit(path) rules cover Write too; Write(path) rules are ignored.
                "Edit(dashboard-app/templates/**)",
                "Edit(dashboard-app/static/**)",
                "Bash(sh dashboard-app/screenshot.sh:*)",
                "Bash(dashboard-app/venv/bin/python -m pytest:*)",
            ],
            # The impeccable skill's reference files live outside the workspace.
            "add_dirs": [str(Path.home() / ".agents" / "skills" / "impeccable")],
        },
    },
    "ui-ux-review": {
        "label": "UI/UX review",
        "blurb": "ui-ux-pro-max pass over the templates and stylesheet. Read-only.",
        "icon": "◐",
        "kind": "claude",
        "prompt": (
            "/ui-ux-pro-max Review the dashboard-app Run tab "
            "(templates/pages/run.html, static/app.js and static/style.css). "
            "Read the skill's applicable reference files. Report at most five "
            "concrete findings with file:line citations; do not edit any file."
        ),
        "model": "sonnet",
        "options": True,
        "read_only": True,
        "context_files": [
            "dashboard-app/templates/pages/run.html",
            "dashboard-app/static/app.js",
            "dashboard-app/static/style.css",
        ],
    },
    "update-sheet": {
        "label": "Update sheet",
        "blurb": "Bring every dated workspace file current. Writes to TASKS.md, DASHBOARD.md, routine.md.",
        "icon": "▭",
        "kind": "claude",
        "prompt": None,  # rendered from the index.html template at run time
        "model": "sonnet",
    },
    "youtube-summary": {
        "label": "Summarize video",
        "blurb": "youtube-summarizer skill. Needs a video URL.",
        "icon": "▶",
        "kind": "claude",
        "prompt": "/youtube-summarizer {input}",
        "model": "sonnet",
        "options": True,
        "input_label": "YouTube URL",
        "input_pattern": r"^https?://(www\.)?(youtube\.com|youtu\.be)/\S+$",
    },
    "trail-build": {
        "label": "Rebuild graph",
        "blurb": "Refresh the trail repo context graph. Deterministic, no model, $0.",
        "icon": "⬢",
        "kind": "shell",
        "argv": ["trail", "build"],
    },
    "resume-build": {
        "label": "Build résumés",
        "blurb": "Export the four variants and tailored copies to .docx and .pdf. Deterministic, no model, $0.",
        "icon": "▤",
        "kind": "shell",
        "argv": ["sh", "resume/build.sh"],
        # Optional month, passed as its own argv element; blank = build.sh's current month.
        "input_label": "Month (YYYY-MM, blank = this month)",
        "input_type": "text",
        "input_pattern": r"^\d{4}-(0[1-9]|1[0-2])$",
        "input_optional": True,
        "input_argv": True,
    },
    # ── Organizer tools: also shown as one-tap buttons on the Today page ──
    "plan-today": {
        "label": "Plan today",
        "blurb": "Top three moves for today from TASKS.md, routine.md and DASHBOARD.md, with file:line cites. Read-only.",
        "icon": "☀",
        "kind": "claude",
        "prompt": (
            "Today is {today} (ISO week {week}). Read TASKS.md, routine.md and "
            "DASHBOARD.md in this workspace. Output, short enough to read on a "
            "phone: 1) today's routine block per routine.md (odd ISO week = Week A, "
            "even = Week B); 2) the three highest-leverage open TASKS.md items "
            "doable today, each with one concrete first step; 3) anything overdue "
            "or stale. Cite file:line for every item. Never invent a task, date or "
            "status. Do not edit any file."
        ),
        "model": "sonnet",
        "context_files": ["TASKS.md", "routine.md", "DASHBOARD.md"],
    },
    "scout-scan": {
        "label": "Run Scout scan",
        "blurb": "Free search-and-rank pass over the configured job sources. Writes a scan to workspace/agents/scout/outputs/.",
        "icon": "◎",
        "kind": "opencode-agent",
        "agent": "scout",
        "prompt": (
            "Today is {today}. You are Scout. Read workspace/agents/scout/memory/index.md "
            "and the search history in workspace/agents/scout/memory/log.jsonl first. "
            "Run a free search-and-rank pass using the job sources configured for the "
            "system; if none are configured, use the sources recorded in your memory. "
            "Merge and de-duplicate listings, score every listing 0-100 against "
            "Roosevelt's profile, and read no full job descriptions. Write the complete "
            "result to workspace/agents/scout/outputs/scan-{today}.json and a readable "
            "summary to workspace/agents/scout/outputs/scan-{today}.md. Update "
            "workspace/agents/scout/memory/index.md and append your events to "
            "workspace/agents/scout/memory/log.jsonl. Do not run Job Reader, do not "
            "tailor a CV, and do not use any paid step. Finish by reporting source "
            "failures, the number of listings found and scored, and the top matches."
        ),
        "options": True,
        "providers": ["opencode"],
        "read_only": False,
    },
    "triage-inbox": {
        "label": "Triage inbox",
        "blurb": "Jev judges which existing section each unchecked Inbox item belongs to in TASKS.md; code does the filing, wording unchanged. Edits TASKS.md.",
        "icon": "⇲",
        # Jev answers two questions per item (does a section fit, which one) and
        # triage_jev.py holds the thresholds and the edit. No model selector:
        # the decision, not a prompt, is what this card runs.
        "kind": "shell",
        "argv": [sys.executable, "dashboard-app/triage_jev.py"],
    },
    "brain-index": {
        "label": "Reindex brain",
        "blurb": "Rebuild the second-brain catalogue from sources and memories. Deterministic, no model, $0.",
        "icon": "◎",
        "kind": "shell",
        "argv": [sys.executable, "second-brain/brain.py", "index"],
    },
    "arms-report": {
        "label": "Routine report",
        "blurb": "Regenerate the ARMS passive routine findings (tools/arms/data/routines.json). No model, $0.",
        "icon": "☰",
        "kind": "shell",
        "argv": [sys.executable, "tools/arms/routines.py", "run"],
    },
    "artifact-catalog": {
        "label": "Artifact catalog",
        "blurb": "Rebuild the searchable artifacts/ index. No model, $0.",
        "icon": "▦",
        "kind": "shell",
        "argv": [sys.executable, "artifacts/catalog.py"],
    },
}

_RUNS: dict[str, dict] = {}
_RUNS_LOCK = threading.Lock()


class RunRequest(BaseModel):
    skill: str
    model: str | None = None
    effort: str | None = None
    input: str | None = None


def _log_run(entry: dict) -> None:
    """Append one JSON event per state change; preserve command and output path."""
    with RUNS_LOG.open("a") as fh:
        fh.write(
            json.dumps(
                {
                    "timestamp": datetime.now().astimezone().isoformat(),
                    **entry,
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def _build_update_sheet_prompt() -> str:
    """Reuse the prompt already embedded in index.html so there is one copy."""
    today = date.today()
    src = (Path(__file__).parent / "templates" / "index.html").read_text()
    m = re.search(r'<template id="update-sheet-prompt">(.*?)</template>', src, re.S)
    if not m:
        return (
            "Update the CloudTransition workspace so every dated file reflects today."
        )
    return (
        m.group(1)
        .replace("{{ today }}", today.isoformat())
        .replace("{{ current_week }}", str(current_week_of_year(today)))
    )


def _parse_model(value: str | None) -> tuple[str, str] | None:
    """Parse a model selection into (provider, model_id).

    Accepts "provider:model_id" for any provider, or a bare Claude alias
    (sonnet/opus/fable) treated as "claude:<alias>" for backward compatibility.
    Returns None when the value cannot be parsed.
    """
    if value is None:
        return None
    if value in ALLOWED_MODELS:
        return "claude", value
    if ":" in value:
        provider, _, model_id = value.partition(":")
        if provider in PROVIDERS and model_id:
            return provider, model_id
    return None


def _card_allows_provider(cfg: dict, provider: str) -> tuple[bool, str | None]:
    """Whether a provider may run this card, respecting read/write boundaries.

    A card that declares ``providers`` is restricted to exactly those
    providers; every other card keeps the permissive behavior. For those
    unrestricted cards, Claude is always allowed (its existing per-card tool
    restrictions apply) and every other provider is allowed too: the user
    accepts that the provider cannot machine-enforce the card's read-only or
    file/command allowlist. Boundary enforcement is then the user's
    responsibility when choosing a provider.
    """
    allowed = cfg.get("providers")
    if allowed and provider not in allowed:
        return False, f"{cfg['label']} only supports {', '.join(allowed)} models."
    return True, None


def _run_openrouter(model_id: str, prompt: str) -> dict:
    """Call the OpenRouter chat API. Returns {status, exit_code, body}.

    Never logs the API key. Returns a failed result when
    OPENROUTER_API_KEY is unset, so no model call is made.
    """
    api_key = os.environ.get(OPENROUTER_API_KEY_ENV)
    if not api_key:
        return {
            "status": "failed",
            "exit_code": -1,
            "body": (
                "OpenRouter is not configured: set OPENROUTER_API_KEY. "
                "No model call was made."
            ),
        }
    payload = json.dumps(
        {"model": model_id, "messages": [{"role": "user", "content": prompt}]}
    ).encode()
    request = urllib.request.Request(
        OPENROUTER_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=RUN_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", "replace")
            return {"status": "done", "exit_code": 0, "body": body}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:2000]
        return {"status": "failed", "exit_code": -1, "body": body}
    except urllib.error.URLError as exc:
        return {
            "status": "failed",
            "exit_code": -1,
            "body": f"OpenRouter request failed: {exc}",
        }
    except OSError as exc:
        return {"status": "failed", "exit_code": -1, "body": f"OpenRouter error: {exc}"}


def _workspace_context(files: list[str]) -> str:
    """Inline a card's declared files for providers that cannot read them.

    Paths outside the workspace and privacy-flagged paths are skipped, and the
    rendered text is bounded so a request cannot balloon.
    """
    base = WORKSPACE.resolve()
    remaining = CONTEXT_MAX_CHARS
    parts: list[str] = []
    for rel in files:
        rel_path = Path(rel)
        target = (WORKSPACE / rel_path).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            continue
        if wc.privacy_violation(rel_path.as_posix()) or not target.is_file():
            continue
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        limited = text[: min(CONTEXT_MAX_FILE_CHARS, max(remaining, 0))]
        if not limited:
            break
        numbered = "\n".join(
            f"{number:>5}| {line}"
            for number, line in enumerate(limited.splitlines(), start=1)
        )
        suffix = "\n… truncated" if len(limited) < len(text) else ""
        parts.append(f"### {rel_path.as_posix()}\n{numbered}{suffix}")
        remaining -= len(numbered)
        if remaining <= 0:
            break
    if not parts:
        return ""
    return (
        "Workspace context follows because this provider cannot read files. "
        "Use it and cite line numbers as path:line.\n\n" + "\n\n".join(parts)
    )


def _resolve_run(cfg: dict, req: RunRequest) -> tuple[dict, str]:
    """Build a run specification. Returns (run_spec, human-readable command).

    run_spec has a "kind" key: "shell", "claude", "codex", "opencode", or
    "openrouter". Subprocess kinds carry an "argv" list; OpenRouter carries
    "model" and "prompt" and is dispatched over HTTP in _execute_run.
    """
    if cfg["kind"] == "shell":
        argv = list(cfg["argv"])
        if cfg.get("input_argv") and req.input:
            argv.append(req.input)
        return {"kind": "shell", "argv": argv}, shlex.join(argv)

    today = date.today()
    if cfg.get("prompt") is None:
        prompt = _build_update_sheet_prompt()
    else:
        # Placeholders: {input} (validated form value), {today}, {week}.
        prompt = cfg["prompt"].format(
            input=req.input or "",
            today=today.isoformat(),
            week=current_week_of_year(today),
        )

    options = cfg.get("options", True)
    if options and req.model is not None:
        parsed = _parse_model(req.model)
        if parsed is None:
            provider, model_id = "claude", cfg.get("model", "sonnet")
        else:
            provider, model_id = parsed
    else:
        provider, model_id = "claude", cfg.get("model", "sonnet")

    effort = req.effort if req.effort and req.effort != "default" else None

    # OpenRouter chats cannot read files, so inline the card's declared
    # workspace context for it. Local CLIs (claude/codex/opencode) read the
    # files themselves and must not get a copy in the prompt.
    if provider == "openrouter" and cfg.get("context_files"):
        if context := _workspace_context(cfg["context_files"]):
            prompt = f"{prompt}\n\n{context}"

    if provider == "claude":
        argv = [
            "claude",
            "-p",
            prompt,
            "--model",
            model_id,
            "--permission-mode",
            "dontAsk" if cfg.get("read_only") or cfg.get("permissions") else "acceptEdits",
            "--permission-prompts",
            "none",
        ]
        if cfg.get("read_only"):
            argv += [
                "--tools",
                "Read,Glob,Grep,Skill",
                "--allowedTools",
                "Read,Glob,Grep,Skill",
            ]
        if perms := cfg.get("permissions"):
            argv += ["--tools", ",".join(perms["tools"]), "--allowedTools", *perms["allow"]]
            for d in perms.get("add_dirs", []):
                argv += ["--add-dir", d]
        if effort:
            argv += ["--effort", effort]
        return {"kind": "claude", "argv": argv}, shlex.join(argv)

    if provider == "codex":
        exe = _resolve_codex_exe()
        if exe is None:
            return (
                {"kind": "error", "error": "codex executable not on PATH"},
                "codex exec -m <model> <prompt>",
            )
        sandbox = "read-only" if cfg.get("read_only") else "workspace-write"
        argv = [
            exe,
            "exec",
            "-m",
            model_id,
            "-s",
            sandbox,
            "-C",
            str(WORKSPACE),
            "--color",
            "never",
            prompt,
        ]
        if effort:
            argv += ["-c", f"model_reasoning_effort={effort}"]
        return {"kind": "codex", "argv": argv}, shlex.join(argv)

    if provider == "opencode":
        exe = _resolve_opencode_exe()
        if exe is None:
            return (
                {"kind": "error", "error": "opencode executable not on PATH"},
                "opencode run --standalone -m <model> <prompt>",
            )
        # --standalone avoids the shared background service so a stale service
        # registration cannot make the run hang.
        argv = [exe, "run", "--standalone"]
        if cfg.get("kind") == "opencode-agent":
            argv += ["--agent", cfg["agent"]]
        argv += ["-m", model_id, prompt]
        return {"kind": "opencode", "argv": argv}, shlex.join(argv)

    # openrouter — dispatched over HTTP in _execute_run
    return (
        {"kind": "openrouter", "model": model_id, "prompt": prompt},
        f"openrouter {model_id} <prompt>",
    )


def _execute_run(run_id: str, run_spec: dict) -> None:
    """Run the command to completion in a worker thread; record the result.

    run_spec["kind"] is "shell"/"claude"/"codex"/"opencode" (subprocess via
    run_spec["argv"]) or "openrouter" (HTTP via run_spec["model"]/prompt).
    """
    RUNS_DIR.mkdir(exist_ok=True)
    out_path = RUNS_DIR / f"{run_id}.txt"
    started = time.time()
    try:
        if run_spec["kind"] == "error":
            result = {
                "status": "failed",
                "exit_code": -1,
                "body": run_spec.get("error", "run spec error"),
            }
        elif run_spec["kind"] == "openrouter":
            result = _run_openrouter(run_spec["model"], run_spec["prompt"])
        else:
            argv = run_spec["argv"]
            proc = subprocess.run(
                argv,
                cwd=WORKSPACE,
                capture_output=True,
                text=True,
                timeout=RUN_TIMEOUT,
                check=False,
            )
            body = proc.stdout + (
                f"\n\n--- stderr ---\n{proc.stderr}" if proc.stderr.strip() else ""
            )
            result = {
                "status": "done" if proc.returncode == 0 else "failed",
                "exit_code": proc.returncode,
                "body": body,
            }
    except subprocess.TimeoutExpired:
        result = {
            "status": "failed",
            "exit_code": -1,
            "body": f"Timed out after {RUN_TIMEOUT}s.",
        }
    except FileNotFoundError:
        result = {
            "status": "failed",
            "exit_code": -1,
            "body": f"Command not found: {run_spec['argv'][0]}. Is it on PATH?",
        }
    except OSError as exc:
        result = {"status": "failed", "exit_code": -1, "body": f"Failed to start: {exc}"}

    out_path.write_text(result["body"])
    duration = f"{time.time() - started:.1f}s"

    with _RUNS_LOCK:
        entry = _RUNS.get(run_id)
        if entry is not None:
            entry.update(
                status=result["status"],
                exit_code=result["exit_code"],
                duration=duration,
                output=str(out_path.relative_to(WORKSPACE)),
                preview=result["body"].strip()[-400:],
            )
            _log_run(entry)


@app.get("/api/skills/catalog")
def api_skill_catalog():
    """The buttons the UI should render, with provider-labelled model catalogues."""
    return JSONResponse(_cached_skill_catalog())


@app.post("/api/skills/catalog/refresh")
def api_skill_catalog_refresh():
    """Force a fresh read of the provider catalogues (Refresh models button)."""
    return JSONResponse(_cached_skill_catalog(force=True))


@app.post("/api/skills/run")
def api_skill_run(req: RunRequest, x_requested_with: str = Header(default="")):
    """Start one skill run in the background; return its id immediately."""
    if x_requested_with != "XMLHttpRequest":
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)

    cfg = SKILL_RUNNERS.get(req.skill)
    if cfg is None:
        return JSONResponse({"error": "Unknown skill"}, status_code=400)

    # Resolve provider/model, validating against the provider catalogues.
    options = cfg.get("options", True)
    if options and req.model is not None:
        parsed = _parse_model(req.model)
        if parsed is None:
            return JSONResponse({"error": "Unknown model"}, status_code=400)
        provider, model_id = parsed
    else:
        provider, model_id = "claude", cfg.get("model", "sonnet")

    # Effort validation is provider-specific.
    effort = req.effort if req.effort is not None else "default"
    if provider == "claude":
        valid_efforts = list(ALLOWED_EFFORT)
    elif provider == "codex":
        # Only the Codex cache is needed here; loading every provider catalogue
        # would shell out to `opencode models` on each launch and delay the run.
        codex_models, codex_ok, codex_reason = _load_codex_models()
        if not codex_ok:
            # Missing cache or missing executable: report it instead of
            # launching (or rejecting it as an "unsupported effort").
            return JSONResponse({"error": codex_reason}, status_code=400)
        valid_efforts = [
            e for m in codex_models if m["id"] == model_id for e in m.get("efforts", [])
        ]
    else:  # opencode / openrouter — effort stays Default
        valid_efforts = ["default"]
    if effort not in valid_efforts:
        return JSONResponse({"error": "Unsupported effort for this model"}, status_code=400)

    # Permission parity: refuse provider/card pairings that cannot enforce the
    # card's read-only or command/template boundary.
    allowed, reason = _card_allows_provider(cfg, provider)
    if not allowed:
        return JSONResponse({"error": reason}, status_code=400)

    # OpenRouter requires a configured API key before anything launches.
    if provider == "openrouter" and not os.environ.get(OPENROUTER_API_KEY_ENV):
        return JSONResponse(
            {
                "error": "OpenRouter is not configured: set OPENROUTER_API_KEY. No model call was made."
            },
            status_code=400,
        )

    if cfg.get("input_label"):
        value = (req.input or "").strip()
        if not value and cfg.get("input_optional"):
            req.input = None
        elif not value:
            return JSONResponse(
                {"error": f"{cfg['input_label']} is required"}, status_code=400
            )
        elif not re.match(cfg["input_pattern"], value):
            return JSONResponse(
                {"error": f"Not a valid {cfg['input_label']}"}, status_code=400
            )
        else:
            req.input = value

    run_spec, shown = _resolve_run(cfg, req)

    run_id = uuid4().hex
    entry = {
        "id": run_id,
        "skill": req.skill,
        "label": cfg["label"],
        "provider": provider,
        "model": model_id,
        "effort": effort,
        "status": "running",
        "started": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "command": shown,
        "output": None,
        "duration": None,
        "preview": None,
    }
    with _RUNS_LOCK:
        # Check and reserve together: double-clicks must not start two processes.
        if any(
            r["status"] == "running" and r["skill"] == req.skill for r in _RUNS.values()
        ):
            return JSONResponse({"error": "Already running"}, status_code=409)
        try:
            _log_run(entry)
        except OSError:
            return JSONResponse(
                {"error": "Cannot write runs.log; run not started"}, status_code=503
            )
        _RUNS[run_id] = entry
        completed = sorted(
            (key for key, run in _RUNS.items() if run["status"] != "running"),
            key=lambda key: _RUNS[key]["started"],
        )
        for stale in completed[:-MAX_RUNS_KEPT]:
            _RUNS.pop(stale, None)

    threading.Thread(target=_execute_run, args=(run_id, run_spec), daemon=True).start()
    return JSONResponse({"ok": True, "run": entry})


@app.get("/api/skills/runs")
def api_skill_runs():
    """Current status of every tracked run, newest first."""
    with _RUNS_LOCK:
        runs = sorted(_RUNS.values(), key=lambda r: r["started"], reverse=True)
    return JSONResponse({"runs": runs})


@app.get("/api/metrics")
def api_metrics():
    """Collect observed tailnet telemetry and local project health."""
    try:
        from metrics import collect_all_metrics

        return JSONResponse(collect_all_metrics())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/metrics/history")
def api_metrics_history(window: str = "1h"):
    """Read bounded, allowlisted performance history from Prometheus."""
    if window not in ("1h", "6h", "24h"):
        return JSONResponse({"error": "Choose 1h, 6h, or 24h."}, status_code=422)
    try:
        from metrics import collect_metric_history

        return JSONResponse(collect_metric_history(window))
    except Exception:
        return JSONResponse(
            {"error": "Performance history is unavailable."}, status_code=503
        )


@app.get("/api/metrics/rates")
def api_metrics_rates(window: str = "1h"):
    """Network/disk rates, probe timeline and log volume for the Metrics charts."""
    if window not in ("1h", "6h", "24h"):
        return JSONResponse({"error": "Choose 1h, 6h, or 24h."}, status_code=400)
    try:
        from metric_charts import collect_chart_history

        return JSONResponse(collect_chart_history(window))
    except Exception:
        return JSONResponse({"error": "Chart history is unavailable."}, status_code=503)
