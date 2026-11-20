import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import connectors
import kb_privacy
import kb_store
from fixtures import session


class PrivacyRegressions(unittest.TestCase):
    def test_numeric_credentials_are_not_token_counters(self):
        masked = kb_privacy.redact('max_api_key=123456 password=yourpassword max_tokens: 4096.')
        self.assertNotIn('123456', masked)
        self.assertNotIn('yourpassword', masked)
        self.assertIn('max_tokens: 4096.', masked)

    def test_extractor_version_reprocesses_unchanged_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with patch.dict(os.environ, {'KB_HOME': str(root / 'runtime')}):
                session(root / 'sessions')
                conn = kb_store.connect(root / 'kb.sqlite')
                try:
                    connectors.ingest_claude(conn, root / 'sessions')
                    self.assertEqual(connectors.ingest_claude(conn, root / 'sessions')['parsed'], 0)
                    with patch.object(connectors, 'STORE_VERSION', 'next-extractor'):
                        outcome = connectors.ingest_claude(conn, root / 'sessions')
                    self.assertEqual(outcome['parsed'], 1)
                    self.assertEqual(outcome['updated'], 1)
                    self.assertEqual(conn.execute('select count(distinct source_id) from docs').fetchone()[0], 1)
                finally:
                    conn.close()
