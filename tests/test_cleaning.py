from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from src import cleaning
from src.sensor_aliases import read_aliases
from src.training.train import discover_mask_paths, load_source


class CleaningTests(unittest.TestCase):
    def test_sql_query_is_read_only_and_includes_the_last_minute(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.description = [(" DateTime ",), ("A1_Qin",)]
        cursor.__iter__.return_value = iter([(datetime(2026, 4, 23, 12, 30), None)])
        with patch.object(cleaning, "get_connection", return_value=connection):
            frame = cleaning.read_sql_readings("dbo.ImportedSensors", "2026-04-23 12:00", "2026-04-23 12:30")

        cursor.execute.assert_called_once_with(
            "SELECT * FROM [dbo].[ImportedSensors] WHERE [datetime] >= ? AND [datetime] < ? ORDER BY [datetime]",
            datetime(2026, 4, 23, 12), datetime(2026, 4, 23, 12, 31),
        )
        cursor.close.assert_called_once_with()
        connection.close.assert_called_once_with()
        self.assertEqual(frame.index.name, "datetime")
        self.assertTrue(frame["A1_Qin"].isna().all())

    def test_preparation_and_export_round_trip_with_training(self):
        times = pd.date_range("2026-04-23", periods=100, freq="min", name="datetime")
        variation = pd.Series(range(len(times)), index=times) / 100
        raw = pd.DataFrame(index=times)
        for sensor in cleaning.TANK_SENSORS:
            raw[f"A1_{sensor}"] = 4 + variation
            raw[f"A2_{sensor}"] = 6 + variation
        raw = raw.rename(columns={"A1_A_DO": "70DOA1Anoxic"})
        raw["Q_A1_air"] = 10 + variation
        raw["Eff_NO3_N"] = 1.0
        raw.loc[times[12], "A2_A_DO"] = float("nan")
        raw.loc[times[20], "Q_A1_air"] = -1.0
        for column in raw:
            raw.loc[times[30:91], column] = raw.loc[times[30], column]
        raw = raw.drop(times[1:12])

        prepared = cleaning.clean_readings(raw, read_aliases())
        self.assertEqual(prepared.data.loc[times[0], "A_DO"], 5.0)
        self.assertEqual(prepared.data.loc[times[12], "A_DO"], 4.12)
        self.assertEqual(prepared.data.loc[times[10], "A_DO"], 5.0)
        self.assertTrue(prepared.fill_mask.loc[times[10], "A_DO"])
        self.assertTrue(pd.isna(prepared.data.loc[times[11], "A_DO"]))
        self.assertFalse(prepared.fill_mask.loc[times[11], "A_DO"])
        self.assertTrue(prepared.fault_mask.loc[times[20], "A1_Q_air"])
        self.assertTrue(prepared.replacement_mask.loc[times[20], "A1_Q_air"])
        self.assertAlmostEqual(prepared.data.loc[times[20], "A1_Q_air"], 10.2)
        self.assertNotIn("Eff_NO3_N", prepared.data)
        self.assertTrue(prepared.synchronized_mask.loc[times[30:91]].all())
        self.assertFalse(prepared.synchronized_mask.loc[times[29]])
        self.assertFalse(prepared.synchronized_mask.loc[times[91]])

        with TemporaryDirectory() as folder:
            output = Path(folder)
            run = cleaning.export_readings(raw, prepared, output)
            csv_path = run / "data_filled.csv"
            source = load_source(csv_path, *discover_mask_paths(csv_path))
            self.assertEqual(list(output.iterdir()), [run])
            self.assertTrue((run / "sensor_timeseries.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
            snapshot = pd.read_csv(run / "sql_raw.csv", index_col="datetime", parse_dates=True)
            pd.testing.assert_frame_equal(snapshot, raw)
            self.assertTrue(pd.isna(source.observed.loc[times[10], "A_DO"]))
            self.assertTrue(pd.isna(source.observed.loc[times[20], "A1_Q_air"]))
            self.assertTrue(pd.isna(source.data.loc[times[30], "A_DO"]))
