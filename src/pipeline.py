"""Reusable single-sensor extraction and submission workflow, without CLI prompts."""
from datetime import datetime

import pyodbc
import requests

from src.api_client import APIClient
from src.database import close_connection, get_connection
from src.extractor import extract_parameter
from src.logger import get_logger
from src.transformer import build_import_payload


def run_pipeline(*, sensor_alias, sensor, data_window, timestamp_columns,
                 dry_run=True):
    """Run one sensor with explicit configuration and return an exit status.

    Returns 0 on completion, 1 on failure/skipped invalid readings,
    or 130 on interruption. Configure logging in the calling application.
    Dry runs count SQL readings without opening the API.
    """
    logger = get_logger(__name__)
    connection = client = readings = None
    count = non_null = submitted = skipped = failed = uncertain = 0
    try:
        start = datetime.fromisoformat(data_window["start"])
        end = datetime.fromisoformat(data_window["end"])
        if start > end:
            raise ValueError("DATA_WINDOW start must not be after end")
        source = sensor["source"]
        logger.info("Mode=%s sensor=%s source=%s.%s.%s window=[%s, %s] (inclusive)",
                    "count only" if dry_run else "API submission", sensor_alias,
                    source["schema"], source["table"], source["column"], start, end)
        if not dry_run:
            client = APIClient()
        connection = get_connection()
        logger.info("Database connected. Starting extraction.")
        readings = extract_parameter(
            connection, source["table"], source["column"], start, end,
            schema=source["schema"], timestamp_columns=timestamp_columns,
        )
        for reading in readings:
            count += 1
            non_null += reading["value"] is not None
            if dry_run:
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
    except (pyodbc.Error, OSError, ValueError, TypeError):
        # Exception text can contain connection or request secrets.
        logger.error("Run failed. Check database connectivity, required environment settings, and timestamp configuration.")
        return 1
    except KeyboardInterrupt:
        logger.warning("Interrupted. An in-flight request may have reached the API; check before resending.")
        return 130
    finally:
        logger.info("Run summary: extracted=%d submitted_http_2xx=%d skipped=%d failed=%d uncertain=%d dry_run=%s",
                    count, submitted, skipped, failed, uncertain, dry_run)
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

