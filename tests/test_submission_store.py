import tempfile
import unittest
from pathlib import Path
from src.submission_store import SubmissionStore


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'ledger.sqlite3'
        self.payload = {'fullTagName': 'tag', 'datetime': '2026-04-23 13:00:00', 'value': 3.5}

    def claim(self, store, payload=None, destination='endpoint/account'):
        return store.claim(destination, 'sensor', 123, payload or self.payload)

    def test_success_survives_reopening_and_payload_change_is_new(self):
        store = SubmissionStore(self.path)
        key, status = self.claim(store)
        self.assertEqual(status, 'claimed')
        store.finish(key, 'http_success', 200)
        store.close()
        store = SubmissionStore(self.path)
        try:
            self.assertEqual(self.claim(store), (key, 'http_success'))
            self.assertEqual(self.claim(store, {**self.payload, 'value': 4})[1], 'claimed')
            self.assertEqual(self.claim(store, destination='other-account')[1], 'claimed')
        finally:
            store.close()

    def test_crash_and_two_connections_do_not_resend(self):
        first = SubmissionStore(self.path)
        second = SubmissionStore(self.path)
        try:
            key, _ = self.claim(first)
            self.assertEqual(self.claim(second), (key, 'in_flight'))
        finally:
            first.close()
            second.close()
        reopened = SubmissionStore(self.path)
        try:
            self.assertEqual(self.claim(reopened), (key, 'in_flight'))
            reopened.resolve(key, 'retry')
            self.assertEqual(self.claim(reopened), (key, 'claimed'))
            self.assertEqual(reopened.connection.execute('SELECT attempts FROM submissions').fetchone()[0], 2)
            reopened.finish(key, 'uncertain')
            reopened.resolve(key, 'delivered')
            self.assertEqual(self.claim(reopened), (key, 'confirmed_delivered'))
        finally:
            reopened.close()

    def test_http_failure_requires_explicit_retry(self):
        store = SubmissionStore(self.path)
        try:
            key, _ = self.claim(store)
            store.finish(key, 'http_failed', 503)
            self.assertEqual(self.claim(store), (key, 'http_failed'))
            store.resolve(key, 'retry')
            self.assertEqual(self.claim(store), (key, 'claimed'))
        finally:
            store.close()
