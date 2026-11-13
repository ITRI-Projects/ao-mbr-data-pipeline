from datetime import date, datetime, time
from time import monotonic

from src.logger import get_logger


def _identifier(value):
    return "[" + value.replace("]", "]]") + "]"


def extract_parameter(
    connection, table, column, start_date, end_date, *,
    schema="dbo", timestamp_columns=None,
):
    """Stream readings in an inclusive datetime window using source date/time."""
    start = datetime.fromisoformat(start_date) if isinstance(start_date, str) else start_date
    end = datetime.fromisoformat(end_date) if isinstance(end_date, str) else end_date
    if start > end:
        raise ValueError("Extraction start must not be after end")
    columns = timestamp_columns or {"id": "DATA_ID", "date": "DATA_DATE", "time": "DATA_TIME"}
    id_col, date_col, time_col = (_identifier(columns[k]) for k in ("id", "date", "time"))
    query = f"""
        SELECT {id_col}, {date_col}, {time_col}, {_identifier(column)}
        FROM {_identifier(schema)}.{_identifier(table)}
        WHERE CAST({date_col} AS date) >= ?
          AND CAST({date_col} AS date) <= ?
          AND (CAST({date_col} AS date) > ? OR CAST({time_col} AS time) >= CAST(? AS time))
          AND (CAST({date_col} AS date) < ? OR CAST({time_col} AS time) <= CAST(? AS time))
        ORDER BY CAST({date_col} AS date), CAST({time_col} AS time), {id_col}
    """
    cursor = connection.cursor()
    try:
        logger = get_logger(__name__)
        logger.info("Executing extraction query for %s.%s.%s; waiting for database results.",
                    schema, table, column)
        started = monotonic()
        cursor.execute(query, start.date(), end.date(), start.date(),
                       start.time().isoformat(), end.date(), end.time().isoformat())
        logger.info("Extraction query ready after %.1fs; streaming rows.", monotonic() - started)
        for row in cursor:
            row_date, row_time = row[1], row[2]
            if isinstance(row_date, datetime):
                row_date = row_date.date()
            elif isinstance(row_date, str):
                row_date = date.fromisoformat(row_date)
            if isinstance(row_time, str):
                row_time = time.fromisoformat(row_time)
            yield {
                "data_id": row[0],
                "timestamp": datetime.combine(row_date, row_time),
                "value": row[3],
            }
    finally:
        cursor.close()
