"""Tune one saved parameter run using frozen arrays and validation-only selection."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import ParameterSampler
from sklearn.metrics import mean_squared_error
from xgboost import XGBRegressor

from .lstm import train_lstm
from .train import metrics, load_source, prediction_offset
from .forecast_dataset import plot_training_report

ALGORITHMS = {"ridge": "Ridge", "random_forest": "Random Forest", "xgboost": "XGBoost", "lstm": "LSTM"}


def run(args):
    source, output = Path(args.source).resolve(), Path(args.output).resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Use a separate output directory outside the baseline run.")
    array_path = source / "preprocessing_and_sequences.npz"
    metadata = json.loads((source / "metadata.json").read_text(encoding="utf-8"))
    source_manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    config = metadata["workbook"]
    with np.load(array_path) as saved:
        arrays = {k: saved[k] for k in saved.files}
    channels = [arrays["X"], arrays["missing"].astype(np.float32)]
    if "quality" in arrays:
        channels.append(arrays["quality"].astype(np.float32))
    X = np.concatenate(channels, axis=2)
    y, split = arrays["y"], arrays["split"]
    flat = X.reshape(len(X), -1)
    train, val = split == "train", split == "validation"
    prediction_mode = metadata.get("prediction_mode", "absolute")
    if prediction_mode != source_manifest.get("prediction_mode"):
        raise ValueError("Baseline metadata and manifest disagree on prediction mode.")
    offset = prediction_offset(arrays, config["target"], prediction_mode)
    model_y = y - offset
    samples = pd.read_csv(source / "predictions.csv", parse_dates=["origin", "target_time"])
    np.testing.assert_allclose(samples.target, y)
    np.testing.assert_array_equal(samples.split, split)
    np.testing.assert_array_equal(samples.origin.to_numpy(), arrays["origin"])
    np.testing.assert_array_equal(samples.target_time.to_numpy(), arrays["target_time"])
    # Plot the exact original source; reject changed inputs rather than mixing runs.
    source_files = list(source_manifest["files"])
    for filename in source_files:
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != source_manifest["files"][filename]:
            raise ValueError(f"Baseline source file changed: {filename}")
    load_paths = source_files[:5] if len(source_files) >= 6 else source_files[:2]
    _, raw = load_source(*load_paths)
    spaces = {
        "ridge": [{"alpha": float(a)} for a in np.logspace(-3, 6, 16)],
        "random_forest": list(ParameterSampler({"n_estimators": [200, 400], "max_depth": [3, 5, 8, 12, None],
            "min_samples_leaf": [1, 3, 6, 12], "max_features": [0.5, 0.8, 1.0]}, n_iter=args.tree_trials, random_state=42)),
        "xgboost": list(ParameterSampler({"n_estimators": [100, 250, 500], "max_depth": [1, 2, 3, 5],
            "learning_rate": [0.015, 0.04, 0.08], "min_child_weight": [1, 5, 15],
            "subsample": [0.7, 1.0], "colsample_bytree": [0.7, 1.0],
            "reg_lambda": [1., 10., 50.], "reg_alpha": [0., 0.1, 1.]}, n_iter=args.xgb_trials, random_state=42)),
    }
    output.mkdir(parents=True, exist_ok=True)
    summaries, trials, chosen, predictions = [], [], [], {}
    constant = np.ptp(model_y[train]) == 0
    for key in args.algorithms:
        algorithm = ALGORITHMS[key]
        print(f"Tuning {config['name']}: {algorithm}", flush=True)
        filename = "lstm.pt" if key == "lstm" else key + ".joblib"
        if key == "lstm":
            best_prediction = samples[algorithm].to_numpy()
            best = mean_squared_error(y[val], best_prediction[val])
            shutil.copy2(source / filename, output / filename)
            best_settings = {"candidate": "baseline"}
            trials.append({"algorithm": algorithm, "candidate": "baseline", "validation_mse": best})
            settings_list = [] if constant else [(12, .001, 0.), (24, .001, .0001),
                (48, .001, .0001), (12, .003, .001), (48, .003, .001)]
            for i, (hidden, lr, decay) in enumerate(settings_list):
                settings = {"hidden": hidden, "learning_rate": lr, "weight_decay": decay, "epochs": args.epochs}
                prefix = f"lstm_candidate_{i}_"
                raw_prediction, history = train_lstm(X, model_y, split, output, epochs=args.epochs,
                    hidden=hidden, learning_rate=lr, weight_decay=decay, prefix=prefix)
                predicted = raw_prediction + offset
                pd.DataFrame(history).to_csv(output / f"{prefix}loss.csv", index=False)
                score = mean_squared_error(y[val], predicted[val])
                print(f"  LSTM candidate {i + 1}/{len(settings_list)}: validation MSE={score:.8g}", flush=True)
                trials.append({"algorithm": algorithm, "candidate": i, "parameters": json.dumps(settings), "validation_mse": score})
                if score < best:
                    best, best_prediction, best_settings = score, predicted, settings
                    shutil.copy2(output / f"{prefix}lstm.pt", output / filename)
        else:
            best_model = joblib.load(source / filename)
            best_prediction = best_model.predict(flat) + offset
            best = mean_squared_error(y[val], best_prediction[val])
            trials.append({"algorithm": algorithm, "candidate": "baseline", "validation_mse": best})
            for i, settings in enumerate([] if constant else spaces[key]):
                if key == "ridge": model = Ridge(**settings)
                elif key == "random_forest": model = RandomForestRegressor(**settings, random_state=42, n_jobs=2)
                else: model = XGBRegressor(**settings, objective="reg:squarederror", random_state=42, n_jobs=2)
                model.fit(flat[train], model_y[train])
                score = mean_squared_error(y[val], model.predict(flat[val]) + offset[val])
                print(f"  {algorithm} candidate {i + 1}/{len(spaces[key])}: validation MSE={score:.8g}", flush=True)
                trials.append({"algorithm": algorithm, "candidate": i, "parameters": json.dumps(settings), "validation_mse": score})
                if score < best:
                    best, best_model = score, model
            best_prediction = best_model.predict(flat) + offset
            best_settings = best_model.get_params()
            joblib.dump(best_model, output / filename)
            np.testing.assert_allclose(best_prediction, joblib.load(output / filename).predict(flat) + offset)
        if not np.isfinite(best_prediction).all():
            raise ValueError(f"Non-finite {algorithm} predictions")
        if key == "lstm":
            import torch
            from .lstm import SequenceRegressor
            saved = torch.load(output / filename, map_location="cpu", weights_only=True)
            restored = SequenceRegressor(saved["input_features"], saved["hidden"])
            restored.load_state_dict(saved["state_dict"])
            restored.eval()
            with torch.no_grad():
                reloaded = (restored(torch.tensor(X, dtype=torch.float32)).numpy()
                            * saved["target_scale"] + saved["target_center"] + offset)
            np.testing.assert_allclose(best_prediction, reloaded, rtol=1e-5, atol=1e-7)
        predictions[algorithm] = best_prediction
        chosen.append({"algorithm": algorithm, "parameters": best_settings, "validation_mse": best})
        for part in ("train", "validation", "test"):
            keep = split == part
            summaries.append({"model": config["name"], "target": config["target"], "unit": config["unit"],
                "algorithm": algorithm, "split": part, **metrics(y[keep], best_prediction[keep])})
        pd.DataFrame(trials).to_csv(output / "search_trials.csv", index=False)
    result = pd.DataFrame(summaries)
    forecasts = samples.drop(columns=list(ALGORITHMS.values()), errors="ignore")
    for algorithm, predicted in predictions.items(): forecasts[algorithm] = predicted
    forecasts.to_csv(output / "predictions.csv", index=False)
    result.to_csv(output / "metrics_summary.csv", index=False)
    result.to_csv(output / "metrics.csv", index=False)
    baseline = pd.read_csv(source / "metrics_summary.csv")
    comparison = baseline.merge(result, on=["model", "target", "unit", "algorithm", "split"],
        suffixes=("_before", "_tuned"), validate="one_to_one")
    comparison.to_csv(output / "comparison.csv", index=False)
    assert (comparison.loc[comparison.split.eq("validation"), "RMSE_tuned"].to_numpy()
        <= comparison.loc[comparison.split.eq("validation"), "RMSE_before"].to_numpy() + 1e-7).all()
    (output / "selected_parameters.json").write_text(json.dumps(chosen, indent=2, default=str), encoding="utf-8")
    np.savez_compressed(output / "preprocessing_and_sequences.npz", **arrays)
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    plot_training_report(raw, forecasts, predictions, result, config, output,
        train_start=source_manifest["train_start_inclusive"],
        train_end=source_manifest["train_end_exclusive"],
        test_start=source_manifest["test_start"],
        horizon_minutes=source_manifest["horizon_minutes"],
        step_minutes=source_manifest["origin_interval_minutes"])
    html = "<html><meta charset='utf-8'><title>Tuned forecast comparison</title><h1>Validation-only hyperparameter tuning</h1>"
    html += (f"<p>Frozen baseline sequences use {source_manifest['history_minutes']} minutes of input "
             f"to predict a {source_manifest['horizon_minutes']}-minute {prediction_mode} target. Parameters minimize "
             "validation MSE; test never selects models. Split figure displays only seven days. "
             "Training scores are in-sample.</p>")
    html += result.round(6).to_html(index=False)
    html += "<h2>Baseline versus tuned metrics</h2>" + comparison.round(6).to_html(index=False)
    for filename in ("dataset_split.png", "train_test_predictions.png", "metrics_comparison.png"):
        html += f"<img width='100%' src='{filename}'>"
    (output / "report.html").write_text(html + "</html>", encoding="utf-8")
    manifest = dict(source_manifest)
    manifest.update({"baseline_source": str(source), "arrays_sha256": hashlib.sha256(array_path.read_bytes()).hexdigest(),
        "selection": "minimum validation MSE including baseline candidate", "test_used_for_selection": False,
        "algorithms": args.algorithms, "max_lstm_epochs": args.epochs})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(result.loc[result.split.eq("test")].to_string(index=False), flush=True)
    print(f"Report: {output / 'report.html'}", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Flat baseline result directory for one parameter")
    parser.add_argument("--output", required=True, help="Separate flat result directory")
    parser.add_argument("--algorithms", nargs="+", choices=list(ALGORITHMS), default=list(ALGORITHMS))
    parser.add_argument("--epochs", type=int, default=100, help="Maximum LSTM epochs; validation early stopping applies")
    parser.add_argument("--tree-trials", type=int, default=24)
    parser.add_argument("--xgb-trials", type=int, default=32)
    args = parser.parse_args()
    if min(args.epochs, args.tree_trials, args.xgb_trials) < 1:
        parser.error("Epochs and trial counts must be positive")
    run(args)


if __name__ == "__main__":
    main()
