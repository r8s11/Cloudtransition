"""Fixture tests for tools/arms/routines.py (standard library unittest).

    python3 -m unittest discover -s tools/arms -p 'test_routines.py'
"""
import datetime as dt
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("routines", Path(__file__).with_name("routines.py"))
routines = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(routines)

NOW = dt.datetime(2026, 10, 28, 12, 0, tzinfo=dt.timezone.utc).astimezone()
SECRET = "sk-" + "A1b2C3d4E5f6G7h8I9j0K1l2"  # assembled so this file is not itself a hit


def iso(days_ago, minutes=0):
    return (NOW - dt.timedelta(days=days_ago) + dt.timedelta(minutes=minutes)).isoformat()


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


class RoutinesFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "work space" / "Proj"
        self.home = base / "home"
        self.root.mkdir(parents=True)
        self.home.mkdir()
        for f in routines.ROUTER_FILES + routines.STATE_FILES:
            (self.root / f).write_text("# %s\n_Last updated: 2026-10-27_\n" % f, encoding="utf-8")
        enc = routines.re.sub(r"[^A-Za-z0-9]", "-", str(self.root))
        cdir = self.home / ".claude" / "projects" / enc
        for i in range(4):
            rows = []  # four sessions, same private prompt shape, one with a cold-cache gap
            sid = "s-%d" % i
            t0 = 2 + i
            rows.append({"type": "user", "cwd": str(self.root), "sessionId": sid, "timestamp": iso(t0),
                         "message": {"role": "user", "content": "please do my SECRET-PERSONAL weekly review of TASKS.md"}})
            rows.append({"type": "assistant", "cwd": str(self.root), "sessionId": sid, "timestamp": iso(t0, 1),
                         "message": {"id": "m%d" % i, "content": [
                             {"type": "tool_use", "id": "t%d" % i, "name": "Skill", "input": {"skill": "caveman"}}],
                             "usage": {"input_tokens": 10, "output_tokens": 20,
                                       "cache_read_input_tokens": 100, "cache_creation_input_tokens": 5}}})
            # duplicate record of same message id must not double count
            rows.append({"type": "assistant", "cwd": str(self.root), "sessionId": sid, "timestamp": iso(t0, 1),
                         "message": {"id": "m%d" % i, "content": [], "usage": {
                             "input_tokens": 10, "output_tokens": 20, "cache_read_input_tokens": 100,
                             "cache_creation_input_tokens": 5}}})
            if i == 0:  # cold gap: 3 hours later, cache re-created
                rows.append({"type": "assistant", "cwd": str(self.root), "sessionId": sid, "timestamp": iso(2, 181),
                             "message": {"id": "late", "content": [], "usage": {
                                 "input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": 0,
                                 "cache_creation_input_tokens": 500}}})
            write_jsonl(cdir / ("%s.jsonl" % sid), rows)
        # other project must be ignored
        write_jsonl(self.home / ".claude" / "projects" / (enc + "-other") / "x.jsonl",
                    [{"type": "user", "cwd": "/somewhere/else", "sessionId": "zz", "timestamp": iso(1),
                      "message": {"role": "user", "content": "other"}}])
        # Codex session for this root
        crows = [{"type": "session_meta", "timestamp": iso(1), "payload": {"id": "cx1", "cwd": str(self.root)}},
                 {"type": "response_item", "timestamp": iso(1, 1), "payload": {
                     "type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi there"}]}},
                 {"type": "event_msg", "timestamp": iso(1, 2), "payload": {"type": "token_count", "info": {
                     "total_token_usage": {"input_tokens": 1000, "cached_input_tokens": 600, "output_tokens": 50,
                                           "cache_write_input_tokens": 0}}}},
                 {"type": "event_msg", "timestamp": iso(1, 3), "payload": {"type": "token_count", "info": {
                     "total_token_usage": {"input_tokens": 1500, "cached_input_tokens": 900, "output_tokens": 80,
                                           "cache_write_input_tokens": 0}}}}]
        d = NOW - dt.timedelta(days=1)
        name = "rollout-%s-x.jsonl" % d.strftime("%Y-%m-%dT00-00-00")
        write_jsonl(self.home / ".codex" / "sessions" / ("%04d" % d.year) / ("%02d" % d.month) / ("%02d" % d.day) / name,
                    crows)

    def tearDown(self):
        self.tmp.cleanup()

    def report(self, rates=None):
        return routines.build_report(self.root, self.home, NOW, rates)

    def test_four_exact_keys_and_json_safe(self):
        r = self.report()
        self.assertEqual(sorted(r), ["checks", "inventory", "suggestions", "usage"])
        text = routines.scrub(r)
        json.loads(text)
        self.assertNotIn("SECRET-PERSONAL", text)

    def test_usage_totals_dedupe_and_codex_deltas(self):
        u = self.report()["usage"]
        self.assertEqual(u["totals"]["sessions"], 5)
        claude = u["by_tool"]["claude"]
        self.assertEqual(claude["sessions"], 4)
        self.assertEqual(claude["output_tokens"], 4 * 20 + 1)  # duplicate message id counted once
        self.assertEqual(claude["cache_creation_tokens"], 4 * 5 + 500)
        codex = u["by_tool"]["codex"]
        self.assertEqual(codex["cache_read_tokens"], 900)
        self.assertEqual(codex["input_tokens"], 600)  # 1500 input - 900 cached
        self.assertEqual(u["cache"]["cold"]["cold_reloads"], 1)
        self.assertEqual(u["cache"]["cold"]["reload_cache_creation_tokens"], 500)
        self.assertEqual(u["skills"]["most_used"], "caveman")
        self.assertEqual(u["estimate"]["status"], "unavailable")
        self.assertIsNone(u["estimate"]["usd"])

    def test_supplied_rates_estimate(self):
        rates = {"claude": {"source": "test", "per_million_tokens": {
            "input": 1.0, "output": 2.0, "cache_read": 0.1, "cache_write": 1.25}}}
        u = self.report(rates)["usage"]
        self.assertEqual(u["estimate"]["status"], "supplied-rates")
        self.assertIsNotNone(u["estimate"]["usd"])
        self.assertIsNotNone(u["cache"]["cold"]["reload_cost_usd"])

    def test_suggestion_threshold_three(self):
        items = self.report()["suggestions"]["items"]
        ids = {i["id"] for i in items}
        self.assertIn("sug-weekly-review", ids)
        self.assertIn("sug-tasks-tidy", ids)
        item = next(i for i in items if i["id"] == "sug-weekly-review")
        self.assertEqual(item["evidence_count"], 4)
        self.assertTrue(all(s.startswith("claude:") for s in item["session_ids"]))
        self.assertTrue(any(i["kind"] == "verbatim" for i in items))
        # below threshold -> none
        low = routines.build_suggestions([], NOW, 3, "salt")
        self.assertEqual(low["items"], [])

    def test_missing_data_is_unknown_not_zero(self):
        empty = Path(self.tmp.name) / "empty-home"
        empty.mkdir()
        r = routines.build_report(self.root, empty, NOW)
        self.assertEqual(r["usage"]["status"], "unknown")
        self.assertIsNone(r["usage"]["totals"]["input_tokens"])
        self.assertIsNone(r["usage"]["cache"]["read_ratio"])

    def test_credential_scan_hides_value(self):
        (self.root / "leak.py").write_text('KEY = "%s"\n' % SECRET, encoding="utf-8")
        r = self.report()
        c = next(i for i in r["checks"]["items"] if i["id"] == "credential-scan")
        text = routines.scrub(r)
        self.assertNotIn(SECRET, text)
        if c["status"] != "unknown":  # git may be absent in the fixture; then scan is skipped honestly
            self.assertEqual(c["status"], "fail")

    def test_plist_is_weekly_friday_local(self):
        import plistlib
        d = plistlib.loads(routines.build_plist(self.root, "/usr/bin/python3", self.home))
        self.assertEqual(d["StartCalendarInterval"]["Weekday"], 5)
        self.assertNotIn("RunAtLoad", d)
        self.assertEqual(d["ProgramArguments"][-1], "run")
        self.assertEqual(d["WorkingDirectory"], str(self.home))
        self.assertTrue(d["StandardOutPath"].startswith(str(self.home / ".local-routines" / "arms-report")))

    def test_cli_writes_default_output(self):
        rc = routines.main(["--root", str(self.root), "--home", str(self.home), "--now", NOW.isoformat()])
        self.assertEqual(rc, 0)
        out = self.root / "tools" / "arms" / "data" / "routines.json"
        self.assertEqual(sorted(json.loads(out.read_text())), ["checks", "inventory", "suggestions", "usage"])


if __name__ == "__main__":
    unittest.main()
