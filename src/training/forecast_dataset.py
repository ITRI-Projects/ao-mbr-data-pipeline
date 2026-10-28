"""Prepare causal multivariate forecasting inputs from an observed minute CSV.

Run: python -m src.training.forecast_dataset --source notebooks/data/google_drive_raw_aliases.csv
No database access or model training is performed.
"""
import argparse
import hashlib
import importlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

CONFIG_MODULES = ("eff_nh3_n", "eff_no3_n", "a1_ch3oh_flow",
                  "a2_ch3oh_flow", "a1_air_flow", "a2_air_flow")


def prepare(raw, config, train_end="2026-04-18", test_start="2026-04-21",
            horizon_minutes=60, step_minutes=20, sequence_steps=12, max_age_minutes=5):
    """Use exact future observed labels and past/current inputs only.

    Validation is April 18-20 by default; train labels cannot cross April 18,
    and validation labels cannot cross April 21. Test history may include
    earlier observations, as it would at a rolling operational forecast origin.
    """
    if min(horizon_minutes, step_minutes, sequence_steps) < 1 or max_age_minutes < 0:
        raise ValueError("Horizon, interval and sequence length must be positive; age nonnegative.")
    if (raw.empty or not isinstance(raw.index, pd.DatetimeIndex)
            or raw.index.hasnans or raw.index.tz is not None
            or not raw.index.is_unique or not raw.index.is_monotonic_increasing
            or not raw.columns.is_unique):
        raise ValueError("Expected nonempty unique sorted naive timestamps and unique sensors.")
    if not raw.index.equals(raw.index.floor("min")):
        raise ValueError("Source timestamps must be minute aligned.")
    raw = raw.apply(pd.to_numeric, errors="raise")
    if np.isinf(raw.to_numpy(dtype=float)).any():
        raise ValueError("Infinite readings are invalid.")
    train_end, test_start = pd.Timestamp(train_end), pd.Timestamp(test_start)
    if not raw.index.min() < train_end < test_start <= raw.index.max():
        raise ValueError("Split boundaries must be ordered and inside source coverage.")
    target = config["target"]
    columns = list(dict.fromkeys([*config["features"], target]))
    absent = set(columns) - set(raw.columns)
    if absent:
        raise ValueError(f"Missing configured sensors: {sorted(absent)}")
    grid = raw.reindex(pd.date_range(raw.index.min(), raw.index.max(), freq="min", name="datetime"))
    # Exclude unusable inputs using training observations only.
    unique = grid.loc[grid.index < train_end, columns].nunique()
    retained = unique.index[unique.gt(1)].tolist()
    if not retained:
        raise ValueError("No varying training inputs remain.")
    observed = grid[retained]
    times = pd.Series(grid.index, index=grid.index)
    last = observed.apply(lambda s: times.where(s.notna()).ffill())
    age = last.apply(lambda s: (times - s).dt.total_seconds() / 60)
    causal = observed.ffill().where(age.le(max_age_minutes))
    origins = pd.date_range(grid.index.min().ceil(f"{step_minutes}min"),
                            grid.index.max(), freq=f"{step_minutes}min")
    values = causal.reindex(origins).to_numpy(dtype=float)
    # Ordered sequences end at each forecast origin, including that origin.
    positions = np.arange(sequence_steps - 1, len(origins))
    offsets = np.arange(sequence_steps - 1, -1, -1)
    X = values[positions[:, None] - offsets]
    origins = origins[positions]
    label_times = origins + pd.Timedelta(minutes=horizon_minutes)
    y = grid[target].reindex(label_times).to_numpy(dtype=float)
    split = np.full(len(origins), "purged", dtype="U10")
    split[(origins < train_end) & (label_times < train_end)] = "train"
    split[(origins >= train_end) & (origins < test_start) & (label_times < test_start)] = "validation"
    split[(origins >= test_start) & (label_times <= grid.index.max())] = "test"
    valid = np.isfinite(y) & (split != "purged")
    X, y, origins, label_times, split = X[valid], y[valid], origins[valid], label_times[valid], split[valid]
    if any(not np.any(split == s) for s in ("train", "validation", "test")):
        raise ValueError(f"{target}: at least one split has no measured labels.")
    supported = np.isfinite(X[split == "train"]).any(axis=(0, 1))
    sequence_excluded = [name for name, keep in zip(retained, supported) if not keep]
    retained = [name for name, keep in zip(retained, supported) if keep]
    X = X[:, :, supported]
    if not retained:
        raise ValueError("No observed training sequence inputs remain.")
    missing = np.isnan(X)
    train = X[split == "train"]
    medians = np.nanmedian(train, axis=(0, 1))
    if not np.isfinite(medians).all():
        raise ValueError("Some retained sensors have no training sequence values.")
    imputed = np.where(missing, medians, X)
    center = imputed[split == "train"].mean(axis=(0, 1))
    scale = imputed[split == "train"].std(axis=(0, 1))
    scale[scale == 0] = 1
    scaled = ((imputed - center) / scale).astype(np.float32)
    metadata = pd.DataFrame({"origin": origins, "target_time": label_times,
                             "split": split, "target": y,
                             "missing_input_fraction": missing.mean(axis=(1, 2))})
    return dict(X_raw=X, X=scaled, missing=missing, y=y, split=split,
                origin=origins.to_numpy(), target_time=label_times.to_numpy(),
                feature_names=np.asarray(retained), median=medians, center=center, scale=scale), metadata, {
                    "target": target, "features": retained,
                    "excluded_no_training_sequence_support": sequence_excluded,
                    "excluded_training_constant_or_unobserved": unique.index[unique.le(1)].tolist(),
                    "split_counts": metadata.groupby("split").size().to_dict(),
                    "target_unique_by_split": metadata.groupby("split")["target"].nunique().to_dict(),
                    "scheduled_origins_after_warmup": len(positions),
                    "excluded_missing_labels_or_boundary": int((~valid).sum())}


def export_dataset(source, output):
    source, output = Path(source), Path(output)
    raw = pd.read_csv(source, index_col="datetime", parse_dates=True)
    prepared = []
    for module in CONFIG_MODULES:
        config = importlib.import_module(f"config.{module}").CONFIG
        arrays, samples, details = prepare(raw, config)
        prepared.append((config["name"], arrays, samples, details))
    output.mkdir(parents=True, exist_ok=True)
    raw.isna().sum().rename("missing_source_rows").to_csv(output / "source_missingness.csv")
    reports = {}
    for name, arrays, samples, details in prepared:
        folder = output / name
        folder.mkdir(exist_ok=True)
        np.savez_compressed(folder / "sequences.npz", **arrays)
        samples.to_csv(folder / "samples.csv", index=False)
        # Flattened sequences share the same information as the 3D LSTM input.
        features = [f"{sensor}__t_minus_{lag * 20}min"
                    for lag in range(11, -1, -1) for sensor in arrays["feature_names"]]
        flat = pd.DataFrame(arrays["X"].reshape(len(samples), -1), columns=features)
        masks = pd.DataFrame(arrays["missing"].reshape(len(samples), -1).astype(int),
                             columns=[f"{f}__missing" for f in features])
        flat = pd.concat([samples.reset_index(drop=True), flat, masks], axis=1)
        for split in ("train", "validation", "test"):
            flat.loc[flat["split"] == split].to_csv(folder / f"{split}.csv", index=False)
        reports[name] = details
    manifest = {
        "source": str(source.resolve()), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_start": str(raw.index.min()), "source_end": str(raw.index.max()),
        "source_rows": len(raw),
        "horizon_minutes": 60, "origin_step_minutes": 20, "sequence_steps": 12,
        "input_policy": "current minute, causal forward fill at most five minutes; no averaging",
        "label_policy": "exact observed source value at origin + 60 minutes, never filled",
        "train_end_exclusive": "2026-04-18", "validation_end_exclusive": "2026-04-21",
        "preprocessing": "training-sequence median imputation and standardization only",
        "missingness": "NPZ missing channels must accompany X; X_raw preserves NaNs",
        "source_caveat": "Observed means non-null in supplied raw export; upstream cleaning is not independently verified.",
        "targets": reports}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Observed minute CSV with datetime and sensor aliases")
    parser.add_argument("--output", default="notebooks/data/multivariate_forecast_drive")
    args = parser.parse_args()
    report = export_dataset(args.source, args.output)
    print(json.dumps(report["targets"], indent=2))
