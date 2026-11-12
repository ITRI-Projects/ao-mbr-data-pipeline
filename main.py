import argparse
import os
import subprocess
import sys

from config.common import DATA_WINDOW, TIMESTAMP_COLUMNS
from config.sensors import SENSORS
from src.logger import setup_logger
from src.pipeline import run_pipeline
from src.csv_loader import load_csv
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
    parser.add_argument("--table", default="CleanedSensorData", help="Cleaned CSV destination table")
    parser.add_argument("--schema", default="dbo")
    parser.add_argument("--timestamp-column", default="datetime", help="Timestamp header in the CSV (case-insensitive; default datetime accepts DateTime)")
    parser.add_argument("--timestamp-format", default=os.getenv("CSV_TIMESTAMP_FORMAT") or None,
                        help="Explicit datetime format, e.g. %%d/%%m/%%Y %%H:%%M; overrides auto parsing")
    parser.add_argument("--validate-only", action="store_true", help="Validate a CSV without connecting to SQL Server")
    return parser


def prompt_operation():
    operations = {
        "1": ("dry_run", "Dry run (count only)"),
        "2": ("submit", "Actual API submission"),
        "3": ("load_csv", "Load cleaned CSV into database"),
        "4": ("db_check", "Check SQL Server connection and permissions"),
        "5": ("train", "Train forecasting models"),
        "6": ("tune", "Tune a single-target baseline"),
        "7": ("clean", "Prepare loaded SQL sensor data for training"),
        "8": ("select_model", "Select one forecast model per target"),
        "9": ("load_forecasts", "Review selected forecasts and optionally load them into SQL Server"),
    }
    print("\nChoose an operation:")
    for number, (_, label) in operations.items():
        print(f"  {number}. {label}")
    print("  q. Quit")
    while True:
        choice = input("Operation [1]: ").strip().lower() or "1"
        if choice == "q":
            return None
        if choice in operations:
            return operations[choice][0]
        print("Enter a listed operation number or q.")


def prompt_sensor():
    aliases = list(SENSORS)
    print("\nSelect a sensor column:")
    previous_group = None
    for number, alias in enumerate(aliases, 1):
        sensor = SENSORS[alias]
        group = sensor.get("group", "Other")
        if group != previous_group:
            print(f"\n{group}:")
            previous_group = group
        source = sensor["source"]
        print(f"  {number}. {alias} — {source['table']}.{source['column']} — {sensor.get('description', '')}")
    while True:
        choice = input("Sensor number or alias, q to quit: ").strip()
        if choice.lower() == "q":
            return None
        if choice in SENSORS:
            return choice
        if choice.isdecimal() and 1 <= int(choice) <= len(aliases):
            return aliases[int(choice) - 1]
        print("Enter a listed sensor number or alias, or q.")


def prompt_training_command(operation, parser):
    if operation == "train":
        data = input("Prepared training CSV path: ").strip()
        if not data:
            parser.error("Prepared training CSV path is required")
        output = input("Baseline output directory: ").strip()
        if not output:
            parser.error("Baseline output directory is required")
        target = input("Target model name (e.g. eff_nh3_n, Enter for all available targets): ").strip()
        command = ["-m", "src.training.train", "--data", data, "--output", output]
        if target:
            command.extend(["--targets", target])
        return command

    source = input("Baseline output directory from a completed single-target training run: ").strip()
    if not source:
        parser.error("Single-target baseline output directory is required")
    output = input("Separate tuned output directory: ").strip()
    if not output:
        parser.error("Tuned output directory is required")
    return ["-m", "src.training.tune", "--source", source, "--output", output]


def prompt_cleaning_command():
    command = ["-m", "src.cleaning"]
    for flag, prompt in (
        ("--table", "SQL table [dbo.CleanedSensorData]: "),
        ("--start", "First minute (YYYY-MM-DD HH:MM, Enter for earliest): "),
        ("--end", "Last minute (YYYY-MM-DD HH:MM, Enter for latest): "),
        ("--output", "Export parent directory [data/cleaning]: "),
    ):
        value = input(prompt).strip()
        if value:
            command.extend([flag, value])
    return command


def prompt_model_selection_command():
    command = ["-m", "src.training.select_model"]
    assets = input("Saved forecast directory [docs/assets]: ").strip()
    output = input("Selection JSON path [data/forecast_selection.json]: ").strip()
    if assets:
        command.extend(["--assets", assets])
    if output:
        command.extend(["--output", output])
    return command


def prompt_forecast_load_command():
    command = ["-m", "src.forecast_loader"]
    selection = input("Selection JSON path [data/forecast_selection.json]: ").strip()
    if selection:
        command.extend(["--selection", selection])
    return command


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
        if operation in ("train", "tune", "clean", "select_model", "load_forecasts"):
            if args.sensor or args.resume_from_id or args.resume_after_id:
                parser.error("The selected operation does not use sensor or resume options")
            if operation == "clean":
                args.module_command = prompt_cleaning_command()
            elif operation == "select_model":
                args.module_command = prompt_model_selection_command()
            elif operation == "load_forecasts":
                args.module_command = prompt_forecast_load_command()
            else:
                args.module_command = prompt_training_command(operation, parser)
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


if __name__ == "__main__":
    raise SystemExit(main())
