import os
import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch

import requests
import main
from src import pipeline
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
            with patch('builtins.input', side_effect=[answer]), patch('builtins.print'), patch.object(main, 'run_pipeline') as connect:
                self.assertIn(main.main([]), (0, 130))
                connect.assert_not_called()

    def test_cli_passes_selected_configuration(self):
        with patch.object(main, 'run_pipeline', return_value=1) as run:
            result = main.main(['--submit', '--sensor', 'A2_Qin'])
        self.assertEqual(result, 1)
        run.assert_called_once_with(
            sensor_alias='A2_Qin', sensor=main.SENSORS['A2_Qin'],
            data_window=main.DATA_WINDOW, timestamp_columns=main.TIMESTAMP_COLUMNS,
            dry_run=False, resume_from_id=None, resume_after_id=None)

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

    def run_pipeline(self, values, *, dry_run=False, outcome=200, **resume):
        rows = ({'data_id': i, 'timestamp': datetime(2026, 4, 23, 13), 'value': v}
                for i, v in enumerate(values))
        with patch.object(pipeline, 'get_connection', return_value=Mock()), \
                patch.object(pipeline, 'close_connection') as close, \
                patch.object(pipeline, 'extract_parameter', return_value=rows), \
                patch.object(pipeline, 'APIClient') as factory, \
                patch.object(pipeline, 'get_logger', return_value=Mock()):
            client = factory.return_value
            client.base_url = "https://example.com/import"
            client.user = "test-user"
            if isinstance(outcome, Exception):
                client.submit_reading.side_effect = outcome
            else:
                client.submit_reading.return_value = outcome
            result = pipeline.run_pipeline(
                sensor_alias='A2_Qin', sensor=main.SENSORS['A2_Qin'],
                data_window=main.DATA_WINDOW, timestamp_columns=main.TIMESTAMP_COLUMNS,
                dry_run=dry_run, **resume)
            close.assert_called_once()
            if dry_run:
                factory.assert_not_called()
            else:
                client.close.assert_called_once()
            return result, client.submit_reading.call_count

    def test_resume_includes_failed_reading(self):
        self.assertEqual(self.run_pipeline([1, 2, 3], resume_from_id='1'), (0, 2))

    def test_resume_excludes_confirmed_reading(self):
        self.assertEqual(self.run_pipeline([1, 2, 3], resume_after_id='1'), (0, 1))

    def test_missing_resume_id_sends_nothing(self):
        self.assertEqual(self.run_pipeline([1, 2, 3], resume_from_id='99'), (1, 0))

    def test_resume_at_final_reading(self):
        self.assertEqual(self.run_pipeline([1, 2, 3], resume_after_id='2'), (0, 0))

    def test_resume_failure_still_stops(self):
        self.assertEqual(self.run_pipeline([1, 2, 3], resume_from_id='1', outcome=requests.Timeout()), (1, 1))

    def test_resume_options_are_exclusive(self):
        with self.assertRaises(SystemExit):
            main.select_options(['--resume-from-id', '1', '--resume-after-id', '2'])

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
