"""Bot-side checks: the dashboard read tool, instructions and permission rules."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BOT = Path(__file__).resolve().parent.parent
WORKSPACE = BOT.parent
TOOL = BOT / "tools" / "dashboard.py"
PAYLOAD = {"generated_at": "2026-11-16T12:00:00-05:00", "interviews": {"counts": {"tracked": 3}}}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(PAYLOAD).encode() if self.path.startswith("/api/assistant/state") else b"{}"
        self.send_response(200 if self.path.startswith("/api/assistant/state") else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def run_tool(*args):
    return subprocess.run(
        [sys.executable, str(TOOL), *args], capture_output=True, text=True, timeout=30
    )


class ToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_tool_prints_state(self):
        proc = run_tool("state", "--url", self.base, "--include", "interviews")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        self.assertEqual(json.loads(proc.stdout), PAYLOAD)

    def test_tool_refuses_non_loopback(self):
        for url in ("https://example.com", "http://192.0.2.1:8000"):
            proc = run_tool("state", "--url", url)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("loopback", proc.stderr)
            self.assertEqual(proc.stdout, "")

    def test_tool_offline_error(self):
        proc = run_tool("state", "--url", "http://127.0.0.1:1")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not running", proc.stderr)

    def test_offline_output_clean(self):
        proc = run_tool("state", "--url", "http://127.0.0.1:1")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(len(proc.stderr.strip().splitlines()), 1)
        self.assertNotIn("Traceback", proc.stderr)


class ConfigTests(unittest.TestCase):
    def rules(self):
        return json.loads((BOT / "opencode.jsonc").read_text())["permissions"]

    def test_instructions_and_brain_query(self):
        for rel in ("AGENTS.md", ".opencode/agents/brain.md", ".opencode/agents/workspace.md"):
            text = (BOT / rel).read_text().lower()
            self.assertIn("tools/dashboard.py", text, rel)
            self.assertIn("untrusted", text, rel)
        script = (
            "import sys; sys.path.insert(0, '.'); import app as m;"
            "from fastapi.testclient import TestClient;"
            "m._brain = lambda *a: {'ok': True, 'echo': list(a)};"
            "c = TestClient(m.app);"
            "r = c.get('/api/brain/query', params={'q': 'hello'});"
            "assert r.status_code == 200, r.text;"
            "assert r.json()['echo'] == ['query', 'hello'], r.text;"
            "print('brain-query-ok')"
        )
        proc = subprocess.run(
            [str(WORKSPACE / "dashboard-app" / "venv" / "bin" / "python"), "-c", script],
            cwd=WORKSPACE / "dashboard-app",
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("brain-query-ok", proc.stdout)

    def test_permissions_keep_ask_outside_bot(self):
        rules = self.rules()
        shell = [r for r in rules if r["action"] == "shell"]
        allowed = [r["resource"] for r in shell if r["effect"] == "allow"]
        self.assertIn("python3 tools/dashboard.py *", allowed)
        self.assertTrue(any("/bot/tools/dashboard.py *" in r for r in allowed))
        for rule in shell:
            if rule["effect"] == "allow":
                self.assertTrue(
                    rule["resource"].startswith("python3 tools/dashboard.py")
                    or "/bot/tools/dashboard.py" in rule["resource"]
                    or rule["resource"] in ("git status *", "git diff *"),
                    rule,
                )
        for rule in rules:
            if rule["action"] == "edit" and rule["resource"] not in ("*",) and not rule["resource"].endswith("/bot/*"):
                self.assertEqual(rule["effect"], "ask", rule)

    def test_permission_paths_cover_both_checkouts(self):
        rules = self.rules()
        roots = ("~/code/Cloudtransition", "/Volumes/SANDISK USB/work/Cloudtransition")
        for root in roots:
            ext = [r for r in rules if r["action"] == "external_directory" and r["resource"] == f"{root}/*"]
            self.assertTrue(ext and all(r["effect"] == "allow" for r in ext), root)
            edit = [r for r in rules if r["action"] == "edit" and r["resource"] == f"{root}/*"]
            self.assertTrue(edit and all(r["effect"] == "ask" for r in edit), root)
            bot_edit = [r for r in rules if r["action"] == "edit" and r["resource"] == f"{root}/bot/*"]
            self.assertTrue(bot_edit and all(r["effect"] == "allow" for r in bot_edit), root)


if __name__ == "__main__":
    unittest.main()
