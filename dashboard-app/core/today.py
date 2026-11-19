"""Today tab data: routine.md, Next up ranking, projects and the command centre."""

import http.client
import json
import re
import socket
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import yaml
from markupsafe import Markup, escape

from core import config
from core import workspace_content as wc
from core.store import load_yaml
from core.tasks import CHECKBOX_RE
from core.workspace_content import workspace_file_href


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
    path = config.WORKSPACE / "routine.md"
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


_MD_INLINE_RE = re.compile(r"`([^`]+)`|\*\*([^*]+)\*\*|\[([^\]]+)\]\([^)]+\)")


def md_inline(value: str) -> Markup:
    """Task text for display: `code` and **bold** render, links keep their text.

    The value is escaped first, so only these fixed tags reach the page.
    """

    def render(match: re.Match) -> str:
        code, bold, link = match.groups()
        if code is not None:
            return f"<code>{code}</code>"
        if bold is not None:
            return f"<strong>{bold}</strong>"
        return link

    return Markup(_MD_INLINE_RE.sub(render, str(escape(value))))



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
    path = path or config.WORKSPACE / "routine.md"
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

    Mon-Fri: Workday folds. Sat: project block and
    DevOps block. Sun: weekend money + review. The gold dot marks today —
    the first fold whose weekday matches the current date is the active step.
    """
    today = today or date.today()
    slots = parse_routine_slots()

    plan = [
        (0, f"Workday — {slots['workday']}"),
        (1, f"Workday — {slots['workday']}"),
        (2, f"Workday — {slots['workday']}"),
        (3, f"Workday — {slots['workday']}"),
        (4, f"Workday — {slots['workday']}"),
        (5, f"Project block — {slots['project']}"),
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
    ("salsasegura", 3),
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
    if "paused" in folded:  # a TASKS.md heading marks the lane on hold
        return _OTHER_LANE
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
        "quick_tools": config.QUICK_TOOLS,
    }


# ── Command centre (Today): daily destinations, recent artifacts, map freshness ──
# Each source is read on its own; a failure blanks only its own section.
# To add a destination, append a row in command_centre(); to add a widget, add a
# key here and a card in templates/pages/today.html.
RECENT_ARTIFACTS = 8
INDEX_STALE_DAYS = 7
ARTIFACT_KINDS = {
    "html": "HTML",
    "pdf": "PDF",
    "svg": "SVG",
    "png": "Image",
    "jpg": "Image",
    "jpeg": "Image",
}


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


_FIRST_PROJECT_LANE = 3  # NEXT_UP_LANES: playbook/MD-102, then DevOps, then Bogatyr


def live_projects(realm_tasks: dict, today: date) -> list[dict]:
    """Project sections of TASKS.md with their real counts.

    A section is a project when its heading falls in a project lane of
    NEXT_UP_LANES, so opening or closing a project is a TASKS.md edit.
    """
    week_a = today.isocalendar().week % 2 == 1
    live, waiting = ("playbook", "bogatyr") if week_a else ("bogatyr", "playbook")
    rows: dict[str, dict] = {}
    for task in realm_tasks["all"]:
        cat = task["cat"]
        if task["realm"] != "tasks":
            continue
        if not _FIRST_PROJECT_LANE <= _next_up_lane(cat) < _OTHER_LANE:
            continue
        folded = cat.casefold()
        if live in folded:
            when = "This week"
        elif waiting in folded:
            when = "Next week"
        else:
            when = "Every week" if "devops" in folded or "salsasegura" in folded else ""
        row = rows.setdefault(
            cat, {"name": cat, "when": when, "done": 0, "total": 0, "next": ""}
        )
        row["total"] += 1
        if task["done"]:
            row["done"] += 1
        elif not row["next"]:
            row["next"] = task["text"]
    for row in rows.values():
        row["pct"] = round(row["done"] / row["total"] * 100)
    return list(rows.values())


def mission_control_summary() -> dict:
    """Live agentic-os counts for Today. Offline is a state, not an error."""

    def rows(path: str) -> list[dict]:
        url = f"{config.MISSION_CONTROL_UPSTREAM}/api/{path}"
        with urllib.request.urlopen(
            url, timeout=config.MISSION_CONTROL_STATUS_TIMEOUT
        ) as resp:
            data = json.load(resp)
        if not isinstance(data, list):
            raise ValueError(path)
        return [row for row in data if isinstance(row, dict)]

    try:
        missions = rows("missions")
        approvals = rows("approvals")
        runs = rows("runs?active=true")
    except (OSError, ValueError, http.client.HTTPException):
        return {"ok": False}
    return {
        "ok": True,
        "missions": sum(m.get("status") in config.MISSION_OPEN_STATUSES for m in missions),
        "approvals": sum(a.get("status") == "pending" for a in approvals),
        "runs": len(runs),
    }


def brain_summary() -> dict:
    """Counts from the catalogue's own header line; brain.py is not run."""
    try:
        with config.BRAIN_CATALOGUE.open(encoding="utf-8") as fh:
            head = fh.read(2000)
        indexed = datetime.fromtimestamp(config.BRAIN_CATALOGUE.stat().st_mtime)
    except OSError:
        return {"ok": False}
    match = re.search(r"^Sources: (\d+) · Memories: (\d+)", head, re.M)
    if not match:
        return {"ok": False}
    return {
        "ok": True,
        "sources": int(match.group(1)),
        "memories": int(match.group(2)),
        "indexed": f"{indexed.day} {indexed:%b, %H:%M}",
    }


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def shortcut_groups() -> list[dict]:
    """SHORTCUTS as rendered rows, grouped in first-seen order."""
    try:
        indexed = wc.indexed_paths(wc.INDEX_FILE)
    except wc.ContentError:
        indexed = frozenset()
    groups: dict[str, list[dict]] = {}
    for tile in config.SHORTCUTS:
        row = {"label": tile["label"], "note": tile.get("note", ""), "ok": True}
        if "url" in tile:
            row.update(href=tile["url"], new_tab=True)
        elif "port" in tile:
            row.update(href=f"http://127.0.0.1:{tile['port']}/", new_tab=True)
            if not _port_open(tile["port"]):
                row.update(ok=False, note="Not running")
        elif "file" in tile:
            row.update(href=workspace_file_href(tile["file"]), new_tab=True, note=tile["file"])
            try:
                wc.resolve_file(config.WORKSPACE, wc.INDEX_FILE, tile["file"])
            except wc.ContentError:
                row.update(ok=False, note="Not available")
        else:
            folder = tile["folder"]
            row.update(
                href="#workspace-map",
                map_query="folder=" + urllib.parse.quote(folder),
                note=folder + "/",
            )
            if not any(p.startswith(folder + "/") for p in indexed):
                row.update(ok=False, note="Not available")
        groups.setdefault(tile["group"], []).append(row)
    return [{"name": name, "rows": rows} for name, rows in groups.items()]


def money_row() -> dict:
    """Daily's Money number: debts listed in the tracker, or a marked placeholder."""
    row = {"label": "Money", "href": "#money"}
    path = next((p for p in config.MONEY_CANDIDATES if p.exists()), None)
    if path is None:
        return {**row, "value": "No money tracker yet", "placeholder": True}
    row["note"] = "/".join(path.parts[-2:])
    try:
        debts = load_yaml(path).get("debts", [])
    except (OSError, yaml.YAMLError):
        debts = None
    if not isinstance(debts, list):
        return {**row, "value": "Tracker unreadable", "placeholder": True}
    if not debts:
        return {**row, "value": "No debts entered yet", "placeholder": True}
    return {**row, "value": f"{len(debts)} debt{'s' if len(debts) != 1 else ''} on file"}


def command_centre(
    realm_tasks: dict,
    today_view: dict,
    project_count: int,
    interview_action: dict | None = None,
    interview_counts: dict | None = None,
) -> dict:
    jobs = interview_counts or {}
    now = datetime.now(timezone.utc).astimezone()
    mission = mission_control_summary()
    brain = brain_summary()
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
            "label": "Job search",
            "href": "#interviews",
            "value": (
                f"{jobs.get('tracked', 0)} live · {jobs.get('active', 0)} in conversation · "
                f"{jobs.get('leads', 0)} new leads"
            ),
        },
        {
            "label": "Pydantic AI course",
            "href": "/learn/pydantic-ai/",
            "new_tab": True,
            "value": "8 lessons",
        },
        {
            "label": "Routine",
            "href": workspace_file_href("routine.md"),
            "new_tab": True,
            "value": "; ".join(blocks) if blocks else "Nothing scheduled today",
            "note": "routine.md",
        },
        {
            "label": "Projects",
            "href": "#projects",
            "value": f"{project_count} in TASKS.md",
        },
        money_row(),
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
            "label": "Mission Control",
            "href": "#mission-control",
            "value": (
                f"{mission['missions']} open missions · "
                f"{mission['approvals']} approvals waiting · "
                f"{mission['runs']} runs active"
            )
            if mission["ok"]
            else "Offline",
            "note": "agentic-os",
            "warn": not mission["ok"] or mission["approvals"] > 0,
        },
        {
            "label": "Second brain",
            "href": "#today",
            "focus": "brainAsk",
            "value": (
                f"{brain['sources']} sources · {brain['memories']} memories · "
                f"indexed {brain['indexed']}"
            )
            if brain["ok"]
            else "Catalogue unreadable: run Reindex brain",
            "warn": not brain["ok"],
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
        "shortcuts": shortcut_groups(),
    }


def money_available() -> bool:
    """True when a money/debt tracker exists in the workspace."""
    return any(p.exists() for p in config.MONEY_CANDIDATES)
