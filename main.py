import argparse

from config.common import DATA_WINDOW, TIMESTAMP_COLUMNS
from config.sensors import SENSORS
from src.logger import setup_logger
from src.pipeline import run_pipeline


def select_options(argv=None):
    parser = argparse.ArgumentParser(description="Choose a SQL count check or cleaning API submission.")
    parser.add_argument("--sensor", choices=sorted(SENSORS))
    resume = parser.add_mutually_exclusive_group()
    resume.add_argument('--resume-from-id', help='Skip earlier readings; include this DATA_ID (verify it was not delivered)')
    resume.add_argument('--resume-after-id', help='Skip through this DATA_ID (verify it was delivered)')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true", help="Count readings without API requests")
    modes.add_argument("--submit", action="store_true", help="Send readings to the cleaning API")
    args = parser.parse_args(argv)

    if not (args.dry_run or args.submit):
        print("\nChoose an operation:\n  1. Dry run (count only)\n  2. Actual API submission\n  q. Quit")
        while True:
            choice = input("Operation [1]: ").strip().lower()
            if choice == "q":
                return None
            if choice in ("", "1", "2"):
                args.dry_run = choice != "2"
                break
            print("Enter 1, 2, or q.")

    if args.sensor is None:
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
                args.sensor = choice
                break
            if choice.isdigit() and 1 <= int(choice) <= len(aliases):
                args.sensor = aliases[int(choice) - 1]
                break
            print("Enter a listed sensor number or alias, or q.")
    return args


def main(argv=None):
    try:
        args = select_options(argv)
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled before extraction or submission.")
        return 130
    if args is None:
        return 0
    setup_logger()
    return run_pipeline(
        sensor_alias=args.sensor,
        sensor=SENSORS[args.sensor],
        data_window=DATA_WINDOW,
        timestamp_columns=TIMESTAMP_COLUMNS,
        dry_run=args.dry_run,
        resume_from_id=args.resume_from_id,
        resume_after_id=args.resume_after_id,
    )


if __name__ == "__main__":
    raise SystemExit(main())
