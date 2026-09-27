import argparse
from datetime import datetime

import pyodbc
import requests

from config.common import DATA_WINDOW, PREVIEW_SENSOR, TIMESTAMP_COLUMNS
from config.sensors import SENSORS
from src.api_client import APIClient
from src.database import close_connection, get_connection
from src.extractor import extract_parameter
from src.logger import get_logger, setup_logger
from src.transformer import build_import_payload


def select_options(argv=None):
    parser = argparse.ArgumentParser(description="Choose a SQL count check or cleaning API submission.")
    parser.add_argument("--sensor", choices=sorted(SENSORS))
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
        # A mode selected interactively is followed by a column selection.
        interactive_sensor = True
    else:
        interactive_sensor = False

    if args.sensor is None and interactive_sensor:
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
            choice = input(f"Sensor number or alias [{PREVIEW_SENSOR}], q to quit: ").strip()
            if choice.lower() == "q":
                return None
            if not choice:
                choice = PREVIEW_SENSOR
            if choice in SENSORS:
                args.sensor = choice
                break
            if choice.isdigit() and 1 <= int(choice) <= len(aliases):
                args.sensor = aliases[int(choice) - 1]
                break
            print("Enter a listed sensor number or alias, or q.")
    args.sensor = args.sensor or PREVIEW_SENSOR
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
    logger = get_logger(__name__)
    connection = client = readings = None
    count = non_null = submitted = skipped = failed = uncertain = 0
    try:
        start = datetime.fromisoformat(DATA_WINDOW["start"])
        end = datetime.fromisoformat(DATA_WINDOW["end"])
        if start > end:
            raise ValueError("DATA_WINDOW start must not be after end")
        sensor = SENSORS[args.sensor]
        source = sensor["source"]
        logger.info("Mode=%s sensor=%s source=%s.%s.%s window=[%s, %s] (inclusive)",
                    "count only" if args.dry_run else "API submission", args.sensor,
                    source["schema"], source["table"], source["column"], start, end)
        if not args.dry_run:
            client = APIClient()
        connection = get_connection()
        logger.info("Database connected. Starting extraction.")
        readings = extract_parameter(
            connection, source["table"], source["column"], start, end,
            schema=source["schema"], timestamp_columns=TIMESTAMP_COLUMNS,
        )
        for reading in readings:
            count += 1
            non_null += reading["value"] is not None
            if args.dry_run:
                continue
            try:
                payload = build_import_payload(sensor, reading)
            except (ValueError, TypeError, OverflowError):
                skipped += 1
                logger.warning("Skipping row=%d data_id=%s: missing or invalid numeric value",
                               count, reading["data_id"])
                continue
            logger.info("Submitting row=%d data_id=%s tag=%s datetime=%s value=%s",
                        count, reading["data_id"], payload["fullTagName"],
                        payload["datetime"], payload["value"])
            try:
                status = client.submit_reading(payload)
            except requests.RequestException:
                uncertain += 1
                logger.error("Delivery uncertain for row=%d data_id=%s. Stopping without retry; check server before resending.",
                             count, reading["data_id"])
                return 1
            if not 200 <= status < 300:
                failed += 1
                logger.error("HTTP failure row=%d status=%d. Stopping without retry.", count, status)
                return 1
            submitted += 1
            logger.info("HTTP success row=%d status=%d submitted=%d (cleaning not verified)",
                        count, status, submitted)
        logger.info("Extraction complete: rows=%d non_null_values=%d null_values=%d",
                    count, non_null, count - non_null)
        return 1 if skipped else 0
    except (pyodbc.Error, ValueError, TypeError):
        # Exception text can contain connection or request secrets.
        logger.error("Run failed. Check database connectivity, required environment settings, and timestamp configuration.")
        return 1
    except KeyboardInterrupt:
        logger.warning("Interrupted. An in-flight request may have reached the API; check before resending.")
        return 130
    finally:
        logger.info("Run summary: extracted=%d submitted_http_2xx=%d skipped=%d failed=%d uncertain=%d dry_run=%s",
                    count, submitted, skipped, failed, uncertain, args.dry_run)
        try:
            if readings is not None:
                readings.close()
        finally:
            try:
                if client is not None:
                    client.close()
            finally:
                if connection is not None:
                    close_connection(connection)
                    logger.info("Database connection closed.")


if __name__ == "__main__":
    raise SystemExit(main())
