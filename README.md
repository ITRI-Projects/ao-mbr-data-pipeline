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

The current database connector uses Windows trusted authentication. Support for `DB_USERNAME`, `DB_PASSWORD`, and the `DB_TRUSTED_CONNECTION` switch still needs to be implemented if SQL Server authentication is required.

## Installation

Install Microsoft ODBC Driver 18 for SQL Server on the machine running the pipeline, then create a Python environment and install the project dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Current implementation status

Implemented:

- SQL Server connection using trusted authentication
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
