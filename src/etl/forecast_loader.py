"""Review selected test forecasts and optionally load them into SQL Server."""

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
import hashlib
import io
import json
import math
import os
import re

import pyodbc

from src.database import get_connection, identifier
from src.paths import local_path
from src.settings import FORECAST_DESTINATION as DESTINATION
from src.settings import FORECAST_SELECTION_PATH as DEFAULT_SELECTION
from src.training.settings import ALGORITHM_ORDER
from src.training.workbook import TARGET_COLUMNS


@dataclass(frozen=True)
class SelectedForecast:
    target: str
    algorithm: str
    variant: str
    rmse: float
    values: dict[datetime, float]


def read_test_forecast(path, algorithm, checksum):
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != checksum:
        raise ValueError(f"{path} changed after selection. Run model selection again.")
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
    fields = reader.fieldnames or []
    if len(fields) != len(set(fields)) or not {"split", "target_time", algorithm}.issubset(fields):
        raise ValueError(f"Missing or duplicate prediction columns in {path}.")
    values = {}
    for row in reader:
        if row["split"] != "test":
            continue
        try:
            timestamp = datetime.fromisoformat(row["target_time"])
            value = float(row[algorithm])
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid test prediction in {path} at line {reader.line_num}.") from error
        if timestamp.tzinfo is not None or timestamp in values or not math.isfinite(value):
            raise ValueError(f"Expected unique local timestamps and finite test predictions in {path}.")
        values[timestamp] = value
    if not values:
        raise ValueError(f"No test predictions in {path}.")
    return values


def read_selection(path):
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    records = document["selections"]
    expected = set(TARGET_COLUMNS)
    if len(records) != len(expected) or {record["model"] for record in records} != expected:
        raise ValueError("Expected one forecast selection for each of the six targets.")

    forecasts = []
    for record in records:
        target = TARGET_COLUMNS[record["model"]]
        algorithm, variant = record["prediction_column"], record["variant"]
        rmse = float(record["validation_rmse"])
        if (record["target"] != target or algorithm not in ALGORITHM_ORDER
                or variant not in {"raw", "tuned"} or not math.isfinite(rmse) or rmse < 0):
            raise ValueError(f"Invalid forecast selection for {target}.")
        values = read_test_forecast(path.parent / record["predictions_csv"], algorithm, record["predictions_sha256"])
        forecasts.append(SelectedForecast(target, algorithm, variant, rmse, values))
    return forecasts


def align_predictions(forecasts):
    timestamps = sorted({timestamp for forecast in forecasts for timestamp in forecast.values})
    return [(timestamp, *(forecast.values.get(timestamp) for forecast in forecasts)) for timestamp in timestamps]


def print_preview(forecasts, rows):
    print("\nSelected forecasts and test coverage")
    print(f"{'Target':<16} {'Algorithm':<15} {'Run':<6} {'Validation RMSE':>16} {'Test rows':>10}")
    for forecast in forecasts:
        print(f"{forecast.target:<16} {forecast.algorithm:<15} {forecast.variant:<6} "
              f"{forecast.rmse:>16.6g} {len(forecast.values):>10,}")
    complete = sum(None not in row for row in rows)
    print(f"\n{len(rows):,} test timestamps from {rows[0][0]} through {rows[-1][0]}.")
    print(f"{complete:,} timestamps have all six forecasts. Missing predictions will be SQL NULL.")


def load_predictions(forecasts, rows):
    columns = [identifier(forecast.target) for forecast in forecasts]
    names = ", ".join(["[target_time]", *columns])
    definitions = ", ".join(f"{column} FLOAT NULL" for column in columns)
    schema = f"[target_time] DATETIME2(6) NOT NULL PRIMARY KEY, {definitions}"
    placeholders = ", ".join("?" for _ in range(len(columns) + 1))
    updates = ", ".join(f"destination.{column} = incoming.{column}" for column in columns)
    values = ", ".join(f"incoming.{column}" for column in ["[target_time]", *columns])

    connection = get_connection()
    try:
        connection.autocommit = False
        cursor = connection.cursor()
        try:
            cursor.execute(f"CREATE TABLE #ForecastImport ({schema})")
            cursor.executemany(f"INSERT INTO #ForecastImport ({names}) VALUES ({placeholders})", rows)
            cursor.execute(f"""
                IF OBJECT_ID(N'{DESTINATION}', N'U') IS NULL
                    CREATE TABLE {DESTINATION} ({schema});
            """)
            cursor.execute(f"""
                MERGE {DESTINATION} WITH (HOLDLOCK) AS destination
                USING #ForecastImport AS incoming
                ON destination.[target_time] = incoming.[target_time]
                WHEN MATCHED THEN UPDATE SET {updates}
                WHEN NOT MATCHED BY TARGET THEN INSERT ({names}) VALUES ({values});
            """)
        finally:
            cursor.close()
        connection.commit()
    except (Exception, KeyboardInterrupt):
        connection.rollback()
        raise
    finally:
        connection.close()


def confirm_load():
    server = os.getenv("DB_SERVER") or "(DB_SERVER unset)"
    database = os.getenv("DB_NAME") or "(DB_NAME unset)"
    print(f"\nDestination: {server} / {database} / {DESTINATION}")
    print("Matching timestamps will be updated. New timestamps will be inserted.")
    while True:
        try:
            answer = input("Load these test forecasts into SQL Server? [y/N]: ").strip().lower()
        except EOFError:
            return False
        if answer in {"y", "yes", "", "n", "no"}:
            return answer in {"y", "yes"}
        print("Enter y or n.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=local_path, default=DEFAULT_SELECTION, help="Saved model selection JSON")
    parser.add_argument("--preview-only", action="store_true", help="Show the selection and test coverage, then exit")
    args = parser.parse_args(argv)
    try:
        forecasts = read_selection(args.selection)
        rows = align_predictions(forecasts)
        print_preview(forecasts, rows)
        if args.preview_only:
            return 0
        if not confirm_load():
            print("Import skipped.")
            return 0
        load_predictions(forecasts, rows)
    except (KeyError, TypeError, ValueError, OSError) as error:
        parser.exit(1, f"Forecast import failed: {error}\n")
    except pyodbc.Error as error:
        state = str(error.args[0]) if error.args else ""
        state = state if re.fullmatch(r"[A-Z0-9]{5}", state) else "unknown"
        parser.exit(1, f"SQL forecast import failed (SQLSTATE={state}). Check access with make db-check.\n")
    except KeyboardInterrupt:
        print("\nForecast import interrupted.")
        return 130
    print(f"Committed {len(rows):,} timestamps to {DESTINATION}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
