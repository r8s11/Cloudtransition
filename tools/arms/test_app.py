"""Boundary tests for tools/arms/app.py and the clipper (stdlib unittest).

Run: python3 -m unittest tools/arms/test_app.py   (or python3 tools/arms/test_app.py)
Uses a temp root/data dir, a fake brain.py and a fake routines.py: no workspace
file, skill or memory is touched, no model is called.
"""

from __future__ import annotations

import contextlib
import hashlib
import http.client
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("arms_app", HERE / "app.py")
arms_app = importlib.util.module_from_spec(spec)
sys.modules["arms_app"] = arms_app
spec.loader.exec_module(arms_app)

FAKE_BRAIN = textwrap.dedent(
    """
    import json, sys
    args = sys.argv[1:]
    cmd = [a for a in args[2:]][0] if len(args) > 2 else ""
    if cmd == "query":
        q = args[3]
        if q == "stale-case":
            print(json.dumps({"status": "stale", "message": "index old"})); sys.exit(3)
        if q == "busy-case":
            print(json.dumps({"status": "error", "message": "busy"})); sys.exit(4)
        if q == "garbage-case":
            print("not json"); sys.exit(0)
        print(json.dumps({"status": "ok", "argv": args, "evidence": [
            {"path": "a.md", "start_line": 1, "end_line": 2, "text": "<script>x</script>"}]}))
    elif cmd == "remember":
        print(json.dumps({"status": "saved", "argv": args, "id": "m1", "path": "second-brain/memories/m1.md"}))
    """
)
FAKE_ROUTINES = textwrap.dedent(
    """
    import json, sys
    args = sys.argv[1:]
    out = args[args.index("--output") + 1]
    open(out + ".argv", "w").write(json.dumps(args))
    json.dump({"inventory": {"items": []}, "usage": {}, "checks": {},
               "suggestions": {"items": [{"id": "sug-1", "title": "T1", "summary": "S1",
                                           "evidence_count": 3, "days": ["2026-10-27"],
                                           "proposed_action": "do it"}]}}, open(out, "w"))
    """
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="arms-app-test-"))
        cls.root = cls.tmp / "root"
        cls.data = cls.tmp / "data"
        cls.root.mkdir()
        (cls.root / ".claude" / "skills" / "demo-skill").mkdir(parents=True)
        cls.skill_file = cls.root / ".claude" / "skills" / "demo-skill" / "SKILL.md"
        cls.skill_file.write_text("# demo skill\n")
        cls.brain = cls.tmp / "brain.py"
        cls.brain.write_text(FAKE_BRAIN)
        cls.routines = cls.tmp / "routines.py"
        cls.routines.write_text(FAKE_ROUTINES)
        cls.artifacts = cls.tmp / "artifacts"
        cls.artifacts.mkdir()
        (cls.artifacts / "index.html").write_text("<h1>ok</h1>")
        (cls.artifacts / ".secret").write_text("no")
        (cls.artifacts / "notes.py").write_text("print(1)")
        (cls.artifacts / "report.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
        cls.managed = cls.tmp / "managed-skills"
        (cls.managed / "cloudtransition-note").mkdir(parents=True)
        (cls.managed / "cloudtransition-note" / "SKILL.md").write_text("# note\n")
        (cls.managed / "no-skill-md").mkdir()
        cls.server = arms_app.create_server(cls.root, cls.data, 0, cls.brain, cls.routines)
        cls.server.app.artifacts_dir = cls.artifacts
        cls.server.app.managed_skills_dir = cls.managed
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def req(self, method, path, body=None, headers=None, raw: bytes | None = None, ctype="application/json"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        hdrs = dict(headers or {})
        payload = raw
        if payload is None and body is not None:
            payload = json.dumps(body).encode()
        if payload is not None and ctype:
            hdrs.setdefault("Content-Type", ctype)
        conn.request(method, path, body=payload, headers=hdrs)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        try:
            obj = json.loads(data)
        except ValueError:
            obj = None
        return res.status, obj, res


class IdleConnectionTests(ServerCase):
    def test_idle_connection_timeout_is_logged_not_crashed(self):
        # A browser keep-alive socket that never sends a request line times out before the
        # request is parsed; logging that must not raise inside the handler thread.
        import socket
        from unittest import mock
        errors: list[str] = []
        with mock.patch.object(arms_app.Handler, "timeout", 0.3), \
                mock.patch.object(self.server, "handle_error",
                                  lambda request, addr: errors.append(repr(sys.exc_info()[1]))), \
                contextlib.redirect_stderr(io.StringIO()):
            sock = socket.create_connection(("127.0.0.1", self.port))
            sock.settimeout(5)
            self.assertEqual(sock.recv(1), b"")  # server closed the idle socket
            sock.close()
            # handle_error runs before the socket is shut down, so it has already fired if it will.
        self.assertEqual(errors, [])
        status, _, _ = self.req("GET", "/api/status")
        self.assertEqual(status, 200)


class BoundaryTests(ServerCase):
    def test_binds_loopback_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_static_assets_and_headers(self):
        for path in ("/", "/static/app.js", "/static/style.css"):
            status, _obj, res = self.req("GET", path)
            self.assertEqual(status, 200, path)
            self.assertIn("script-src 'self'", res.getheader("Content-Security-Policy"))
            self.assertEqual(res.getheader("X-Content-Type-Options"), "nosniff")
        self.assertEqual(self.req("GET", "/static/../app.py")[0], 404)
        self.assertEqual(self.req("GET", "/app.py")[0], 404)

    def test_foreign_host_origin_and_site_rejected(self):
        self.assertEqual(self.req("GET", "/api/status", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.req("GET", "/api/status", headers={"Host": f"127.0.0.1:{self.port + 1}"})[0], 403)
        self.assertEqual(self.req("GET", "/api/status", headers={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.req("GET", "/api/status", headers={"Origin": "null"})[0], 403)
        self.assertEqual(self.req("GET", "/api/status", headers={"Sec-Fetch-Site": "cross-site"})[0], 403)
        self.assertEqual(
            self.req("GET", "/api/status", headers={"Origin": f"http://localhost:{self.port}", "Host": f"localhost:{self.port}"})[0],
            200,
        )
        self.assertEqual(self.req("GET", "/api/status", headers={"Host": f"127.0.0.1:{self.port}"})[0], 200)

    def test_mutations_require_bounded_json(self):
        path = "/api/feedback"
        good = {"target_skill": "demo-skill", "comments": "c"}
        self.assertEqual(self.req("POST", path, raw=json.dumps(good).encode(), ctype="text/plain")[0], 415)
        self.assertEqual(self.req("POST", path, raw=json.dumps(good).encode(), ctype="application/x-www-form-urlencoded")[0], 415)
        self.assertEqual(self.req("POST", path, raw=b"{nope", ctype="application/json")[0], 400)
        self.assertEqual(self.req("POST", path, raw=b"[1]", ctype="application/json")[0], 400)
        big = json.dumps({"target_skill": "demo-skill", "comments": "x" * 70000}).encode()
        self.assertEqual(self.req("POST", path, raw=big)[0], 413)
        self.assertEqual(self.req("POST", path, body={**good, "extra": 1})[0], 400)
        self.assertEqual(self.req("POST", path, body={"target_skill": "bad skill!", "comments": "c"})[0], 400)
        self.assertEqual(self.req("POST", path, body={"target_skill": "demo-skill"})[0], 400)
        self.assertEqual(self.req("POST", path, body={"target_skill": "demo-skill", "comments": "a\x00b"})[0], 400)
        self.assertEqual(self.req("POST", path, body={"target_skill": "demo-skill", "comments": "x" * 4001})[0], 400)
        self.assertEqual(self.req("POST", path, body={"target_skill": "demo-skill", "principle": "a\nb"})[0], 400)
        self.assertEqual(self.req("DELETE", path)[0], 405)
        self.assertEqual(self.req("GET", "/api/memory/query")[0], 405)
        self.assertEqual(self.req("GET", "/api/nope")[0], 404)

    def test_no_user_supplied_command_or_path_is_accepted(self):
        # Routes that launch subprocesses take no command, path or root from the browser.
        for extra in ({"cmd": "id"}, {"root": "/tmp"}, {"path": "/etc/passwd"}, {"argv": ["id"]}):
            self.assertEqual(self.req("POST", "/api/memory/query", body={"question": "x", **extra})[0], 400, extra)
            self.assertEqual(self.req("POST", "/api/memory/remember", body={"title": "t", "summary": "s", "body": "b", **extra})[0], 400, extra)
        self.assertEqual(self.req("POST", "/api/report/refresh", raw=b"{}", ctype="text/plain")[0], 415)
        for route in ("/api/exec", "/api/run", "/api/shell", "/api/memory/index", "/api/skills/apply"):
            self.assertEqual(self.req("POST", route, body={})[0], 404, route)
        self.assertEqual(self.req("POST", "/api/report/refresh", body={"cmd": "id"})[0], 200)  # body ignored


class MemoryTests(ServerCase):
    def test_query_validation_and_cli_status_mapping(self):
        self.assertEqual(self.req("POST", "/api/memory/query", body={"question": "--help"})[0], 400)
        self.assertEqual(self.req("POST", "/api/memory/query", body={"question": "  "})[0], 400)
        self.assertEqual(self.req("POST", "/api/memory/query", body={"question": "q" * 501})[0], 400)
        self.assertEqual(self.req("POST", "/api/memory/query", body={"question": "a\nb"})[0], 400)
        status, obj, _ = self.req("POST", "/api/memory/query", body={"question": "stale-case"})
        self.assertEqual((status, obj["status"]), (200, "stale"))
        self.assertEqual(self.req("POST", "/api/memory/query", body={"question": "busy-case"})[0], 503)
        self.assertEqual(self.req("POST", "/api/memory/query", body={"question": "garbage-case"})[0], 502)

    def test_remember_validation(self):
        flaglike = {"title": "-t", "summary": "--summary", "body": "line1\nline2"}
        status, obj, _ = self.req("POST", "/api/memory/remember", body=flaglike)
        self.assertEqual((status, obj["status"]), (200, "saved"))
        self.assertEqual(self.req("POST", "/api/memory/remember", body={"title": "t" * 121, "summary": "s", "body": "b"})[0], 400)
        self.assertEqual(self.req("POST", "/api/memory/remember", body={"title": "t", "summary": "s\ns", "body": "b"})[0], 400)
        self.assertEqual(self.req("POST", "/api/memory/remember", body={"title": "t", "summary": "s", "body": "b" * 8001})[0], 400)
        self.assertEqual(self.req("POST", "/api/memory/remember", body={"title": "t", "summary": "s", "body": ""})[0], 400)


class StoreTests(ServerCase):
    def test_report_missing_then_refresh(self):
        report = self.data / "routines.json"
        if report.exists():
            report.unlink()
        status, obj, _ = self.req("GET", "/api/report")
        self.assertEqual((status, obj["status"]), (200, "missing"))
        status, obj, _ = self.req("POST", "/api/report/refresh", body={})
        self.assertEqual((status, obj["status"]), (200, "ok"))
        self.assertEqual(obj["report"]["suggestions"]["items"][0]["id"], "sug-1")
        report.write_text("{broken")
        self.assertEqual(self.req("GET", "/api/report")[1]["status"], "invalid")

    def test_cart_roundtrip_and_markdown(self):
        self.req("POST", "/api/report/refresh", body={})
        self.assertEqual(self.req("PUT", "/api/cart", body={"items": [{"suggestion_id": "sug-1", "comment": "line a\nline b"},
                                                                       {"suggestion_id": "gone", "comment": ""}]})[0], 200)
        self.assertEqual(len(self.req("GET", "/api/cart")[1]["items"]), 2)
        self.assertTrue((self.data / "cart.json").is_file())
        md = self.req("GET", "/api/cart/markdown")[1]["markdown"]
        self.assertIn("## 1. T1", md)
        self.assertIn("proposed action (not executed): do it", md)
        self.assertIn("  > line a\n  > line b", md)
        self.assertIn("not present in the current report", md)
        self.assertEqual(self.req("PUT", "/api/cart", body={"items": [{"suggestion_id": "a b"}]})[0], 400)
        self.assertEqual(self.req("PUT", "/api/cart", body={"items": [{"suggestion_id": "x"}, {"suggestion_id": "x"}]})[0], 400)
        self.assertEqual(self.req("PUT", "/api/cart", body={"items": [{"suggestion_id": "x"}] * 101})[0], 400)
        self.assertEqual(self.req("PUT", "/api/cart", body={"items": []})[0], 200)

    def test_feedback_durable_and_never_touches_skills(self):
        before = sha(self.skill_file)
        status, item, _ = self.req("POST", "/api/feedback", body={"target_skill": "demo-skill", "principle": "p", "comments": "<b>c</b>"})
        self.assertEqual(status, 201)
        self.assertEqual((item["status"], item["applied"]), ("parked", False))
        stored = json.loads((self.data / "feedback.json").read_text())
        self.assertTrue(any(i["id"] == item["id"] for i in stored["items"]))
        self.assertEqual(self.req("POST", "/api/feedback/status", body={"id": item["id"], "status": "reviewed"})[1]["status"], "reviewed")
        self.assertEqual(self.req("POST", "/api/feedback/status", body={"id": item["id"], "status": "resolved"})[0], 400)
        self.assertEqual(self.req("POST", "/api/feedback/status", body={"id": "fb-nope", "status": "parked"})[0], 404)
        self.assertEqual(sha(self.skill_file), before)
        self.assertIn("demo-skill", self.req("GET", "/api/status")[1]["known_skills"])

    def test_cli_shares_store_and_requires_approval(self):
        def run(*argv):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = arms_app.main(["--data-dir", str(self.data), "--root", str(self.root), *argv])
            return code, json.loads(buf.getvalue())

        before = sha(self.skill_file)
        code, out = run("note", "--target", "demo-skill", "--body", "from cli", "--principle", "p1")
        self.assertEqual((code, out["status"]), (0, "parked"))
        fid = out["item"]["id"]
        self.assertIn(fid, [i["id"] for i in self.req("GET", "/api/feedback")[1]["items"]])  # server sees CLI write
        self.assertEqual(run("note", "--target", "demo-skill")[0], 2)
        self.assertEqual(run("note", "--target", "../etc", "--body", "x")[0], 2)
        self.assertEqual(run("resolve", fid, "--resolution", "applied")[0], 2)  # no --user-approved
        self.assertEqual(run("notes")[1]["items"][-1]["status"], "parked")
        code, out = run("resolve", fid, "--resolution", "adopted in review", "--user-approved")
        self.assertEqual((code, out["item"]["status"], out["item"]["applied"]), (0, "resolved", True))
        self.assertEqual(out["item"]["applied_principle"], "p1")
        self.assertEqual(run("resolve", fid, "--resolution", "again", "--user-approved")[0], 2)
        self.assertEqual(self.req("POST", "/api/feedback/status", body={"id": fid, "status": "parked"})[0], 409)
        _c, listed = run("notes", "--status", "resolved")
        self.assertIn(fid, [i["id"] for i in listed["items"]])
        code, out = run("note", "--target", "demo-skill", "--body", "dismiss me")
        code, out = run("resolve", out["item"]["id"], "--outcome", "dismissed", "--resolution", "not wanted")
        self.assertEqual((code, out["item"]["status"], out["item"]["applied"]), (0, "dismissed", False))
        self.assertEqual(sha(self.skill_file), before)

    def test_artifacts_explicit_and_confined(self):
        self.assertTrue(self.req("GET", "/api/status")[1]["artifacts_available"])
        status, _o, res = self.req("GET", "/artifacts/index.html")
        self.assertEqual(status, 200)
        self.assertIn("connect-src 'none'", res.getheader("Content-Security-Policy"))
        status, _o, res = self.req("GET", "/artifacts/report.pdf")
        self.assertEqual((status, res.getheader("Content-Type")), (200, "application/pdf"))
        for bad in ("/artifacts/.secret", "/artifacts/../app.py", "/artifacts/%2e%2e/app.py", "/artifacts/notes.py", "/artifacts/missing.html"):
            self.assertEqual(self.req("GET", bad)[0], 404, bad)

    def test_known_skills_lists_managed_skill_names_only(self):
        skills = self.req("GET", "/api/status")[1]["known_skills"]
        self.assertIn("cloudtransition-note", skills)
        self.assertIn("demo-skill", skills)
        self.assertNotIn("no-skill-md", skills)


class ClipperTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_clip_markdown_and_filename(self):
        script = textwrap.dedent(
            """
            const c = require(process.argv[1]);
            const d = new Date(2026, 9, 28, 8, 5, 9);
            const out = {
              good: c.buildClip({title: "Héllo / ../Wörld\\n# x", url: "https://u:p@example.com/a?b=1#frag", text: "one\\n\\ntwo"}, d),
              empty: c.buildClip({title: "t", url: "https://example.com", text: "  \\n"}, d),
              js: c.buildClip({title: "t", url: "javascript:alert(1)", text: "x"}, d),
              file: c.buildClip({title: "t", url: "file:///etc/passwd", text: "x"}, d),
              evil: c.safeFilename("../../etc/passwd\\\\..:*?", d),
              blank: c.safeFilename("日本語", d),
            };
            console.log(JSON.stringify(out));
            """
        )
        proc = subprocess.run(["node", "-e", script, str(HERE / "clipper" / "clip.js")], capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        good = out["good"]
        self.assertTrue(good["ok"])
        self.assertIn('source: "https://example.com/a?b=1"', good["markdown"])
        self.assertNotIn("u:p@", good["markdown"])
        self.assertIn("> one\n>\n> two", good["markdown"])
        self.assertRegex(good["markdown"], r'captured: "\d{4}-\d{2}-\d{2}T[^"]+Z"')
        self.assertEqual(good["filename"], "arms-clips/20261028-080509-hello-world-x.md")
        self.assertFalse(out["empty"]["ok"])
        self.assertFalse(out["js"]["ok"])
        self.assertFalse(out["file"]["ok"])
        self.assertRegex(out["evil"], r"^arms-clips/\d{8}-\d{6}-[a-z0-9-]+\.md$")
        self.assertNotIn("..", out["evil"])
        self.assertEqual(out["blank"], "arms-clips/20261028-080509-clip.md")


if __name__ == "__main__":
    unittest.main()
