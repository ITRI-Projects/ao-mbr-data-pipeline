"""Parse CLI options and dispatch pipeline operations."""

import argparse
import os
import subprocess
import sys

from config.common import DATA_WINDOW, TIMESTAMP_COLUMNS
from config.sensors import SENSORS
from src.cli.prompts import prompt_operation, prompt_sensor
from src.logger import setup_logger
from src.settings import CLEANED_SENSOR_TABLE, DEFAULT_SCHEMA
from src.etl.api_submission import run_pipeline
from src.etl.csv_loader import load_csv
from src.database_check import main as check_database


def build_parser():
    parser = argparse.ArgumentParser(description="Choose an AO-MBR pipeline operation.")
    parser.add_argument("--sensor", choices=sorted(SENSORS))
    resume = parser.add_mutually_exclusive_group()
    resume.add_argument('--resume-from-id', help='Skip earlier readings; include this DATA_ID (verify it was not delivered)')
    resume.add_argument('--resume-after-id', help='Skip through this DATA_ID (verify it was delivered)')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true", help="Count readings without API requests")
    modes.add_argument("--submit", action="store_true", help="Send readings to the cleaning API")
    modes.add_argument("--load-csv", metavar="PATH", nargs="?", const="",
                       help="Load a cleaned CSV; prompt for its path when omitted")
    parser.add_argument("--table", default=CLEANED_SENSOR_TABLE, help="Cleaned CSV destination table")
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    parser.add_argument("--timestamp-column", default="datetime", help="Timestamp header in the CSV (case-insensitive; default datetime accepts DateTime)")
    parser.add_argument("--timestamp-format", default=os.getenv("CSV_TIMESTAMP_FORMAT") or None,
                        help="Explicit datetime format, e.g. %%d/%%m/%%Y %%H:%%M; overrides auto parsing")
    parser.add_argument("--validate-only", action="store_true", help="Validate a CSV without connecting to SQL Server")
    return parser


def select_options(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.db_check = False
    args.module_command = None
    if args.validate_only and args.load_csv is None:
        parser.error("--validate-only requires --load-csv")

    if not (args.dry_run or args.submit or args.load_csv is not None):
        operation = prompt_operation()
        if operation is None:
            return None
        if callable(operation):
            if args.sensor or args.resume_from_id or args.resume_after_id:
                parser.error("The selected operation does not use sensor or resume options")
            args.module_command = operation(parser)
            return args
        setattr(args, operation, "" if operation == "load_csv" else True)

    if args.load_csv == "":
        args.load_csv = input("CSV path (Windows or local path): ").strip()
        if not args.load_csv:
            parser.error("CSV path is required")
    if args.load_csv or args.db_check:
        if args.sensor or args.resume_from_id or args.resume_after_id:
            activity = "Database check" if args.db_check else "CSV loading"
            parser.error(f"{activity} does not use sensor or resume options")
    elif args.sensor is None:
        args.sensor = prompt_sensor()
        if args.sensor is None:
            return None
    return args


def dispatch(args):
    if args.module_command is not None:
        try:
            result = subprocess.run([sys.executable, *args.module_command], check=False)
        except KeyboardInterrupt:
            return 130
        return result.returncode
    if args.db_check:
        return check_database()
    setup_logger()
    if args.load_csv:
        return load_csv(args.load_csv, table=args.table, schema=args.schema,
                        timestamp_column=args.timestamp_column, validate_only=args.validate_only,
                        timestamp_format=args.timestamp_format)
    return run_pipeline(
        sensor_alias=args.sensor,
        sensor=SENSORS[args.sensor],
        data_window=DATA_WINDOW,
        timestamp_columns=TIMESTAMP_COLUMNS,
        dry_run=args.dry_run,
        resume_from_id=args.resume_from_id,
        resume_after_id=args.resume_after_id,
    )


def main(argv=None):
    try:
        args = select_options(argv)
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled before running an operation.")
        return 130
    if args is None:
        return 0
    return dispatch(args)
