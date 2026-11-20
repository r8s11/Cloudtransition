"""Storage and search tests (U1 U5 U6 U7 F7 F10 R2). Deterministic, isolated temp DBs only."""

import json
import math
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import kb_store  # noqa: E402

KB = ROOT / "kb.py"
NOW = datetime(2026, 11, 5, 12, 0, 0, tzinfo=timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def row(kind, ts, title, content, **metadata):
    return {"kind": kind, "ts": ts, "title": title, "content": content, "metadata": metadata}


class KbCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.db = str(self.dir / "kb.sqlite")
        self.elsewhere = self.dir / "elsewhere"
        self.elsewhere.mkdir()
        self.conn = kb_store.connect(self.db)
        self.addCleanup(self.conn.close)

    def cli(self, *args, db=True):
        cmd = [sys.executable, str(KB), *args]
        if db:
            cmd += ["--db", self.db]
        return subprocess.run(cmd, cwd=self.elsewhere, capture_output=True, text=True, timeout=60)

    def count(self, sql="SELECT COUNT(*) FROM docs", *params):
        return self.conn.execute(sql, params).fetchone()[0]

    def fts_hits(self, term):
        return {r[0] for r in self.conn.execute("SELECT rowid FROM docs_fts WHERE docs_fts MATCH ?", (f'"{term}"',))}

    def assert_fts_consistent(self):
        self.conn.execute("INSERT INTO docs_fts(docs_fts) VALUES('integrity-check')")
        self.assertEqual(self.conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(self.count("SELECT COUNT(*) FROM docs_fts_docsize"), self.count())

    def dangling_refs(self):
        return self.count(
            "SELECT COUNT(*) FROM docs c WHERE c.superseded_by IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM docs t WHERE t.id = c.superseded_by)"
        )


class InitAndSchemaTests(KbCase):
    def test_init_and_empty_stats(self):
        fresh = str(self.dir / "fresh.sqlite")
        for _ in range(2):
            proc = subprocess.run(
                [sys.executable, str(KB), "init", "--db", fresh], cwd=self.elsewhere, capture_output=True, text=True, timeout=60
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.exists(fresh))
        self.assertEqual(os.listdir(self.elsewhere), [], "init must not create files in the cwd")
        self.assertEqual(os.stat(fresh).st_mode & 0o777, 0o600)
        # --db accepted before the subcommand too
        proc = subprocess.run(
            [sys.executable, str(KB), "--db", fresh, "stats", "--json"], cwd=self.elsewhere, capture_output=True, text=True, timeout=60
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        st = json.loads(proc.stdout)
        self.assertEqual((st["rows"], st["items"], st["last_ingest"]), (0, 0, None))
        self.assertEqual(st["by_source"], {})
        text = self.cli("stats").stdout
        self.assertIn("never recorded", text)

        cols = [r["name"] for r in self.conn.execute("PRAGMA table_info(docs)")]
        self.assertEqual(cols, ["id", "kind", "source", "source_id", "ts", "title", "content", "metadata", "superseded_by"])
        cols = [r["name"] for r in self.conn.execute("PRAGMA table_info(ingest_state)")]
        self.assertEqual(cols, ["source", "key", "watermark"])
        sql = self.conn.execute("SELECT sql FROM sqlite_master WHERE name = 'docs_fts'").fetchone()[0].lower()
        self.assertIn("fts5", sql)
        self.assertIn("porter unicode61", sql)

        # triggers keep the index in step with insert / update / delete
        c = self.conn
        c.execute(
            "INSERT INTO docs(kind, source, source_id, ts, title, content, metadata) VALUES "
            "('short', 's', '1', '2026-01-01', 'Gadget notes', 'the quick walruses', '{}')"
        )
        rid = c.execute("SELECT id FROM docs").fetchone()[0]
        self.assertEqual(self.fts_hits("walruses"), {rid})
        self.assertEqual(self.fts_hits("gadget"), {rid}, "title is indexed")
        c.execute("UPDATE docs SET content = 'builds failed twice' WHERE id = ?", (rid,))
        self.assertEqual(self.fts_hits("failing"), {rid}, "porter stemming applies")
        c.execute("UPDATE docs SET content = 'slow tortoises' WHERE id = ?", (rid,))
        self.assertEqual(self.fts_hits("walruses"), set())
        self.assertEqual(self.fts_hits("tortoises"), {rid})
        c.execute("DELETE FROM docs WHERE id = ?", (rid,))
        self.assertEqual(self.fts_hits("tortoises"), set())
        self.assertEqual(self.fts_hits("gadget"), set())
        self.assert_fts_consistent()

        # a second init keeps existing data
        kb_store.replace_rows(c, "s", "keep", [row("short", "2026-01-02", "Keep", "kept content")])
        self.assertEqual(self.cli("init").returncode, 0)
        self.assertEqual(self.count(), 1)

        # stats/search never create a missing database
        missing = str(self.elsewhere / "absent.sqlite")
        for args in (["stats"], ["search", "x"]):
            proc = subprocess.run(
                [sys.executable, str(KB), *args, "--db", missing], cwd=self.elsewhere, capture_output=True, text=True, timeout=60
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("init", proc.stderr)
        self.assertFalse(os.path.exists(missing))

    def test_database_files_are_private(self):
        kb_store.replace_rows(self.conn, "s", "1", [row("short", "2026-01-01", "t", "content")])
        for suffix in ("", "-wal", "-shm"):
            path = self.db + suffix
            if os.path.exists(path):
                self.assertEqual(os.stat(path).st_mode & 0o077, 0, path)
        self.conn.close()
        os.chmod(self.db, 0o644)
        self.conn = kb_store.connect(self.db)
        self.addCleanup(self.conn.close)
        self.assertEqual(os.stat(self.db).st_mode & 0o077, 0, "loose permissions are tightened on connect")

    def test_state_roundtrip(self):
        c = self.conn
        self.assertIsNone(kb_store.get_state(c, "gmail", "watermark"))
        self.assertEqual(kb_store.get_state(c, "gmail", "watermark", "dflt"), "dflt")
        kb_store.set_state(c, "gmail", "watermark", "2026-11-01T00:00:00Z")
        kb_store.set_state(c, "gmail", "counts", {"n": 3, "reasons": {"a": 1}})
        kb_store.set_state(c, "claude", "watermark", "other")
        self.assertEqual(kb_store.get_state(c, "gmail", "watermark"), "2026-11-01T00:00:00Z")
        self.assertEqual(kb_store.get_state(c, "gmail", "counts"), {"n": 3, "reasons": {"a": 1}})
        kb_store.set_state(c, "gmail", "watermark", "2026-11-02T00:00:00Z")
        self.assertEqual(kb_store.get_state(c, "gmail", "watermark"), "2026-11-02T00:00:00Z")
        self.assertEqual(kb_store.get_state(c, "claude", "watermark"), "other")
        self.assertEqual(self.count("SELECT COUNT(*) FROM ingest_state"), 3)


class SearchOutputTests(KbCase):
    def seed(self):
        c = self.conn
        kb_store.replace_rows(
            c,
            "claude",
            "s1",
            [
                row(
                    "short",
                    "2026-10-01T10:00:00Z",
                    "Fixing the build",
                    "npm run build failed with ENOENT in /tmp/café/app.js; the fix was the --force flag",
                    path="/projects/a/s1.jsonl",
                )
            ],
        )
        kb_store.replace_rows(
            c,
            "claude",
            "s2",
            [
                row("segment", "2025-01-15T09:00:00Z", "Old walrus topic", "walrus migration notes", path="/projects/a/s2.jsonl"),
                row("raw", "2025-01-15T09:00:00Z", "Old walrus topic", "raw walrus transcript text", path="/projects/a/s2.jsonl", chunk_index=0),
            ],
        )
        kb_store.replace_rows(
            c,
            "gmail",
            "t1",
            [row("short", "2026-03-01T08:00:00Z", "Invoice from Zoë", "walrus supplies invoice attached", url="https://mail.google.com/mail/u/0/#all/t1")],
        )
        kb_store.replace_rows(
            c,
            "gmail",
            "t2",
            [row("raw", "2024-06-01T08:00:00Z", "Ancient mail", "an ancient walrus mail", url="https://mail.google.com/mail/u/0/#all/t2")],
        )

    def test_search_terms_filters_output(self):
        self.seed()
        proc = self.cli("search", "ENOENT")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("KB: 5 rows, 4 items", proc.stdout)
        self.assertIn("2026-10-01", proc.stdout)
        self.assertIn("claude", proc.stdout)
        self.assertIn("/projects/a/s1.jsonl", proc.stdout)
        self.assertIn("[ENOENT]", proc.stdout, "snippet highlights the matching text")

        # stemming and OR semantics; Unicode words
        self.assertIn("/projects/a/s1.jsonl", self.cli("search", "failing").stdout)
        self.assertIn("/projects/a/s1.jsonl", self.cli("search", "café").stdout)
        res = kb_store.search(self.conn, "ENOENT unrelatedword", now=NOW)
        self.assertEqual([r["source_id"] for r in res["results"]], ["s1"], "terms are OR-ed")
        self.assertEqual(res["terms"], ["enoent", "unrelatedword"])

        # hostile / quoted input is data, not syntax
        for q in ['"ENOENT" OR 1=1; DROP TABLE docs; --', "ENOENT AND NOT x NEAR(a b) *", "'quoted' \"half"]:
            proc = self.cli("search", q)
            self.assertEqual(proc.returncode, 0, (q, proc.stderr))
            self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(self.count(), 5)

        # filters apply to both the summary and the raw pass
        res = kb_store.search(self.conn, "walrus", now=NOW)
        self.assertEqual({r["source_id"] for r in res["results"]}, {"s2", "t1", "t2"})
        res = kb_store.search(self.conn, "walrus", after="2026-01-01", now=NOW)
        self.assertEqual([r["source_id"] for r in res["results"]], ["t1"])
        res = kb_store.search(self.conn, "walrus", after="2024-12-31", now=NOW)
        self.assertEqual({r["source_id"] for r in res["results"]}, {"s2", "t1"}, "raw-only t2 (2024) excluded by --after")
        res = kb_store.search(self.conn, "walrus", source="gmail", now=NOW)
        self.assertEqual({r["source_id"] for r in res["results"]}, {"t1", "t2"})
        res = kb_store.search(self.conn, "walrus", source="claude", after="2025-01-15", now=NOW)
        self.assertEqual([r["source_id"] for r in res["results"]], ["s2"])
        # limit bounds distinct items; s2 matches in both passes but is one result
        res = kb_store.search(self.conn, "walrus", limit=2, now=NOW)
        keys = [(r["source"], r["source_id"]) for r in res["results"]]
        self.assertEqual(len(keys), 2)
        self.assertEqual(len(set(keys)), 2)
        full = kb_store.search(self.conn, "walrus", limit=10, now=NOW)
        self.assertEqual(len(full["results"]), 3)
        s2 = next(r for r in full["results"] if r["source_id"] == "s2")
        self.assertEqual(sorted(k for k, v in s2["lists"].items() if v), ["raw", "summary"])

        # CLI filter flags
        out = self.cli("search", "walrus", "--source", "gmail", "--after", "2026-01-01", "--limit", "5").stdout
        self.assertIn("https://mail.google.com/mail/u/0/#all/t1", out)
        self.assertNotIn("#all/t2", out)
        self.assertNotIn("/projects/a/s2.jsonl", out)
        data = json.loads(self.cli("search", "walrus", "--json").stdout)
        self.assertEqual({r["pointer"] for r in data["results"]}, {"/projects/a/s2.jsonl", "https://mail.google.com/mail/u/0/#all/t1", "https://mail.google.com/mail/u/0/#all/t2"})

        # no match: header plus explicit message, exit 0
        proc = self.cli("search", "zzzznomatch")
        self.assertEqual(proc.returncode, 0)
        self.assertTrue(proc.stdout.startswith("KB: 5 rows"))
        self.assertIn("No matches.", proc.stdout)

    def test_output_neutralises_control_characters(self):
        kb_store.replace_rows(
            self.conn,
            "claude",
            "esc",
            [row("short", "2026-10-01", "Title\x1b[31m red", "payload \x1b[2J clear walrus\x07 bell", path="/p/\x1b]0;x\x07.jsonl")],
        )
        out = self.cli("search", "walrus").stdout
        self.assertNotIn("\x1b", out)
        self.assertNotIn("\x07", out)
        self.assertIn("walrus", out)


class FusionTests(KbCase):
    def expected(self, terms):
        """Independent re-implementation of the documented ranking."""
        match = " OR ".join(f'"{t}"' for t in terms)
        ranks = {}
        for name, op in (("summary", "!="), ("raw", "=")):
            best = {}
            for r in self.conn.execute(
                f"SELECT d.source, d.source_id, bm25(docs_fts) AS s FROM docs_fts JOIN docs d ON d.id = docs_fts.rowid "
                f"WHERE docs_fts MATCH ? AND d.kind {op} 'raw' ORDER BY s, d.id",
                (match,),
            ):
                key = (r["source"], r["source_id"])
                best[key] = min(best.get(key, r["s"]), r["s"])
            ordered = sorted(best, key=lambda k: (best[k], k[0], k[1]))
            for rank, key in enumerate(ordered, 1):
                ranks.setdefault(key, {})[name] = rank
        superseded = {
            (r[0], r[1]) for r in self.conn.execute("SELECT source, source_id FROM docs WHERE superseded_by IS NOT NULL")
        }
        scores = {}
        for key, rk in ranks.items():
            ts = self.conn.execute("SELECT ts FROM docs WHERE source = ? AND source_id = ?", key).fetchone()[0]
            age = (NOW - datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds() / 86400
            base = 0.0
            if "summary" in rk:
                base += 1 / (60 + rk["summary"])
            if "raw" in rk:
                base += 0.5 / (60 + rk["raw"])
            value = base * (1 + 0.1 * math.exp(-max(0, age) / 180))
            scores[key] = value / 2 if key in superseded else value
        return ranks, scores

    def seed(self):
        c = self.conn
        day = lambda n: iso(NOW - timedelta(days=n))  # noqa: E731
        kb_store.replace_rows(
            c, "claude", "A",
            [row("segment", day(10), "Item A", "alpha alpha alpha beta")]
            + [row("raw", day(10), "Item A", "alpha gamma delta words", chunk_index=i) for i in range(3)],
        )
        kb_store.replace_rows(c, "claude", "B", [row("segment", day(10), "Item B", "alpha beta gamma delta epsilon zeta eta theta iota")])
        kb_store.replace_rows(
            c, "claude", "C", [row("raw", day(10), "Item C", "alpha filler words here", chunk_index=i) for i in range(20)]
        )
        same = "alpha shared evidence text"
        kb_store.replace_rows(c, "gmail", "twin-a", [row("short", day(181), "Twin", same)])
        kb_store.replace_rows(c, "gmail", "twin-b", [row("short", day(1), "Twin", same)])
        kb_store.replace_rows(c, "gmail", "twin-c", [row("short", day(181), "Twin", same)])
        kb_store.replace_rows(c, "gmail", "twin-d", [row("short", day(-30), "Twin", same)])  # future-dated
        anchor = c.execute("SELECT id FROM docs WHERE source_id = 'A' AND kind = 'segment'").fetchone()[0]
        c.execute("UPDATE docs SET superseded_by = ? WHERE source_id = 'twin-c'", (anchor,))

    def test_rrf_recency_superseded(self):
        self.seed()
        result = kb_store.search(self.conn, "alpha", limit=20, now=NOW)
        ranks, scores = self.expected(["alpha"])
        got = [(r["source"], r["source_id"]) for r in result["results"]]
        want = sorted(scores, key=lambda k: (-scores[k], k))
        self.assertEqual(got, want)
        for r in result["results"]:
            key = (r["source"], r["source_id"])
            self.assertAlmostEqual(r["score"], scores[key], places=12)
            self.assertEqual({k: v for k, v in r["lists"].items() if v}, ranks[key])
        self.assertEqual(len(got), 7)

        # lists are collapsed per item: ranks are contiguous even though C has 20 chunks
        by_key = {(r["source"], r["source_id"]): r for r in result["results"]}
        self.assertEqual(sorted(r["lists"]["raw"] for r in result["results"] if r["lists"]["raw"]), [1, 2])
        self.assertEqual(sorted(r["lists"]["summary"] for r in result["results"] if r["lists"]["summary"]), [1, 2, 3, 4, 5, 6])
        # raw-only item is kept
        c = by_key[("claude", "C")]
        self.assertIsNone(c["lists"]["summary"])
        self.assertEqual(c["kind"], "raw")
        # newer identical evidence outranks older identical evidence
        pos = {k: i for i, k in enumerate(got)}
        self.assertLess(pos[("gmail", "twin-b")], pos[("gmail", "twin-a")])
        # superseded identical item scores half of its non-superseded twin (same evidence, same age)
        self.assertLess(pos[("gmail", "twin-a")], pos[("gmail", "twin-c")])
        twin_c = by_key[("gmail", "twin-c")]
        self.assertTrue(twin_c["superseded"])
        rank_c = twin_c["lists"]["summary"]
        age_mult = 1 + 0.1 * math.exp(-181 / 180)
        self.assertAlmostEqual(twin_c["score"], 0.5 * age_mult / (60 + rank_c), places=12)
        # future-dated item: age clamps to zero, bonus never exceeds 10%
        future = by_key[("gmail", "twin-d")]
        self.assertAlmostEqual(future["score"], 1.1 / (60 + future["lists"]["summary"]), places=12)
        # deterministic
        again = kb_store.search(self.conn, "alpha", limit=20, now=NOW)
        self.assertEqual([r["id"] for r in again["results"]], [r["id"] for r in result["results"]])

    def test_relevance_beats_small_recency_bonus(self):
        c = self.conn
        old = iso(NOW - timedelta(days=400))
        kb_store.replace_rows(
            c, "s", "old-relevant",
            [row("segment", old, "T", "kiwi kiwi kiwi kiwi"), row("raw", old, "T", "kiwi kiwi kiwi kiwi")],
        )
        kb_store.replace_rows(c, "s", "new-weak", [row("segment", iso(NOW - timedelta(days=1)), "T", "kiwi " + "padding " * 40)])
        res = kb_store.search(c, "kiwi", now=NOW)
        self.assertEqual([r["source_id"] for r in res["results"]], ["old-relevant", "new-weak"])

class FreshnessTests(KbCase):
    def test_stats_source_freshness(self):
        c = self.conn
        now = datetime.now(timezone.utc)
        kb_store.replace_rows(
            c, "claude", "s1",
            [row("raw", "2026-09-01T00:00:00Z", "Long", "walrus part %d" % i, summary_status="pending", chunk_index=i) for i in range(3)],
        )
        kb_store.replace_rows(c, "claude", "s2", [row("short", "2026-10-05T00:00:00Z", "Short", "walrus short"), row("raw", "2026-10-05T00:00:00Z", "Short", "walrus short", chunk_index=0)])
        kb_store.replace_rows(
            c, "claude", "s3",
            [row("segment", "2026-10-06T00:00:00Z", "Seg", "walrus seg"), row("atom", "2026-10-06T00:00:00Z", "Atom", "walrus atom")]
            + [row("raw", "2026-10-06T00:00:00Z", "Seg", "walrus raw", summary_status="done", chunk_index=0)],
        )
        kb_store.replace_rows(c, "gmail", "t1", [row("short", "2026-02-01T00:00:00Z", "Mail", "walrus mail", url="u")])
        kb_store.set_state(c, "claude", "last_attempt", iso(now - timedelta(hours=1, minutes=1)))
        kb_store.set_state(c, "claude", "last_success", iso(now - timedelta(hours=1)))
        kb_store.set_state(c, "claude", "last_error", {})
        kb_store.set_state(c, "claude", "skipped", {"count": 2, "reasons": {"excluded": 2}})
        kb_store.set_state(c, "gmail", "last_success", iso(now - timedelta(hours=30)))
        kb_store.set_state(c, "gmail", "last_attempt", iso(now - timedelta(minutes=5)))
        kb_store.set_state(c, "gmail", "last_error", {"type": "HttpError", "at": iso(now)})
        kb_store.set_state(c, "gmail", "skipped", {"count": 1})

        st = kb_store.stats(c)
        self.assertEqual((st["rows"], st["items"]), (9, 4))
        self.assertEqual(st["by_kind"], {"raw": 5, "short": 2, "segment": 1, "atom": 1})
        self.assertEqual(st["pending_summaries"], 1)
        self.assertEqual(st["skipped"], 3)
        cl, gm = st["by_source"]["claude"], st["by_source"]["gmail"]
        self.assertEqual((cl["items"], cl["rows"], cl["pending_summaries"], cl["skipped"]), (3, 8, 1, 2))
        self.assertEqual((cl["first_ts"], cl["last_ts"]), ("2026-09-01T00:00:00Z", "2026-10-06T00:00:00Z"))
        self.assertEqual((gm["items"], gm["rows"], gm["pending_summaries"]), (1, 1, 0))
        self.assertEqual(cl["status"], "fresh")
        self.assertEqual(gm["status"], "failed")
        self.assertEqual(gm["last_error"], "HttpError")
        self.assertEqual(gm["last_success"], iso(now - timedelta(hours=30)))
        # Gmail's failure never borrows Claude's success time, and vice versa
        self.assertEqual(st["last_ingest"], iso(now - timedelta(hours=1)))
        self.assertTrue(st["stale"])
        json.dumps(st)

        # CLI from another directory: header and stats expose per-source state
        out = self.cli("stats").stdout
        self.assertIn("pending summaries: 1", out)
        self.assertIn("gmail", out)
        self.assertIn("failed", out)
        header = self.cli("search", "walrus").stdout.splitlines()
        self.assertTrue(header[0].startswith("KB: 9 rows, 4 items | last ingest: "))
        self.assertTrue(any("gmail" in line and "FAILED" in line for line in header[:4]))
        self.assertFalse(any("claude" in line and line.lstrip().startswith("!") for line in header[:4]))

        # age over 12 hours is visible in the header
        kb_store.set_state(c, "claude", "last_success", iso(now - timedelta(hours=20)))
        kb_store.set_state(c, "claude", "last_attempt", iso(now - timedelta(hours=20)))
        out = self.cli("search", "walrus").stdout
        self.assertIn("STALE", out.splitlines()[0])
        self.assertTrue(any("claude" in line and "STALE" in line for line in out.splitlines()[1:4]))

        # an attempt newer than the last success without an error = interrupted run
        kb_store.set_state(c, "claude", "last_attempt", iso(now))
        self.assertEqual(kb_store.stats(c)["by_source"]["claude"]["status"], "incomplete")

    def test_never_ingested_is_not_invented(self):
        kb_store.replace_rows(self.conn, "claude", "s1", [row("short", "2026-10-05", "T", "walrus")])
        res = kb_store.search(self.conn, "walrus", now=NOW)
        self.assertIsNone(res["header"]["last_ingest"])
        self.assertEqual(res["header"]["sources"]["claude"]["status"], "never")
        self.assertIn("never recorded", self.cli("search", "walrus").stdout)


class ReplaceTests(KbCase):
    def test_atomic_replace_and_concurrency(self):
        c = self.conn
        kb_store.replace_rows(c, "claude", "X", [row("short", "2026-01-01", "X", "oldterm one"), row("raw", "2026-01-01", "X", "oldterm two")])
        kb_store.replace_rows(c, "claude", "XY", [row("short", "2026-01-01", "XY", "oldterm sibling")])
        kb_store.replace_rows(c, "gmail", "X", [row("short", "2026-01-01", "other", "oldterm other source")])
        before = [tuple(r) for r in c.execute("SELECT id, kind, source, source_id, content FROM docs ORDER BY id")]

        # forced failure midway: nothing changes, index included
        c.execute("CREATE TRIGGER boom BEFORE INSERT ON docs WHEN NEW.title = 'BOOM' BEGIN SELECT RAISE(ABORT, 'boom'); END")
        with self.assertRaises(sqlite3.DatabaseError):
            kb_store.replace_rows(c, "claude", "X", [row("short", "2026-02-01", "ok", "newterm"), row("raw", "2026-02-01", "BOOM", "newterm")])
        self.assertFalse(c.in_transaction)
        after = [tuple(r) for r in c.execute("SELECT id, kind, source, source_id, content FROM docs ORDER BY id")]
        self.assertEqual(after, before)
        self.assertEqual(self.fts_hits("newterm"), set())
        self.assertEqual(len(self.fts_hits("oldterm")), 4)
        self.assert_fts_consistent()
        c.execute("DROP TRIGGER boom")

        # validation failure happens before any write
        for bad in ([row("short", "not-a-date", "t", "c")], [{"kind": "short", "ts": "2026-01-01", "title": "t", "content": "c", "metadata": "x"}], [row("", "2026-01-01", "t", "c")]):
            with self.assertRaises((ValueError, TypeError)):
                kb_store.replace_rows(c, "claude", "X", bad)
        self.assertEqual([tuple(r) for r in c.execute("SELECT id, kind, source, source_id, content FROM docs ORDER BY id")], before)

        # item + watermark commit or roll back together
        with self.assertRaises(RuntimeError):
            with kb_store.transaction(c):
                kb_store.replace_rows(c, "claude", "X", [row("short", "2026-02-01", "X", "newterm")])
                kb_store.set_state(c, "claude", "watermark", "W1")
                raise RuntimeError("late failure")
        self.assertIsNone(kb_store.get_state(c, "claude", "watermark"))
        self.assertEqual(self.fts_hits("newterm"), set())
        with kb_store.transaction(c):
            kb_store.replace_rows(c, "claude", "X", [row("short", "2026-02-01", "X", "newterm")])
            kb_store.set_state(c, "claude", "watermark", "W2")

        # successful replacement: exactly the new rows, others untouched
        self.assertEqual(kb_store.get_state(c, "claude", "watermark"), "W2")
        rows = c.execute("SELECT source, source_id, content FROM docs ORDER BY id").fetchall()
        self.assertEqual(sorted(tuple(r) for r in rows), sorted([("claude", "XY", "oldterm sibling"), ("gmail", "X", "oldterm other source"), ("claude", "X", "newterm")]))
        self.assertEqual(len(self.fts_hits("newterm")), 1)
        self.assertEqual(len(self.fts_hits("oldterm")), 2)
        # idempotent: replacing with the same rows twice gives the same item
        kb_store.replace_rows(c, "claude", "X", [row("short", "2026-02-01", "X", "newterm")])
        self.assertEqual(self.count("SELECT COUNT(*) FROM docs WHERE source = 'claude' AND source_id = 'X'"), 1)
        # empty list purges the item
        self.assertEqual(kb_store.replace_rows(c, "claude", "X", []), {"deleted": 1, "inserted": 0})
        self.assertEqual(self.fts_hits("newterm"), set())
        self.assert_fts_consistent()

    def test_superseded_references_stay_coherent(self):
        c = self.conn
        kb_store.replace_rows(c, "s", "P", [row("segment", "2026-01-01", "P", "pterm"), row("raw", "2026-01-01", "P", "pterm raw")])
        kb_store.replace_rows(c, "s", "Q", [row("short", "2026-01-01", "Q", "qterm")])
        p_seg = c.execute("SELECT id FROM docs WHERE source_id = 'P' AND kind = 'segment'").fetchone()[0]
        c.execute("UPDATE docs SET superseded_by = ? WHERE source_id = 'Q'", (p_seg,))

        # refreshing the replacement keeps Q pointing at a live P row of the same kind
        kb_store.replace_rows(c, "s", "P", [row("raw", "2026-02-01", "P", "praw2"), row("segment", "2026-02-01", "P", "pterm2")])
        target = c.execute("SELECT superseded_by FROM docs WHERE source_id = 'Q'").fetchone()[0]
        self.assertEqual(c.execute("SELECT source_id, kind FROM docs WHERE id = ?", (target,)).fetchone()[:], ("P", "segment"))
        self.assertEqual(self.dangling_refs(), 0)

        # refreshing the superseded item keeps it superseded
        kb_store.replace_rows(c, "s", "Q", [row("short", "2026-03-01", "Q", "qterm2")])
        target2 = c.execute("SELECT superseded_by FROM docs WHERE source_id = 'Q'").fetchone()[0]
        self.assertEqual(target2, target)
        self.assertTrue(kb_store.search(c, "qterm2", now=NOW)["results"][0]["superseded"])

        # deleting the replacement clears the reference instead of dangling
        kb_store.replace_rows(c, "s", "P", [])
        self.assertIsNone(c.execute("SELECT superseded_by FROM docs WHERE source_id = 'Q'").fetchone()[0])
        self.assertEqual(self.dangling_refs(), 0)
        self.assert_fts_consistent()

    def test_concurrent_replacement_is_serialised(self):
        kb_store.replace_rows(self.conn, "claude", "shared", [row("raw", "2026-01-01", "t", "seed chunk")])
        errors = []

        def writer(w):
            try:
                conn = kb_store.connect(self.db)
                try:
                    for i in range(6):
                        kb_store.replace_rows(
                            conn, "claude", "shared",
                            [row("raw", "2026-01-01", "t", f"writer{w} iter{i} chunk{n}", chunk_index=n) for n in range(3)],
                        )
                        kb_store.replace_rows(conn, "gmail", f"own{w}", [row("short", "2026-01-01", "t", f"own{w} iter{i}")])
                finally:
                    conn.close()
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))

        threads = [threading.Thread(target=writer, args=(w,)) for w in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(120)
        self.assertEqual(errors, [])
        contents = [r[0] for r in self.conn.execute("SELECT content FROM docs WHERE source_id = 'shared' ORDER BY id")]
        self.assertEqual(len(contents), 3)
        self.assertEqual(len({c.rsplit(" ", 1)[0] for c in contents}), 1, "rows come from a single writer version")
        self.assertEqual(self.count("SELECT COUNT(*) FROM docs WHERE source = 'gmail'"), 4)
        self.assert_fts_consistent()


class InvalidInputTests(KbCase):
    def test_invalid_search_inputs(self):
        kb_store.replace_rows(self.conn, "claude", "s1", [row("short", "2026-10-01", "T", "walrus words")])
        for bad_after in ("2026-13-45", "tomorrow", "2026-02-30", "20261001", "2026-1-1", ""):
            proc = self.cli("search", "walrus", "--after", bad_after)
            self.assertEqual(proc.returncode, 2, bad_after)
            self.assertTrue(proc.stderr.strip())
            self.assertNotIn("Traceback", proc.stderr)
        for bad_limit in ("0", "-3", "abc", "1.5", "100000"):
            proc = self.cli("search", "walrus", "--limit", bad_limit)
            self.assertEqual(proc.returncode, 2, bad_limit)
            self.assertNotIn("Traceback", proc.stderr)
        for query in ("", "   ", "!!! ??? ***", '"""', "_ _"):
            proc = self.cli("search", query)
            self.assertEqual(proc.returncode, 0, (query, proc.stderr))
            self.assertTrue(proc.stdout.startswith("KB: 1 rows"))
            self.assertIn("No searchable terms", proc.stdout)
        for query in ['foo"bar', "walrus'; DROP TABLE docs; --", "walrus) OR (", "NEAR(", "walrus*", "col:walrus", "^walrus"]:
            proc = self.cli("search", query)
            self.assertEqual(proc.returncode, 0, (query, proc.stderr))
            self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(self.count(), 1)
        proc = self.cli("search", "walrus", "--source", "no-such-source")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("No matches.", proc.stdout)
        self.assertEqual(self.count(), 1)
        # API-level validation mirrors the CLI
        for kwargs in ({"after": "2026-02-30"}, {"limit": 0}, {"limit": True}, {"limit": "5"}):
            with self.assertRaises(ValueError):
                kb_store.search(self.conn, "walrus", now=NOW, **kwargs)
        # a future-dated row can never produce an exploding or negative score
        kb_store.replace_rows(self.conn, "claude", "future", [row("short", "2999-01-01", "T", "walrus words")])
        for r in kb_store.search(self.conn, "walrus", now=NOW)["results"]:
            self.assertTrue(0 < r["score"] <= 1.1 / 61 + 1e-12)


class QueryPlanTests(KbCase):
    def test_superseded_lookup_uses_partial_index(self):
        """Search and stats must find the (normally empty) superseded set through the partial
        index, never by walking docs_item and probing every row of the content table."""
        kb_store.replace_rows(self.conn, "claude", "A", [row("segment", "2026-10-01", "Item A", "alpha beta")])
        kb_store.replace_rows(self.conn, "claude", "B", [row("raw", "2026-10-02", "Item B", "alpha gamma", chunk_index=0)])
        executed = []
        self.conn.set_trace_callback(executed.append)
        self.assertEqual(len(kb_store.search(self.conn, "alpha", now=NOW)["results"]), 2)
        kb_store.stats(self.conn, now=NOW)
        self.conn.set_trace_callback(None)
        lookups = [sql for sql in executed if "superseded_by IS NOT NULL" in sql]
        self.assertGreaterEqual(len(lookups), 2)  # one from search, one from stats
        for sql in lookups:
            plan = " | ".join(r[3] for r in self.conn.execute("EXPLAIN QUERY PLAN " + sql))
            self.assertIn("docs_superseded", plan, sql)
            self.assertNotIn("SCAN docs", plan, sql)


class StdlibCliTests(KbCase):
    def test_stdlib_cli_no_network(self):
        script = """
import runpy, socket, sys
def deny(*a, **k):
    raise RuntimeError("network access attempted")
socket.socket = deny
socket.create_connection = deny
socket.getaddrinfo = deny
kb, db = sys.argv[1], sys.argv[2]
for argv in (["init"], ["stats"], ["search", "walrus"]):
    sys.argv = ["kb.py", *argv, "--db", db]
    try:
        runpy.run_path(kb, run_name="__main__")
    except SystemExit as exc:
        assert exc.code in (0, None), (argv, exc.code)
banned = sorted(m for m in sys.modules if m.split(".")[0] in {"google", "googleapiclient", "anthropic", "requests", "urllib3", "httpx", "numpy", "sqlite_vec", "dotenv"})
assert not banned, banned
"""
        kb_store.replace_rows(self.conn, "claude", "s1", [row("short", "2026-10-01", "T", "walrus words")])
        proc = subprocess.run(
            [sys.executable, "-c", script, str(KB), self.db], cwd=self.elsewhere, capture_output=True, text=True, timeout=60
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("walrus", proc.stdout)


class HeaderCountTests(KbCase):
    def check_counts(self):
        expected_rows = self.conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        expected_items = self.conn.execute("SELECT COUNT(*) FROM (SELECT DISTINCT source,source_id FROM docs)").fetchone()[0]
        result = kb_store.search(self.conn, "walrus", now=NOW)
        self.assertEqual((result["header"]["rows"], result["header"]["items"]), (expected_rows, expected_items))
        counts = self.conn.execute("SELECT SUM(rows),SUM(items) FROM source_counts").fetchone()
        self.assertEqual((counts[0] or 0, counts[1] or 0), (expected_rows, expected_items))

    def test_header_counts_survive_item_replacement_deletion_and_rollback(self):
        self.check_counts()
        for source, item, n in [("claude", "A", 3), ("gmail", "A", 2), ("claude", "B", 1), ("claude", "A", 2)]:
            kb_store.replace_rows(self.conn, source, item, [row("raw", "2026-10-01", "T", "walrus", chunk_index=i) for i in range(n)])
            self.check_counts()
        self.conn.execute("UPDATE docs SET source='gmail',source_id='B' WHERE source='claude' AND source_id='B'")
        self.check_counts()
        with self.assertRaises(RuntimeError):
            with kb_store.transaction(self.conn):
                kb_store.replace_rows(self.conn, "gmail", "C", [row("short", "2026-10-01", "T", "walrus")])
                raise RuntimeError("rollback")
        self.check_counts()
        kb_store.replace_rows(self.conn, "claude", "A", [])
        self.check_counts()
        self.conn.execute("DELETE FROM docs")
        self.check_counts()

    def test_version_one_migration_preserves_rows_and_fts(self):
        old_path = self.dir / "v1.sqlite"
        old = sqlite3.connect(old_path)
        for statement in kb_store._SCHEMA:
            old.execute(statement)
        old.execute("PRAGMA user_version=1")
        old.execute("INSERT INTO docs(kind,source,source_id,ts,title,content) VALUES('short','claude','old','2026-10-01','Original','walrus preserved')")
        old.commit()
        old.close()
        upgraded = kb_store.connect(old_path)
        try:
            result = kb_store.search(upgraded, "walrus", now=NOW)
            self.assertEqual((result["header"]["rows"], result["header"]["items"]), (1, 1))
            self.assertEqual(result["results"][0]["title"], "Original")
            self.assertEqual(upgraded.execute("SELECT rows,items FROM source_counts").fetchone()[:], (1, 1))
        finally:
            upgraded.close()


if __name__ == "__main__":
    unittest.main()
