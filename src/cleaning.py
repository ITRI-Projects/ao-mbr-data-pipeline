"""Prepare SQL Server sensor readings for forecasting"""

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import pyodbc

from src.cleaning_policy import (
    CONSTANT_SENSORS,
    FLATLINE_MINUTES,
    FORWARD_FILL_MINUTES,
    FREEZE_SENSOR_FRACTION,
    SENSOR_BOUNDS,
    SHORT_REPAIR_MINUTES,
    SYNCHRONIZED_FREEZE_MINUTES,
    TANK_SENSORS,
)
from src.database import close_connection, get_connection, identifier
from src.paths import local_path
from src.prepared_data import (
    FILL_MASK_CSV,
    PREPARED_CSV,
    SENSOR_FAULT_MASK_CSV,
    SHORT_REPAIR_MASK_CSV,
    SYNCHRONIZED_MASK_CSV,
)
from src.sensor_aliases import read_aliases
from src.settings import CLEANED_SENSOR_TABLE, CLEANING_OUTPUT_DIR, DEFAULT_SCHEMA
from src.visuals.cleaning import plot_sensor_readings


DEFAULT_TABLE = f"{DEFAULT_SCHEMA}.{CLEANED_SENSOR_TABLE}"


@dataclass
class CleanedReadings:
    before_fill: pd.DataFrame
    data: pd.DataFrame
    fill_mask: pd.DataFrame
    fault_mask: pd.DataFrame
    replacement_mask: pd.DataFrame
    synchronized_mask: pd.Series


def minute_boundary(value):
    if value is None:
        return None
    time = pd.Timestamp(value)
    if pd.isna(time) or time.tz is not None or time != time.floor("min"):
        raise ValueError("Use timezone-naive, minute-aligned query boundaries.")
    return time


def read_sql_readings(table=DEFAULT_TABLE, start=None, end=None):
    """Read an inclusive minute range and return the original sensor columns."""
    schema, _, name = table.rpartition(".")
    source = f"{identifier(schema or DEFAULT_SCHEMA)}.{identifier(name)}"
    start, end = minute_boundary(start), minute_boundary(end)
    if start is not None and end is not None and start > end:
        raise ValueError("Start must be at or before end.")

    conditions, parameters = [], []
    if start is not None:
        conditions.append("[datetime] >= ?")
        parameters.append(start.to_pydatetime())
    if end is not None:
        conditions.append("[datetime] < ?")
        parameters.append((end + pd.Timedelta(minutes=1)).to_pydatetime())
    query = f"SELECT * FROM {source}"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY [datetime]"

    connection = get_connection()
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(query, *parameters)
            columns = [column[0].strip() for column in cursor.description]
            frame = pd.DataFrame.from_records(
                (tuple(row) for row in cursor), columns=columns
            )
        finally:
            cursor.close()
    finally:
        close_connection(connection)

    timestamps = [column for column in frame if column.casefold() == "datetime"]
    if len(timestamps) != 1 or not frame.columns.is_unique:
        raise ValueError(
            "Expected one datetime column and unique sensor columns in the SQL result."
        )
    if frame.empty:
        raise ValueError(
            "The SQL query returned no sensor readings. Review the table and time range."
        )
    timestamp = timestamps[0]
    frame[timestamp] = pd.to_datetime(frame[timestamp], errors="raise")
    frame = frame.set_index(timestamp).sort_index().rename_axis("datetime")
    index = frame.index
    if index.hasnans or index.tz is not None or not index.equals(index.floor("min")):
        raise ValueError(
            "Expected nonmissing, timezone-naive, minute-aligned SQL timestamps."
        )
    if not index.is_unique:
        raise ValueError("Expected unique SQL timestamps.")
    return frame


def normalize_sensors(raw, aliases):
    """Apply workbook aliases and average each pair where both sensors report."""
    lookup = {alias.casefold(): alias for alias in aliases.values()}
    lookup.update({tag.casefold(): alias for tag, alias in aliases.items()})
    lookup.update({"q_a1_air": "A1_Q_air", "q_a2_air": "A2_Q_air"})
    frame = raw.rename(columns=lambda column: lookup.get(column.casefold(), column))
    if not frame.columns.is_unique:
        raise ValueError("Preferred aliases produced duplicate sensor columns.")
    frame = frame.apply(pd.to_numeric, errors="raise")
    if frame.isin([float("inf"), float("-inf")]).any().any():
        raise ValueError("Sensor readings must be finite or missing.")

    pairs = {sensor: [f"A1_{sensor}", f"A2_{sensor}"] for sensor in TANK_SENSORS}
    sources = [column for pair in pairs.values() for column in pair]
    missing = [column for column in sources if column not in frame]
    if missing:
        raise ValueError(
            f"Missing A1/A2 columns required for consolidation: {', '.join(missing)}"
        )
    for sensor, pair in pairs.items():
        if sensor in frame:
            raise ValueError(f"Consolidated sensor column already exists: {sensor}")
        frame[sensor] = frame[pair].mean(axis=1)
    return frame.drop(columns=sources)


def run_lengths(values):
    groups = values.ne(values.shift()).cumsum()
    return groups.groupby(groups).transform("size")


def clean_readings(raw, aliases):
    frame = normalize_sensors(raw, aliases)
    minute_index = pd.date_range(
        frame.index.min(), frame.index.max(), freq="min", name="datetime"
    )
    before_fill = frame.reindex(minute_index)
    filled = before_fill.ffill(limit=FORWARD_FILL_MINUTES)
    fill_mask = before_fill.isna() & filled.notna()

    # A synchronized freeze flags the initial reading as well as its repeats.
    informative = filled.loc[:, filled.nunique(dropna=True).gt(1)]
    frozen = informative.eq(informative.shift()).mean(axis=1).ge(FREEZE_SENSOR_FRACTION)
    synchronized = frozen & run_lengths(frozen).ge(SYNCHRONIZED_FREEZE_MINUTES)
    synchronized |= synchronized.shift(-1, fill_value=False)
    working = filled.loc[~synchronized]
    if working.empty:
        raise ValueError("No readings remain after removing synchronized freezes.")

    flatlines = working.apply(
        lambda values: values.notna() & run_lengths(values).ge(FLATLINE_MINUTES)
    )
    physical = pd.DataFrame(False, index=working.index, columns=working.columns)
    for sensor, (lower, upper) in SENSOR_BOUNDS.items():
        if sensor in working:
            physical[sensor] = working[sensor].lt(lower)
            if upper is not None:
                physical[sensor] |= working[sensor].gt(upper)

    faults = flatlines | physical
    masked = working.mask(faults)
    interpolated = masked.interpolate(method="time", limit=SHORT_REPAIR_MINUTES, limit_area="inside")
    short_errors = physical.apply(lambda values: values & run_lengths(values).le(SHORT_REPAIR_MINUTES))
    replacements = short_errors & interpolated.notna()
    cleaned = masked.where(~replacements, interpolated)

    # Apply the notebook's exclusions only when the source sensor is constant.
    columns = [
        sensor
        for sensor in cleaned
        if sensor not in CONSTANT_SENSORS or frame[sensor].nunique(dropna=True) > 1
    ]
    return CleanedReadings(
        before_fill,
        cleaned[columns],
        fill_mask.loc[cleaned.index, columns],
        faults[columns],
        replacements[columns],
        synchronized.rename("synchronized_corrupt"),
    )


def export_readings(raw, readings, output):
    """Publish the complete CSV, mask and plot bundle in one directory rename."""
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output, prefix=".preparing-") as staging:
        staging = Path(staging)
        frames = {
            "sql_raw.csv": raw,
            PREPARED_CSV: readings.data,
            FILL_MASK_CSV: readings.fill_mask,
            SENSOR_FAULT_MASK_CSV: readings.fault_mask,
            SHORT_REPAIR_MASK_CSV: readings.replacement_mask,
            SYNCHRONIZED_MASK_CSV: readings.synchronized_mask,
        }
        for filename, frame in frames.items():
            frame.to_csv(
                staging / filename, index_label="datetime", encoding="utf-8-sig"
            )
        plot_sensor_readings(readings, staging / "sensor_timeseries.png")
        suffix = staging.name.removeprefix(".preparing-")
        destination = output / f"{datetime.now():%Y%m%d-%H%M%S}-{suffix}"
        return staging.rename(destination)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--table",
        default=DEFAULT_TABLE,
        help="SQL table in schema.table form",
    )
    parser.add_argument("--start", help="First minute to read, inclusive")
    parser.add_argument("--end", help="Last minute to read, inclusive")
    parser.add_argument(
        "--output",
        type=local_path,
        default=CLEANING_OUTPUT_DIR,
        help="Parent directory for export runs",
    )
    args = parser.parse_args(argv)
    try:
        raw = read_sql_readings(args.table, args.start, args.end)
        print(
            f"Loaded {len(raw):,} rows and {len(raw.columns)} columns from {args.table}."
        )
        readings = clean_readings(raw, read_aliases())
        destination = export_readings(raw, readings, args.output).resolve()
    except pyodbc.Error:
        parser.exit(
            1,
            "SQL read failed. Check the connection and table permissions with make db-check.\n",
        )
    except (ValueError, OSError) as error:
        parser.exit(1, f"Cleaning failed: {error}\n")
    print(
        f"Saved {len(readings.data):,} rows and {len(readings.data.columns)} sensors to {destination}"
    )
    print(
        f"Removed {readings.synchronized_mask.sum():,} synchronized freeze timestamps."
    )
    print(f"Training input: {destination / PREPARED_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
