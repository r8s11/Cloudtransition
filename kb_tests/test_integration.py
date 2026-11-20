from __future__ import annotations
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import plistlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kb_runtime import install_guidance, install_schedule, ingest_lock, launcher_source
from fixtures import row, session


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_ingest_all_entrypoint(self):
        # Patch the network boundary in a separate Python process; run the real CLI.
        program = '''
import sys
from unittest.mock import patch
import kb_store, connectors, ingest_all
from pathlib import Path
folder=Path(sys.argv[1])
def ingest(source):
    def call(conn, **kwargs):
        kb_store.replace_rows(conn, source, 'item', [dict(kind='raw',ts='2026-11-04',title='fixture',content=source+' evidence',metadata={'path':'/synthetic'})])
        return {'processed':1}
    return call
with patch.object(connectors,'ingest_claude',ingest('claude')), patch.object(connectors,'ingest_gmail',ingest('gmail')):
    sys.exit(ingest_all.main(['--db',str(folder/'kb.sqlite'),'--runtime',str(folder/'runtime')]))
'''
        for _ in range(2):
            result = subprocess.run([sys.executable, "-c", program, str(self.root)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            logs = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual({x["source"] for x in logs}, {"claude", "gmail"})
        with contextlib.closing(sqlite3.connect(self.root / "kb.sqlite")) as conn:
            self.assertEqual(conn.execute("select count(*) from docs").fetchone()[0], 2)

    def test_partial_connector_failure(self):
        import kb_store
        from ingest_all import run_all
        for failed in ("gmail", "claude"):
            with self.subTest(failed=failed):
                conn = kb_store.connect(self.root / (failed + ".sqlite"))
                self.addCleanup(conn.close)
                kb_store.set_state(conn, failed, "last_success", "2026-10-01T00:00:00Z")
                def bad(c):
                    raise RuntimeError("api_key=synthetic-sensitive-canary")
                healthy = "claude" if failed == "gmail" else "gmail"
                def good(c):
                    kb_store.replace_rows(c, healthy, "item", [row()])
                    return {"processed": 1}
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = run_all(conn, {failed: bad, healthy: good}, runtime=self.root / "runtime")
                self.assertEqual(result[healthy]["status"], "ok")
                self.assertEqual(result[failed]["status"], "failed")
                self.assertNotIn("synthetic-sensitive-canary", output.getvalue())
                self.assertEqual(kb_store.get_state(conn, failed, "last_success"), "2026-10-01T00:00:00Z")
                self.assertEqual(conn.execute("select count(*) from docs where source=?", (healthy,)).fetchone()[0], 1)

    def test_storage_and_launcher_failures(self):
        import kb_store
        # The launcher lives on internal storage and refuses unavailable workspaces.
        launcher = self.root / "launch.py"
        launcher.write_text(launcher_source(self.root / "missing-volume", Path(sys.executable)))
        result = subprocess.run([sys.executable, str(launcher)], cwd=self.root, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("workspace unavailable", result.stdout)
        self.assertFalse((self.root / "missing-volume").exists())
        self.assertFalse((self.root / "kb.sqlite").exists())
        with ingest_lock(self.root / "runtime"):
            with self.assertRaises(RuntimeError):
                with ingest_lock(self.root / "runtime"):
                    self.fail("Concurrent ingest acquired a live lock")
        # Kernel releases flock on process death; restart also recovers uncommitted SQLite work.
        db = self.root / "interrupted.sqlite"
        conn = kb_store.connect(db)
        kb_store.replace_rows(conn, "claude", "kept", [row()])
        conn.close()
        program = '''import sqlite3,os,sys
c=sqlite3.connect(sys.argv[1]); c.execute('begin immediate'); c.execute('delete from docs'); os._exit(9)'''
        result = subprocess.run([sys.executable, "-c", program, str(db)])
        self.assertEqual(result.returncode, 9)
        conn = kb_store.connect(db)
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute("pragma integrity_check").fetchone()[0], "ok")
        self.assertEqual(conn.execute("select count(*) from docs").fetchone()[0], 1)
        with ingest_lock(self.root / "runtime"):
            pass
        # Unwritable/non-directory targets fail rather than creating an alternate DB.
        blocker = self.root / "not-directory"
        blocker.write_text("fixture")
        with self.assertRaises((OSError, sqlite3.Error)):
            kb_store.connect(blocker / "kb.sqlite")

    def test_git_and_shared_index_privacy(self):
        brain = load("kb_test_brain", "second-brain/brain.py")
        indexer = load("kb_test_indexer", "visual-second-brain/refresh-index.py")
        paths = ["kb.sqlite", "kb.sqlite-wal", "kb.sqlite-shm", "kb.sqlite-journal", ".env",
                 "gmail-token.json", "gmail-credentials.json", "kb-ingest.log", "kb-approval.json",
                 ".kb-private/manifest.json", ".kb-private/snapshot.md"]
        ignored = subprocess.run(["git", "check-ignore", "--stdin"], input="\n".join(paths) + "\n",
                                 cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(set(ignored.stdout.splitlines()), set(paths))
        for rel in paths:
            with self.subTest(path=rel):
                name = Path(rel).name
                if rel.startswith(".kb-private/"):
                    self.assertIsNotNone(brain.dir_exclusion(".kb-private", ".kb-private"))
                    self.assertIsNotNone(indexer.exclusion(".kb-private", ".kb-private", True))
                else:
                    self.assertIsNotNone(brain.file_exclusion(rel, name, 100))
                    self.assertIsNotNone(indexer.exclusion(rel, name, False))
        self.assertIsNone(brain.file_exclusion("TASKS.md", "TASKS.md", 100))
        self.assertIsNone(indexer.exclusion("TASKS.md", "TASKS.md", False))

    def test_dashboard_private_kb_boundary(self):
        # Exercise actual FastAPI routes in its already-installed environment.
        python = ROOT / "dashboard-app/venv/bin/python"
        self.assertTrue(python.is_file(), "Existing dashboard environment is required")
        program = '''
import sys,json,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'dashboard-app'))
import app as module
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory() as name:
    root=Path(name)
    files=['kb.sqlite','.env','gmail-token.json','kb-ingest.log','.kb-private/snapshot.md']
    for rel in files+['TASKS.md']:
        path=root/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('synthetic fixture')
    (root/'alias.md').symlink_to(root/'.kb-private/snapshot.md')
    index=root/'index.json';index.write_text(json.dumps({'schemaVersion':2,'files':[{'relativePath':p} for p in files+['TASKS.md']]}))
    module.WORKSPACE=root;module.wc.WORKSPACE=root;module.wc.INDEX_FILE=index
    with TestClient(module.app) as client:
        for rel in files+['alias.md']:
            assert client.get('/api/file',params={'path':rel}).status_code==403,rel
            assert client.get('/workspace-file/'+rel).status_code==403,rel
        assert client.get('/api/file',params={'path':'TASKS.md'}).status_code==200
        listing=client.get('/api/files').json()
        assert not any(item['path']=='alias.md' for item in listing)
        assert not any(item['path'].startswith('.kb-private/') for item in listing)
    print('Private file routes denied; TASKS.md remains accessible')
'''
        result = subprocess.run([str(python), "-c", program, str(ROOT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("routes denied", result.stdout)

    def test_existing_settings_sources_jobs_unchanged(self):
        global_file = self.root / "claude" / "CLAUDE.md"
        global_file.parent.mkdir()
        original = "# Existing guidance\nPreserve this exact line.\n"
        global_file.write_text(original)
        install_guidance(global_file, ROOT)
        first = global_file.read_text()
        install_guidance(global_file, ROOT)
        self.assertEqual(global_file.read_text(), first)
        self.assertTrue(first.startswith(original))
        self.assertEqual(first.count("## Knowledge base (search it first)"), 1)
        relocated = self.root / "relocated-claude"
        relocated.symlink_to(global_file.parent, target_is_directory=True)
        install_guidance(relocated / "CLAUDE.md", ROOT)
        self.assertTrue(relocated.is_symlink())
        self.assertEqual(global_file.read_text(), first)
        self.assertIn(f'python3 "{ROOT / "kb.py"}"', first)
        agents = self.root / "agents"
        agents.mkdir()
        old_job = agents / "com.cloudtransition.dashboard.plist"
        old_job.write_bytes(b"untouched fixture")
        settings = self.root / "settings.json"
        settings.write_text('{"cleanupPeriodDays":90}')
        plist = install_schedule(ROOT, self.root / "runtime", agents, load=False)
        config = plistlib.loads(plist.read_bytes())
        self.assertEqual(config["StartInterval"], 21600)
        self.assertEqual(config["Label"], "com.cloudtransition.personal-kb")
        self.assertEqual(old_job.read_bytes(), b"untouched fixture")
        self.assertEqual(settings.read_text(), '{"cleanupPeriodDays":90}')
        self.assertTrue(all(Path(p).is_absolute() for p in config["ProgramArguments"]))
        from connectors import ingest_claude
        import kb_store
        path = session(self.root / "sessions")
        before = path.read_bytes()
        conn = kb_store.connect(self.root / "kb.sqlite")
        self.addCleanup(conn.close)
        ingest_claude(conn, root=self.root / "sessions")
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
