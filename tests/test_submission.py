import os
import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch

import requests
import main
from src.api_client import APIClient
from src.transformer import build_import_payload


class SubmissionTests(unittest.TestCase):
    def test_interactive_submit_and_invalid_choices(self):
        with patch('builtins.input', side_effect=['bad', '2', '0', 'A2_Qin']), patch('builtins.print'):
            args = main.select_options([])
        self.assertFalse(args.dry_run)
        self.assertEqual(args.sensor, 'A2_Qin')

    def test_quit_and_eof_do_not_connect(self):
        for answer in ['q', EOFError()]:
            with patch('builtins.input', side_effect=[answer]), patch('builtins.print'), patch.object(main, 'get_connection') as connect:
                self.assertIn(main.main([]), (0, 130))
                connect.assert_not_called()

    def test_payload_and_authentication(self):
        payload = build_import_payload({'fullTagName': 'tag'}, {
            'timestamp': datetime(2026, 4, 23, 13), 'value': Decimal('3.5')})
        with patch.dict(os.environ, {'API_URL': 'https://example.com/import',
                                     'API_USER': 'user', 'API_TOKEN': 'secret'}), \
                patch('src.api_client.requests.Session') as session:
            response = session.return_value.post.return_value.__enter__.return_value
            response.status_code = 204
            client = APIClient()
            self.assertEqual(client.submit_reading(payload), 204)
            session.return_value.post.assert_called_once_with(
                'https://example.com/import', json={
                    'user': 'user', 'token': 'secret', 'fullTagName': 'tag',
                    'datetime': '2026-04-23 13:00:00', 'value': 3.5},
                timeout=30, allow_redirects=False)
            client.close()
            session.return_value.close.assert_called_once()

    def run_pipeline(self, values, *, dry_run=False, outcome=200):
        rows = ({'data_id': i, 'timestamp': datetime(2026, 4, 23, 13), 'value': v}
                for i, v in enumerate(values))
        with patch.object(main, 'get_connection', return_value=Mock()), \
                patch.object(main, 'close_connection') as close, \
                patch.object(main, 'extract_parameter', return_value=rows), \
                patch.object(main, 'APIClient') as factory, \
                patch.object(main, 'get_logger', return_value=Mock()):
            client = factory.return_value
            if isinstance(outcome, Exception):
                client.submit_reading.side_effect = outcome
            else:
                client.submit_reading.return_value = outcome
            result = main.main(['--dry-run' if dry_run else '--submit', '--sensor', 'A2_Qin'])
            close.assert_called_once()
            if dry_run:
                factory.assert_not_called()
            else:
                client.close.assert_called_once()
            return result, client.submit_reading.call_count

    def test_success_and_zero(self):
        self.assertEqual(self.run_pipeline([0, Decimal('3.5')]), (0, 2))

    def test_invalid_values_skipped(self):
        self.assertEqual(self.run_pipeline([None, float('nan'), 'bad', 3]), (1, 1))

    def test_http_failure_stops_without_retry(self):
        self.assertEqual(self.run_pipeline([1, 2], outcome=401), (1, 1))

    def test_timeout_stops_without_retry(self):
        self.assertEqual(self.run_pipeline([1, 2], outcome=requests.Timeout()), (1, 1))

    def test_dry_run(self):
        self.assertEqual(self.run_pipeline([None, 1], dry_run=True), (0, 0))


if __name__ == '__main__':
    unittest.main()
