import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.training.workbook import read_workbook
from src.training.train import load_source, metrics
from src.training.forecast_dataset import prepare


class TrainingScriptTests(unittest.TestCase):
    def test_workbook_checks_and_confirmed_airflow_targets(self):
        configs, audit = read_workbook(Path(__file__).resolve().parents[1] / "Sensor_Configurations.xlsx")
        self.assertEqual(len(configs), 6)
        self.assertEqual(configs["a1_air_flow"]["target"], "Q_A1_air")
        self.assertEqual(configs["a2_air_flow"]["target"], "Q_A2_air")
        self.assertTrue(configs["a1_air_flow"]["target_mark_corrected"])
        for name, config in configs.items():
            checked = [r["sensor"] for r in audit if r["model"] == name and r["checked"]]
            self.assertEqual(config["features"], checked)
            self.assertEqual(len(config["features"]), len(set(config["features"])))

    def test_estimated_labels_are_removed_and_mask_is_strict(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            folder = Path(folder)
            data = pd.DataFrame({"x": [1., 2.]}, index=pd.date_range("2026-01-01", periods=2, freq="min"))
            mask = data.gt(1)
            data.to_csv(folder / "data.csv", index_label="datetime")
            mask.to_csv(folder / "mask.csv", index_label="datetime")
            filled, raw = load_source(folder / "data.csv", folder / "mask.csv")
            self.assertEqual(filled.iloc[1, 0], 2)
            self.assertTrue(pd.isna(raw.iloc[1, 0]))
            (folder / "mask.csv").write_text((folder / "mask.csv").read_text().replace("True", "maybe"))
            with self.assertRaises(ValueError):
                load_source(folder / "data.csv", folder / "mask.csv")

    def test_constant_labels_have_undefined_r2(self):
        result = metrics(np.ones(3), np.zeros(3))
        self.assertTrue(np.isnan(result["R2"]))
        self.assertEqual(result["RMSE"], 1.)

    def test_supplied_preparation_is_used_without_refilling(self):
        index = pd.date_range("2026-04-14", "2026-04-23 23:59", freq="min")
        raw = pd.DataFrame({"x": np.arange(len(index), dtype=float), "y": np.arange(len(index), dtype=float)}, index=index)
        inputs = raw.copy()
        inputs.loc["2026-04-15 00:20", "x"] = np.nan
        arrays, _, _ = prepare(raw, {"features": ["x"], "target": "y"}, prepared_inputs=inputs)
        pos = np.flatnonzero(arrays["origin"] == np.datetime64("2026-04-15T00:20"))[0]
        self.assertTrue(arrays["missing"][pos, -1, 0])

