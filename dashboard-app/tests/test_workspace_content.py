"""Workspace map file access: only indexed or live-artifact files, rechecked at request time."""

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import workspace_content as wc  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("catalog", ROOT / "artifacts" / "catalog.py")
catalog = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(catalog)


def touch(root: Path, rel: str, text: str = "x") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "ws"
    touch(root, "resume/master.md", "# Master")
    touch(root, "resume/café #1.md", "# Unicode")
    touch(root, "artifacts/report.html", "<title>Report</title><script>alert(1)</script>")
    touch(root, "artifacts/style.css", "body{}")
    touch(root, "resume/not-yet-indexed.md")
    index = tmp_path / "index.json"
    files = ["resume/master.md", "resume/café #1.md", "artifacts/style.css"]
    index.write_text(json.dumps({"schemaVersion": 2, "files": [{"relativePath": f} for f in files]}))
    (root / "resume/not-yet-indexed.md").touch()
    return root, index


def status(fn):
    with pytest.raises(wc.ContentError) as err:
        fn()
    return err.value.status


def test_indexed_file_resolves_to_exact_path(ws):
    root, index = ws
    assert wc.resolve_file(root, index, "resume/café #1.md") == (root / "resume/café #1.md").resolve()


@pytest.mark.parametrize(
    "rel",
    ["../secret.md", "resume/../../secret.md", "/etc/passwd", "resume\\master.md", "", "resume/./master.md",
     "resume//master.md", "resume/master.md\x00.png", "C:/x.md"],
)
def test_malformed_or_traversing_paths_are_denied(ws, rel):
    root, index = ws
    assert status(lambda: wc.resolve_file(root, index, rel)) == 403


def test_existing_file_outside_index_is_denied(ws):
    root, index = ws
    assert status(lambda: wc.resolve_file(root, index, "resume/not-yet-indexed.md")) == 403


@pytest.mark.parametrize(
    "rel",
    ["resume/.env", "resume/api-token.txt", "IT Mgmt/Employer-IT-Playbook-Private/a.md",
     "College Planning/transcript.pdf", "unlisted/notes.md"],
)
def test_private_paths_are_denied_even_when_listed_in_index(ws, rel):
    root, index = ws
    touch(root, rel)
    data = json.loads(index.read_text())
    data["files"].append({"relativePath": rel})
    index.write_text(json.dumps(data))
    assert status(lambda: wc.resolve_file(root, index, rel)) == 403


def test_symlinks_are_denied_even_when_listed(ws, tmp_path):
    root, index = ws
    outside = touch(tmp_path, "outside/secret.md", "outside")
    (root / "resume/link.md").symlink_to(outside)
    (root / "resume/linkdir").symlink_to(outside.parent, target_is_directory=True)
    data = json.loads(index.read_text())
    data["files"] += [{"relativePath": "resume/link.md"}, {"relativePath": "resume/linkdir/secret.md"}]
    index.write_text(json.dumps(data))
    assert status(lambda: wc.resolve_file(root, index, "resume/link.md")) == 403
    assert status(lambda: wc.resolve_file(root, index, "resume/linkdir/secret.md")) == 403


def test_file_deleted_after_indexing_is_not_found(ws):
    root, index = ws
    (root / "resume/master.md").unlink()
    assert status(lambda: wc.resolve_file(root, index, "resume/master.md")) == 404


@pytest.mark.parametrize("content", [None, "{not json", '{"schemaVersion": 1, "files": []}'])
def test_unusable_index_is_unavailable(ws, content):
    root, index = ws
    if content is None:
        index.unlink()
    else:
        index.write_text(content)
    assert status(lambda: wc.resolve_file(root, index, "resume/master.md")) == 503


def test_new_artifact_opens_before_index_refresh(ws):
    root, index = ws
    index.unlink()
    assert wc.resolve_file(root, index, "artifacts/report.html").name == "report.html"


def test_active_documents_are_sandboxed_without_network():
    media, headers = wc.file_headers(Path("artifacts/report.html"), download=False)
    assert media.startswith("text/html")
    csp = headers["Content-Security-Policy"]
    assert "sandbox" in csp and "default-src 'none'" in csp
    _, svg = wc.file_headers(Path("a/logo.svg"), download=False)
    assert "sandbox" in svg["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_source_files_are_shown_as_plain_text():
    media, _ = wc.file_headers(Path("dashboard-app/static/app.js"), download=False)
    assert media == "text/plain; charset=utf-8"


def test_download_uses_exact_unicode_filename():
    _, headers = wc.file_headers(Path("resume/café #1.md"), download=True)
    assert headers["Content-Disposition"] == "attachment; filename*=UTF-8''caf%C3%A9%20%231.md"


def test_artifact_entries_are_newest_first_and_safe(ws):
    root, _ = ws
    touch(root, "artifacts/index.html", "<title>generated</title>")
    touch(root, "artifacts/client_secret.html", "<title>secret</title>")
    touch(root, "artifacts/.hidden/x.html")
    older = root / "artifacts/report.html"
    os.utime(older, (time.time() - 3600, time.time() - 3600))
    touch(root, "artifacts/new-deck.pdf")
    rows = wc.artifact_entries(root)
    paths = [r["relativePath"] for r in rows]
    assert paths == ["artifacts/new-deck.pdf", "artifacts/report.html"]
    assert rows[1]["title"] == "Report"
    assert rows[0]["modified"][-6] in "+-"


def test_catalog_collects_entries_and_escapes_titles(tmp_path):
    touch(tmp_path, "a.html", "<title>&lt;b&gt; <script>x</script></title>")
    touch(tmp_path, "index.html", "old")
    (tmp_path / "linked.html").symlink_to(tmp_path / "a.html")
    entries = catalog.collect_entries(tmp_path)
    assert [e["relativePath"] for e in entries] == ["a.html"]
    assert catalog.build(tmp_path) == 1
    page = (tmp_path / "index.html").read_text()
    assert "<script>x</script>" not in page


@pytest.mark.parametrize("name", ["feed.xht", "logo.svgz", "style.xsl", "page.mhtml", "data.rdf", "tool.exe"])
def test_unknown_or_active_types_download_sandboxed_instead_of_rendering(name):
    media, headers = wc.file_headers(Path("projects/x") / name, download=False)
    assert media == "application/octet-stream"
    assert headers["Content-Disposition"].startswith("attachment")
    assert "sandbox" in headers["Content-Security-Policy"]


@pytest.mark.parametrize("name", ["photo.png", "deck.pdf", "notes.md"])
def test_safe_types_still_preview_inline(name):
    _, headers = wc.file_headers(Path("resources") / name, download=False)
    assert headers["Content-Disposition"].startswith("inline")


def test_catalog_skips_generated_index_in_subfolders(tmp_path):
    touch(tmp_path, "deck/index.html", "<title>nested generated</title>")
    touch(tmp_path, "deck/slides.html", "<title>Slides</title>")
    assert [e["relativePath"] for e in catalog.collect_entries(tmp_path)] == ["deck/slides.html"]


@pytest.mark.parametrize("name", ["resume/notes\\draft.md", "resume/C:notes.md"])
def test_posix_names_with_backslash_or_drive_prefix_open(ws, name):
    root, index = ws
    touch(root, name, "ok")
    data = json.loads(index.read_text())
    data["files"].append({"relativePath": name})
    index.write_text(json.dumps(data))
    assert wc.resolve_file(root, index, name) == (root / name).resolve()


def test_unindexed_generated_artifact_index_is_denied(ws):
    root, index = ws
    touch(root, "artifacts/index.html", "<title>generated</title>")
    assert status(lambda: wc.resolve_file(root, index, "artifacts/index.html")) == 403


def test_artifact_with_unreadable_title_is_still_listed(ws):
    root, _ = ws
    locked = touch(root, "artifacts/locked.html", "<title>x</title>")
    locked.chmod(0)
    try:
        paths = [r["relativePath"] for r in wc.artifact_entries(root)]
    finally:
        locked.chmod(0o644)
    assert "artifacts/locked.html" in paths


@pytest.mark.parametrize(
    "rel, allowed",
    [("College Planning/README.md", False), ("IT Mgmt/Employer-IT-Playbook-Private/x.md", False),
     ("interviews/ross-work-log.md", False), ("resume/.env", False), ("dashboard-app/runs/abc.txt", True),
     ("archive/notes.md", True), (".trail/cache/College Planning/x.md", False),
     ("backup/it mgmt/employer-it-playbook-private/y.md", False)],
)
def test_reader_privacy_rules(rel, allowed):
    assert (wc.privacy_violation(rel) is None) is allowed


def test_reader_api_refuses_private_files_and_lists_none():
    import app

    resp = app.api_file(path="College Planning/README.md")
    assert resp.status_code == 403
    listed = [f["path"] for f in app.discover_md_files()]
    assert not any(p.startswith("College Planning/") or "Private" in p for p in listed)
    assert any(p == "TASKS.md" for p in listed)


def test_artifacts_api_reports_unreadable_folder(monkeypatch):
    import app

    def boom(*_a, **_k):
        raise OSError("drive gone")

    monkeypatch.setattr(wc, "artifact_entries", boom)
    assert app.workspace_artifacts().status_code == 503
