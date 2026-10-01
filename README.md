## Submit sensor readings to the cleaning API

```bash
.venv/bin/python main.py --submit --sensor A1_COD_in
# Count only, without HTTP requests:
.venv/bin/python main.py --dry-run --sensor A1_COD_in
```

`main.py` and `make dev` open an interactive menu: choose dry run or API
submission, then a sensor by number or alias. Enter defaults to dry run; a sensor must be selected explicitly. `q` exits. Use `--submit` or `--dry-run` to skip the
menus for scripted runs by also supplying `--sensor`. Without `--sensor`,
the sensor menu is shown. Extraction uses the inclusive `DATA_WINDOW` in `config/common.py`. Set `API_URL`, `API_USER`, and `API_TOKEN` in `.env`.
The client uses the JSON authentication fields in `api_blueprint.http`.
Timestamps currently combine `DATA_DATE` and `DATA_TIME`, as in the validated
extraction preview; interpreting `DATA_ID` as a timestamp is not implemented.

Logs show extraction start, warnings/errors, resume instructions on submission
failure, and final counts. Per-reading submission and success messages use DEBUG
and are hidden by default. Credentials and response bodies are not logged. NULL, non-numeric,
and non-finite readings are skipped with a warning and a nonzero exit code.
The run stops on the first HTTP or transport failure, without retries.
HTTP 2xx means HTTP success only: the application's response contract and
cleaning completion are not yet verified. No retrieval is performed.
Persistent tracking is disabled. Reruns submit the selected window again unless
you supply an explicit resume boundary as described below.

## SQL extraction count verification

1. Run `.venv/bin/python main.py --dry-run` to count extracted readings
   after choosing a sensor from the menu. Specify the sensor directly with
   `.venv/bin/python main.py --dry-run --sensor A2_Qin`.
2. Run `sql_data_query/count_sensor.sql` in the database selected by `DB_NAME`.
   Set its schema, table, and column from the selected alias in
   `config/sensors.py`, and match its start/end to `DATA_WINDOW` in
   `config/common.py`. Defaults match `A1_Qin` and the current window.

Compare all three counts: `rows` includes NULL readings, `non_null_values`
excludes them, and `null_values` counts missing values. Python streams and
counts the actual extracted rows; SQL independently computes aggregates.
Both use inclusive boundaries, including the time-of-day cutoff. Compare
against unchanged source data so concurrent updates do not skew the results.

The command logs counts instead of individual readings, sends no API requests,
and makes no database writes. Timestamps combine `DATA_DATE` and `DATA_TIME`.
Database credentials must be configured in `.env`.

---

# AO-MBR Time-Series Prediction Pipeline

This project extracts time-series sensor data from a local Microsoft SQL Server database, prepares model inputs, sends them to a prediction API, and stores the API results back in SQL Server.

The prediction definitions are configuration-driven. The first configured prediction is `NH3_n` in [`config/eff_nh3_n.py`](config/eff_nh3_n.py).

## Pipeline overview

```text
SQL Server source tables
        |
        | Extract configured feature and target columns
        v
Align records by timestamp and build model inputs
        |
        | One prediction payload per forecast timestamp
        v
Prediction API
        |
        | Parse and validate the API response
        v
SQL Server prediction table
```

The pipeline has two related data paths:

1. **Training-data preparation** combines historical input features from multiple SQL tables with the configured target column. Each training observation must contain a timestamp, its feature values, and the target value that the model should learn to predict.
2. **Prediction processing** creates an input row for each forecast timestamp, sends it to the API, receives the prediction, and saves the result to SQL Server.

## Configured prediction: effluent NH3-N

`config/eff_nh3_n.py` defines the `effluent_nh3_n` prediction.

### Input features

| Feature    | Source table        | Source column |
| ---------- | ------------------- | ------------- |
| `A1_Q_in`  | `T02_0506A_SCADA`   | `A1_Q_in`     |
| `A1_MLSS`  | `T02_07A1_RealData` | `A1_MLSS`     |
| `A1_NH3_N` | `T02_06A1_SCADA`    | `A1_NH3_N`    |
| `A1_Q_air` | `T02_07A_air`       | `A1_Q_air`    |

### Training target

| Target  | Source table           | Source column |
| ------- | ---------------------- | ------------- |
| `NH3_N` | `T02_09A_outlet_SCADA` | `Eff_NH3-N`   |

The configured timestamp fields are:

- Record identifier: `DATA_ID`
- Date: `DATA_DATE`
- Time: `DATA_TIME`

The extractor combines `DATA_DATE` and `DATA_TIME` into a single timestamp. Records from the feature and target tables must then be aligned to a common timestamp before a training row or prediction payload can be produced.

### Time windows

The prediction currently uses:

- Historical data window: `2026-03-24 00:00:00` through `2026-04-23 13:00:00`
- Forecast window: `2026-04-18 14:00:00` through `2026-04-23 13:00:00`
- Forecast frequency: one hour

These values can be changed independently for each prediction in its configuration file.

## Processing sequence

For each configured prediction, the completed pipeline will perform the following operations:

1. Open a connection to SQL Server.
2. Read every configured feature from its source table for the historical data window.
3. Read the target column for the same historical period.
4. Align feature and target readings by timestamp. The exact matching, resampling, and missing-value policy must be defined before model inputs are sent.
5. Build one feature record for each valid timestamp.
6. For timestamps in the forecast window, serialize the feature record into the API request format.
7. Send the request to the configured prediction endpoint.
8. Validate the response and associate it with the prediction name and forecast timestamp.
9. Insert or update the result in the SQL destination table.
10. Commit successful writes and close the API and database connections.

The API request loop is expected to process one logical observation at a time. If the API instead requires one request per individual sensor, the payload-building and response-grouping behavior will need to follow that API contract.

## Project structure

```text
config/
  common.py          Shared time and timestamp configuration
  eff_nh3_n.py       Effluent NH3-N feature and target definition
src/
  database.py        SQL Server connection management
  extractor.py       Reads a configured column from SQL Server
  transformer.py     Converts values and builds API payloads
  api_client.py      Sends requests to the prediction API
  loader.py          Writes predictions back to SQL Server (pending schema)
  logger.py          Application logging configuration
explore_query.sql     Source-table exploration queries
```

## Environment configuration

Copy `.env.example` to `.env` and fill in the local values:

```dotenv
# SQL Server
DB_DRIVER=ODBC Driver 18 for SQL Server
DB_SERVER=localhost
DB_NAME=ITRI
DB_USERNAME=
DB_PASSWORD=
DB_TRUSTED_CONNECTION=true

# Prediction API
API_URL=
API_KEY=

# Runtime controls
START_DATE=2025-01-01
END_DATE=2025-04-01
DRY_RUN=true
BATCH_SIZE=500
```

Do not commit `.env`; it may contain database or API credentials.

The database connector supports Windows/integrated authentication with `DB_TRUSTED_CONNECTION=true`, or SQL Server authentication with `DB_TRUSTED_CONNECTION=false` and `DB_USERNAME` / `DB_PASSWORD`. For WSL connecting to Windows SQL Server, use a reachable Windows host address and TCP port in `DB_SERVER`.

## Installation

Install Microsoft ODBC Driver 18 for SQL Server on the machine running the pipeline, then create a Python environment and install the project dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Development commands (WSL/Linux)

Run these commands from the project root:

```bash
make install  # Create .venv if needed and install dependencies
make dev      # Connect to SQL Server and wait; Ctrl+C closes the connection
make check    # Check Python syntax and installed dependency compatibility
make help     # List available commands
```

These commands use `.venv/bin/python` directly, so activation is not required.
`make check` does not connect to the database or run automated tests.
You can select a different environment with `make dev VENV=/path/to/venv`.

## Current implementation status

Implemented:

- SQL Server connection using integrated or SQL Server authentication
- Development entry point that holds the connection until Ctrl+C
- Extraction of an individual configured sensor column
- Conversion of SQL/Python values into JSON-compatible values
- Prediction payload construction
- Authenticated HTTP prediction requests
- Initial `effluent_nh3_n` prediction configuration

Still to be implemented or confirmed:

- Multi-table timestamp alignment and resampling rules
- Training dataset assembly with the target column
- Main pipeline/orchestration command
- API request and response schemas
- Retry and partial-failure handling
- Destination SQL table and response-to-column mapping
- Idempotent insert/update logic in `src/loader.py`
- Automated tests

## Information required to complete the pipeline

The remaining implementation depends on four contracts:

1. A representative API request body.
2. A representative successful API response.
3. The destination SQL table definition or desired output columns.
4. The timestamp-alignment rule for readings that do not have exactly matching timestamps, such as nearest reading, hourly average, or forward fill.

Keeping these decisions in configuration will allow additional predictions to be added without rewriting the extraction and API-processing code.

## Submission tracking (inactive)

`src/submission_store.py` and existing ledger files are retained, but `main.py`
and `run_pipeline()` do not use them. Submission runs perform no ledger reads
or writes and do not skip previously submitted readings. Rerunning a window
sends its valid readings again unless a resume boundary is supplied.

## Resume using a failure log (no local database)

Failures log the sensor alias, DATA_ID, source timestamp, original time window,
and shell-quoted resume commands. After checking delivery on the server, use:

```bash
# The failed reading was NOT delivered: include it.
.venv/bin/python main.py --submit --sensor A2_Q_r1 --resume-from-id '2026-04-07 08:08:00'
# The reading WAS delivered: skip it too.
.venv/bin/python main.py --submit --sensor A2_Q_r1 --resume-after-id '2026-04-07 08:08:00'
```

Use the actual sensor alias and DATA_ID from your log. Keep the original source,
destination, and DATA_WINDOW. DATA_ID must uniquely identify a reading within
the selected source/window, and source readings must remain unchanged. Earlier
readings are assumed already handled; this does not check their delivery or
revisit previously skipped invalid values. The extractor still scans the window
in timestamp/ID order, but no API calls occur before the boundary. An ID absent
from the window produces an error without sending any readings. Extraction
counts (including dry-run counts) describe the scanned window, not just its
remaining portion.

A timeout or HTTP error does not prove the server made no changes. Verify the
boundary reading before choosing whether to include it. HTTP 2xx is not a
verification of downstream cleaning. No automatic retry or resume is performed.

Logging goes to the console; retain it for later use, for example in Bash:

```bash
set -o pipefail
.venv/bin/python main.py --submit --sensor A2_Q_r1 2>&1 | tee -a submission.log
```

There are no per-reading ledger writes. Start/end summaries and unusual events
are logged by default. A handled interruption logs resume context when available;
a forced kill, power loss, or machine crash may leave no usable restart point.
Changes apply to the next process, not a submission already running. Old failure
logs containing a unique DATA_ID can also be used with these options.

## Reusing the workflow

`main.py` handles menus, command-line arguments, and logging setup.
`src/pipeline.py` owns extraction, API submission, summaries,
and resource cleanup. Call it directly without interactive input:

```python
from config.common import DATA_WINDOW, TIMESTAMP_COLUMNS
from config.sensors import SENSORS
from src.logger import setup_logger
from src.pipeline import run_pipeline

setup_logger()
status = run_pipeline(
    sensor_alias="A2_Qin",
    sensor=SENSORS["A2_Qin"],
    data_window=DATA_WINDOW,
    timestamp_columns=TIMESTAMP_COLUMNS,
    dry_run=True,
)
```

The function returns 0 for completion, 1 for failure or invalid readings,
and 130 for interruption. Pass `dry_run=False` to submit. Existing CLI commands remain the same.
