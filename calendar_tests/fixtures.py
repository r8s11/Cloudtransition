"""Synthetic source data only; never reads the owner's workspace checklist."""
from pathlib import Path

CHECKLIST = "## Work\n- [ ] Review plan\n- [ ] Read notes\n- [ ] Prepare outline\n- [x] Finished\n```md\n- [ ] Example only\n```\n"


def make_checklist(directory, text=CHECKLIST):
    source = Path(directory) / "TASKS.md"
    source.write_text(text, encoding="utf-8")
    return source
