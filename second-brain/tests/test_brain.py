"""Boundary regression tests for second-brain/brain.py (stdlib unittest).

Run:  python3 -m unittest discover -s second-brain/tests -v
Each test builds a throwaway workspace; nothing touches the real workspace.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
BRAIN_PATH = HERE.parent / "brain.py"

_spec = importlib.util.spec_from_file_location("brain_under_test", BRAIN_PATH)
brain = importlib.util.module_from_spec(_spec)
sys.modules["brain_under_test"] = brain
_spec.loader.exec_module(brain)  # type: ignore[union-attr]

AWS_LIKE = "AKIA" + "ABCDEFGHIJKLMNOP"


def write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


class WorkspaceCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name).resolve()
        self.root = self.base / "ws"
        self.root.mkdir()
        self.outside = write(self.base, "outside.md", "# Outside\n\nOutside secret zebra.\n")
        self.populate()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def populate(self) -> None:
        r = self.root
        write(r, "TASKS.md", "# Tasks\n\n> Phase: employed.\n\n## Active\n\n### Debt plan\n\n"
                             "- [ ] Pick a method (avalanche = highest APR first, snowball = smallest balance first)\n"
                             "- [ ] Automate minimums\n\n### Income sprint\n\n- [ ] Publish a profile\n")
        write(r, "OPERATIONS.md", "# Operations Index\n\n| File | What |\n| --- | --- |\n"
                                  "| `TASKS.md` | Active task list across all realms |\n")
        write(r, "docs/guide.md", "# Guide\n\nGeneral prose about nothing in particular, long enough to not be thin. " * 4 + "\n")
        # excluded material
        write(r, ".env", "API_TOKEN=supersecretvalue1\n")
        write(r, "docs/.env", "x=1\n")
        write(r, "node_modules/pkg/readme.md", "# Vendored\n\nvendoredcanary details\n")
        write(r, "IT Mgmt/Employer-IT-Playbook-Private/notes.md", "# Private\n\nemployercanary content\n")
        write(r, "CLAUDE.md", "# Instructions\n\ninstructioncanary rules\n")
        write(r, "docs/CLAUDE.md", "# Instructions\n\ninstructioncanary rules\n")
        write(r, "page_files/saved.md", "# Saved page\n\nsavedpagecanary\n")
        write(r, "archive/old.md", "# Old\n\narchivecanary\n")
        write(r, "notes/pem-notes.md", "# Keys\n\n-----BEGIN RSA PRIVATE KEY-----\nMIIEpQIBAAKCAQEA\n\npemcanary\n")
        write(r, "notes/credentials.md", "# Creds\n\ncredfilecanary\n")
        write(r, "docs/work-log.md", "# Work log\n\nworklogcanary\n")

    def call(self, *args: str):
        return brain.run(["--root", str(self.root), *args])

    def remember(self, title: str, summary: str, body: str):
        return brain.run(["--root", str(self.root), "remember",
                          f"--title={title}", f"--summary={summary}", f"--body={body}"])

    def index(self) -> dict:
        payload, code = self.call("index")
        self.assertEqual(code, 0, payload)
        return payload

    def catalogue_text(self) -> str:
        return (self.root / "second-brain" / "catalogue.md").read_text(encoding="utf-8")


class IndexPolicyTests(WorkspaceCase):
    def test_excluded_paths_never_enter_catalogue(self) -> None:
        payload = self.index()
        cat = self.catalogue_text()
        for canary in ("vendoredcanary", "employercanary", "instructioncanary", "savedpagecanary",
                       "archivecanary", "pemcanary", "credfilecanary", "worklogcanary",
                       "supersecretvalue1", "node_modules", "Employer-IT", "CLAUDE.md", ".env"):
            self.assertNotIn(canary, cat, canary)
        self.assertIn("../TASKS.md", cat)
        self.assertIn("notes/pem-notes.md", payload["excluded_secret_paths"])
        for reason in ("vendor_or_generated", "private_or_employer", "instruction_file", "saved_web_page",
                       "archived", "secret_content", "secret_file", "employer_work_log"):
            self.assertIn(reason, payload["skipped"], reason)
        for canary in ("vendoredcanary", "employercanary", "instructioncanary", "pemcanary", "worklogcanary"):
            result, _ = self.call("query", canary)
            self.assertEqual(result["status"], "no_match", canary)
            self.assertEqual(result["evidence"], [])

    def test_playwright_reports_stay_excluded_across_index_and_check(self) -> None:
        source = "job-autofill/docs/testing.md"
        write(self.root, source, "# Testing\n\nReal browser testing documentation.\n")
        self.index()
        self.assertIn(source, self.catalogue_text())
        reports = (
            "job-autofill/test-results/safety-U15-safe-submit-navigates-once-and-confirms/error-context.md",
            "job-autofill/playwright-report/data/error-context.md",
            "test-results/case/error-context.md",
            "playwright-report/data/error-context.md",
        )
        for rel in reports:
            write(self.root, rel, "# Browser failure\n\nGenerated failure context.\n")
        result, code = self.call("check")
        self.assertEqual((result["status"], code), ("ok", 0), result)
        self.index()
        cat = self.catalogue_text()
        self.assertIn(source, cat)
        for rel in reports:
            self.assertNotIn(rel, cat)
            (self.root / rel).unlink()
        result, code = self.call("check")
        self.assertEqual((result["status"], code), ("ok", 0), result)
        write(self.root, "job-autofill/docs/new.md", "# New source\n\nReal new documentation.\n")
        result, code = self.call("check")
        self.assertEqual(code, 1, result)
        self.assertIn(
            ("unindexed_source", "job-autofill/docs/new.md"),
            {(problem["kind"], problem["path"]) for problem in result["problems"]},
        )

    def test_check_is_clean_after_index_and_flags_drift(self) -> None:
        self.index()
        result, code = self.call("check")
        self.assertEqual((result["status"], code), ("ok", 0), result)
        write(self.root, "docs/new.md", "# New\n\nfresh content\n")
        (self.root / "docs" / "guide.md").unlink()
        result, code = self.call("check")
        kinds = {p["kind"] for p in result["problems"]}
        self.assertEqual(code, 1)
        self.assertTrue({"unindexed_source", "dangling_entry"} <= kinds, kinds)

    def test_forged_catalogue_path_is_rejected(self) -> None:
        self.index()
        cat = self.root / "second-brain" / "catalogue.md"
        line = next(l for l in self.catalogue_text().split("\n") if "../TASKS.md" in l)
        forged = line.replace("../TASKS.md", "../../outside.md")
        cat.write_text(self.catalogue_text() + forged + "\n", encoding="utf-8")
        result, _ = self.call("query", "outside secret zebra")
        self.assertNotIn("outside.md", json.dumps(result["evidence"]))
        check, code = self.call("check")
        self.assertEqual(code, 1)
        self.assertIn("bad_line", {p["kind"] for p in check["problems"]})


class QueryTests(WorkspaceCase):
    def test_opens_exactly_one_source_and_cites_real_lines(self) -> None:
        self.index()
        orig = Path.read_bytes
        reads: list[str] = []

        def spy(self: Path) -> bytes:
            reads.append(str(self))
            return orig(self)

        with mock.patch.object(Path, "read_bytes", spy):
            result, code = self.call("query", "Which debt method should I use, avalanche?")
        self.assertEqual((result["status"], code), ("ok", 0), result)
        self.assertEqual(reads, [str(self.root / "TASKS.md")])
        self.assertEqual(result["files_opened"], 1)
        self.assertTrue({"question", "evidence", "files_opened", "elapsed_ms"} <= set(result))
        ev = result["evidence"][0]
        self.assertEqual(set(ev), {"path", "start_line", "end_line", "text"})
        lines = (self.root / ev["path"]).read_text(encoding="utf-8").split("\n")
        self.assertEqual(ev["text"], "\n".join(l.rstrip() for l in lines[ev["start_line"] - 1:ev["end_line"]]))
        self.assertIn("avalanche", ev["text"])

    def test_no_match_empty_invalid_and_unindexed(self) -> None:
        result, code = self.call("query", "--no-reindex", "avalanche")
        self.assertEqual((result["status"], code), ("not_indexed", 3))
        self.index()
        result, code = self.call("query", "quantum chromodynamics lattice")
        self.assertEqual((result["status"], code, result["evidence"], result["files_opened"]), ("no_match", 0, [], 0))
        result, code = self.call("query", "what is the of and")
        self.assertEqual((result["status"], code), ("empty_question", 0))
        result, code = self.call("query", "x" * 501)
        self.assertEqual((result["status"], code), ("error", 2))

    def test_changed_source_is_stale_not_silently_answered(self) -> None:
        self.index()
        with (self.root / "TASKS.md").open("a", encoding="utf-8") as fh:
            fh.write("\n- [ ] avalanche edited later\n")
        result, code = self.call("query", "--no-reindex", "debt method avalanche")
        self.assertEqual((result["status"], code, result["evidence"]), ("stale", 3, []))
        self.assertEqual(result["stale_paths"], ["TASKS.md"])
        self.index()
        result, _ = self.call("query", "debt method avalanche")
        self.assertEqual(result["status"], "ok")

    def test_secret_like_tokens_are_redacted_from_evidence(self) -> None:
        write(self.root, "notes/rotation.md", "# Rotation\n\n## Leftovers\n\nDefault password `Peakstarter1!` "
              "and DC=corp,DC=local remain; api_key = abcd1234efgh must rotate.\n")
        self.index()
        result, _ = self.call("query", "rotation leftovers default password")
        text = json.dumps(result["evidence"])
        self.assertEqual(result["status"], "ok", result)
        self.assertNotIn("Peakstarter1", text)
        self.assertNotIn("DC=corp", text)
        self.assertNotIn("abcd1234efgh", text)
        self.assertGreaterEqual(result["redactions"], 3)
        cat = self.catalogue_text()
        for leaked in ("Peakstarter1", "DC=corp", "abcd1234efgh"):
            self.assertNotIn(leaked, cat)

    def test_section_extraction_is_bounded_and_centred_on_the_hit(self) -> None:
        filler = "\n".join(f"filler row {i} with text" for i in range(600))
        write(self.root, "docs/giant.md",
              f"# Reference\n\n## Details\n\n{filler[:2000]}\nneedlexyz sits here\n{filler}\n")
        self.index()
        result, _ = self.call("query", "giant needlexyz")
        self.assertEqual(result["status"], "ok", result)
        ev = result["evidence"][0]
        self.assertLessEqual(ev["end_line"] - ev["start_line"] + 1, brain.MAX_EVIDENCE_LINES)
        self.assertLessEqual(len(ev["text"]), brain.MAX_EVIDENCE_CHARS)
        self.assertIn("needlexyz", ev["text"])


class PointerTests(WorkspaceCase):
    def test_pointer_followed_once_not_chained(self) -> None:
        write(self.root, "plans/zebrafish.md", "# Zebrafish protocol\n\n## Zebrafish handling\n\nSee [details](details.md).\n")
        write(self.root, "plans/details.md", "# Details\n\n## Details\n\nSee [more](more.md).\n")
        write(self.root, "plans/more.md", "# More\n\nmorecanary final destination\n")
        self.index()
        result, _ = self.call("query", "zebrafish protocol handling")
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["pointer"], "plans/details.md")
        self.assertEqual(result["files_opened"], 2)
        self.assertEqual([e["path"] for e in result["evidence"]], ["plans/zebrafish.md", "plans/details.md"])
        self.assertNotIn("morecanary", json.dumps(result))

    def test_unsafe_or_excluded_pointers_are_never_followed(self) -> None:
        write(self.root, "docs/quokka.md",
              "# Quokka notes\n\n## Quokka handling\n\nSee [a](../../outside.md), [b](/etc/passwd), "
              "[c](https://example.com/quokka.md), [d](CLAUDE.md), [e](.env), [f](sym.md), "
              "`docs/missing.md`, [g](../notes/pem-notes.md).\n")
        try:
            os.symlink(self.outside, self.root / "docs" / "sym.md")
        except (OSError, NotImplementedError):
            pass
        self.index()
        result, _ = self.call("query", "quokka handling")
        self.assertEqual(result["status"], "ok", result)
        self.assertIsNone(result["pointer"])
        self.assertEqual(result["files_opened"], 1)
        self.assertNotIn("pemcanary", json.dumps(result))
        self.assertNotIn("zebra", json.dumps(result))

    def test_pointer_swapped_for_symlink_after_indexing_is_skipped(self) -> None:
        write(self.root, "plans/zebrafish.md", "# Zebrafish protocol\n\n## Zebrafish handling\n\nSee [details](details.md).\n")
        target = write(self.root, "plans/details.md", "# Details\n\n## Details\n\nbenign\n")
        self.index()
        target.unlink()
        try:
            os.symlink(self.outside, target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        result, _ = self.call("query", "--no-reindex", "zebrafish protocol handling")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result.get("pointer_status"), "stale")
        self.assertIsNone(result["pointer"])
        self.assertEqual(result["files_opened"], 1)
        self.assertNotIn("Outside secret", json.dumps(result))
        healed, _ = self.call("query", "zebrafish protocol handling")  # reindex drops the symlink
        self.assertEqual((healed["status"], healed["pointer"], healed["files_opened"]), ("ok", None, 1))
        self.assertNotIn("Outside secret", json.dumps(healed))


class RememberTests(WorkspaceCase):
    def test_save_index_query_roundtrip_and_traversal_safety(self) -> None:
        self.index()
        saved, code = self.remember("../../etc/passwd nebulizer", "Nebulizer settings summary",
                                "The nebulizer runs at 40 psi.\n\n## Maintenance\n\nReplace filters monthly.")
        self.assertEqual((saved["status"], code, saved["indexed"]), ("saved", 0, True), saved)
        mem = (self.root / saved["path"]).resolve()
        self.assertEqual(mem.parent, (self.root / "second-brain" / "memories").resolve())
        self.assertIn(f"../{saved['path']}", self.catalogue_text())
        again, _ = self.remember("../../etc/passwd nebulizer", "dup", "same title twice")
        self.assertNotEqual(again["path"], saved["path"])
        result, _ = self.call("query", "what psi does the nebulizer run at")
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["source"]["path"], saved["path"])
        self.assertIn("40 psi", result["evidence"][0]["text"])
        check, code = self.call("check")
        self.assertEqual((check["status"], code), ("ok", 0), check)

    def test_first_use_builds_catalogue_with_sources_included(self) -> None:
        saved, code = self.remember("Cold start", "Saved before any index", "cold body text")
        self.assertEqual(code, 0, saved)
        self.assertIn("../TASKS.md", self.catalogue_text())
        self.assertIn(saved["path"], self.catalogue_text())

    def test_invalid_input_is_rejected_without_writing(self) -> None:
        cases = [
            ("", "s", "b"), ("t", "", "b"), ("t", "s", ""), ("t" * 121, "s", "b"), ("t", "s" * 501, "b"),
            ("t", "s", "b" * 8001), ("two\nlines", "s", "b"), ("t", "s\nx", "b"), ("t", "s", "bad\x00body"),
            ("t", "s", f"key {AWS_LIKE} oops"),
        ]
        for title, summary, body in cases:
            result, code = brain.run(["--root", str(self.root), "remember",
                                      f"--title={title}", f"--summary={summary}", f"--body={body}"])
            self.assertEqual(code, 2, (title[:10], result))
            self.assertEqual(result["status"], "error")
        self.assertFalse((self.root / "second-brain" / "memories").exists())

    def test_values_starting_with_dash_are_accepted(self) -> None:
        result, code = brain.run(["--root", str(self.root), "remember", "--title", "-dash title",
                                  "--summary", "- dash summary", "--body", "-dash body"])
        self.assertEqual((result["status"], code), ("saved", 0), result)

    def test_concurrent_writers_lose_nothing(self) -> None:
        self.index()
        procs = [subprocess.Popen(
            [sys.executable, str(BRAIN_PATH), "--root", str(self.root), "remember",
             "--title", f"parallel note {i}", "--summary", f"summary {i}", "--body", f"body {i} parallelcanary"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(8)]
        outs = [p.communicate(timeout=60) + (p.returncode,) for p in procs]
        for out, err, rc in outs:
            self.assertEqual(rc, 0, (out, err))
            self.assertEqual(json.loads(out)["status"], "saved")
        files = sorted((self.root / "second-brain" / "memories").glob("*.md"))
        self.assertEqual(len(files), 8)
        lines = [l for l in self.catalogue_text().split("\n") if "· memory ·" in l]
        self.assertEqual(len(lines), 8)
        check, code = self.call("check")
        self.assertEqual((check["status"], code), ("ok", 0), check)
        self.assertEqual(list((self.root / "second-brain").rglob(".brain-*.tmp")), [])

    def test_lock_contention_fails_retryably_without_writing(self) -> None:
        self.index()
        with brain.WriterLock(self.root / "second-brain", timeout=1):
            with mock.patch.dict(os.environ, {"BRAIN_LOCK_TIMEOUT": "0.2"}):
                result, code = self.remember("Blocked", "blocked write", "should not land")
        self.assertEqual((result["status"], result["error"], code), ("error", "locked", 4))
        mem_dir = self.root / "second-brain" / "memories"
        self.assertEqual(list(mem_dir.glob("*.md")) if mem_dir.exists() else [], [])


class MemoryIndexTests(WorkspaceCase):
    def memory_md(self) -> str:
        return (self.root / "memory.md").read_text(encoding="utf-8")

    def memory_lines(self) -> list[str]:
        return [l for l in self.memory_md().split("\n") if l.startswith("- [")]

    def kinds(self) -> set[str]:
        return {p["kind"] for p in self.call("check")[0]["problems"]}

    def test_index_and_remember_keep_short_index_synced_and_drift_is_repaired(self) -> None:
        self.index()
        self.assertIn("_No memories saved yet._", self.memory_md())
        self.assertEqual(self.call("check")[1], 0)
        long_summary = "Use `chmod` | <b>now</b> & later " + "word " * 90
        saved, code = self.remember("Router [fix] draft", long_summary, "zzbodycanary unique sentence about routers")
        self.assertEqual((code, saved["memory_index"]), (0, "memory.md"), saved)
        second, _ = self.remember("Second note", "second summary", "second body")
        lines = self.memory_lines()
        self.assertEqual(len(lines), 2, lines)
        self.assertNotIn("zzbodycanary", self.memory_md())
        first_line = next(l for l in lines if saved["path"] in l)
        self.assertIn(f"({saved['path']})", first_line)
        self.assertLessEqual(len(first_line.split(" — ", 1)[1]), 200)
        self.assertIn("\\|", first_line)
        self.assertIn("\\&", first_line)
        self.assertIn("\\[fix\\]", first_line)
        self.assertNotIn("../memory.md", self.catalogue_text())
        self.assertEqual(self.call("check")[1], 0)
        # removal: file deleted behind the brain's back -> drift reported, index drops the line
        (self.root / second["path"]).unlink()
        self.assertIn("memory_index_drift", self.kinds())
        payload = self.index()
        self.assertEqual(len(self.memory_lines()), 1)
        self.assertEqual(payload["skipped"].get("generated_memory_index"), 1)
        self.assertEqual(self.call("check")[1], 0)
        # tampering: extra line, then a hand edit repaired by the next remember
        with (self.root / "memory.md").open("a", encoding="utf-8") as fh:
            fh.write("- [forged](second-brain/memories/nope.md) — stale\n")
        self.assertIn("memory_index_drift", self.kinds())
        self.remember("Third note", "third summary", "third body")
        self.assertNotIn("forged", self.memory_md())
        self.assertEqual(len(self.memory_lines()), 2)
        # deleted index: check flags it, index regenerates it
        (self.root / "memory.md").unlink()
        self.assertIn("memory_index_drift", self.kinds())
        self.index()
        self.assertEqual(len(self.memory_lines()), 2)
        self.assertEqual(self.call("check")[1], 0)

    def test_orphan_memory_is_listed_and_untrusted_text_cannot_break_links_or_leak_secrets(self) -> None:
        self.index()
        name = "2026-10-29-odd name (1).md"
        write(self.root, f"second-brain/memories/{name}",
              "# Evil](https://evil.example/x) [click\n\n> a < b & c | d " + "word " * 100 +
              f" key {AWS_LIKE}\n\nbodyonlycanary\n")
        self.assertIn("memory_index_drift", self.kinds())
        self.index()
        text = self.memory_md()
        self.assertNotIn(AWS_LIKE, text)
        self.assertNotIn("bodyonlycanary", text)
        (line,) = self.memory_lines()
        self.assertIn("(second-brain/memories/2026-10-29-odd%20name%20%281%29.md)", line)
        self.assertEqual(len(re.findall(r"(?<!\\)\]\(", line)), 1, line)
        self.assertNotIn("](https://evil", line.replace("\\](https://evil", ""))
        summary = line.split(" — ", 1)[1]
        self.assertIsNone(re.search(r"(?<!\\)[\[\]<>|&`]", summary), summary)
        self.assertLessEqual(len(summary), 200)
        self.assertEqual(self.call("check")[1], 0)

    def test_hand_written_memory_md_is_never_overwritten(self) -> None:
        mine = write(self.root, "memory.md", "my own notes\n")
        for result, code in (self.call("index"), self.remember("Blocked", "blocked", "blocked body")):
            self.assertEqual((result["status"], code), ("error", 2), result)
        self.assertEqual(mine.read_text(encoding="utf-8"), "my own notes\n")
        mem_dir = self.root / "second-brain" / "memories"
        self.assertEqual(list(mem_dir.glob("*.md")) if mem_dir.exists() else [], [])


class RouterTests(WorkspaceCase):
    def test_content_router_is_recognised_with_its_own_area(self) -> None:
        write(self.root, "CONTENT.md", "# Content Index\n\n| File | What |\n| --- | --- |\n"
                                       "| `content/ideas.md` | Content ideas and drafts |\n")
        write(self.root, "content/ideas.md", "# Ideas\n\nVideo ideas for the channel, long enough to matter.\n")
        self.index()
        cat = self.catalogue_text()
        self.assertIn("(../CONTENT.md) · router · content ·", cat)
        self.assertIn("(../content/ideas.md) · source · content ·", cat)
        self.assertIn("Content ideas and drafts", cat)


class RecoveryTests(WorkspaceCase):
    def test_crash_leftovers_are_reported_then_adopted_and_cleaned(self) -> None:
        self.index()
        mem_dir = self.root / "second-brain" / "memories"
        write(self.root, "second-brain/memories/2026-10-28-orphan.md",
              "# Orphan\n\n> written before the catalogue update crashed\n\nbody orphancanary\n")
        write(self.root, "second-brain/.brain-crashed.tmp", "partial")
        check, code = self.call("check")
        kinds = {p["kind"] for p in check["problems"]}
        self.assertEqual(code, 1)
        self.assertTrue({"orphan_memory", "stray_tmp"} <= kinds, kinds)
        saved, code = self.remember("Next write", "heals", "next body")
        self.assertEqual(code, 0, saved)
        self.assertEqual(saved["adopted_orphans"], 1)
        self.assertEqual(saved["recovered_tmp_files"], 1)
        check, code = self.call("check")
        self.assertEqual((check["status"], code), ("ok", 0), check)
        result, _ = self.call("query", "orphancanary orphan")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(list(mem_dir.glob("*.md"))), 2)

    def test_corrupt_catalogue_is_not_trusted_and_remember_heals_it(self) -> None:
        self.index()
        first, _ = self.remember("Keep me", "kept across corruption", "keepcanary body")
        (self.root / "second-brain" / "catalogue.md").write_text("garbage\x00 not a catalogue", encoding="utf-8")
        result, code = self.call("query", "--no-reindex", "avalanche debt")
        self.assertEqual((result["status"], code), ("not_indexed", 3))
        saved, code = self.remember("After corruption", "heals", "afterbody")
        self.assertEqual(code, 0, saved)
        cat = self.catalogue_text()
        self.assertIn(first["path"], cat)
        self.assertIn(saved["path"], cat)
        self.assertIn("../TASKS.md", cat)


class CliBoundaryTests(WorkspaceCase):
    def test_cwd_independent_and_default_root_is_script_parent(self) -> None:
        other = self.base / "elsewhere"
        other.mkdir()
        script_dir = self.root / "second-brain"
        script_dir.mkdir(exist_ok=True)
        local_script = script_dir / "brain.py"
        shutil.copy(BRAIN_PATH, local_script)
        for cmd in (["index"], ["query", "avalanche debt method"]):
            proc = subprocess.run([sys.executable, str(local_script), *cmd], cwd=other, text=True,
                                  capture_output=True, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["evidence"][0]["path"], "TASKS.md")
        proc = subprocess.run([sys.executable, str(BRAIN_PATH), "--root", str(self.root), "query", "debt avalanche"],
                              cwd=other, text=True, capture_output=True, timeout=60)
        self.assertEqual(json.loads(proc.stdout)["status"], "ok")

    def test_default_root_is_nearest_cwd_ancestor_holding_second_brain(self) -> None:
        script_dir = self.root / "second-brain"
        script_dir.mkdir(exist_ok=True)
        shutil.copy(BRAIN_PATH, script_dir / "brain.py")
        sub = self.root / "nested" / "deeper"
        sub.mkdir(parents=True)
        # Run the *repo's* script (whose own parent is a different folder) from inside the fixture.
        proc = subprocess.run([sys.executable, str(BRAIN_PATH), "index"], cwd=sub, text=True,
                              capture_output=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((script_dir / "catalogue.md").is_file())
        self.assertFalse((sub / "second-brain").exists())

    def test_bad_arguments_and_root_emit_json_exit_2(self) -> None:
        for argv in (["--root", str(self.root)], ["--root", str(self.root / "nope"), "check"],
                     ["--root", str(self.root), "remember", "--title", "x"]):
            proc = subprocess.run([sys.executable, str(BRAIN_PATH), *argv], text=True, capture_output=True, timeout=60)
            self.assertEqual(proc.returncode, 2, (argv, proc.stdout, proc.stderr))
            self.assertEqual(json.loads(proc.stdout)["status"], "error")


class BenchmarkTests(WorkspaceCase):
    def test_benchmark_labels_proxy_and_compares_with_scan(self) -> None:
        filler = "\n".join(f"filler row {i} unrelated text" for i in range(300))
        write(self.root, "docs/giant.md", f"# Reference\n\n## Details\n\n{filler}\nneedlexyz is forty two\n{filler}\n")
        self.index()
        qfile = self.base / "q.json"
        qfile.write_text(json.dumps({"questions": [
            {"id": "deep", "question": "giant needlexyz value", "expect_any": ["needlexyz is forty two"],
             "technical": True},
            {"id": "miss", "question": "quantum chromodynamics lattice", "expect_any": ["never present"]},
        ]}), encoding="utf-8")
        result, code = self.call("benchmark", "--questions", str(qfile), "--repeat", "1")
        self.assertEqual((result["status"], code), ("ok", 0), result)
        self.assertIn("NOT a Claude", result["disclaimer"])
        deep = next(r for r in result["results"] if r["id"] == "deep")
        self.assertTrue(deep["brain"]["answer_found"])
        self.assertTrue(deep["baseline"]["answer_found"])
        self.assertLess(deep["brain"]["model_context_bytes"], deep["baseline"]["model_context_bytes"])
        self.assertGreater(deep["baseline"]["files_opened"], deep["brain"]["files_opened"])
        miss = next(r for r in result["results"] if r["id"] == "miss")
        self.assertEqual(miss["brain"]["status"], "no_match")
        self.assertFalse(miss["brain"]["answer_found"])
        self.assertEqual(result["totals_technical_only"]["questions"], 1)

    def test_shipped_question_file_is_well_formed(self) -> None:
        spec = json.loads((HERE.parent / "benchmark-questions.json").read_text(encoding="utf-8"))
        ids = [q["id"] for q in spec["questions"]]
        self.assertEqual(len(ids), len(set(ids)))
        for q in spec["questions"]:
            self.assertTrue(q["question"] and q["expect_any"], q["id"])


class SelfHealTests(WorkspaceCase):
    def test_query_reindexes_a_missing_index_and_a_changed_source(self) -> None:
        result, code = self.call("query", "debt method avalanche")
        self.assertEqual((result["status"], code, result.get("reindexed")), ("ok", 0, True), result)
        with (self.root / "TASKS.md").open("a", encoding="utf-8") as fh:
            fh.write("\n### Debt plan review\n\n- [ ] avalanche reviewed quarterly\n")
        result, code = self.call("query", "debt avalanche reviewed quarterly")
        self.assertEqual((result["status"], code, result.get("reindexed")), ("ok", 0, True), result)
        self.assertIn("reviewed quarterly", result["evidence"][0]["text"])
        self.assertNotIn("_drift", result)
        again, _ = self.call("query", "debt avalanche reviewed quarterly")
        self.assertNotIn("reindexed", again)  # index is true again: no second rebuild
        self.assertEqual(self.call("check")[0]["status"], "ok")

    def test_busy_lock_reports_the_drift_instead_of_hiding_it(self) -> None:
        self.index()
        with (self.root / "TASKS.md").open("a", encoding="utf-8") as fh:
            fh.write("\n- [ ] avalanche edited later\n")
        os.environ["BRAIN_LOCK_TIMEOUT"] = "0.05"
        try:
            with brain.WriterLock(self.root / "second-brain", timeout=1):
                result, code = self.call("query", "debt method avalanche")
        finally:
            del os.environ["BRAIN_LOCK_TIMEOUT"]
        self.assertEqual((result["status"], code, result["reindex_error"], result["evidence"]),
                         ("stale", 3, "locked", []))


class SupersedeAndRecencyTests(WorkspaceCase):
    def test_superseded_memory_scores_half_and_is_marked(self) -> None:
        self.index()
        old, _ = self.remember("Nebulizer pressure", "Runs at 40 psi", "The nebulizer pressure is 40 psi.")
        new, code = self.call("remember", "--title=Nebulizer pressure update", "--summary=Runs at 55 psi",
                              "--body=The nebulizer pressure is 55 psi.", f"--supersedes={old['id']}")
        self.assertEqual((code, new["supersedes"]), (0, [old["id"]]), new)
        result, _ = self.call("query", "nebulizer pressure psi")
        self.assertEqual(result["source"]["path"], new["path"], result)
        self.assertNotIn("superseded_by", result["source"])
        scores = {c["path"]: c["score"] for c in result["candidates"]}
        self.assertLess(scores[old["path"]], scores[new["path"]] * 0.75)
        index_text = (self.root / "memory.md").read_text(encoding="utf-8")
        marked = [l for l in index_text.splitlines() if "superseded by" in l]
        self.assertEqual(len(marked), 1, index_text)
        self.assertIn(old["id"], marked[0])
        self.assertIn(f"superseded by {new['id']}", marked[0])
        self.index()  # a full rebuild keeps the relation
        self.assertEqual((self.root / "memory.md").read_text(encoding="utf-8"), index_text)
        self.assertEqual(self.call("check")[0]["status"], "ok")

    def test_supersedes_rejects_unknown_or_unsafe_ids_without_writing(self) -> None:
        self.index()
        for bad in ("2026-01-01-does-not-exist", "../../etc/passwd", "x"):
            result, code = self.call("remember", "--title=T", "--summary=S", "--body=B", f"--supersedes={bad}")
            self.assertEqual((result["status"], code), ("error", 2), result)
        mdir = self.root / "second-brain" / "memories"
        self.assertFalse(mdir.is_dir() and any(mdir.iterdir()))

    def test_newer_of_two_equal_memories_wins(self) -> None:
        body = "# Router firmware\n\n> Router firmware version\n\n_Saved: x_\n\nRouter firmware is version {v}.\n"
        write(self.root, "second-brain/memories/2020-01-01-router-firmware.md", body.format(v="seven"))
        today = brain._today().isoformat()
        write(self.root, f"second-brain/memories/{today}-router-firmware.md", body.format(v="eight"))
        self.index()
        result, _ = self.call("query", "router firmware version")
        self.assertEqual(result["source"]["path"], f"second-brain/memories/{today}-router-firmware.md", result)


class DurationIntentTests(WorkspaceCase):
    def test_how_long_prefers_the_section_that_states_a_duration(self) -> None:
        write(self.root, "board.md", "# Board\n\n## Weekly kiln block\n\n"
                                     "The weekly kiln block is for glaze builds. The kiln block is weekly.\n")
        write(self.root, "cadence.md", "# Cadence\n\n## Blocks\n\nFiller about the studio.\n\n"
                                       "## Kiln\n\nWeekly kiln block: 45\u201360 min on Thursdays.\n")
        self.index()
        plain, _ = self.call("query", "weekly kiln block")
        self.assertEqual(plain["source"]["path"], "board.md", plain)
        self.assertNotIn("intent", plain)
        result, _ = self.call("query", "How long is the weekly kiln block?")
        self.assertEqual((result["intent"], result["source"]["path"]), ("duration", "cadence.md"), result)
        self.assertNotIn("long", result["keywords"])
        self.assertIn("45\u201360 min", result["evidence"][0]["text"])

    def test_duration_intent_never_matches_on_the_marker_alone(self) -> None:
        write(self.root, "cadence.md", "# Cadence\n\n## Kiln\n\nWeekly kiln block: 45 min.\n")
        self.index()
        result, _ = self.call("query", "How long is the quasar flyby?")
        self.assertEqual((result["status"], result["evidence"]), ("no_match", []), result)


if __name__ == "__main__":
    unittest.main()
