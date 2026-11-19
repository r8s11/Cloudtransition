"""Behavior tests for refresh-index.py: curated scope, privacy, refresh safety."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent.parent / "refresh-index.py"
spec = importlib.util.spec_from_file_location("refresh_index", SCRIPT)
ri = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ri)


def touch(root: Path, rel: str, text: str = "content\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class Workspace(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "ws"
        self.root.mkdir()
        self.outside = Path(self._tmp.name) / "outside"
        self.outside.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def build(self) -> dict:
        return ri.build(self.root)

    def paths(self, index: dict) -> set[str]:
        return {f["relativePath"] for f in index["files"]}


class CuratedScope(Workspace):
    def test_only_approved_roots_and_root_documents_are_indexed(self):
        touch(self.root, "resume/master.md", "# Master resume\n")
        touch(self.root, "artifacts/brand-book.html", "<title>Brand</title>")
        touch(self.root, "TASKS.md", "# Tasks\n")
        touch(self.root, "unlisted-folder/notes.md")
        touch(self.root, "bun.lock")
        index = self.build()
        self.assertEqual(
            self.paths(index), {"resume/master.md", "artifacts/brand-book.html", "TASKS.md"}
        )

    def test_dependency_and_generated_outputs_are_skipped(self):
        touch(self.root, "dashboard-app/app.py")
        touch(self.root, "dashboard-app/venv/lib/x.py")
        touch(self.root, "dashboard-app/node_modules/a/index.js")
        touch(self.root, "dashboard-app/runs/abc.txt")
        touch(self.root, "artifacts/index.html")
        touch(self.root, "visual-second-brain/workspace-index.json", "{}")
        self.assertEqual(self.paths(self.build()), {"dashboard-app/app.py"})


class Privacy(Workspace):
    def test_private_records_leave_no_trace_in_serialized_index(self):
        touch(self.root, "resume/master.md")
        secrets = [
            "resume/.env",
            "resume/client_secret.json",
            "resume/api-token.txt",
            "resume/deploy.pem",
            "resume/prod.env",
            "resume/AuthKey_ABC.p8",
            "projects/infra/terraform.tfstate",
            "projects/infra/terraform.tfstate.backup",
            "projects/infra/prod.tfvars",
            "projects/infra/kubeconfig",
            "projects/infra/office.ovpn",
            "resume/deploy_key.txt",
            "interviews/~$b Application.docx",
            "interviews/ross-work-log.md",
            "IT Mgmt/Employer-IT-Playbook-Private/runbook.md",
            "College Planning/transcript.pdf",
            "docs/backup/College Planning/grades.pdf",
        ]
        for rel in secrets:
            touch(self.root, rel, "hunter2")
        text = json.dumps(self.build())
        for rel in secrets:
            self.assertNotIn(Path(rel).name, text)
        self.assertNotIn("Employer-IT-Playbook-Private", text)
        self.assertNotIn("hunter2", text)

    def test_excluded_files_are_counted_not_named(self):
        touch(self.root, "resume/master.md")
        touch(self.root, "resume/password-list.txt")
        index = self.build()
        self.assertGreaterEqual(sum(index["excluded"].values()), 1)
        self.assertIn("secret_name", index["excluded"])

    def test_ordinary_key_and_token_words_stay_indexed(self):
        for rel in ["IT Mgmt/00-meta/TOKENS.md", "resume/key-takeaways.md", "docs/keyboard.md"]:
            touch(self.root, rel)
        self.assertEqual(
            self.paths(self.build()),
            {"IT Mgmt/00-meta/TOKENS.md", "resume/key-takeaways.md", "docs/keyboard.md"},
        )

    def test_symlinks_are_never_followed(self):
        touch(self.root, "resume/master.md")
        touch(self.outside, "stolen.md", "outside secret")
        (self.root / "resume/link.md").symlink_to(self.outside / "stolen.md")
        (self.root / "resume/linkdir").symlink_to(self.outside, target_is_directory=True)
        text = json.dumps(self.build())
        self.assertNotIn("link.md", text)
        self.assertNotIn("stolen.md", text)
        self.assertNotIn("outside secret", text)


class UnreadableFolders(Workspace):
    def test_unreadable_folder_is_reported_not_silently_skipped(self):
        touch(self.root, "resume/master.md")
        locked = self.root / "resume/locked"
        touch(self.root, "resume/locked/a.md")
        locked.chmod(0)
        try:
            index = self.build()
        finally:
            locked.chmod(0o755)
        self.assertEqual(index["readErrors"], 1)


class Content(Workspace):
    def test_unicode_and_duplicate_names_keep_distinct_exact_paths(self):
        expected = [
            touch(self.root, "resume/café notes #1.md"),
            touch(self.root, "resume/a/README.md"),
            touch(self.root, "resume/b/README.md"),
        ]
        index = self.build()
        for path in expected:
            # Filesystems may return canonically decomposed Unicode names.
            # Both indexed paths must identify the original file, not another
            # file with the same basename in a different folder.
            matches = [f for f in index["files"] if Path(f["path"]).samefile(path)]
            self.assertEqual(len(matches), 1)
            relative = Path(matches[0]["relativePath"])
            self.assertFalse(relative.is_absolute())
            self.assertTrue((self.root / relative).samefile(path))

    def test_image_preview_comes_from_caption_sidecar(self):
        (self.root / "resources").mkdir()
        (self.root / "resources/diagram.png").write_bytes(b"\x89PNG\r\n")
        touch(self.root, "resources/diagram.png.md", "# Azure network diagram\n")
        (self.root / "resources/photo.jpg").write_bytes(b"\xff\xd8")
        files = {f["relativePath"]: f for f in self.build()["files"]}
        self.assertEqual(files["resources/diagram.png"]["previewKind"], "caption")
        self.assertIn("Azure network diagram", files["resources/diagram.png"]["preview"])
        self.assertEqual(files["resources/photo.jpg"]["previewKind"], "none")
        self.assertEqual(files["resources/photo.jpg"]["preview"], "")

    def test_topics_match_words_not_substrings(self):
        touch(self.root, "resources/guides/build-guide.md", "# Steps\n")
        touch(self.root, "resume/devops-cloud/resume.md", "# Resume\n")
        files = {f["relativePath"]: f for f in self.build()["files"]}
        self.assertNotIn("frontend", files["resources/guides/build-guide.md"]["topics"])
        self.assertEqual(files["resume/devops-cloud/resume.md"]["topics"][0], "career")

    def test_file_removed_during_scan_is_counted_as_read_error(self):
        touch(self.root, "resume/master.md")
        real_walk = ri.walk

        def walk_with_ghost(root, excluded):
            return real_walk(root, excluded) + [root / "resume/ghost.md"]

        with mock.patch.object(ri, "walk", walk_with_ghost):
            index = self.build()
        self.assertEqual(index["readErrors"], 1)
        self.assertNotIn("resume/ghost.md", self.paths(index))

    def test_index_contract_fields(self):
        touch(self.root, "resume/master.md")
        index = self.build()
        self.assertEqual(index["schemaVersion"], ri.SCHEMA_VERSION)
        self.assertRegex(index["generated"], r"[+-]\d\d:\d\d$")
        self.assertRegex(index["files"][0]["modified"], r"[+-]\d\d:\d\d$")
        self.assertIn("resume", index["coverage"]["roots"])
        for key in ("workspace", "files", "projects", "fileCount", "projectCount"):
            self.assertIn(key, index)


class RefreshSafety(Workspace):
    def test_failed_replace_keeps_previous_index(self):
        out = Path(self._tmp.name) / "index.json"
        out.write_text('{"old": true}')
        with mock.patch.object(ri.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                ri.write_index({"new": True}, out)
        self.assertEqual(json.loads(out.read_text()), {"old": True})
        self.assertEqual(list(out.parent.glob("*.tmp")), [])

    def test_unavailable_workspace_exits_nonzero_without_writing(self):
        out = Path(self._tmp.name) / "index.json"
        out.write_text('{"old": true}')
        env = dict(os.environ, VSB_WORKSPACE=str(self.root / "missing"), VSB_OUTPUT=str(out))
        result = subprocess.run([sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(out.read_text()), {"old": True})

    def test_empty_scope_refuses_to_publish(self):
        out = Path(self._tmp.name) / "index.json"
        out.write_text('{"old": true}')
        env = dict(os.environ, VSB_WORKSPACE=str(self.root), VSB_OUTPUT=str(out))
        result = subprocess.run([sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(out.read_text()), {"old": True})


if __name__ == "__main__":
    unittest.main()
