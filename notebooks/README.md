# Cleaned data notebook

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

`02_explore_google_drive_csv.ipynb` provides the same inspections and charts using
a CSV stored on Google Drive. It runs independently of SQL Server and reads its
Drive configuration from the repository's `.env`.

```bash
.venv/bin/python -m pip install -r notebooks/requirements-drive.txt
.venv/bin/python -m jupyterlab notebooks/02_explore_google_drive_csv.ipynb
```

Set the file's share link or ID in the repository's `.env` (also shown in
`.env.example`):

```dotenv
DRIVE_FILE_URL_OR_ID="https://drive.google.com/file/d/YOUR_FILE_ID/view"
```

The file must allow downloads for **Anyone with the link**. The notebook uses
[gdown](https://github.com/wkentaro/gdown) to handle Drive's download pages.
No access-mode setting, Google sign-in, or Google Cloud setup is needed.
The `.env` file is Git-ignored. After changing it, rerun the import and
configuration cells so the notebook reloads the value. In the notebook's configuration cell, set
`TIMESTAMP_COLUMN` to the CSV's timestamp header (default: `datetime`). Timestamp
header matching ignores capitalization and surrounding whitespace, so `DateTime`
also works with the default. Multiple matching timestamp headers are rejected.
The remaining columns should be numeric sensor readings; blanks remain missing
in the original `df`. `START_TIME` and `END_TIME` filter the downloaded data,
with an inclusive start and exclusive end. Each load
downloads the current CSV in full, so the file must fit in memory. The notebook
reads an uploaded CSV, not a Google Sheets document.

The notebook reports missing readings and plots each sensor over time. It also
validates and plots `70mlssa2aerobic` separately, showing a message when that
column has no recorded values in the selected window. An earlier example
interpolates short gaps in `70coda1inf` for comparison.

The **A2 aerobic tank: MLSS and surrounding parameters** cell follows the
bilingual sensor plots. It shows MLSS, DO, ORP, pH, and aeration airflow on a
shared time axis with larger bilingual labels and valid/missing counts. An
entirely missing sensor is explicitly marked without substituting zero readings.
Adjust `A2_FONT_SIZE` and `A2_FIGSIZE` for presentation, or set
`SAVE_A2_FIGURE = False` to display only. By default it saves a 200-DPI image to
`notebooks/data/a2_aerobic_sensor_context.png`; rerunning replaces that image.

Run the final gap-aware cell after loading `df` to create `df_filled` for all
sensor columns. It uses time-based linear interpolation only for interior gaps
of up to three rows, with observed endpoints no more than four minutes apart,
in columns with less than 20% missing readings. Flow columns also require the
readings on both sides of a gap to have the same zero, positive, or negative
state. Columns with recurring high missingness and columns with no observations
retain their nulls; these need valve-state or other operational evidence before
values can be assigned. The 20% cutoff reflects the current window's distinct
gap patterns and should be reviewed for other windows.

`df_filled` keeps the same index and columns as `df`, and `df` is unchanged.
`df_fill_mask` marks estimated cells, while `fill_summary` shows the policy,
gap counts, and before/after null counts per sensor. `df_filled` can still
contain nulls. Rerun the load and fill cells after changing the date window.

Run the final export cell to save `df_filled` as
`notebooks/data/google_drive_filled.csv`. It creates the directory if needed
and includes the datetime index as a `datetime` column. Remaining nulls are
written as blank fields. Edit `EXPORT_PATH` to choose a different filename;
rerunning the cell replaces the file at that path. The existing `data/` ignore
rule keeps this local export out of Git. The Google Drive source stays unchanged.

Clear notebook outputs before committing to keep sensor readings out of Git.

The Google Drive sensor plots show English and Traditional Chinese together.
The plot cell preserves `CJK_FONT` from earlier cells and registers Windows
Microsoft JhengHei automatically under WSL. For other setups, set a font file
path before running the plot cell:

```python
CJK_FONT_PATH = "/mnt/c/Windows/Fonts/msjh.ttc"  # WSL
# CJK_FONT_PATH = r"C:\Windows\Fonts\msjh.ttc"   # Windows kernel
```

The file must exist on the machine running the Python kernel. The cell prints
the selected font file and checks its Chinese glyph coverage. Fonts are
registered immediately using
[Matplotlib's font manager](https://matplotlib.org/stable/api/font_manager_api.html);
there is no need to restart the kernel. If a requested font name is unavailable,
set `CJK_FONT_PATH` to a Traditional Chinese font file accessible to the kernel.

## Seven-day database training candidate

Run notebook 01 from the top with both exploration boundaries set to `None`.
The final sections rank every full seven-day interval after applying notebook
02's conservative gap rules to SQL sensor aliases. Six configured targets remain
observed-only, and interpolation brackets cannot cross the candidate boundaries.
The selected minute-level dataset is exported to `notebooks/data/data_filled.csv`,
with an imputation mask, per-column summary, model coverage and window rankings.
Long gaps remain null. A separate `data_filled_20min.csv` averages raw observations
only, with bin-end availability timestamps and an observed-count companion CSV.

Retrospective interpolation uses future observations: split raw data chronologically
before filling, and wait for right-hand observations before using estimates online.
The coverage ranking establishes completeness, not forecast accuracy. The notebook
reports whether configured models have complete inputs and whether aggregation is
needed to obtain a complete training candidate.

## Effluent forecast training

Run `03_train_effluent_nh3_no3.ipynb` after notebook 01. It reads
`data_filled_20min.csv` and its observed-count companion, using SQL aliases.
Both effluent XGBoost models predict the mean in the bin ending one hour after
the forecast origin. The latest 20% of origins form the test set; training
labels unavailable at the first test origin are purged. Compare held-out
predictions with one-hour persistence before judging model usefulness.

Models, predictions, metrics, split diagnostics, plots and source hashes are
saved to `notebooks/data/effluent_training_20min/`. Saved models are fitted only
on the training split. The current constant NO3 target cannot demonstrate skill
on changing nitrate levels. This seven-day, completeness-selected experiment
requires evaluation on a separate later period before deployment.

The comparison sections also fit Random Forest, Extra Trees and a scaled Ridge
regression pipeline on the same training examples. Tables compare all four
algorithms with persistence using identical held-out targets. Test-only and
train/test overview plots use consistent model colors and highlight split regions.
Comparison metrics, predictions, parameters and additional models are saved beside
the XGBoost artifacts. No parameters are tuned on the test set; reserve a new later
period for unbiased evaluation after comparing algorithms on this holdout.

## Google Drive forecast comparison

Notebook 02 now includes the same XGBoost, Random Forest, Extra Trees, Ridge and
persistence comparison, following its exploration/export sections. Install
`notebooks/requirements-drive.txt` in the notebook's environment. On Windows:

```powershell
.venv\Scripts\python.exe -m pip install -r notebooks/requirements-drive.txt
```

Set `DRIVE_FILE_URL_OR_ID` in `.env`, choose the date window, and run the notebook
in order. Full-tag CSV headers are mapped to configured sensor aliases. Training
uses raw observed 20-minute means, with bin-end availability and one-hour future
labels. Input gaps are handled inside training-only median-imputation pipelines;
future targets remain observed-only. Short or sparse source coverage is reported.

Both test-only and train/test overview plots use English/Traditional Chinese
labels, consistent estimator colors, and shaded train/purge/test regions. Windows
Microsoft JhengHei is detected through `%WINDIR%\Fonts\msjh.ttc`; use
`CJK_FONT_PATH` to override. Outputs go to
`notebooks/data/google_drive_effluent_training_20min/`, separate from SQL results.

## Methanol dosing forecast training

Run `04_train_ch3oh_dosing.ipynb` after notebook 01 to forecast A1 and A2 methanol
flow one hour ahead using the same observed-only 20-minute aggregate as notebook
03. The workbook's checked **A1 CH3OH Flow** and **A2 CH3OH Flow** columns select
11 inputs each, including current dosing flow exactly once. The notebook audits
these selections against the application configuration and stops on a mismatch.
Reading the workbook uses standard ZIP/XML libraries; no Excel engine is required.

It repeats notebook 03's purged chronological 80/20 split, XGBoost, Random Forest,
Extra Trees, scaled Ridge and persistence comparison. Metrics use m³/hour. Both
test-only plots and train/test overview plots with shaded split regions are saved
with models, predictions, source/workbook hashes and a feature audit under
`notebooks/data/ch3oh_dosing_training_20min/`. These models forecast recorded dosing
flow; they do not optimize or prescribe chemical doses. A separate later period
is required to validate model selection beyond the demo.

## Aeration airflow forecast training

Run `05_train_aeration_flow.ipynb` after notebook 01. It forecasts A1 `Q_A1_air`
and A2 `Q_A2_air` one hour ahead from the same observed-only 20-minute aggregate.
The workbook audit verifies nine A1 and ten A2 checked external inputs. Following
notebook 03, each model additionally receives its own current airflow, explicitly
marked as an unchecked autoregressive input in the audit (10/11 total inputs).

The notebook repeats the purged chronological 80/20 split, XGBoost, Random Forest,
Extra Trees, scaled Ridge and persistence comparison. Metrics and plot units are
m³/min, following the workbook. Test-only timelines and shaded train/purge/test
overviews accompany models, predictions, feature audits and source hashes in
`notebooks/data/aeration_flow_training_20min/`. These models forecast recorded
flow; they do not prescribe aeration setpoints. Keep a separate later period for
validation before operational use.
