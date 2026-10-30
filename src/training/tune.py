"""Tune on April 18–20 only, using frozen expanded-history arrays and splits."""
import json
import hashlib
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
from .train import metrics, plot_forecasts


def main():
    source = Path("data/training/expanded_history_forecasts")
    output = Path("data/training/tuned_history_forecasts")
    output.mkdir(parents=True, exist_ok=True)
    summary, trials, chosen = [], [], []
    manifest = {"selection": "minimum validation MSE, equivalent to maximum R2 for a fixed nonconstant validation target",
                "test_used_for_selection": False, "seed": 42, "source": str(source), "arrays_sha256": {}}
    for folder in sorted(source.iterdir()):
        if not (folder / "preprocessing_and_sequences.npz").exists():
            continue
        name = folder.name
        print(f"Tuning {name}", flush=True)
        dest = output / name
        dest.mkdir(exist_ok=True)
        array_path = folder / "preprocessing_and_sequences.npz"
        manifest["arrays_sha256"][name] = hashlib.sha256(array_path.read_bytes()).hexdigest()
        with np.load(array_path) as arrays:
            X = np.concatenate([arrays["X"], arrays["missing"].astype(np.float32)], axis=2)
            y, split = arrays["y"], arrays["split"]
        train, val = split == "train", split == "validation"
        flat = X.reshape(len(X), -1)
        samples = pd.read_csv(folder / "predictions.csv", parse_dates=["origin", "target_time"])
        metadata = json.loads((folder / "metadata.json").read_text())
        config = metadata["workbook"]
        predictions = {}
        # Include each existing fitted model so validation performance cannot regress.
        spaces = {
            "Ridge": [{"alpha": float(a)} for a in np.logspace(-3, 6, 16)],
            "Random Forest": list(ParameterSampler({"n_estimators": [200, 400], "max_depth": [3, 5, 8, 12, None],
                "min_samples_leaf": [1, 3, 6, 12], "max_features": [0.5, 0.8, 1.0]}, n_iter=24, random_state=42)),
            "XGBoost": list(ParameterSampler({"n_estimators": [100, 250, 500], "max_depth": [1, 2, 3, 5],
                "learning_rate": [0.015, 0.04, 0.08], "min_child_weight": [1, 5, 15],
                "subsample": [0.7, 1.0], "colsample_bytree": [0.7, 1.0],
                "reg_lambda": [1., 10., 50.], "reg_alpha": [0., 0.1, 1.]}, n_iter=32, random_state=42))}
        constant = np.ptp(y[train]) == 0
        for algorithm, params in spaces.items():
            filename = algorithm.lower().replace(" ", "_") + ".joblib"
            best_model = joblib.load(folder / filename)
            best = mean_squared_error(y[val], best_model.predict(flat[val]))
            trials.append({"model": name, "algorithm": algorithm, "candidate": "existing", "validation_mse": best})
            for i, settings in enumerate([] if constant else params):
                if algorithm == "Ridge":
                    model = Ridge(**settings)
                elif algorithm == "Random Forest":
                    model = RandomForestRegressor(**settings, random_state=42, n_jobs=2)
                else:
                    model = XGBRegressor(**settings, objective="reg:squarederror", random_state=42, n_jobs=2)
                model.fit(flat[train], y[train])
                score = mean_squared_error(y[val], model.predict(flat[val]))
                trials.append({"model": name, "algorithm": algorithm, "candidate": i,
                               "parameters": json.dumps(settings), "validation_mse": score})
                if score < best:
                    best, best_model = score, model
            joblib.dump(best_model, dest / filename)
            predictions[algorithm] = best_model.predict(flat)
            np.testing.assert_allclose(predictions[algorithm], joblib.load(dest / filename).predict(flat))
            chosen.append({"model": name, "algorithm": algorithm, "parameters": best_model.get_params(), "validation_mse": best})
        # Default LSTM is retained as a candidate; tune width, learning rate and regularization.
        import shutil
        best_prediction = samples["LSTM"].to_numpy()
        best = mean_squared_error(y[val], best_prediction[val])
        trials.append({"model": name, "algorithm": "LSTM", "candidate": "existing", "validation_mse": best})
        shutil.copy2(folder / "lstm.pt", dest / "lstm.pt")
        winner = {"candidate": "existing"}
        lstm_settings = [] if constant else [(12, .001, 0.), (24, .001, .0001), (48, .001, .0001), (12, .003, .001), (48, .003, .001)]
        for i, (hidden, lr, decay) in enumerate(lstm_settings):
            candidate = dest / f"lstm_candidate_{i}"
            candidate.mkdir(exist_ok=True)
            predicted, history = train_lstm(X, y, split, candidate, epochs=100, hidden=hidden,
                                            learning_rate=lr, weight_decay=decay)
            score = mean_squared_error(y[val], predicted[val])
            settings = {"hidden": hidden, "learning_rate": lr, "weight_decay": decay, "max_epochs": 100}
            pd.DataFrame(history).to_csv(candidate / "loss.csv", index=False)
            trials.append({"model": name, "algorithm": "LSTM", "candidate": i, "parameters": json.dumps(settings), "validation_mse": score})
            if score < best:
                best, best_prediction, winner = score, predicted, settings
                shutil.copy2(candidate / "lstm.pt", dest / "lstm.pt")
        predictions["LSTM"] = best_prediction
        chosen.append({"model": name, "algorithm": "LSTM", "parameters": winner, "validation_mse": best})
        for algorithm, predicted in predictions.items():
            samples[algorithm] = predicted
            for part in ("train", "validation", "test"):
                keep = split == part
                summary.append({"model": name, "target": config["target"], "unit": config["unit"],
                                "algorithm": algorithm, "split": part, **metrics(y[keep], predicted[keep])})
        samples.to_csv(dest / "predictions.csv", index=False)
        plot_forecasts(samples, predictions, config, dest)
        pd.DataFrame(summary).to_csv(output / "metrics_summary.csv", index=False)
        pd.DataFrame(trials).to_csv(output / "search_trials.csv", index=False)
        (output / "selected_parameters.json").write_text(json.dumps(chosen, indent=2, default=str))
    result = pd.DataFrame(summary)
    baseline = pd.read_csv(source / "metrics_summary.csv")
    comparison = baseline.merge(result, on=["model", "target", "unit", "algorithm", "split"], suffixes=("_before", "_tuned"), validate="one_to_one")
    comparison.to_csv(output / "comparison.csv", index=False)
    # Choose the algorithm by validation, never by the test result.
    validation = result.query("split == 'validation'")
    winners = validation.loc[validation.groupby("model").RMSE.idxmin(), ["model", "algorithm"]]
    selected = result.merge(winners, on=["model", "algorithm"])
    selected.to_csv(output / "validation_selected_models.csv", index=False)
    html = "<html><meta charset='utf-8'><h1>Validation-selected hyperparameter tuning</h1><p>Training ends April 17. Validation April 18–20. Fixed test April 21–23. Test results never select parameters or algorithms. Constant targets have undefined R2. This test period has already been inspected; a later independent period is needed for confirmation.</p>"
    html += selected.to_html(index=False)
    for name in winners.model:
        html += f"<h2>{name}</h2><img width='100%' src='{name}/train_test_predictions.png'>"
    (output / "report.html").write_text(html + "</html>")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(selected.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
