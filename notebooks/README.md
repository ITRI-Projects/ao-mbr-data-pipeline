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

Run the cells in order. Optional start/end timestamps restrict the query;
otherwise it loads the entire table into memory. The resulting `df` has a
sorted datetime index and one column per sensor. Connections are closed after
loading, and no database writes are performed.

Clear notebook outputs before committing to keep sensor readings out of Git.

## Google Drive CSV notebook

`02_explore_google_drive_csv.ipynb` prepares sensor history without SQL Server.
Install `notebooks/requirements-drive.txt`, configure `DRIVE_FILE_URL_OR_ID` in
`.env`, and run the notebook in order. The Drive CSV must allow downloading.
Alternatively, set `LOCAL_CSV_PATH` to a saved snapshot for offline execution.

`START_TIME = None` and `END_TIME = None` select the first through last available
source minute. Explicit boundaries select an inclusive subset. The source is
validated for unique, timezone-naive, minute-aligned timestamps and numeric finite
readings (or blanks). Uniform ISO timestamps and day/month/year minute timestamps
are supported. The complete source remains in `full_source_df`.

Preparation follows notebook 01: reindex to the complete minute grid and forward
fill independently per sensor with no gap-length limit. Recorded values and zeros
are preserved. Leading gaps and entirely unobserved sensors remain null. No
backfill, donor replacement, smoothing, clipping, or automatic outlier deletion is
applied. Coverage audits distinguish absent minutes from null values in existing
rows. Bilingual raw and filled plots retain the full selected timeline. April
21–23 shading is retained for historical test context; it does not limit the
preparation window. Sensor behavior review uses only observations before April 21.

The export cell writes alias-named `data_filled.csv`, `data_filled_mask.csv`, and
`data_filled_summary.csv` to `notebooks/data/`. These replace
any existing shared exports. Both data and Boolean masks are reloaded and checked.
Future forecast labels must use observed values recovered with the matching mask.

Reproducibility files in `notebooks/data/` include original CSV bytes in
`google_drive_download.csv`, full numeric source in `google_drive_full_raw.csv`,
selected original-tag observations in `google_drive_raw.csv`, the alias-named raw
minute grid in `google_drive_raw_grid.csv`, daily coverage in
`google_drive_window_coverage.csv`, and source hash, coverage, alias mapping and
fill policy in `data_source.json`. The remote Drive file is unchanged.

The notebook auto-detects a CJK font. Override `CJK_FONT` or `CJK_FONT_PATH` if
needed; on Windows Microsoft JhengHei is normally available. The executed notebook
contains source readings and plots; clear outputs before committing if required.

## Restarted SQL dataset review (notebook 01)

Notebook 01 loads April 14–23 using inclusive minute boundaries:
`START_TIME = "2026-04-14 00:00:00"` and
`END_TIME = "2026-04-23 23:59:00"`. This retains seven training days (April
14–20) plus three test days (April 21–23), not seven total source days.
Run through the daily missingness and sensor time-series plots first.
The notebook shows null counts/percentages per sensor, daily null counts, and
absent source minutes separately. Sensor plots retain the entire ten-day axis
and show gaps without filling readings.

The next section uses unlimited forward filling per sensor across the full
one-minute grid, including missing source timestamps. `df_filled` holds the
result while `df` stays raw; `df_fill_mask` marks estimated cells. `fill_summary`
reports filled source nulls, fills at absent minutes, and remaining nulls.
Daily count tables, stacked bars and observed/filled timelines show the effect.
Leading gaps and entirely unobserved sensors remain null because no readings
before `START_TIME` are loaded to seed them. Filled future targets must not be
used as measured labels. Run the save cell after the audit to replace `notebooks/data/data_filled.csv`,
`data_filled_mask.csv` and `data_filled_summary.csv` with the current window.
The data and Boolean estimate mask share a `datetime` index and sensor columns,
as expected by notebook 03. Notebooks 04–05 use separate 20-minute aggregates.


The coverage/target audit works on the configured ten-day source window. The later
original-source query and historical benchmark are skipped by default via
`RUN_HISTORICAL_REVIEW = False`. To repeat the earlier 3/7/14/21-day benchmark,
use a separate longer-history configuration (including adjusting the source-window validation) covering March 28 onward, then enable the switch. The findings
below describe that previous full-history run.
Two causal input policies are compared: operational forward filling and a
five-minute maximum measurement age. No historical MLSS donor is used. Constant
and entirely unobserved sensors are excluded using training observations only.
Future labels always use observed values.

Ridge, compact Extra Trees and a mean-only reference screen the candidates using
April 18–20 validation days. Each fold purges labels crossing its training boundary
and confines validation labels to that day. Candidate selection never uses April
21–23 scores. Once selected, the benchmark is evaluated on available measured test
labels. Constant nitrate R² is explicitly undefined.

A separate original-source audit reads `dbo.T02_08A_SCADA`. It found 802 original
effluent observations on April 23 (through 13:25), absent from the cleaned table,
and negative original ammonia concentrations requiring review. Original and
cleaned targets are exported separately and are not mixed as ground truth.

Audit tables, candidate rankings, selected raw data and model-input matrices,
predictions, screening models, source comparisons and metadata are exported to
`notebooks/data/dataset_review/`. Existing `data_filled.csv`, its mask and earlier
model runs stay unchanged. Notebook 03 still points to the prior experiment;
review outputs require an explicit subsequent training update.

## Preparation strategy comparisons and forecasting (notebooks 03–05)

Run notebooks 03, 04 and 05 after exporting the shared `data_filled.csv` and
Boolean `data_filled_mask.csv` from notebook 01 or 02. All three read the
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
