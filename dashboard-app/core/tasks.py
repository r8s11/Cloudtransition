"""Markdown checkbox tasks across the REALMS files, and Inbox capture."""

import re
from pathlib import Path

from core import calendar_sources, config
from core import workspace_content as wc


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
            raw_text = m.group(3)[2:]
            try:
                text, schedule = calendar_sources.split_metadata(raw_text)
            except ValueError:
                text, schedule = raw_text.split("<!-- calendar:", 1)[0].rstrip(), {}
            realm = next((r for r in config.REALMS if r["id"] == realm_id), None)
            items.append(
                {
                    "text": text,
                    "raw_text": raw_text,
                    "schedule": schedule,
                    "calendar_available": bool(realm and not wc.privacy_violation(realm["file"])),
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

    for realm in config.REALMS:
        path = config.WORKSPACE / realm["file"]
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


# ── Inbox capture ─────────────────────────────────────────────
INBOX_HEADING = "## Inbox"


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
