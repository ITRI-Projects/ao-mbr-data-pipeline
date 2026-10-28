import unittest
import numpy as np
import pandas as pd
from src.training.forecast_dataset import prepare


class ForecastDatasetTests(unittest.TestCase):
    def setUp(self):
        index = pd.date_range("2026-04-14", "2026-04-23 23:59", freq="min")
        self.raw = pd.DataFrame({"x": np.sin(np.arange(len(index)) / 100),
                                 "y": np.arange(len(index), dtype=float)}, index=index)
        self.config = {"features": ["x"], "target": "y"}

    def test_future_changes_cannot_change_training_or_past_inputs(self):
        a, samples, _ = prepare(self.raw, self.config)
        changed = self.raw.copy()
        changed.loc["2026-04-21":] += 100000
        b, _, _ = prepare(changed, self.config)
        historical = a["origin"] < np.datetime64("2026-04-21")
        np.testing.assert_array_equal(a["X"][historical], b["X"][historical])
        np.testing.assert_array_equal(a["median"], b["median"])
        self.assertTrue((samples.loc[samples.split == "train", "target_time"] < pd.Timestamp("2026-04-18")).all())
        self.assertTrue((samples.loc[samples.split == "validation", "target_time"] < pd.Timestamp("2026-04-21")).all())
        np.testing.assert_array_equal(a["y"], self.raw.y.reindex(a["target_time"]).to_numpy())

    def test_missing_future_labels_are_dropped_and_input_age_is_bounded(self):
        self.raw.loc["2026-04-15 01:00", "y"] = np.nan
        self.raw.loc["2026-04-15 00:01":"2026-04-15 00:20", "x"] = np.nan
        a, _, _ = prepare(self.raw, self.config)
        self.assertNotIn(np.datetime64("2026-04-15T01:00"), a["target_time"])
        pos = np.flatnonzero(a["origin"] == np.datetime64("2026-04-15T00:20"))[0]
        self.assertTrue(a["missing"][pos, -1, 0])
        self.assertTrue(np.isfinite(a["X"]).all())

    def test_duplicate_times_are_rejected(self):
        with self.assertRaises(ValueError):
            prepare(pd.concat([self.raw.iloc[:1], self.raw]), self.config)
