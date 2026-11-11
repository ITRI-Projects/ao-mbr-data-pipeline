# Cleaned data notebook

## General forecasting results

Open `06_multivariate_forecast_results.ipynb` for the latest saved expanded-history
and tuned experiments. It compares all four algorithms, reports training,
validation and fixed April 21–23 test metrics, and generates figures used by
`docs/forecast_results_slides.md`. It reads portable result snapshots from
`docs/assets/current_forecasts`; no retraining, SQL or Drive connection is needed.
Run all cells with a Python environment containing NumPy, pandas, matplotlib and
IPython. Rerunning replaces report figures and summary CSVs in that asset folder.

## SQL exploration setup

From the repository root, install the notebook dependencies and start Jupyter:

```bash
.venv/bin/python -m pip install -r notebooks/requirements.txt
.venv/bin/python -m jupyterlab notebooks/01_explore_clean_data.ipynb
```

Use the Python kernel from this environment. If using the VS Code notebook editor,
select `.venv/bin/python` as the kernel.

Configure the repository `.env` using `.env.example`. The notebook reuses
`src.database.get_connection()` to connect to `DB_SERVER` and `DB_NAME` and read
`dbo.CleanedSensorData`. The configured account needs SELECT permission on the
table. Install Microsoft ODBC Driver 18 for SQL Server separately from the Python
requirements.

Run the cells in order. The default query covers April 14–23, 2026. Set either
boundary to `None` to use the first or last available reading. The notebook
closes the SQL connection after loading and prepares the data using Notebook
02's sensor consolidation, limited forward fill, fault cleaning, and plots.
The final cell writes `sql_raw.csv`, `data_filled.csv`, and the four training
masks to `docs/raw/sql_server/` by default. Change `EXPORT_DIR` in the settings
cell to choose another location.

Clear notebook outputs before committing to keep sensor readings out of Git.

## Google Drive CSV notebook

`02_explore_google_drive_csv.ipynb` downloads the CSV configured by
`DRIVE_FILE_URL_OR_ID` in the repository `.env`. Install the dependencies in
`notebooks/requirements-drive.txt` and run the cells in order. The Drive CSV
must allow downloads.

Notebook 02 normalizes sensor aliases, combines paired A1/A2 tank readings,
and plots missingness. It reindexes to a minute grid, carries readings forward
for up to 10 minutes, reviews and cleans sensor faults, and plots original and
cleaned readings. The final cell writes the prepared CSV and four masks to
`docs/raw/`.

## Preparation strategy comparisons and forecasting (notebooks 03–05)

Notebooks 03, 04 and 05 use historical `data_filled.csv` and
`data_filled_mask.csv` exports from the earlier workflow. All three read the
minute-level exports directly and recover observations by masking filled cells.
No SQL history or prior 20-minute export is required. Notebook 03 forecasts
ammonium and nitrate; 04 forecasts A1/A2 methanol flows; 05 forecasts A1/A2 airflow.
The workbook-selected input audits are retained in notebooks 04 and 05.

The shared helper `src/preparation_experiments.py` compares 24 preparations:
raw, unlimited forward fill or five-minute age-limited inputs; 1/5/10/20-minute
input summaries; current-only or compact 1/3/6-hour lag representations; and
a fixed seven-day final training history (April 14–20). Input summaries use completed
past windows; age limits apply before aggregation. Each feature representation
includes measurement age and observation support. Fold-specific constant and
unobserved sensors are excluded; remaining missing inputs use training-only
median imputation and indicators.

Every strategy uses identical 20-minute forecast origins and the observed exact
minute reading one hour later as its label. This keeps the forecasting objective
fixed across aggregation strategies. It differs from the earlier minute-origin
experiment and from predicting future 20-minute averages. Strategy comparisons
must use the common labels from this run.

Select preparation and a screening algorithm (mean, Ridge or Extra Trees) by
mean validation RMSE on April 18–20, purging labels crossing fold boundaries.
Validation folds expand over four, five and six days within the training week.
Every final fit uses the seven-day April 14–20 training window. Test origins
are restricted so their one-hour targets also remain on April 23 or earlier;
the last scheduled origin is April 23 at 22:40, targeting 23:40. Thus each target
has 213 scheduled test origins rather than 216. Under the
selected preparation, also compare fixed XGBoost and Random Forest models plus
persistence. Additional algorithms and all-preparation test comparisons do not
change the validation-selected winner. Future targets are never imputed.

Long exact repeated runs are exported for review, without assuming that constant
plant setpoints are faults. Test metrics include a separate sensitivity excluding
targets after 60 consecutive identical observed minutes. Upstream fills cannot
be recovered when the source mask incorrectly marks them observed. Seven pre-test days are now loaded from SQL. Fourteen- and twenty-eight-day
training histories remain unavailable until earlier trustworthy observations are supplied.

Outputs live under `notebooks/data/preparation_strategies/effluent/`, `ch3oh/`
and `aeration/`. Each target directory contains validation rankings/folds,
all-preparation held-out forecasts and metrics, the selected preparation's
all-algorithm forecasts/metrics, selected feature names, train/test feature
matrices, fitted models and a forecast/overview plot. Group directories include
flat-signal audits, daily observation counts, unavailable-history reports,
source hashes and combined target metrics. The original exports and earlier
experiments stay unchanged. Models are reloaded to verify predictions.

Ammonium/nitrate units are mg-N/L, methanol flow m³/hour, and airflow m³/min.
These forecasts describe recorded flow; they do not prescribe operating settings.
Constant targets have undefined R². These dates were previously inspected;
a later independent period is required to confirm performance.

## XGBoost, LSTM and Ridge visual comparisons

Notebooks 03–05 now train the requested three-algorithm comparison after
training-only preparation screening. Install `notebooks/requirements.txt`.
For the CPU-only PyTorch build used for this run:

```bash
.venv/bin/python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
```

All algorithms receive identical 12-step historical sequences on the regular
20-minute origin grid. The selected preparation's values, age/support features
and lags are retained. LSTM processes steps in order; XGBoost/Ridge receive the
same sequence flattened. Per-sensor imputation/scaling and target scaling fit
training only; explicit per-step missingness channels are shared by all models.
LSTM uses 24 hidden units. A purged chronological tail inside the training week
selects epoch count (up to 80 with patience 12); the model is reset and refitted
on the full training sequences. Test data never controls early stopping. The
12-step warmup excludes initial origins without sufficient sequence context.

Each target's `comparison_xgb_lstm_ridge/` directory contains `forecasts.csv`,
`metrics.csv`, fitted models, preprocessing, sequence inputs, metadata and four
plots: an overlay with April 23 detail, separate panels for each algorithm,
MAE/RMSE bars and LSTM training loss. Stored models are reloaded to check their
predictions. Persistence and flat-signal sensitivity remain reference metrics.
The neural network is also trained for constant nitrate, whose R² is undefined;
any nonzero error is reported rather than hidden behind a constant fallback.

Open `notebooks/data/preparation_strategies/forecast_comparison_report.html`
for the six-target visual report. `algorithm_comparison_summary.csv` contains
all metrics for XGBoost, LSTM, Ridge and persistence. The older
`selected_strategy_summary.csv` describes preparation-screening models and is
separate from this identical-sequence algorithm comparison.

Notebook 01 exports `sql_raw.csv`, `sql_raw_grid.csv`, SQL-specific filled data
and mask, shared `data_filled.csv`/mask, and `data_source.json`. Notebook 02
exports `google_drive_download.csv` (original bytes), `google_drive_full_raw.csv`,
`google_drive_raw.csv`, raw aliases, filled data and masks separately. Its strict
auto parser accepts uniform ISO timestamps or day/month/year minute timestamps;
set an explicit `DATETIME_FORMAT` for another representation. SQL is selected
for this run: `EXPORT_SHARED_DATA = False` prevents the Drive notebook from
replacing SQL exports. The earlier inline Drive forecast section is centralized
in notebooks 03–05. Exploration figures are saved under
`notebooks/data/exploration_plots/01/` and `02/` during this rerun.

## Methanol dosing forecast training

Run `04_train_ch3oh_dosing.ipynb` using the shared preparation comparison above.
The workbook audit requires eleven checked inputs per stream, including current
methanol flow exactly once. Results go to `preparation_strategies/ch3oh/`.

## Aeration airflow forecast training

Run `05_train_aeration_flow.ipynb` using the same preparation comparison.
The workbook audit verifies nine A1 and ten A2 checked external inputs, plus a
separately identified current-airflow autoregressive input for each model.
Results go to `preparation_strategies/aeration/`.
