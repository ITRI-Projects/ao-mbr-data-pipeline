"""Train workbook-defined multivariate forecasts and export plots and metrics.

Run from repository root: python -m src.training.train
"""
import argparse
import hashlib
import importlib.metadata
import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from .forecast_dataset import (
    DEFAULT_HORIZON_MINUTES,
    DEFAULT_SEQUENCE_STEPS,
    DEFAULT_STEP_MINUTES,
    DEFAULT_TEST_START,
    DEFAULT_TRAIN_END,
    DEFAULT_TRAIN_START,
    prepare,
    plot_training_report,
)
from .workbook import read_workbook

MASK_FILENAMES = (
    "data_filled_mask.csv",
    "data_sensor_fault_mask.csv",
    "data_short_error_replacement_mask.csv",
    "data_synchronized_corrupt_mask.csv",
)


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


def metrics(y, prediction):
    return {"n": len(y), "MAE": mean_absolute_error(y, prediction),
            "RMSE": float(np.sqrt(mean_squared_error(y, prediction))),
            "R2": float(r2_score(y, prediction)) if len(y) > 1 and np.ptp(y) > 0 else np.nan,
            "constant_target": bool(np.ptp(y) == 0)}

PREDICTION_MODES = ("absolute", "delta")
DEFAULT_PREDICTION_MODE = "absolute"


class UnavailableTargetError(ValueError):
    """A requested forecast target is missing from the prepared data."""


def prediction_offset(arrays, target, mode):
    """Return the level added to raw model output to obtain absolute forecasts."""
    if mode not in PREDICTION_MODES:
        raise ValueError(f"Unknown prediction mode: {mode}")
    if mode == "absolute":
        return np.zeros(len(arrays["y"]), dtype=float)
    names = [str(name) for name in arrays["feature_names"]]
    if target not in names:
        raise ValueError(f"Delta prediction requires target history for {target}.")
    index = names.index(target)
    offset = (arrays["X"][:, -1, index].astype(float) * arrays["scale"][index]
              + arrays["center"][index])
    if not np.isfinite(offset).all():
        raise ValueError(f"Delta prediction has non-finite origin values for {target}.")
    return offset


def run(args):
    from xgboost import XGBRegressor
    from .lstm import train_lstm
    mask_paths = discover_mask_paths(args.data)
    source = load_source(
        args.data, *mask_paths,
    )
    data, raw = source
    configs, audit = read_workbook(args.workbook)
    if args.targets:
        unknown = set(args.targets) - set(configs)
        if unknown:
            raise ValueError(f"Unknown target models: {sorted(unknown)}")
        configs = {k: v for k, v in configs.items() if k in args.targets}
    skipped_targets = {}
    available_configs = {}
    for name, config in configs.items():
        if config["target"] not in data.columns:
            skipped_targets[name] = {
                "target": config["target"], "reason": "target_absent_from_cleaned_data"
            }
            continue
        unavailable = [feature for feature in config["features"] if feature not in data.columns]
        revised = dict(config)
        revised["features"] = [
            feature for feature in config["features"] if feature in data.columns
        ]
        revised["excluded_unavailable_features"] = unavailable
        available_configs[name] = revised
    if args.targets and skipped_targets:
        missing = ", ".join(
            f"{name} requires {details['target']}"
            for name, details in sorted(skipped_targets.items())
        )
        available = ", ".join(sorted(available_configs)) or "none of the requested targets"
        raise UnavailableTargetError(
            f"{args.data} is missing target columns: {missing}. "
            f"Available among the requested targets: {available}. "
            "Omit --targets to train all available models, or use a prepared CSV "
            "that retains the requested target and has matching mask exports."
        )
    configs = available_configs
    if not configs:
        raise ValueError("No trainable targets remain in the cleaned data.")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(audit).to_csv(output / "workbook_feature_audit.csv", index=False)
    summaries, manifest_targets = [], {}
    for name, config in configs.items():
        print(f"Training {name}: {config['target']}", flush=True)
        folder = output
        prefix = f"{name}_" if len(configs) > 1 else ""
        def artifact(filename):
            return folder / (prefix + filename)
        arrays, samples, details = prepare(
            raw, config, train_start=args.train_start, train_end=args.train_end,
            test_start=args.test_start, horizon_minutes=args.horizon_minutes,
            step_minutes=args.step_minutes, sequence_steps=args.sequence_steps,
            prepared_inputs=data, input_quality_mask=source.quality_mask,
            excluded_timestamps=source.synchronized_mask)
        # Workbook inputs are authoritative; target history is an explicitly added autoregressive input.
        X = np.concatenate([
            arrays["X"], arrays["missing"].astype(np.float32),
            arrays["quality"].astype(np.float32),
        ], axis=2)
        flat = X.reshape(len(X), -1)
        y, splits = arrays["y"], arrays["split"]
        offset = prediction_offset(arrays, config["target"], args.prediction_mode)
        model_y = y - offset
        train, val = splits == "train", splits == "validation"
        models = {
            "Ridge": [Ridge(alpha=a) for a in (1., 10., 100.)],
            "Random Forest": [RandomForestRegressor(n_estimators=120, max_depth=d, min_samples_leaf=3,
                                                      random_state=42, n_jobs=2) for d in (5, 10)],
            "XGBoost": [XGBRegressor(n_estimators=150, max_depth=d, learning_rate=0.04,
                                       objective="reg:squarederror", random_state=42, n_jobs=2) for d in (2, 4)],
        }
        predictions, selections = {}, {}
        for algorithm, candidates in models.items():
            best_score, best_model = float("inf"), None
            for model in candidates:
                model.fit(flat[train], model_y[train])
                score = mean_squared_error(y[val], model.predict(flat[val]) + offset[val])
                if score < best_score:
                    best_score, best_model = score, model
            predictions[algorithm] = best_model.predict(flat) + offset
            path = artifact(algorithm.lower().replace(" ", "_") + ".joblib")
            joblib.dump(best_model, path)
            np.testing.assert_allclose(predictions[algorithm], joblib.load(path).predict(flat) + offset)
            selections[algorithm] = {"parameters": best_model.get_params(), "validation_mse": best_score}
        lstm_prediction, history = train_lstm(X, model_y, splits, folder, epochs=args.epochs, prefix=prefix)
        predictions["LSTM"] = lstm_prediction + offset
        pd.DataFrame(history).to_csv(artifact("lstm_loss.csv"), index=False)
        fig, ax = plt.subplots(figsize=(7, 4))
        loss = pd.DataFrame(history)
        ax.plot(loss.epoch, loss.train_mse_scaled, label="Train")
        ax.plot(loss.epoch, loss.validation_mse_scaled, label="Validation")
        ax.set(xlabel="Epoch", ylabel="MSE in scaled target units", title=f"{config['target']}: LSTM loss")
        ax.legend();fig.tight_layout();fig.savefig(artifact("lstm_loss.png"), dpi=140);plt.close(fig)
        for algorithm, predicted in predictions.items():
            if not np.isfinite(predicted).all():
                raise ValueError(f"{name}/{algorithm}: non-finite predictions")
            for split in ("train", "validation", "test"):
                chosen = splits == split
                summaries.append({"model": name, "target": config["target"], "unit": config["unit"],
                                  "algorithm": algorithm, "split": split, **metrics(y[chosen], predicted[chosen])})
        forecasts = samples.copy()
        for algorithm, predicted in predictions.items():
            forecasts[algorithm] = predicted
        forecasts.to_csv(artifact("predictions.csv"), index=False)
        np.savez_compressed(artifact("preprocessing_and_sequences.npz"), **arrays)
        details.update({"workbook": config, "hyperparameter_selection": selections,
                        "prediction_mode": args.prediction_mode,
                        "model_target": "future_minus_origin" if args.prediction_mode == "delta" else "future_absolute",
                        "added_target_history": config["target"] not in config["features"],
                        "excluded_unavailable_workbook_features": config["excluded_unavailable_features"],
                        "label_policy": "exact observed future labels only; fill, fault and replacement masks remove estimates",
                        "input_channels": "scaled readings, missing flags, and fill/fault/replacement quality flags"})
        (artifact("metadata.json")).write_text(json.dumps(details, indent=2, default=str), encoding="utf-8")
        manifest_targets[name] = {"target": config["target"], "split_counts": details["split_counts"]}
        target_scores = pd.DataFrame(summaries).query("model == @name")
        plot_training_report(raw, samples, predictions, target_scores, config, folder,
                             train_start=args.train_start, train_end=args.train_end,
                             test_start=args.test_start,
                             horizon_minutes=args.horizon_minutes,
                             step_minutes=args.step_minutes, prefix=prefix)
        pd.DataFrame(summaries).query("model == @name").to_csv(artifact("metrics.csv"), index=False)
    summary = pd.DataFrame(summaries)
    summary.to_csv(output / "metrics_summary.csv", index=False)
    test = summary[summary.split.eq("test")].copy()
    display = test[["target", "algorithm", "n", "MAE", "RMSE", "R2", "unit"]].round(5)
    fig, ax = plt.subplots(figsize=(15, max(4, .36 * len(display) + 1)))
    ax.axis("off")
    table = ax.table(cellText=display.fillna("undefined").values, colLabels=display.columns, loc="center")
    table.auto_set_font_size(False);table.set_fontsize(9);table.scale(1, 1.5)
    ax.set_title(f"Held-out test metrics: {args.horizon_minutes}-minute-ahead forecasts", pad=15)
    fig.tight_layout();fig.savefig(output / "metrics_summary.png", dpi=150);plt.close(fig)
    html = "<html><meta charset='utf-8'><title>Forecast comparison</title><body><h1>Forecast comparison</h1>"
    html += f"<p>Train labels from {args.train_start} through the instant before {args.train_end}; validation labels continue through the instant before {args.test_start}; test origins begin at {args.test_start}. Inputs cover {args.step_minutes * (args.sequence_steps - 1)} minutes and forecasts look ahead {args.horizon_minutes} minutes. Test metrics never select models. R2 is undefined for constant labels. Recorded flows are predicted; this is not an operating recommendation.</p>"
    html += summary.round(6).fillna("undefined").to_html(index=False)
    for name in configs:
        prefix = f"{name}_" if len(configs) > 1 else ""
        html += f"<h2>{name}</h2><img width='100%' src='{prefix}dataset_split.png'><img width='100%' src='{prefix}train_test_predictions.png'><img width='100%' src='{prefix}metrics_comparison.png'>"
    (output / "report.html").write_text(html + "</body></html>", encoding="utf-8")
    source_files = [args.data, *mask_paths, args.workbook]
    manifest = {"files": {str(p): hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in source_files},
                "train_start_inclusive": args.train_start,
                "train_end_exclusive": args.train_end, "test_start": args.test_start,
                "prediction_mode": args.prediction_mode,
                "horizon_minutes": args.horizon_minutes,
                "sequence_steps": args.sequence_steps,
                "origin_interval_minutes": args.step_minutes,
                "history_minutes": args.step_minutes * (args.sequence_steps - 1),
                "seed": 42, "max_lstm_epochs": args.epochs, "targets": manifest_targets,
                "skipped_targets": skipped_targets,
                "versions": {p: importlib.metadata.version(p) for p in ("numpy", "pandas", "scikit-learn", "xgboost", "torch")},
                "limitations": ["Short previously inspected source period; independent future evaluation needed.",
                                "Upstream observations rely on fill and sensor-quality mask accuracy.",
                                "Rolling test forecasts use past available test observations."]}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(display.to_string(index=False))
    print(f"Saved report: {output / 'report.html'}", flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="docs/raw/data_filled.csv")
    parser.add_argument("--workbook", default="Sensor_Configurations.xlsx")
    parser.add_argument("--output", default="data/training/workbook_forecasts")
    parser.add_argument("--train-start", default=DEFAULT_TRAIN_START)
    parser.add_argument("--train-end", default=DEFAULT_TRAIN_END)
    parser.add_argument("--test-start", default=DEFAULT_TEST_START)
    parser.add_argument("--horizon-minutes", type=int, default=DEFAULT_HORIZON_MINUTES)
    parser.add_argument("--step-minutes", type=int, default=DEFAULT_STEP_MINUTES)
    parser.add_argument("--sequence-steps", type=int, default=DEFAULT_SEQUENCE_STEPS)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--targets", nargs="*", help="Optional model names, e.g. eff_nh3_n a1_air_flow")
    parser.add_argument(
        "--prediction-mode", choices=PREDICTION_MODES, default=DEFAULT_PREDICTION_MODE,
        help="Model the absolute future value (default) or its change from the forecast origin",
    )
    args = parser.parse_args()
    if min(args.epochs, args.horizon_minutes, args.step_minutes, args.sequence_steps) < 1:
        parser.error("Epochs, horizon, interval, and sequence length must be positive")
    try:
        run(args)
    except UnavailableTargetError as error:
        parser.exit(2, f"{parser.prog}: error: {error}\n")


if __name__ == "__main__":
    main()
