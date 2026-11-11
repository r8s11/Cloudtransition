#!/usr/bin/env python3
"""R5: no real contact value from resume/master.md appears in job-autofill/ or the plan's eval-evidence/.

Reads the header contact line of the real master resume at run time and extracts
phone, email, LinkedIn handle and GitHub handle. Exits 1 on any hit. Never prints
the matched value itself, only which kind of value hit and where.
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "resume" / "master.md"
SCAN_ROOTS = [ROOT / "job-autofill", ROOT / "docs" / "plans" / "job-autofill-extension" / "eval-evidence"]
SKIP_DIRS = {"node_modules", ".cache", "test-results", "playwright-report", "__pycache__", ".git"}
MAX_BYTES = 5_000_000


def contact_line(text):
    """First line after the H1 heading that holds pipe-separated contact values."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("# "):
            for nxt in lines[i + 1:i + 8]:
                if nxt.count("|") >= 2:
                    return nxt
            break
    raise SystemExit("check_no_personal_data: contact line not found in resume/master.md")


def extract(line):
    """Return a list of (kind, regex) for each contact value found."""
    found = []
    for m in re.finditer(r"\+?\d[\d ().-]{7,}\d", line):
        digits = re.sub(r"\D", "", m.group())
        if len(digits) >= 10:
            found.append(("phone", re.compile(r"\D*".join(re.escape(d) for d in digits[-10:]))))
    for m in re.finditer(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", line):
        found.append(("email", re.compile(re.escape(m.group()), re.I)))
    for kind, pat in (("linkedin", r"linkedin\.com/in/([A-Za-z0-9_%-]+)"), ("github", r"github\.com/([A-Za-z0-9_-]+)")):
        for m in re.finditer(pat, line, re.I):
            found.append((kind, re.compile(re.escape(m.group(1)), re.I)))
    return found


def text_files(base):
    if not base.exists():
        return
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            try:
                if p.stat().st_size > MAX_BYTES:
                    continue
                data = p.read_bytes()
            except OSError:
                continue
            if b"\0" in data[:4096]:
                continue
            yield p, data.decode("utf-8", errors="ignore")


def main():
    patterns = extract(contact_line(MASTER.read_text(encoding="utf-8")))
    kinds = {k for k, _ in patterns}
    missing = {"phone", "email", "linkedin", "github"} - kinds
    if missing:
        raise SystemExit(f"check_no_personal_data: could not extract {sorted(missing)} from resume/master.md header")
    hits = []
    for base in SCAN_ROOTS:
        for path, text in text_files(base):
            for kind, rx in patterns:
                if rx.search(text):
                    hits.append((kind, path.relative_to(ROOT)))
    for kind, path in hits:
        print(f"personal {kind} value found in {path}", file=sys.stderr)
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
