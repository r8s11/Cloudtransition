"""Approval, untrusted output and raw-preservation boundaries for explicit Codex runs."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import connectors
import kb_store
try:
    import kb_codex
except ImportError:
    kb_codex = None


class CodexFallbackTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(kb_codex, "Explicit Codex fallback is not implemented")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.env = patch.dict(os.environ, {"KB_HOME": str(self.root / "private")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.conn = kb_store.connect(self.root / "kb.sqlite")
        self.addCleanup(self.conn.close)
        self.text = "The exact error is ENOENT. Use /synthetic/path to investigate. " * 160
        for source, ident in [("claude", "one"), ("claude", "two"), ("gmail", "mail")]:
            connectors.store_item(self.conn, source, ident, "2026-11-04", "Synthetic", self.text, {})
        self.catalogue = self.root / "models.json"
        self.catalogue.write_text(json.dumps({"models": [{"slug": "gpt-6-luna", "visibility": "list", "supported_in_api": True, "context_window": 272000, "effective_context_window_percent": 95}]}))
        self.cat = patch.object(kb_codex, "CODEX_CACHE", self.catalogue)
        self.cat.start()
        self.addCleanup(self.cat.stop)
        self.marker = self.root / "calls"
        self.output = {"segments": [{"title": "Failure", "question": "Which error?", "summary": "The error is ENOENT. The source names a diagnostic path.", "chunks": [0]}], "atoms": [{"kind": "error", "text": "ENOENT", "note": ""}]}
        self.exe = self.root / "codex"
        self.fixture()
        self.which = patch.object(kb_codex.shutil, "which", return_value=str(self.exe))
        self.which.start()
        self.addCleanup(self.which.stop)

    def fixture(self, mode="ok"):
        script = f'''#!{sys.executable}
import json, os, pathlib, sys, time
args=sys.argv[1:]
prompt=sys.stdin.read()
marker=pathlib.Path({str(self.marker)!r})
marker.write_text(marker.read_text()+"x" if marker.exists() else "x")
assert "ENOENT" in prompt and all("ENOENT" not in a for a in args)
assert os.stat(os.getcwd()).st_mode & 0o077 == 0
mode={mode!r}
if mode=="error":
    print("password=do-not-log-this-value",file=sys.stderr);sys.exit(7)
if mode=="timeout": time.sleep(2)
if mode=="drift":
    import sqlite3
    c=sqlite3.connect({str(self.root / 'kb.sqlite')!r})
    c.execute("update docs set content=content||' changed' where source_id='one' and kind='raw'");c.commit()
out={self.output!r}
if mode=="invalid": out["atoms"][0]["text"]="INVENTED"
if mode=="secret": out["segments"][0]["summary"]="password=secret-output-value. Do not save it."
pathlib.Path(args[args.index("-o")+1]).write_text("not json" if mode=="malformed" else json.dumps(out))
if mode=="tool": print(json.dumps({{"type":"item.completed","item":{{"type":"command_execution","command":"private canary"}}}}))
print(json.dumps({{"type":"turn.completed","usage":{{"input_tokens":42,"output_tokens":17}}}}))
'''
        self.exe.write_text(script)
        self.exe.chmod(0o700)

    def manifest(self):
        return kb_codex.preview(self.conn, [("claude", "one")])

    def run_manifest(self, manifest, **kwargs):
        return kb_codex.run(self.conn, manifest, manifest["fingerprint"], transfer_ack=True, usage_ack=True, **kwargs)

    def raw(self, ident="one"):
        return [r for r in connectors.read_item_rows(self.conn, "claude", ident) if r["kind"] == "raw"]

    def test_preview_scope_selected_private_pending_only(self):
        manifest = self.manifest()
        self.assertEqual([r["source_id"] for r in manifest["items"]], ["one"])
        self.assertEqual(manifest["calls"], 1)
        self.assertEqual(manifest["model"], "gpt-6-luna")
        self.assertGreaterEqual(manifest["items"][0]["input_tokens_upper"], len(self.text.encode()))
        path = self.root / "private" / "preview.json"
        kb_codex.save_preview(path, manifest)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        for identities in [[("gmail", "mail")], [("claude", "absent")], []]:
            with self.subTest(identities=identities), self.assertRaises(ValueError):
                kb_codex.preview(self.conn, identities)
        connectors.rewrite_item(self.conn, "claude", "two", lambda r: r["metadata"].update(summary_status="done"))
        with self.assertRaises(ValueError):
            kb_codex.preview(self.conn, [("claude", "two")])
        self.assertFalse(self.marker.exists())

    def test_preview_scope_hidden_missing_or_oversized_model(self):
        for model in [None, {"slug":"gpt-6-luna","visibility":"hide","context_window":272000}, {"slug":"gpt-6-luna","visibility":"list","supported_in_api":True,"context_window":100}]:
            self.catalogue.write_text(json.dumps({"models": [model] if model else []}))
            with self.subTest(model=model), self.assertRaises(ValueError):
                self.manifest()
        self.assertFalse(self.marker.exists())

    def test_stale_preview_rejects_manifest_and_source_drift_before_egress(self):
        original = self.manifest()
        for field, value in [("model","other"),("calls",99),("items",[]),("context_window",999999)]:
            altered = copy.deepcopy(original)
            altered[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.run_manifest(altered)
        self.conn.execute("update docs set content=content||' changed' where source_id='one'")
        self.conn.commit()
        with self.assertRaises(ValueError):
            self.run_manifest(original)
        self.assertFalse(self.marker.exists())

    def test_consent_gate_no_transfer_usage_or_matching_fingerprint(self):
        manifest = self.manifest()
        for transfer, usage, fingerprint, scheduled in [(False,True,manifest['fingerprint'],False),(True,False,manifest['fingerprint'],False),(True,True,'wrong',False),(True,True,manifest['fingerprint'],True)]:
            with self.subTest(transfer=transfer,usage=usage,scheduled=scheduled), self.assertRaises(ValueError):
                kb_codex.run(self.conn,manifest,fingerprint,transfer_ack=transfer,usage_ack=usage,scheduled=scheduled)
        self.assertFalse(self.marker.exists())

    def test_approved_run_preserves_raw_usage_and_skips_successful_replay(self):
        manifest = self.manifest()
        before = [(r['title'],r['content']) for r in self.raw()]
        result = self.run_manifest(manifest)
        self.assertEqual(result['summarized'], 1)
        self.assertEqual([(r['title'],r['content']) for r in self.raw()], before)
        rows = connectors.read_item_rows(self.conn,'claude','one')
        self.assertEqual({r['kind'] for r in rows}, {'raw','segment','atom'})
        usage = self.raw()[0]['metadata']['summary']
        self.assertEqual((usage['provider'],usage['model'],usage['input_tokens'],usage['output_tokens']), ('codex','gpt-6-luna',42,17))
        self.assertIsNone(usage['cost_usd'])
        self.assertIsNone(kb_store.get_state(self.conn,'summaries','spend'))
        self.assertEqual(self.run_manifest(manifest)['cached'],1)
        self.assertEqual(self.marker.read_text(),'x')
        self.assertEqual(list((self.root/'private'/'codex-work').iterdir()),[])

    def test_failure_preserves_raw_and_pending_without_secret_or_retry(self):
        for mode in ['error','timeout','malformed','invalid','secret','tool','drift']:
            with self.subTest(mode=mode):
                connectors.store_item(self.conn,'claude','one','2026-11-04','Synthetic',self.text,{})
                self.fixture(mode)
                before = self.raw()
                result = self.run_manifest(self.manifest(), timeout=0.2)
                self.assertEqual(result['failed'],1)
                self.assertEqual({r['kind'] for r in connectors.read_item_rows(self.conn,'claude','one')},{'raw'})
                self.assertTrue(all(r['metadata']['summary_status'] != 'done' for r in self.raw()))
                if mode != 'drift':
                    self.assertEqual(self.raw(),before)
                self.assertNotIn('secret-output-value',json.dumps(result))
                self.assertNotIn('do-not-log-this-value',json.dumps(result))
        self.assertEqual(self.marker.read_text(),'x'*7)

    def test_consent_gate_ingestion_lock_prevents_concurrent_egress(self):
        from kb_runtime import ingest_lock
        manifest=self.manifest()
        with ingest_lock(self.root/'private'):
            with self.assertRaises(RuntimeError):
                self.run_manifest(manifest)
        self.assertFalse(self.marker.exists())
