"""Train workbook-defined multivariate forecasts and export plots and metrics.

Run from repository root: python -m src.training.train
"""
import argparse
import hashlib
import importlib.metadata
import json
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

from .forecast_dataset import prepare
from .workbook import read_workbook


def load_source(data_path, mask_path):
    data = pd.read_csv(data_path, index_col="datetime", parse_dates=True)
    mask_text = pd.read_csv(mask_path, index_col="datetime", parse_dates=True, dtype=str)
    if not data.index.equals(mask_text.index) or not data.columns.equals(mask_text.columns):
        raise ValueError("Data and fill mask must have identical timestamps and sensors.")
    if not mask_text.isin(["True", "False"]).all().all():
        raise ValueError("Mask must contain only True/False values; missing or estimated labels are forbidden.")
    mask = mask_text.eq("True")
    data = data.apply(pd.to_numeric, errors="raise")
    if np.isinf(data.to_numpy(dtype=float)).any() or (mask & data.isna()).any().any():
        raise ValueError("Invalid data or a fill mask marking missing values as estimates.")
    return data, data.where(~mask)


def metrics(y, prediction):
    return {"n": len(y), "MAE": mean_absolute_error(y, prediction),
            "RMSE": float(np.sqrt(mean_squared_error(y, prediction))),
            "R2": float(r2_score(y, prediction)) if len(y) > 1 and np.ptp(y) > 0 else np.nan,
            "constant_target": bool(np.ptp(y) == 0)}


def plot_forecasts(samples, predictions, config, folder):
    fig, axes = plt.subplots(4, 2, figsize=(17, 13), sharex="col", squeeze=False)
    for row, (algorithm, predicted) in enumerate(predictions.items()):
        for col, split in enumerate(("train", "test")):
            chosen = samples.split.eq(split).to_numpy()
            ax = axes[row, col]
            ax.plot(samples.target_time[chosen], samples.target[chosen], color="black", linewidth=1, label="Observed future label")
            ax.plot(samples.target_time[chosen], predicted[chosen], linewidth=0.9, alpha=0.8, label=algorithm)
            ax.set_title(f"{algorithm}: {split} (n={chosen.sum()})")
            ax.set_ylabel(config["unit"])
            ax.grid(alpha=0.25)
            ax.legend(fontsize=8)
    fig.suptitle(f"{config['target']}: observed versus 1-hour-ahead predictions\nTraining fits on left; held-out rolling test forecasts on right")
    fig.autofmt_xdate()
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(folder / "train_test_predictions.png", dpi=140)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(15, 4))
    for split, color in (("train", "steelblue"), ("validation", "darkorange"), ("test", "seagreen")):
        chosen = samples.split.eq(split)
        ax.plot(samples.target_time[chosen], samples.target[chosen], label=split, color=color, linewidth=1)
    ax.set(title=f"{config['target']}: chronological dataset split", ylabel=config["unit"], xlabel="Future label timestamp")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(folder / "dataset_split.png", dpi=140)
    plt.close(fig)


def run(args):
    from xgboost import XGBRegressor
    from .lstm import train_lstm
    data, raw = load_source(args.data, args.mask)
    configs, audit = read_workbook(args.workbook)
    if args.targets:
        unknown = set(args.targets) - set(configs)
        if unknown:
            raise ValueError(f"Unknown target models: {sorted(unknown)}")
        configs = {k: v for k, v in configs.items() if k in args.targets}
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(audit).to_csv(output / "workbook_feature_audit.csv", index=False)
    summaries, manifest_targets = [], {}
    for name, config in configs.items():
        print(f"Training {name}: {config['target']}", flush=True)
        folder = output / name
        folder.mkdir(exist_ok=True)
        arrays, samples, details = prepare(
            raw, config, train_end=args.train_end, test_start=args.test_start,
            horizon_minutes=60, step_minutes=20, sequence_steps=12, prepared_inputs=data)
        # Workbook inputs are authoritative; target history is an explicitly added autoregressive input.
        X = np.concatenate([arrays["X"], arrays["missing"].astype(np.float32)], axis=2)
        flat = X.reshape(len(X), -1)
        y, splits = arrays["y"], arrays["split"]
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
                model.fit(flat[train], y[train])
                score = mean_squared_error(y[val], model.predict(flat[val]))
                if score < best_score:
                    best_score, best_model = score, model
            predictions[algorithm] = best_model.predict(flat)
            path = folder / (algorithm.lower().replace(" ", "_") + ".joblib")
            joblib.dump(best_model, path)
            np.testing.assert_allclose(predictions[algorithm], joblib.load(path).predict(flat))
            selections[algorithm] = {"parameters": best_model.get_params(), "validation_mse": best_score}
        predictions["LSTM"], history = train_lstm(X, y, splits, folder, epochs=args.epochs)
        pd.DataFrame(history).to_csv(folder / "lstm_loss.csv", index=False)
        fig, ax = plt.subplots(figsize=(7, 4))
        loss = pd.DataFrame(history)
        ax.plot(loss.epoch, loss.train_mse_scaled, label="Train")
        ax.plot(loss.epoch, loss.validation_mse_scaled, label="Validation")
        ax.set(xlabel="Epoch", ylabel="MSE in scaled target units", title=f"{config['target']}: LSTM loss")
        ax.legend();fig.tight_layout();fig.savefig(folder / "lstm_loss.png", dpi=140);plt.close(fig)
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
        forecasts.to_csv(folder / "predictions.csv", index=False)
        np.savez_compressed(folder / "preprocessing_and_sequences.npz", **arrays)
        details.update({"workbook": config, "hyperparameter_selection": selections,
                        "added_target_history": config["target"] not in config["features"],
                        "label_policy": "exact observed future labels only; source mask removes estimates"})
        (folder / "metadata.json").write_text(json.dumps(details, indent=2, default=str), encoding="utf-8")
        manifest_targets[name] = {"target": config["target"], "split_counts": details["split_counts"]}
        plot_forecasts(samples, predictions, config, folder)
        pd.DataFrame(summaries).query("model == @name").to_csv(folder / "metrics.csv", index=False)
    summary = pd.DataFrame(summaries)
    summary.to_csv(output / "metrics_summary.csv", index=False)
    test = summary[summary.split.eq("test")].copy()
    display = test[["target", "algorithm", "n", "MAE", "RMSE", "R2", "unit"]].round(5)
    fig, ax = plt.subplots(figsize=(15, max(4, .36 * len(display) + 1)))
    ax.axis("off")
    table = ax.table(cellText=display.fillna("undefined").values, colLabels=display.columns, loc="center")
    table.auto_set_font_size(False);table.set_fontsize(9);table.scale(1, 1.5)
    ax.set_title("Held-out test metrics: one-hour-ahead forecasts", pad=15)
    fig.tight_layout();fig.savefig(output / "metrics_summary.png", dpi=150);plt.close(fig)
    html = "<html><meta charset='utf-8'><title>Forecast comparison</title><body><h1>Forecast comparison</h1>"
    html += f"<p>Train labels before {args.train_end}; validation labels before {args.test_start}; test origins from {args.test_start}. Test metrics never select models. R2 is undefined for constant labels. Recorded flows are predicted; this is not an operating recommendation.</p>"
    html += display.fillna("undefined").to_html(index=False)
    for name in configs:
        html += f"<h2>{name}</h2><img width='100%' src='{name}/dataset_split.png'><img width='100%' src='{name}/train_test_predictions.png'>"
    (output / "report.html").write_text(html + "</body></html>", encoding="utf-8")
    manifest = {"files": {str(p): hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (args.data, args.mask, args.workbook)},
                "train_end_exclusive": args.train_end, "test_start": args.test_start,
                "horizon_minutes": 60, "sequence_steps": 12, "origin_interval_minutes": 20,
                "seed": 42, "max_lstm_epochs": args.epochs, "targets": manifest_targets,
                "versions": {p: importlib.metadata.version(p) for p in ("numpy", "pandas", "scikit-learn", "xgboost", "torch")},
                "limitations": ["Short previously inspected source period; independent future evaluation needed.",
                                "Upstream observations rely on source fill mask accuracy.",
                                "Rolling test forecasts use past available test observations."]}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(display.to_string(index=False))
    print(f"Saved report: {output / 'report.html'}", flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="notebooks/data/data_filled.csv")
    parser.add_argument("--mask", default="notebooks/data/data_filled_mask.csv")
    parser.add_argument("--workbook", default="Sensor_Configurations.xlsx")
    parser.add_argument("--output", default="data/training/workbook_forecasts")
    parser.add_argument("--train-end", default="2026-04-18")
    parser.add_argument("--test-start", default="2026-04-21")
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--targets", nargs="*", help="Optional model names, e.g. eff_nh3_n a1_air_flow")
    args = parser.parse_args()
    if args.epochs < 1:
        parser.error("--epochs must be positive")
    run(args)


if __name__ == "__main__":
    main()
