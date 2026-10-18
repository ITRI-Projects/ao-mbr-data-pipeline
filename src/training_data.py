"""Conservative retrospective feature filling and exact seven-day window ranking."""
import numpy as np
import pandas as pd


def fill_short_gaps(data, target_columns, flow_columns):
    """Match notebook 02: <=3 missing minutes, <=4-minute brackets; targets untouched.

    Interior interpolation uses a later observation. Apply separately within each
    chronological split, and only use estimates once their right bracket is available.
    """
    filled = data.copy()
    mask = pd.DataFrame(False, index=data.index, columns=data.columns)
    for column in data.columns:
        if column in target_columns or not data[column].notna().any():
            continue
        values = data[column]
        missing = values.isna()
        groups = missing.ne(missing.shift(fill_value=False)).cumsum()
        lengths = missing.groupby(groups).transform('sum')
        times = pd.Series(data.index, index=data.index).where(values.notna())
        eligible = missing & lengths.le(3) & (times.bfill() - times.ffill()).le(pd.Timedelta(minutes=4))
        if column in flow_columns:
            before, after = values.ffill(), values.bfill()
            eligible &= (before.eq(0) & after.eq(0)) | before.mul(after).gt(0)
        estimates = values.interpolate(method='time', limit_area='inside')
        eligible &= estimates.notna()
        filled.loc[eligible, column] = estimates.loc[eligible]
        mask[column] = eligible
    return filled, mask


def rank_training_windows(data, target_columns, flow_columns, minutes=10_080):
    """Rank every complete minute-aligned window by residual missing cells.

    Account for interpolation brackets at each candidate's boundaries so no
    candidate receives estimates from observations outside its own interval.
    """
    if data.empty or not data.index.is_unique or not data.index.is_monotonic_increasing:
        raise ValueError('Expected nonempty data with unique increasing timestamps.')
    if not (data.index == data.index.floor('min')).all():
        raise ValueError('Expected minute-aligned timestamps.')
    index = pd.date_range(data.index.min(), data.index.max(), freq='min', name='datetime')
    grid = data.reindex(index).apply(pd.to_numeric, errors='raise')
    n = len(grid)
    if n < minutes:
        raise ValueError('Less than seven days of source coverage.')
    _, mask = fill_short_gaps(grid, target_columns, flow_columns)
    missing = grid.isna().to_numpy(dtype=np.int64)
    prefix = np.vstack([np.zeros((1, len(grid.columns)), dtype=np.int64), missing.cumsum(axis=0)])
    raw_counts = prefix[minutes:] - prefix[:-minutes]
    filled_counts = np.zeros_like(raw_counts)
    for j, column in enumerate(grid.columns):
        positions = np.flatnonzero(mask[column].to_numpy())
        observed = np.flatnonzero(grid[column].notna().to_numpy())
        if not len(positions):
            continue
        right = np.searchsorted(observed, positions)
        left_brackets, right_brackets = observed[right - 1], observed[right]
        first_start = np.maximum(0, right_brackets - minutes + 1)
        last_start = np.minimum(left_brackets, n - minutes)
        valid = first_start <= last_start
        changes = np.zeros(n - minutes + 2, dtype=np.int64)
        np.add.at(changes, first_start[valid], 1)
        np.add.at(changes, last_start[valid] + 1, -1)
        filled_counts[:, j] = changes.cumsum()[:-1]
    remaining = raw_counts - filled_counts
    present = index.isin(data.index).astype(np.int64)
    present_prefix = np.r_[0, present.cumsum()]
    ranking = pd.DataFrame({
        'start_inclusive': index[:len(remaining)],
        'end_exclusive': index[:len(remaining)] + pd.Timedelta(minutes=minutes),
        'raw_missing_cells': raw_counts.sum(axis=1),
        'feature_cells_filled': filled_counts.sum(axis=1),
        'remaining_missing_cells': remaining.sum(axis=1),
        'remaining_missing_percent': remaining.sum(axis=1) / (minutes * len(grid.columns)) * 100,
        'worst_column_missing': remaining.max(axis=1),
        'absent_timestamps': minutes - (present_prefix[minutes:] - present_prefix[:-minutes]),
    })
    ranking = ranking.sort_values(
        ['remaining_missing_cells', 'worst_column_missing', 'start_inclusive'],
        kind='stable',
    ).reset_index(drop=True)
    return grid, ranking
