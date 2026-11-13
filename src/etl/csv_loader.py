"""Import wide, cleaned sensor CSVs into a separate SQL Server table."""
import csv
from datetime import datetime
import math
import re
import xml.etree.ElementTree as ET
from zipfile import BadZipFile

import pyodbc

from src.database import get_connection, identifier
from src.logger import get_logger
from src.paths import local_path
from src.sensor_aliases import WORKBOOK, read_aliases
from src.settings import CLEANED_SENSOR_TABLE, DEFAULT_SCHEMA

__all__ = ["WORKBOOK", "identifier", "load_csv", "local_path", "parse_timestamp", "read_aliases", "read_clean_csv"]

def parse_timestamp(value, timestamp_format=None):
    """Accept ISO or month/day/year timestamps from the downloaded CSV."""
    value = value.strip()
    if timestamp_format:
        timestamp = datetime.strptime(value, timestamp_format)
        if timestamp.tzinfo is not None:
            raise ValueError('Use local timestamps without a timezone offset')
        return timestamp
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError:
        for fmt in ('%m/%d/%Y %H:%M', '%m/%d/%Y %H:%M:%S',
                    '%m/%d/%Y %H:%M:%S.%f'):
            try:
                timestamp = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError('Expected ISO or month/day/year timestamp with time')
    if timestamp.tzinfo is not None:
        raise ValueError('Use local timestamps without a timezone offset')
    return timestamp


def read_clean_csv(path, mapping, timestamp_column='datetime', timestamp_format=None):
    with local_path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.reader(stream)
        headers = [h.strip() for h in next(reader, [])]
        normalized_headers = [h.casefold() for h in headers]
        if len(set(normalized_headers)) != len(headers) or timestamp_column.casefold() not in normalized_headers:
            raise ValueError('CSV needs unique headers and the configured timestamp column')
        time_index = normalized_headers.index(timestamp_column.casefold())
        sensor_headers = [h for i, h in enumerate(headers) if i != time_index]
        if not sensor_headers:
            raise ValueError('CSV has no sensor columns')
        unknown = [h for h in sensor_headers if h not in mapping]
        if unknown:
            raise ValueError('Unknown full tag name columns: ' + ', '.join(unknown))
        aliases = [mapping[h] for h in sensor_headers]
        if 'datetime' in [a.lower() for a in aliases]:
            raise ValueError('Sensor alias conflicts with datetime')
        rows, seen = [], set()
        for number, row in enumerate(reader, 2):
            if not row or all(not v.strip() for v in row):
                continue
            if len(row) != len(headers):
                raise ValueError(f'CSV row {number}: incorrect column count')
            try:
                timestamp = parse_timestamp(row[time_index], timestamp_format)
                if timestamp in seen:
                    raise ValueError('Duplicate timestamp')
                seen.add(timestamp)
                values = []
                for index, value in enumerate(row):
                    if index == time_index:
                        continue
                    numeric = float(value) if value.strip() else None
                    if numeric is not None and not math.isfinite(numeric):
                        raise ValueError('Non-finite sensor value')
                    values.append(numeric)
                rows.append((timestamp, *values))
            except (ValueError, OverflowError) as error:
                raise ValueError(f'CSV row {number}: invalid timestamp or numeric value ({error})') from error
    if not rows:
        raise ValueError('CSV contains no data rows')
    return aliases, rows


def load_csv(path, *, table=CLEANED_SENSOR_TABLE, schema=DEFAULT_SCHEMA,
             timestamp_column='datetime', validate_only=False, timestamp_format=None):
    logger = get_logger(__name__)
    connection = None
    stage = 'CSV validation'
    try:
        destination = identifier(schema) + '.' + identifier(table)
        mapping = read_aliases()
        aliases, rows = read_clean_csv(path, mapping, timestamp_column, timestamp_format)
        logger.info('CSV validated: rows=%d destination=%s columns=%s', len(rows), destination, ', '.join(aliases))
        if validate_only:
            return 0
        # Never import cleaned data over configured raw source tables.
        from config.sensors import SENSORS
        if any(table.lower() == s['source']['table'].lower() and
               schema.lower() == s['source']['schema'].lower() for s in SENSORS.values()):
            raise ValueError('Choose a separate cleaned-data table')
        stage = 'database connection'
        connection = get_connection()
        connection.autocommit = False
        cursor = connection.cursor()
        try:
            stage = 'destination table lookup'
            exists = cursor.execute('SELECT OBJECT_ID(?, ?)', f'{schema}.{table}', 'U').fetchone()[0]
            if exists is None:
                definitions = ', '.join(identifier(a) + ' FLOAT NULL' for a in mapping.values())
                stage = 'destination table creation'
                cursor.execute(f'CREATE TABLE {destination} ([datetime] DATETIME2(6) NOT NULL PRIMARY KEY, {definitions})')
            columns = ', '.join(['[datetime]'] + [identifier(a) for a in aliases])
            placeholders = ', '.join('?' for _ in range(len(aliases) + 1))
            for start in range(0, len(rows), 500):
                stage = f'inserting CSV data rows {start + 1}–{min(start + 500, len(rows))}'
                cursor.executemany(f'INSERT INTO {destination} ({columns}) VALUES ({placeholders})', rows[start:start + 500])
            stage = 'transaction commit'
            connection.commit()
        finally:
            cursor.close()
        logger.info('CSV import committed: %d rows into %s', len(rows), destination)
        return 0
    except (ValueError, OSError, csv.Error, ET.ParseError, BadZipFile) as error:
        if connection is not None:
            connection.rollback()
        logger.error('CSV import failed: %s', error)
        return 1
    except pyodbc.Error as error:
        if connection is not None:
            connection.rollback()
        # Log structured diagnostics, not raw messages that may contain credentials.
        state = str(error.args[0]) if error.args else ''
        state = state if re.fullmatch(r'[A-Z0-9]{5}', state) else 'unknown'
        message = str(error).lower()
        hint = 'Check database access and destination column types.'
        if state.startswith('08') or state in {'HYT00', 'HYT01'}:
            hint = 'Check DB_SERVER, SQL Server availability, TCP port, and network access.'
        elif state == '28000':
            hint = 'Check database authentication settings.'
        elif 'permission' in message or 'denied' in message:
            hint = 'SQL Server reported a permission denial. Run make db-check to inspect the actual connection and effective permissions.'
        elif 'duplicate' in message or state == '23000':
            hint = 'Check existing timestamps and destination constraints; the file may already be imported.'
        elif 'invalid column' in message:
            hint = 'The existing destination table is missing required alias or datetime columns.'
        elif state in {'HY004', 'HY105', '07006'}:
            hint = 'The ODBC driver rejected a parameter type.'
        native_codes = ','.join(dict.fromkeys(re.findall(r'\((\d+)\)', message))) or 'unknown'
        logger.error('CSV import failed during %s (SQLSTATE=%s, native=%s). %s', stage, state, native_codes, hint)
        if connection is not None:
            logger.error('The import transaction was rolled back.')
        return 1
    except KeyboardInterrupt:
        if connection is not None:
            connection.rollback()
        return 130
    finally:
        if connection is not None:
            connection.close()
