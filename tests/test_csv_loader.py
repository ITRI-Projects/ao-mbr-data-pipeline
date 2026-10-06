import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import main
from src import csv_loader


class CSVLoaderTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'clean.csv'
        self.path.write_text('datetime,70flowa1qin,70coda1inf\n2026-04-23 13:00:00,3.5,\n', encoding='utf-8-sig')

    def test_workbook_aliases_and_windows_path(self):
        mapping = csv_loader.read_aliases()
        self.assertEqual(mapping['70flowa1qin'], 'A1_Qin')
        self.assertEqual(mapping['70flowa1aerobic'], 'Q_A1_air')
        self.assertEqual(str(csv_loader.local_path(r'C:\Users\Bryan\Downloads\clean.csv')), '/mnt/c/Users/Bryan/Downloads/clean.csv')
        aliases, rows = csv_loader.read_clean_csv(self.path, mapping)
        self.assertEqual(aliases, ['A1_Qin', 'A1_COD_in'])
        self.assertEqual(rows[0][1:], (3.5, None))

    def test_validation_without_database(self):
        with patch.object(csv_loader, 'get_connection') as connect:
            self.assertEqual(main.main(['--load-csv', str(self.path), '--validate-only']), 0)
            connect.assert_not_called()

    def test_interactive_load_skips_sensor_menu(self):
        with patch('builtins.input', side_effect=['3', str(self.path)]), patch('builtins.print'):
            args = main.select_options([])
        self.assertEqual(args.load_csv, str(self.path))
        self.assertIsNone(args.sensor)

    def test_invalid_rows_fail_before_connecting(self):
        for data in [
            'datetime,unknown\n2026-04-23,1\n',
            'datetime,70flowa1qin\n2026-04-23,nan\n',
            'datetime,70flowa1qin\n2026-04-23,1\n2026-04-23,2\n',
            'datetime,70flowa1qin\n2026-04-23,1,2\n',
        ]:
            self.path.write_text(data)
            with patch.object(csv_loader, 'get_connection') as connect:
                self.assertEqual(csv_loader.load_csv(self.path), 1)
                connect.assert_not_called()

    def test_downloaded_csv_format(self):
        self.path.write_text(
            'DateTime,70coda1inf,70doa1anoxic,70flowa1qin\n'
            '3/24/2026 13:00,88.552,-4.882,\n'
            '3/24/2026 13:01:30,90.172,,50.278\n', encoding='utf-8-sig')
        aliases, rows = csv_loader.read_clean_csv(self.path, csv_loader.read_aliases())
        self.assertEqual(aliases, ['A1_COD_in', 'A1_A_DO', 'A1_Qin'])
        self.assertEqual(rows[0][0].isoformat(), '2026-03-24T13:00:00')
        self.assertEqual(rows[0][1:], (88.552, -4.882, None))
        self.assertEqual(rows[1][0].second, 30)
        with patch.object(csv_loader, 'get_connection') as connect:
            self.assertEqual(main.main(['--load-csv', str(self.path), '--validate-only']), 0)
            connect.assert_not_called()

    def test_timestamp_validation(self):
        for value in ('24/3/2026 13:00', '2/30/2026 13:00',
                      '2026-03-24T13:00:00+08:00', ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                csv_loader.parse_timestamp(value)
        self.path.write_text('DateTime,datetime,70flowa1qin\n3/24/2026 13:00,3/24/2026 13:00,1\n')
        with self.assertRaises(ValueError):
            csv_loader.read_clean_csv(self.path, csv_loader.read_aliases())
        self.path.write_text('DateTime,70flowa1qin\n3/24/2026 13:00,1\n2026-03-24 13:00:00,2\n')
        with self.assertRaisesRegex(ValueError, 'Duplicate timestamp'):
            csv_loader.read_clean_csv(self.path, csv_loader.read_aliases())

    def test_commit_and_rollback(self):
        for fail in (False, True):
            connection = Mock()
            cursor = connection.cursor.return_value
            cursor.execute.return_value.fetchone.return_value = (None,)
            if fail:
                cursor.executemany.side_effect = csv_loader.pyodbc.Error('failure')
            with patch.object(csv_loader, 'get_connection', return_value=connection):
                self.assertEqual(csv_loader.load_csv(self.path), int(fail))
            if fail:
                connection.rollback.assert_called_once()
                connection.commit.assert_not_called()
            else:
                connection.commit.assert_called_once()
                sql, rows = cursor.executemany.call_args.args
                self.assertIn('[A1_Qin], [A1_COD_in]', sql)
                self.assertEqual(rows[0][1:], (3.5, None))
            connection.close.assert_called_once()
            cursor.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
