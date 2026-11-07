# Python forecasting training

Run from the repository root (no training notebook required):

```bash
python -m pip install -r src/training/requirements.txt
python -m src.training.train
```

The defaults consume `docs/raw/data_filled.csv` plus the fill, sensor-fault,
short-error-replacement, and synchronized-corruption masks exported by notebook
02. Filled, faulty, and repaired values cannot become future measured labels.
Synchronized corrupt intervals are restored as gaps on the minute grid, and any
forecast sequence or label touching them is excluded. Input preparation is used
as exported: the trainer does not apply another uniform fill policy.

`Sensor_Configurations.xlsx` supplies the six prediction groups, checkmarked
inputs, aliases (falling back to the source column for airflow) and units.
The owner confirmed that the airflow targets should follow the headings:
A1 = `A1_Q_air`, A2 = `A2_Q_air`. Their inconsistent green workbook marks are
recorded in the exported audit rather than changing the workbook. Current target
history is added once as an explicit autoregressive input. Sensors removed from
the cleaned CSV are removed from workbook feature lists; a model is skipped when
its target was removed. Other constant, unobserved, or unsampled training inputs
are excluded and recorded in each model metadata.

All four algorithms receive identical 12-step sequences at 20-minute origins
and exact observed labels 60 minutes later. LSTM uses the ordered sequences;
Ridge, Random Forest and XGBoost use the same sequences flattened. Missingness
and source-quality channels accompany training-only imputation and scaling. LSTM target scaling
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

Tune one saved single-parameter run into a separate flat result directory:

```bash
python -m src.training.tune --source data/training/effluent_ammonia_full_history --output data/training/effluent_ammonia_tuned
```

The defaults search 16 Ridge, 24 Random Forest, 32 XGBoost, and five LSTM
configurations (up to 100 epochs with validation early stopping), in addition to
the existing baseline models. The training sequences, preprocessing, labels, and
chronological splits are frozen. Selection minimizes validation MSE. Test scores
do not select parameters. The original training results are preserved.

Tune one algorithm with `--algorithms ridge`, `--algorithms random_forest`,
`--algorithms xgboost`, or `--algorithms lstm`. Use a distinct output directory for
each run. `--epochs`, `--tree-trials`, and `--xgb-trials` control search cost.

Outputs include `report.html`, `predictions.csv`, `metrics_summary.csv`,
`comparison.csv` (baseline versus tuned scores), `search_trials.csv`,
`selected_parameters.json`, selected fitted models, frozen sequences, source
metadata and hashes, and split/prediction/metric comparison plots. LSTM candidate
checkpoints and losses use flat prefixed filenames. No subfolders are created.
The split plot shows only seven days; training still uses all baseline history.

## Effluent ammonia from the full Drive history

Run the four-model comparison on the notebook 02 output:

```bash
python -m src.training.train --targets eff_nh3_n --output data/training/effluent_ammonia_full_history
```

The matching masks remove forward-filled, faulty, and repaired estimates from
future labels while retaining eligible prepared inputs and their quality flags. Training uses available
history before April 18; validation covers April 18-20; rolling held-out forecasts
cover April 21-23. All algorithms use the same 12-step sequences, 20-minute origins,
and exact observed one-hour-ahead targets. Validation selects model settings.

`forecast_dataset.plot_training_report` generates `dataset_split.png` (compact final-seven-day observed
series with train/validation/test line colors; display window only), `train_test_predictions.png` (one row per
algorithm, with train/validation/test columns), and `metrics_comparison.png`
(MAE, RMSE, R2 across all splits). The HTML report includes these figures and the
complete metric table. Training plots/scores are in-sample fits. Missing observed
labels remain gaps in forecast plots. This entry point trains models;
`python -m src.training.forecast_dataset` still only exports input datasets.

Results are written directly into the selected `--output` directory without
parameter subfolders. A single-target run uses plain filenames such as
`predictions.csv`, `ridge.joblib`, and `dataset_split.png`. When multiple targets
are requested together, target names prefix per-target filenames to avoid
collisions. The dataset split figure displays only the final seven days (April
17-23 for the current source). This display window does not restrict training,
preprocessing, metrics, or the other forecast plots.
