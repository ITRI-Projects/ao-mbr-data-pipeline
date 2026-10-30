"""Compare fixed-test predictions from the original and expanded runs."""
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    root = Path("data/training")
    old = root / "workbook_forecasts"
    new = root / "expanded_history_forecasts"
    before = pd.read_csv(old / "metrics_summary.csv").query("split == 'test'")
    after = pd.read_csv(new / "metrics_summary.csv").query("split == 'test'")
    for target in after.model.unique():
        a = pd.read_csv(old / target / "predictions.csv").query("split == 'test'")
        b = pd.read_csv(new / target / "predictions.csv").query("split == 'test'")
        pd.testing.assert_frame_equal(a[["origin", "target_time", "target"]].reset_index(drop=True),
                                      b[["origin", "target_time", "target"]].reset_index(drop=True))
    joined = before.merge(after, on=["model", "target", "algorithm", "split", "unit"], suffixes=("_original", "_expanded"), validate="one_to_one")
    for metric in ("MAE", "RMSE"):
        joined[f"{metric}_improvement_pct"] = np.where(
            joined[f"{metric}_original"].ne(0),
            100 * (1 - joined[f"{metric}_expanded"] / joined[f"{metric}_original"]), np.nan)
    joined.to_csv(new / "history_comparison.csv", index=False)
    best = after.loc[after.groupby("model").RMSE.idxmin()]
    print("Test origins and observed labels match the original run for all targets.")
    print(best[["model", "algorithm", "n", "MAE", "RMSE", "R2"]].to_string(index=False))


if __name__ == "__main__":
    main()
