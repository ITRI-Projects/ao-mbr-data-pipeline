# Python forecasting training

Run from the repository root (no training notebook required):

```bash
python -m pip install -r src/training/requirements.txt
python -m src.training.train
```

The defaults consume `notebooks/data/data_filled.csv` and
`notebooks/data/data_filled_mask.csv` exported by notebook 02. The mask is required
so filled estimates cannot become future measured labels. Input preparation is
used as exported: the trainer does not apply another uniform fill policy.

`Sensor_Configurations.xlsx` supplies the six prediction groups, checkmarked
inputs, aliases (falling back to the source column for airflow) and units.
The owner confirmed that the airflow targets should follow the headings:
A1 = `Q_A1_air`, A2 = `Q_A2_air`. Their inconsistent green workbook marks are
recorded in the exported audit rather than changing the workbook. Current target
history is added once as an explicit autoregressive input. Constant, unobserved
or unsampled training inputs are excluded and recorded in each model metadata.

All four algorithms receive identical 12-step sequences at 20-minute origins
and exact observed labels 60 minutes later. LSTM uses the ordered sequences;
Ridge, Random Forest and XGBoost use the same sequences flattened. Missingness
channels accompany training-only imputation and scaling. LSTM target scaling
also fits training only. Future labels crossing split boundaries are purged.

Defaults train on April 14-17, validate on April 18-20 and test on April 21-23.
Validation selects Ridge regularization, tree depth, and LSTM epoch count
(maximum 60, patience 12). Models retain their training-only fits; there is no
subsequent combined train/validation refit. Test observations can enter later
rolling forecast histories when they have become available. This is not a
single forecast of all three days made at the test boundary.

Outputs in `data/training/workbook_forecasts/`:

- `report.html`: metrics table, chronological split and per-algorithm train/test plots.
- `metrics_summary.csv` and `.png`: MAE, RMSE and R2 (undefined for constant labels).
- `workbook_feature_audit.csv` and `manifest.json`: input choices, corrections,
  source hashes, package versions, split definitions and seed.
- Each target directory: predictions with origin/label times and split,
  metrics, training/test and dataset-split plots, LSTM loss plot/history,
  models, preprocessing/sequence arrays and selection metadata.

Stored models are reloaded and their predictions checked during each run.
Re-running replaces files in the selected output directory. Predictions remain
in original target units. Train metrics are in-sample fits, not forecast skill
estimates. Constant nitrate and the short previously inspected period limit
interpretation; use a later independent period to confirm generalization.

Examples:

```bash
python -m src.training.train --targets eff_nh3_n a1_air_flow --epochs 40
python -m src.training.train --data path/data_filled.csv --mask path/data_filled_mask.csv --output data/training/another_run
```

Modules: `workbook.py` reads the feature matrix; `train.py` orchestrates models
and reporting; `lstm.py` implements the CPU sequence model;
`forecast_dataset.py` builds leakage-controlled sequences; `sensor_preparation.py`
and `training_data.py` provide exploration/preparation utilities. The old
notebook-only `preparation_experiments` and `dataset_review` helpers are not needed.

## Expanded historical comparison

The local full CSV snapshot starts March 24, 2026 at 13:00. Prepare that history
with the same sensor-specific fill limits as notebook 02, then train separately:

```bash
python -m src.training.expand_history
python -m src.training.train --data data/training/expanded_history_inputs/data_filled.csv --mask data/training/expanded_history_inputs/data_filled_mask.csv --output data/training/expanded_history_forecasts
python -m src.training.compare_history
```

Training ends before April 18; validation remains April 18–20 and test remains
April 21–23. Preparation asserts that all test-minute inputs and fill masks
equal the original exports before writing. The original short-window data and
model outputs are preserved. Workbook features, algorithms, sequence length,
forecast horizon and hyperparameter search remain the same for comparison.
The comparison checks that test forecast origins and observed labels match and
exports `history_comparison.csv` beside the expanded report. Positive improvement
percentages mean lower error. Historical inputs can alter training-only feature
eligibility and scaling; these are recomputed without using test observations.

## Validation-based hyperparameter tuning

After the expanded run, execute `python -m src.training.tune`. This reuses the
frozen expanded arrays and chronological splits, searching 16 Ridge, 24 Random
Forest, 32 XGBoost and five LSTM configurations per varying target. The existing
fitted model is also a candidate. LSTM searches hidden width, learning rate and
weight decay with up to 100 epochs and validation early stopping. Constant
training targets retain existing models because their R2 cannot be optimized.

Selection minimizes April 18–20 validation MSE, equivalent to maximizing R2 for
the same nonconstant validation labels. April 21–23 test results never choose
parameters or algorithms. Training-only preprocessing remains frozen; models
are not refitted on validation. Results, search trials, selected parameters,
before/after comparisons and plots are saved in
`data/training/tuned_history_forecasts/`. The report selects each target's
algorithm by validation error, not by test performance. The already inspected
test period should be followed by a new independent evaluation period.
Run `python -m src.training.audit_tuning` to verify unchanged labels/splits,
nonincreasing validation error, validation-only algorithm choices and predictions
from the serialized models. Results are saved as `verification.json`.

For the workspace-local Windows dependency installation used during verification,
start a PowerShell session at the repository root and run:

```powershell
$env:PYTHONPATH = (Resolve-Path .training-deps).ProviderPath
python -m src.training.train
```

The `.training-deps/` folder is ignored by Git and leaves the global Python
installation unchanged. WSL/Linux should install the requirements in `.venv`
instead; Windows binary packages in `.training-deps/` cannot be used under WSL.

