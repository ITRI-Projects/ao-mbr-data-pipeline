from datetime import datetime


def extract_parameter(
    connection,
    table,
    column,
    start_date,
    end_date,
):
    query = f"""
        SELECT
            DATA_ID,
            DATA_DATE,
            DATA_TIME,
            [{column}]
        FROM [{table}]
        WHERE DATA_DATE >= ?
          AND DATA_DATE <= ?
        ORDER BY DATA_DATE, DATA_TIME
    """

    cursor = connection.cursor()
    cursor.execute(query, start_date, end_date)

    for row in cursor:
        timestamp = datetime.combine(
            row.DATA_DATE,
            row.DATA_TIME,
        )

        yield {
            "data_id": row.DATA_ID,
            "timestamp": timestamp,
            "value": row[3],
        }
