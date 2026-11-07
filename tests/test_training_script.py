import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.training.workbook import read_workbook
from src.training.train import discover_mask_paths, load_source, metrics, prediction_offset
from src.training.forecast_dataset import prepare


class TrainingScriptTests(unittest.TestCase):
    def test_masks_are_discovered_beside_data(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            folder = Path(folder)
            data = folder / "data_filled.csv"
            data.touch()
            expected = [
                folder / "data_filled_mask.csv",
                folder / "data_sensor_fault_mask.csv",
                folder / "data_short_error_replacement_mask.csv",
                folder / "data_synchronized_corrupt_mask.csv",
            ]
            for path in expected:
                path.touch()
            self.assertEqual(discover_mask_paths(data), tuple(expected))
            expected[-1].unlink()
            with self.assertRaises(FileNotFoundError):
                discover_mask_paths(data)

    def test_workbook_checks_and_confirmed_airflow_targets(self):
        configs, audit = read_workbook(Path(__file__).resolve().parents[1] / "Sensor_Configurations.xlsx")
        self.assertEqual(len(configs), 6)
        self.assertEqual(configs["a1_air_flow"]["target"], "A1_Q_air")
        self.assertEqual(configs["a2_air_flow"]["target"], "A2_Q_air")
        self.assertTrue(configs["a1_air_flow"]["target_mark_corrected"])
        for name, config in configs.items():
            checked = [r["sensor"] for r in audit if r["model"] == name and r["checked"]]
            self.assertEqual(config["features"], list(dict.fromkeys(checked)))
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

    def test_quality_masks_restore_grid_and_remove_estimated_labels(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            folder = Path(folder)
            full_index = pd.date_range("2026-01-01", periods=4, freq="min", name="datetime")
            kept_index = full_index.delete(1)
            data = pd.DataFrame({"x": [1., 2., 3.]}, index=kept_index)
            false_mask = pd.DataFrame(False, index=kept_index, columns=data.columns)
            fault = false_mask.copy()
            replacement = false_mask.copy()
            fault.loc[kept_index[1], "x"] = True
            replacement.loc[kept_index[1], "x"] = True
            synchronized = pd.Series(False, index=full_index, name="synchronized_corrupt")
            synchronized.iloc[1] = True
            data.to_csv(folder / "data.csv", index_label="datetime")
            false_mask.to_csv(folder / "fill.csv", index_label="datetime")
            fault.to_csv(folder / "fault.csv", index_label="datetime")
            replacement.to_csv(folder / "replacement.csv", index_label="datetime")
            synchronized.to_csv(folder / "synchronized.csv", index_label="datetime")

            source = load_source(
                folder / "data.csv", folder / "fill.csv", folder / "fault.csv",
                folder / "replacement.csv", folder / "synchronized.csv",
            )
            self.assertTrue(source.data.index.equals(full_index))
            self.assertTrue(pd.isna(source.data.loc[full_index[1], "x"]))
            self.assertTrue(pd.isna(source.observed.loc[kept_index[1], "x"]))
            self.assertTrue(source.quality_mask.loc[full_index[1], "x"])
            self.assertTrue(source.quality_mask.loc[kept_index[1], "x"])

    def test_constant_labels_have_undefined_r2(self):
        result = metrics(np.ones(3), np.zeros(3))
        self.assertTrue(np.isnan(result["R2"]))
        self.assertEqual(result["RMSE"], 1.)

    def test_delta_prediction_offset_restores_current_target_level(self):
        arrays = {
            "y": np.array([20., 30.]),
            "feature_names": np.array(["x", "target"]),
            "X": np.array([[[0., 1.]], [[0., 2.]]], dtype=np.float32),
            "center": np.array([0., 10.]),
            "scale": np.array([1., 2.]),
        }
        np.testing.assert_allclose(
            prediction_offset(arrays, "target", "delta"), [12., 14.])
        np.testing.assert_array_equal(
            prediction_offset(arrays, "target", "absolute"), [0., 0.])

    def test_supplied_preparation_is_used_without_refilling(self):
        index = pd.date_range("2026-04-14", "2026-04-23 23:59", freq="min")
        raw = pd.DataFrame({"x": np.arange(len(index), dtype=float), "y": np.arange(len(index), dtype=float)}, index=index)
        inputs = raw.copy()
        inputs.loc["2026-04-15 00:20", "x"] = np.nan
        arrays, _, _ = prepare(raw, {"features": ["x"], "target": "y"}, prepared_inputs=inputs)
        pos = np.flatnonzero(arrays["origin"] == np.datetime64("2026-04-15T00:20"))[0]
        self.assertTrue(arrays["missing"][pos, -1, 0])

