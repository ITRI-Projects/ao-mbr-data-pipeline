"""Verify fixed test labels, validation selection and serialized tuned models."""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch

from .lstm import SequenceRegressor


def main():
    torch.set_num_threads(2)
    old = Path("data/training/expanded_history_forecasts")
    new = Path("data/training/tuned_history_forecasts")
    original = pd.read_csv(old / "metrics_summary.csv")
    tuned = pd.read_csv(new / "metrics_summary.csv")
    joined = original.query("split == 'validation'").merge(
        tuned.query("split == 'validation'"), on=["model", "algorithm"], suffixes=("_old", "_new"), validate="one_to_one")
    assert len(joined) == len(original.query("split == 'validation'"))
    assert (joined.RMSE_new <= joined.RMSE_old + 1e-7).all(), "Validation error regressed"
    checks = []
    for name in tuned.model.unique():
        a = pd.read_csv(old / name / "predictions.csv")
        b = pd.read_csv(new / name / "predictions.csv")
        pd.testing.assert_frame_equal(a[["origin", "target_time", "split", "target"]],
                                      b[["origin", "target_time", "split", "target"]])
        with np.load(old / name / "preprocessing_and_sequences.npz") as arrays:
            X = np.concatenate([arrays["X"], arrays["missing"].astype(np.float32)], axis=2)
        flat = X.reshape(len(X), -1)
        for algorithm in ("Ridge", "Random Forest", "XGBoost"):
            model = joblib.load(new / name / (algorithm.lower().replace(" ", "_") + ".joblib"))
            np.testing.assert_allclose(model.predict(flat), b[algorithm], rtol=1e-5, atol=1e-6)
        saved = torch.load(new / name / "lstm.pt", map_location="cpu", weights_only=True)
        model = SequenceRegressor(saved["input_features"], saved["hidden"])
        model.load_state_dict(saved["state_dict"])
        model.eval()
        with torch.no_grad():
            predicted = model(torch.tensor(X)).numpy() * saved["target_scale"] + saved["target_center"]
        np.testing.assert_allclose(predicted, b.LSTM, rtol=1e-5, atol=1e-6)
        checks.append(name)
    selected = pd.read_csv(new / "validation_selected_models.csv")
    for name, group in tuned.query("split == 'validation'").groupby("model"):
        winner = group.loc[group.RMSE.idxmin(), "algorithm"]
        assert selected.loc[selected.model.eq(name), "algorithm"].eq(winner).all()
    report = {"targets_verified": checks, "all_sample_labels_and_splits_unchanged": True,
              "validation_error_nonincreasing_for_every_model": True,
              "serialized_models_reproduce_predictions": True,
              "algorithm_selection_matches_validation_only": True}
    (new / "verification.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
