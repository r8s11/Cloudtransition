#!/usr/bin/env python3
"""Build the local HTML artifact inbox; no model, network, or dependencies."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import html
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import quote

SUFFIXES = {'.html', '.pdf', '.png', '.jpg', '.jpeg', '.svg'}


def is_artifact(rel: str) -> bool:
    """Whether a root-relative path is listed by the inbox: no hidden parts, not the index, known suffix."""
    parts = rel.split('/')
    return (not any(p.startswith('.') for p in parts) and parts[-1] != 'index.html'
            and Path(parts[-1]).suffix.lower() in SUFFIXES)


def collect_entries(root: Path) -> list[dict]:
    """Artifacts under root, newest first. Hidden paths, symlinks and the generated index are skipped."""
    root = root.resolve()
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and not (here / d).is_symlink()]
        for name in filenames:
            path = here / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink() or not is_artifact(rel):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            title = path.stem.replace('-', ' ')
            if path.suffix.lower() == '.html':
                try:
                    text = path.read_text(encoding='utf-8', errors='replace')
                except OSError:
                    text = ''  # unreadable: keep the filename title, still list it
                match = re.search(r'<title>(.*?)</title>', text, re.I | re.S)
                if match:
                    title = html.unescape(match.group(1).strip())
            modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc).astimezone()
            entries.append({
                'title': title,
                'relativePath': rel,
                'extension': path.suffix.lower().lstrip('.'),
                'bytes': stat.st_size,
                'modified': modified.isoformat(timespec='seconds'),
                '_mtime_ns': stat.st_mtime_ns,
            })
    entries.sort(key=lambda row: (-row['_mtime_ns'], row['relativePath']))
    for row in entries:
        del row['_mtime_ns']
    return entries


def build(root: Path) -> int:
    root = root.resolve()
    entries = collect_entries(root)
    rows = '\n'.join(
        f'<li><a href="{quote(e["relativePath"], safe="/")}">{html.escape(e["title"])}</a>'
        f'<small>{html.escape(e["relativePath"])}</small></li>' for e in entries
    )
    page = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>CloudTransition artifact inbox</title>
<link rel="stylesheet" href="style.css"><main><header><h1>Artifact inbox</h1>
<p>HTML sources and final exports. Newest first. Everything stays local.</p></header>
<label for="search">Find an artifact</label><input id="search" type="search" placeholder="Title or filename">
<p id="count" role="status"></p><ul id="artifacts">''' + rows + '''</ul>
<p id="empty" hidden>No matching artifacts.</p><footer>Rebuild after saving: <code>python3 artifacts/catalog.py</code></footer></main>
<script>
const search = document.querySelector('#search');
const rows = [...document.querySelectorAll('#artifacts li')];
function filter() {
  const query = search.value.toLocaleLowerCase();
  let count = 0;
  rows.forEach(row => { row.hidden = !row.textContent.toLocaleLowerCase().includes(query); if (!row.hidden) count++; });
  document.querySelector('#count').textContent = `${count} artifact${count === 1 ? '' : 's'}`;
  document.querySelector('#empty').hidden = count !== 0;
}
search.addEventListener('input', filter); filter();
</script></html>'''
    descriptor, temporary = tempfile.mkstemp(prefix='.catalog-', dir=root)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            output.write(page)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, root / 'index.html')
    finally:
        Path(temporary).unlink(missing_ok=True)
    return len(entries)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(f'Indexed {build(args.root)} artifacts in {args.root / "index.html"}')
