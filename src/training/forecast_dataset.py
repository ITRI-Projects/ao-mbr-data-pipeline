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

DEFAULT_TRAIN_START = "2026-04-04"
DEFAULT_TRAIN_END = "2026-04-18"
DEFAULT_TEST_START = "2026-04-21"
DEFAULT_HORIZON_MINUTES = 10
DEFAULT_STEP_MINUTES = 10
DEFAULT_SEQUENCE_STEPS = 7


def prepare(raw, config, train_start=DEFAULT_TRAIN_START, train_end=DEFAULT_TRAIN_END,
            test_start=DEFAULT_TEST_START, horizon_minutes=DEFAULT_HORIZON_MINUTES,
            step_minutes=DEFAULT_STEP_MINUTES, sequence_steps=DEFAULT_SEQUENCE_STEPS,
            max_age_minutes=5,
            prepared_inputs=None, input_quality_mask=None, excluded_timestamps=None):
    """Use exact future observed labels and past/current inputs only.

    Training labels are April 4-17 and validation labels are April 18-20 by
    default. Test origins begin April 21. Input history and forecast origins
    may precede a label boundary, as they would for an operational forecast.
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
    train_start = pd.Timestamp(train_start)
    train_end, test_start = pd.Timestamp(train_end), pd.Timestamp(test_start)
    if not raw.index.min() <= train_start < train_end < test_start <= raw.index.max():
        raise ValueError("Split boundaries must be ordered and inside source coverage.")
    target = config["target"]
    columns = list(dict.fromkeys([*config["features"], target]))
    absent = set(columns) - set(raw.columns)
    if absent:
        raise ValueError(f"Missing configured sensors: {sorted(absent)}")
    grid = raw.reindex(pd.date_range(raw.index.min(), raw.index.max(), freq="min", name="datetime"))
    # Exclude unusable inputs using training observations only.
    unique = grid.loc[(grid.index >= train_start) & (grid.index < train_end), columns].nunique()
    retained = unique.index[unique.gt(1)].tolist()
    if not retained:
        raise ValueError("No varying training inputs remain.")
    observed = grid[retained]
    times = pd.Series(grid.index, index=grid.index)
    last = observed.apply(lambda s: times.where(s.notna()).ffill())
    age = last.apply(lambda s: (times - s).dt.total_seconds() / 60)
    causal = observed.ffill().where(age.le(max_age_minutes))
    if prepared_inputs is not None:
        if not prepared_inputs.index.equals(grid.index) or not set(retained).issubset(prepared_inputs.columns):
            raise ValueError("Prepared inputs must align exactly with the source minute grid.")
        causal = prepared_inputs[retained]
    if input_quality_mask is None:
        input_quality_mask = pd.DataFrame(False, index=grid.index, columns=grid.columns)
    elif (not input_quality_mask.index.equals(grid.index)
          or not set(retained).issubset(input_quality_mask.columns)):
        raise ValueError("Input quality mask must align exactly with the source minute grid.")
    if excluded_timestamps is None:
        excluded_timestamps = pd.Series(False, index=grid.index)
    elif not excluded_timestamps.index.equals(grid.index):
        raise ValueError("Excluded timestamps must align exactly with the source minute grid.")
    excluded_timestamps = excluded_timestamps.astype(bool)
    origins = pd.date_range(grid.index.min().ceil(f"{step_minutes}min"),
                            grid.index.max(), freq=f"{step_minutes}min")
    values = causal.reindex(origins).to_numpy(dtype=float)
    quality_values = input_quality_mask[retained].reindex(origins).to_numpy(dtype=bool)
    # Ordered sequences end at each forecast origin, including that origin.
    positions = np.arange(sequence_steps - 1, len(origins))
    offsets = np.arange(sequence_steps - 1, -1, -1)
    X = values[positions[:, None] - offsets]
    quality = quality_values[positions[:, None] - offsets]
    origins = origins[positions]
    label_times = origins + pd.Timedelta(minutes=horizon_minutes)
    y = grid[target].reindex(label_times).to_numpy(dtype=float)
    split = np.full(len(origins), "purged", dtype="U10")
    split[(label_times >= train_start) & (label_times < train_end)] = "train"
    split[(label_times >= train_end) & (label_times < test_start)] = "validation"
    split[(origins >= test_start) & (label_times <= grid.index.max())] = "test"
    history_starts = origins - pd.Timedelta(minutes=step_minutes * (sequence_steps - 1))
    corrupt_sequence = np.array([
        excluded_timestamps.loc[start:origin].any()
        for start, origin in zip(history_starts, origins)
    ])
    corrupt_label = excluded_timestamps.reindex(label_times, fill_value=False).to_numpy()
    valid = np.isfinite(y) & (split != "purged") & ~corrupt_sequence & ~corrupt_label
    X, quality, y, origins, label_times, split = (
        X[valid], quality[valid], y[valid], origins[valid], label_times[valid], split[valid]
    )
    if any(not np.any(split == s) for s in ("train", "validation", "test")):
        raise ValueError(f"{target}: at least one split has no measured labels.")
    supported = np.isfinite(X[split == "train"]).any(axis=(0, 1))
    sequence_excluded = [name for name, keep in zip(retained, supported) if not keep]
    retained = [name for name, keep in zip(retained, supported) if keep]
    X = X[:, :, supported]
    quality = quality[:, :, supported]
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
                             "missing_input_fraction": missing.mean(axis=(1, 2)),
                             "quality_flagged_input_fraction": quality.mean(axis=(1, 2))})
    return dict(X_raw=X, X=scaled, missing=missing, quality=quality, y=y, split=split,
                origin=origins.to_numpy(), target_time=label_times.to_numpy(),
                feature_names=np.asarray(retained), median=medians, center=center, scale=scale), metadata, {
                    "target": target, "features": retained,
                    "train_start": str(train_start),
                    "train_end_exclusive": str(train_end),
                    "test_start": str(test_start),
                    "horizon_minutes": horizon_minutes,
                    "origin_interval_minutes": step_minutes,
                    "sequence_steps": sequence_steps,
                    "history_minutes": step_minutes * (sequence_steps - 1),
                    "excluded_no_training_sequence_support": sequence_excluded,
                    "excluded_training_constant_or_unobserved": unique.index[unique.le(1)].tolist(),
                    "split_counts": metadata.groupby("split").size().to_dict(),
                    "target_unique_by_split": metadata.groupby("split")["target"].nunique().to_dict(),
                    "scheduled_origins_after_warmup": len(positions),
                    "excluded_missing_labels_boundary_or_corruption": int((~valid).sum()),
                    "excluded_corrupt_sequence_or_label": int((corrupt_sequence | corrupt_label).sum())}



def plot_training_report(raw, samples, predictions, scores, config, folder,
                         train_start=DEFAULT_TRAIN_START, train_end=DEFAULT_TRAIN_END,
                         test_start=DEFAULT_TEST_START,
                         horizon_minutes=DEFAULT_HORIZON_MINUTES,
                         step_minutes=DEFAULT_STEP_MINUTES, prefix=""):
    """Compare identical forecast samples across chronological splits and models.

    Missing observed labels remain gaps. Training predictions are in-sample fits.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    splits = ("train", "validation", "test")
    colors = ("steelblue", "darkorange", "seagreen")
    boundaries = [pd.Timestamp(train_start), pd.Timestamp(train_end), pd.Timestamp(test_start),
                  raw.index.max() + pd.Timedelta(minutes=1)]
    # Visualization only: crop the display, never the source used by prepare().
    display_end = raw.index.max() + pd.Timedelta(minutes=1)
    display_start = max(raw.index.min(), display_end - pd.Timedelta(days=7))
    display_raw = raw.loc[(raw.index >= display_start) & (raw.index < display_end)]
    fig, ax = plt.subplots(figsize=(13, 3.5))
    for i, split in enumerate(splits):
        left, right = max(boundaries[i], display_start), min(boundaries[i+1], display_end)
        if left < right:
            # Include the following boundary point to join adjacent colored segments.
            segment = display_raw.loc[(display_raw.index >= left) & (display_raw.index <= right)]
            ax.plot(segment.index, segment[config["target"]], color=colors[i],
                    linewidth=.8, label=split.capitalize())
    ax.set_xlim(display_start, display_end)
    ax.set(title=f"{config['target']}: final seven days (14-day training window)",
           ylabel=config["unit"], xlabel="Measurement timestamp")
    locator = mdates.AutoDateLocator(minticks=5, maxticks=8)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax.legend(loc="upper left", ncol=4); ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(folder / f"{prefix}dataset_split.png", dpi=150); plt.close(fig)

    fig, axes = plt.subplots(len(predictions), 3, figsize=(21, 3 * len(predictions)),
                             squeeze=False, sharex="col")
    for row, (algorithm, predicted) in enumerate(predictions.items()):
        for col, split in enumerate(splits):
            chosen = samples.split.eq(split).to_numpy()
            subset = samples.loc[chosen].copy()
            subset["prediction"] = np.asarray(predicted)[chosen]
            timeline = subset.set_index("target_time")[["target", "prediction"]]
            timeline = timeline.reindex(pd.date_range(
                timeline.index.min(), timeline.index.max(), freq=f"{step_minutes}min"
            ))
            ax = axes[row, col]
            ax.plot(timeline.index, timeline.target, color="black", linewidth=.85, label="Observed")
            ax.plot(timeline.index, timeline.prediction, color=colors[col], linewidth=.9, alpha=.85, label=algorithm)
            score = scores.loc[scores.algorithm.eq(algorithm) & scores.split.eq(split)].iloc[0]
            ax.set_title(f"{algorithm} | {split} | n={chosen.sum():,}\n"
                         f"MAE={score.MAE:.4g}, RMSE={score.RMSE:.4g}, R2={score.R2:.3f}")
            ax.set_ylabel(config["unit"]); ax.grid(alpha=.2); ax.legend(fontsize=8)
            locator = mdates.AutoDateLocator(minticks=3, maxticks=5)
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    fig.suptitle(f"{config['target']}: observed versus {horizon_minutes}-minute-ahead predictions\n"
                 "Train: fitted | Validation: model selection | Test: held-out rolling forecast")
    fig.tight_layout(rect=(0, 0, 1, .95))
    fig.savefig(folder / f"{prefix}train_test_predictions.png", dpi=150); plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(17, 5))
    for ax, metric in zip(axes, ("MAE", "RMSE", "R2")):
        comparison = scores.pivot(index="algorithm", columns="split", values=metric).reindex(
            index=list(predictions), columns=list(splits))
        comparison.plot.bar(ax=ax, color=list(colors), rot=15)
        ax.set_title(metric + (" (higher is better)" if metric == "R2" else " (lower is better)"))
        ax.set_ylabel("R2" if metric == "R2" else config["unit"])
        ax.set_xlabel(""); ax.grid(axis="y", alpha=.2)
        if metric == "R2": ax.axhline(0, color="black", linewidth=.7)
    fig.suptitle(f"{config['target']}: algorithm metrics; training scores are in-sample")
    fig.tight_layout(rect=(0, 0, 1, .94))
    fig.savefig(folder / f"{prefix}metrics_comparison.png", dpi=150); plt.close(fig)


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
        features = [f"{sensor}__t_minus_{lag * DEFAULT_STEP_MINUTES}min"
                    for lag in range(DEFAULT_SEQUENCE_STEPS - 1, -1, -1)
                    for sensor in arrays["feature_names"]]
        flat = pd.DataFrame(arrays["X"].reshape(len(samples), -1), columns=features)
        masks = pd.DataFrame(arrays["missing"].reshape(len(samples), -1).astype(int),
                             columns=[f"{f}__missing" for f in features])
        quality = pd.DataFrame(arrays["quality"].reshape(len(samples), -1).astype(int),
                               columns=[f"{f}__quality_flagged" for f in features])
        flat = pd.concat([samples.reset_index(drop=True), flat, masks, quality], axis=1)
        for split in ("train", "validation", "test"):
            flat.loc[flat["split"] == split].to_csv(folder / f"{split}.csv", index=False)
        reports[name] = details
    manifest = {
        "source": str(source.resolve()), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_start": str(raw.index.min()), "source_end": str(raw.index.max()),
        "source_rows": len(raw),
        "horizon_minutes": DEFAULT_HORIZON_MINUTES,
        "origin_step_minutes": DEFAULT_STEP_MINUTES,
        "sequence_steps": DEFAULT_SEQUENCE_STEPS,
        "history_minutes": DEFAULT_STEP_MINUTES * (DEFAULT_SEQUENCE_STEPS - 1),
        "input_policy": "current minute, causal forward fill at most five minutes; no averaging",
        "label_policy": "exact observed source value at origin + 10 minutes, never filled",
        "train_start_inclusive": DEFAULT_TRAIN_START,
        "train_end_exclusive": DEFAULT_TRAIN_END,
        "validation_end_exclusive": DEFAULT_TEST_START,
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
