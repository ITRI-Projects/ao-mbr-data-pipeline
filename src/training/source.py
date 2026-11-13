"""Load prepared readings and their quality masks for forecasting."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.prepared_data import MASK_FILENAMES


def discover_mask_paths(data_path):
    """Find notebook 02 mask exports beside the selected data CSV."""
    folder = Path(data_path).resolve().parent
    paths = tuple(folder / filename for filename in MASK_FILENAMES)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Training requires the four mask exports beside the data CSV. "
            f"Missing: {missing}"
        )
    return paths


def _read_boolean_frame(path, index, columns, label):
    if path is None:
        return pd.DataFrame(False, index=index, columns=columns)
    text = pd.read_csv(path, index_col="datetime", parse_dates=True, dtype=str)
    if not text.index.equals(index) or not text.columns.equals(columns):
        raise ValueError(f"Data and {label} must have identical timestamps and sensors.")
    if not text.isin(["True", "False"]).all().all():
        raise ValueError(f"{label} must contain only True/False values.")
    return text.eq("True")


def _read_synchronized_mask(path):
    if path is None:
        return None
    text = pd.read_csv(path, index_col="datetime", parse_dates=True, dtype=str)
    if text.shape[1] != 1 or not text.iloc[:, 0].isin(["True", "False"]).all():
        raise ValueError("Synchronized mask must contain one True/False column.")
    if text.index.has_duplicates or not text.index.is_monotonic_increasing:
        raise ValueError("Synchronized mask timestamps must be unique and sorted.")
    return text.iloc[:, 0].eq("True").rename("synchronized_corrupt")


@dataclass(frozen=True)
class TrainingSource:
    data: pd.DataFrame
    observed: pd.DataFrame
    quality_mask: pd.DataFrame
    synchronized_mask: pd.Series

    def __iter__(self):
        """Preserve the historical ``data, observed = load_source(...)`` API."""
        yield self.data
        yield self.observed


def load_source(data_path, mask_path, fault_mask_path=None,
                replacement_mask_path=None, synchronized_mask_path=None):
    data = pd.read_csv(data_path, index_col="datetime", parse_dates=True)
    if (data.empty or data.index.has_duplicates or not data.index.is_monotonic_increasing
            or not data.columns.is_unique):
        raise ValueError("Training data must have unique sorted timestamps and sensors.")
    fill_mask = _read_boolean_frame(mask_path, data.index, data.columns, "fill mask")
    fault_mask = _read_boolean_frame(
        fault_mask_path, data.index, data.columns, "sensor fault mask"
    )
    replacement_mask = _read_boolean_frame(
        replacement_mask_path, data.index, data.columns, "short-error replacement mask"
    )
    data = data.apply(pd.to_numeric, errors="raise")
    if np.isinf(data.to_numpy(dtype=float)).any():
        raise ValueError("Infinite training readings are invalid.")
    invalid_fill = fill_mask & data.isna() & ~fault_mask
    if invalid_fill.any().any() or (replacement_mask & data.isna()).any().any():
        raise ValueError(
            "Fill and replacement masks may only mark populated estimates, except fills later removed as faults."
        )
    if (replacement_mask & ~fault_mask).any().any():
        raise ValueError("Every short-error replacement must also be marked as a sensor fault.")

    synchronized = _read_synchronized_mask(synchronized_mask_path)
    if synchronized is None:
        synchronized = pd.Series(False, index=data.index, name="synchronized_corrupt")
    elif synchronized.reindex(data.index, fill_value=False).any():
        raise ValueError("Synchronized corrupt timestamps must be absent from the cleaned data.")
    start = min(data.index.min(), synchronized.index.min())
    end = max(data.index.max(), synchronized.index.max())
    minute_index = pd.date_range(start, end, freq="min", name="datetime")
    data = data.reindex(minute_index)
    fill_mask = fill_mask.reindex(minute_index, fill_value=False)
    fault_mask = fault_mask.reindex(minute_index, fill_value=False)
    replacement_mask = replacement_mask.reindex(minute_index, fill_value=False)
    synchronized = synchronized.reindex(minute_index, fill_value=False)
    synchronized_cells = pd.DataFrame(
        np.broadcast_to(synchronized.to_numpy()[:, None], data.shape),
        index=data.index, columns=data.columns,
    )
    quality_mask = fill_mask | fault_mask | replacement_mask | synchronized_cells
    observed = data.mask(fill_mask | fault_mask | replacement_mask | synchronized_cells)
    return TrainingSource(data, observed, quality_mask, synchronized)
