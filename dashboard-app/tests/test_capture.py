"""Inbox capture must append to the right place without disturbing TASKS.md."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.tasks import insert_inbox_item  # noqa: E402

HEADER = "# Tasks\n\n_Last updated: x_\n\n"


def test_creates_inbox_above_active_when_missing():
    src = HEADER + "## Active\n\n- [ ] keep\n"
    out, line = insert_inbox_item(src, "call bank")
    assert out == HEADER + "## Inbox\n\n- [ ] call bank\n\n## Active\n\n- [ ] keep\n"
    assert out.splitlines()[line - 1] == "- [ ] call bank"


def test_appends_after_last_item_before_next_heading():
    src = HEADER + "## Inbox\n\n- [ ] one\n\n## Active\n\n- [ ] keep\n"
    out, line = insert_inbox_item(src, "two")
    assert out == HEADER + "## Inbox\n\n- [ ] one\n- [ ] two\n\n## Active\n\n- [ ] keep\n"
    assert out.splitlines()[line - 1] == "- [ ] two"


def test_empty_inbox_keeps_blank_line_under_heading():
    src = HEADER + "## Inbox\n\n## Active\n"
    out, line = insert_inbox_item(src, "first")
    assert out == HEADER + "## Inbox\n\n- [ ] first\n\n## Active\n"
    assert out.splitlines()[line - 1] == "- [ ] first"


def test_inbox_as_last_section_and_no_active_heading():
    out, line = insert_inbox_item("# Tasks\n## Inbox\n- [ ] a", "b")
    assert out == "# Tasks\n## Inbox\n- [ ] a\n- [ ] b\n"
    assert line == 4

    out, line = insert_inbox_item("# Tasks\nnotes", "c")
    assert out == "# Tasks\nnotes\n\n## Inbox\n\n- [ ] c\n\n"
    assert out.splitlines()[line - 1] == "- [ ] c"
