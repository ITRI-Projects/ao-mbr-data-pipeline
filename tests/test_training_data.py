"""Check conservative gap eligibility and boundary-aware window scoring."""
import unittest

import numpy as np
import pandas as pd

from src.training.training_data import fill_short_gaps, rank_training_windows


class TrainingDataTests(unittest.TestCase):
    def test_targets_flow_state_and_long_outages(self):
        index = pd.date_range('2026-01-01', periods=7, freq='min')
        data = pd.DataFrame({
            'feature': [0., None, None, None, 4., None, None],
            'flow': [0., None, 2., None, 4., None, None],
            'target': [1., None, None, None, None, None, 7.],
            'long_gap': [1., None, None, None, None, None, 7.],
        }, index=index)
        filled, mask = fill_short_gaps(data, ['target'], ['flow'])
        self.assertEqual(filled.loc[index[2], 'feature'], 2.)
        self.assertTrue(pd.isna(filled.loc[index[1], 'flow']))
        self.assertEqual(filled.loc[index[3], 'flow'], 3.)
        self.assertTrue(filled['target'].equals(data['target']))
        self.assertTrue(filled['long_gap'].equals(data['long_gap']))
        self.assertTrue(filled.loc[index[5]:, 'feature'].isna().all())
        self.assertTrue(filled.where(~mask).equals(data))

    def test_rankings_match_filling_each_window_independently(self):
        rng = np.random.default_rng(7)
        index = pd.date_range('2026-01-01', periods=40, freq='min')
        data = pd.DataFrame(rng.normal(size=(40, 3)), index=index,
                            columns=['feature', 'flow', 'target'])
        data[rng.random(data.shape) < .35] = np.nan
        data = data.drop(index[20])  # Absent timestamps count as missing.
        grid, ranking = rank_training_windows(data, ['target'], ['flow'], minutes=12)
        for row in ranking.itertuples():
            raw = grid.loc[(grid.index >= row.start_inclusive) &
                           (grid.index < row.end_exclusive)]
            filled, mask = fill_short_gaps(raw, ['target'], ['flow'])
            self.assertEqual(int(filled.isna().sum().sum()), row.remaining_missing_cells)
            self.assertEqual(int(mask.to_numpy().sum()), row.feature_cells_filled)
            self.assertEqual(int((~raw.index.isin(data.index)).sum()), row.absent_timestamps)
