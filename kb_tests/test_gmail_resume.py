import json
from datetime import timedelta
from unittest.mock import patch

import connectors
import kb_store
from test_connectors import Base, FakeGmail, FakeHttpError, NOW
import test_connectors as fixtures


class GmailResumeTests(Base):
    def test_interrupted_ingest_resumes_without_relisting_completed_pages(self):
        service = FakeGmail(fixtures.GmailIncremental.threads(None), page_size=2)
        service.get_errors['t2'] = FakeHttpError(403, 'rateLimitExceeded')
        with self.assertRaises(connectors.GmailQuotaError):
            connectors.ingest_gmail(self.conn, service, now=NOW, sleep=lambda _: None)
        checkpoint = self.state('gmail', 'pending_run')
        self.assertIsNotNone(checkpoint, 'Failed backfill must retain its page and item position')
        self.assertIsNone(self.state('gmail', 'watermark'))
        kept = self.raw_text('gmail', 't1')
        service.get_errors.clear()
        service.calls.clear()
        connectors.ingest_gmail(self.conn, service, now=NOW + timedelta(hours=1), sleep=lambda _: None)
        self.assertNotIn('t1', [args['id'] for method, args in service.calls if method == 'get'])
        self.assertFalse(any(method == 'list' and not args.get('pageToken') for method, args in service.calls))
        self.assertEqual(self.raw_text('gmail', 't1'), kept)
        self.assertIsNone(self.state('gmail', 'pending_run'))
        self.assertEqual(self.state('gmail', 'watermark'), NOW.strftime('%Y-%m-%dT%H:%M:%SZ'), 'Catch up changes since the original run start after backfill')
        self.assertEqual(set(r['source_id'] for r in self.rows('gmail')), {'t1', 't2', 't3'})

    def test_quota_diagnostic_preserves_only_safe_reason_and_limit(self):
        service = FakeGmail({})
        error = FakeHttpError(403, 'rateLimitExceeded', 'password=DO_NOT_LOG_THIS')
        error.content = json.dumps({'error': {'message': "Quota exceeded for quota metric 'Total Query Cost' and limit 'Units per minute per user'", 'errors': [{'reason': 'rateLimitExceeded'}]}}).encode()
        service.list_error = error
        waits = []
        with self.assertRaises(connectors.GmailQuotaError):
            connectors.ingest_gmail(self.conn, service, now=NOW, sleep=waits.append)
        state = self.state('gmail', 'last_error')
        self.assertIn('rateLimitExceeded', json.dumps(state))
        self.assertIn('Units per minute per user', json.dumps(state))
        self.assertNotIn('DO_NOT_LOG_THIS', json.dumps(state))
        self.assertTrue(any(delay >= 60 for delay in waits), 'Minute quota needs a recovery window, not only 1-2 seconds')


class GmailPacingTests(Base):
    def test_request_units_are_spread_below_user_minute_limit(self):
        clock = [0.0]
        calls = []
        def sleep(seconds):
            clock[0] += seconds
        with patch.object(connectors.time, 'monotonic', lambda: clock[0]), patch.object(connectors, 'GMAIL_UNITS_PER_SECOND', 80.0):
            limiter = connectors._GmailPacer(sleep)
            for _ in range(51):
                limiter.call(120, lambda: calls.append(clock[0]))
        self.assertGreaterEqual(calls[-1] - calls[0], 60)
        self.assertTrue(all(sum(120 for t in calls if start <= t < start + 60) <= 6000 for start in calls))
