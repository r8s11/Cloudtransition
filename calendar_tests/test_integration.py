import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import py_compile
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from calendar_model import CalendarError, make_preview
from calendar_tests.fake_google import FakeTasksService
from calendar_tests.fixtures import make_checklist

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "calendar_cli.py"


class CalendarIntegrationTests(unittest.TestCase):
    def test_cli_build_and_stdlib_preview(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / "TASKS.md"
            original = "## Work\n- [ ] Review plan\n- [ ] Read notes\n- [x] Finished\n```md\n- [ ] Example only\n```\n"
            source.write_text(original)
            runtime = base / "private" / "personal-kb" / "calendar"
            blocker = base / "imports"
            blocker.mkdir()
            (blocker / "sitecustomize.py").write_text(
                "import sys\n"
                "class NoGoogle:\n"
                "    def find_spec(self, name, path=None, target=None):\n"
                "        if name.split('.')[0] in {'google', 'googleapiclient', 'google_auth_oauthlib'}:\n"
                "            raise ImportError('Google SDK deliberately unavailable')\n"
                "sys.meta_path.insert(0, NoGoogle())\n"
            )
            env = dict(os.environ, PYTHONPATH=str(blocker))
            listed = subprocess.run(
                [sys.executable, str(CLI), "list", "--source", str(source)],
                cwd=base, env=env, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(listed.returncode, 0, listed.stderr)
            items = json.loads(listed.stdout)
            self.assertEqual([(item["id"], item["title"]) for item in items], [("2", "Review plan"), ("3", "Read notes")])
            previewed = subprocess.run(
                [sys.executable, str(CLI), "preview", "--source", str(source), "--task-list", "chosen-list", "--item", "2=2026-11-10"],
                cwd=base, env=env, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(previewed.returncode, 0, previewed.stderr)
            preview = json.loads(previewed.stdout)
            self.assertEqual(preview["tasklist"], "chosen-list")
            self.assertEqual([item["body"]["title"] for item in preview["items"]], ["Review plan"])
            self.assertEqual(preview["items"][0]["body"]["due"], "2026-11-10T00:00:00.000Z")
            self.assertNotIn("Read notes", previewed.stdout)
            self.assertEqual(source.read_text(), original)
            self.assertFalse(runtime.exists())
            py_compile.compile(str(CLI), cfile=str(base / "calendar_cli.pyc"), doraise=True)

    def test_existing_kb_and_google_boundaries(self):
        import calendar_cli
        import calendar_google
        import connectors
        import ingest_all
        import kb_store
        import kb_summaries
        from kb_runtime import install_schedule
        from kb_tests.fixtures import session
        import plistlib

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = make_checklist(root)
            runtime = root / "personal-kb" / "calendar"
            parent = runtime.parent
            parent.mkdir(mode=0o700)
            gmail = parent / "gmail-token.json"
            original = json.dumps({"scopes": ["https://www.googleapis.com/auth/gmail.readonly"], "token": "synthetic-canary"}).encode()
            gmail.write_bytes(original)
            gmail.chmod(0o600)
            job = install_schedule(root, parent, root / "LaunchAgents", load=False)
            before_job = job.read_bytes()
            self.assertEqual(plistlib.loads(before_job)["StartInterval"], 21600)
            with self.assertRaises(CalendarError):
                calendar_google.build_service(runtime)
            preview = make_preview(source, [("2", "2026-11-10")], "chosen-list")
            parent_preview = parent / "preview.json"
            parent_preview.write_text(json.dumps(preview))
            parent_preview.chmod(0o600)
            service = FakeTasksService()
            output = io.StringIO()
            with patch.object(calendar_google, "build_service", return_value=service), patch.object(calendar_google, "login", side_effect=AssertionError("unattended login")), contextlib.redirect_stdout(output):
                code = calendar_cli.main(["publish", "--runtime", str(runtime), "--preview-file", str(parent_preview), "--approve", preview["approval"]])
            self.assertEqual(code, 0, output.getvalue())
            self.assertEqual(json.loads(output.getvalue())["results"][0]["task_id"], service.remote[0]["id"])
            session(root / "history", text="SaffronPuzzle raw fixture evidence.")
            conn = kb_store.connect(root / "kb.sqlite")
            try:
                with patch.object(calendar_google, "login", side_effect=AssertionError("background Tasks auth")), patch.object(calendar_google, "publish", side_effect=AssertionError("background Tasks publication")), contextlib.redirect_stdout(io.StringIO()):
                    outcome = ingest_all.run_all(conn, {"claude": lambda c: connectors.ingest_claude(c, root / "history")}, runtime=parent)
                self.assertEqual(outcome["claude"]["status"], "ok")
                found = kb_store.search(conn, "SaffronPuzzle", source="claude")
                self.assertEqual({item["source_id"] for item in found["results"]}, {"project/session"})
                with patch.dict(os.environ, {"KB_HOME": str(parent)}), self.assertRaises(kb_summaries.ApprovalError):
                    kb_summaries.summarize(conn, {}, object())
            finally:
                conn.close()
            self.assertEqual(gmail.read_bytes(), original)
            self.assertEqual(job.read_bytes(), before_job)
            self.assertEqual(len(service.remote), 1)
            self.assertEqual(service.remote[0]["tasklist"], "chosen-list")
            self.assertEqual(service.remote[0]["status"], "needsAction")

    def test_private_task_state_boundaries(self):
        def load(name, relative):
            spec = importlib.util.spec_from_file_location(name, ROOT / relative)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            return module

        brain = load("calendar_boundary_brain", "second-brain/brain.py")
        indexer = load("calendar_boundary_index", "visual-second-brain/refresh-index.py")
        private = ["personal-kb/calendar/" + name for name in ("token.json", "preview.json", "state.json", "error.log", "source.md")]
        ignored = subprocess.run(["git", "check-ignore", "--stdin"], cwd=ROOT, input="\n".join(private) + "\n", capture_output=True, text=True, check=False)
        self.assertEqual(set(ignored.stdout.splitlines()), set(private))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            canary = "CALENDARRUNTIMECANARY"
            for rel in private + ["TASKS.md", "docs/guide.md"]:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(canary if rel in private else "# Public guide\n- [ ] Public task\n")
            (root / "docs/alias.md").symlink_to(root / private[-1])
            (root / "docs/aliasdir").symlink_to(root / "personal-kb/calendar", target_is_directory=True)
            aliases = ["docs/alias.md", "docs/aliasdir/source.md"]
            _, code = brain.run(["--root", str(root), "index"])
            self.assertEqual(code, 0)
            catalogue = (root / "second-brain/catalogue.md").read_text()
            self.assertNotIn(canary, catalogue)
            self.assertNotIn("personal-kb/calendar", catalogue)
            self.assertNotIn("alias.md", catalogue)
            actual_index = indexer.build(root)
            indexed = {item["relativePath"] for item in actual_index["files"]}
            self.assertTrue({"TASKS.md", "docs/guide.md"} <= indexed)
            self.assertFalse(indexed.intersection(private + aliases))
            self.assertNotIn(canary, json.dumps(actual_index))
            index = root / "test-index.json"
            index.write_text(json.dumps({"schemaVersion": 2, "files": [{"relativePath": rel} for rel in private + aliases + ["TASKS.md", "docs/guide.md"]]}))
            program = '''
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'dashboard-app'))
import app as module
from fastapi.testclient import TestClient
root=Path(sys.argv[2]); paths=json.loads(sys.argv[3])
module.WORKSPACE=root; module.wc.WORKSPACE=root; module.wc.INDEX_FILE=root/'test-index.json'
with TestClient(module.app) as client:
    for rel in paths:
        for endpoint,options in [('/api/file',{'params':{'path':rel}}),('/workspace-file/'+rel,{})]:
            response=client.get(endpoint,**options)
            assert response.status_code==403,(rel,response.status_code)
            assert 'CALENDARRUNTIMECANARY' not in response.text
    for rel in ['TASKS.md','docs/guide.md']:
        assert client.get('/api/file',params={'path':rel}).status_code==200
        assert client.get('/workspace-file/'+rel).status_code==200
print('private routes denied; public documents accessible')
'''
            result = subprocess.run([str(ROOT / "dashboard-app/venv/bin/python"), "-c", program, str(ROOT), str(root), json.dumps(private + aliases)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("private routes denied", result.stdout)

    def test_source_and_dashboard_preserved(self):
        from calendar_google import publish
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = make_checklist(root)
            original = source.read_bytes()
            service = FakeTasksService()
            preview = make_preview(source, [("2", "2026-11-10")], "chosen-list")
            publish(preview, preview["approval"], root / "personal-kb/calendar", service)
            self.assertEqual(source.read_bytes(), original)
            program = '''
import sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'dashboard-app'))
import app as module
from fastapi.testclient import TestClient
root=Path(sys.argv[2]); source=root/'TASKS.md'
module.WORKSPACE=root; module.REALMS=[{'id':'tasks','file':'TASKS.md'}]
assert [(x['text'],x['cat'],x['done']) for x in module.parse_tasks_from_file(source,'tasks')][:4]==[('Review plan','Work',False),('Read notes','Work',False),('Prepare outline','Work',False),('Finished','Work',True)]
source.write_text('Unrelated line\\n'+source.read_text())
with TestClient(module.app) as client:
    response=client.post('/api/tasks/toggle',headers={'X-Requested-With':'XMLHttpRequest'},json={'realm':'tasks','line':2,'text':'Review plan','done':True})
    assert response.status_code==200,response.text
    assert response.json()['line']==3
    assert '- [x] Review plan' in source.read_text()
    source.write_text(source.read_text()+'- [ ] Duplicate\\n- [ ] Duplicate\\n')
    before=source.read_bytes()
    response=client.post('/api/tasks/toggle',headers={'X-Requested-With':'XMLHttpRequest'},json={'realm':'tasks','line':1,'text':'Duplicate','done':True})
    assert response.status_code==409,response.text
    assert source.read_bytes()==before
print('unique moved toggle follows source; ambiguous toggle refused')
'''
            result = subprocess.run([str(ROOT / "dashboard-app/venv/bin/python"), "-c", program, str(ROOT), str(root)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ambiguous toggle refused", result.stdout)
            with self.assertRaises(CalendarError):
                publish(preview, preview["approval"], root / "personal-kb/calendar", service)
            self.assertEqual(len(service.remote), 1)
            self.assertEqual(service.remote[0]["status"], "needsAction")
