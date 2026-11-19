"""Budget boundaries that must survive Unicode input, concurrent runs and crashes."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import connectors
import kb_store
import kb_summaries
from kb_runtime import ingest_lock


class SummaryBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.env = patch.dict(os.environ, {"KB_HOME": str(self.root / "runtime")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.conn = kb_store.connect(self.root / "kb.sqlite")
        self.addCleanup(self.conn.close)
        self.text = "部署🙂 exact failure ENOENT /synthetic/path. " * 200
        connectors.store_item(self.conn, "claude", "item", "2026-11-04", "Synthetic", self.text, {"path": "/synthetic/source"})
        self.config = dict(approval_id="synthetic-approval", remote_transfer_acknowledged=True,
                           sources=["claude"], model="fixture-model", input_per_mtok=1,
                           output_per_mtok=5, price_date="2026-11-05", context_window=1000000,
                           max_output_tokens=1000, max_attempts=1, max_usd=1)

    def test_unicode_budget_reserves_more_than_utf8_payload(self):
        cfg = kb_summaries.validate_config(self.config)
        chunks = connectors.chunk_text(self.text)
        payload = kb_summaries.build_payload("Synthetic", chunks, "synthetic-hash")
        upper = kb_summaries.upper_input_tokens(cfg, len(self.text), len(chunks))
        self.assertGreaterEqual(upper, len(payload.encode("utf-8")) + len(kb_summaries.SYSTEM_PROMPT.encode("utf-8")))

    def test_interrupted_request_keeps_reservation_and_blocks_overspend(self):
        cfg = kb_summaries.validate_config(self.config)
        chunks = connectors.chunk_text(self.text)
        reserve = kb_summaries.worst_case_cost(cfg, kb_summaries.upper_input_tokens(cfg, len(self.text), len(chunks)))
        self.config["max_usd"] = reserve * 1.1
        kb_summaries.estimate(self.conn, self.config)
        class Interrupted:
            def __init__(self):
                self.messages = self
                self.calls = 0
            def create(self, **kwargs):
                self.calls += 1
                raise KeyboardInterrupt("synthetic interrupted process")
        client = Interrupted()
        with self.assertRaises(KeyboardInterrupt):
            kb_summaries.summarize(self.conn, self.config, client)
        ledger = kb_store.get_state(self.conn, "summaries", "spend")["synthetic-approval"]
        self.assertAlmostEqual(ledger["usd"], reserve)
        self.assertEqual(client.calls, 1)
        result = kb_summaries.summarize(self.conn, self.config, client)
        self.assertEqual(result["stopped"], "budget")
        self.assertEqual(client.calls, 1)
        self.assertEqual(len(kb_summaries.pending_items(self.conn)), 1)
        self.assertEqual("".join(r[0] for r in self.conn.execute("select content from docs where kind='raw' order by id")), self.text)

    def test_concurrent_summary_refuses_second_spender(self):
        with ingest_lock(self.root / "runtime"):
            with self.assertRaises(RuntimeError):
                kb_summaries.summarize(self.conn, self.config, object())

    def test_approval_requires_explicit_sources(self):
        del self.config["sources"]
        with self.assertRaises(kb_summaries.ApprovalError):
            kb_summaries.validate_approval(self.config)
