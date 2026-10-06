"""Import wide, cleaned sensor CSVs into a separate SQL Server table."""
import csv
from datetime import datetime
import math
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile, BadZipFile

import pyodbc

from src.database import get_connection
from src.logger import get_logger

WORKBOOK = Path(__file__).resolve().parents[1] / 'Sensor_Configurations.xlsx'


def local_path(value):
    value = str(value).strip().strip('\"').strip("'")
    if os.name != 'nt' and re.match(r'^[A-Za-z]:[\\/]', value):
        value = '/mnt/' + value[0].lower() + '/' + value[3:].replace('\\', '/')
    return Path(value).expanduser()


def identifier(value):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}', value):
        raise ValueError(f'Invalid SQL identifier: {value}')
    return '[' + value + ']'


def read_aliases(workbook=WORKBOOK):
    ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    mapping = {}
    with ZipFile(workbook) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(t.text or '' for t in item.findall('.//m:t', ns))
                       for item in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('m:si', ns)]
        for name in archive.namelist():
            if not re.fullmatch(r'xl/worksheets/sheet\d+\.xml', name):
                continue
            columns = None
            for row in ET.fromstring(archive.read(name)).findall('.//m:row', ns):
                values = {}
                for cell in row:
                    column = re.sub(r'\d+', '', cell.attrib['r'])
                    v = cell.find('m:v', ns)
                    if cell.attrib.get('t') == 's':
                        text = strings[int(v.text)]
                    elif cell.attrib.get('t') == 'inlineStr':
                        text = ''.join(t.text or '' for t in cell.findall('.//m:t', ns))
                    else:
                        text = v.text if v is not None else ''
                    values[column] = text.strip()
                normalized = {v.lower(): k for k, v in values.items() if v}
                if 'full tag name' in normalized:
                    alias_key = normalized.get('prefered alias') or normalized.get('preferred alias')
                    if not alias_key or 'column' not in normalized:
                        raise ValueError('Workbook requires Preferred Alias and Column headers')
                    columns = (normalized['full tag name'], alias_key, normalized['column'])
                    continue
                if columns:
                    tag, alias, source = (values.get(k, '') for k in columns)
                    if tag:
                        alias = alias or source
                        identifier(alias)
                        if tag in mapping and mapping[tag] != alias:
                            raise ValueError(f'Conflicting workbook mapping for {tag}')
                        mapping[tag] = alias
    if not mapping or len(set(a.lower() for a in mapping.values())) != len(mapping):
        raise ValueError('Workbook has missing or duplicate aliases')
    return mapping


def parse_timestamp(value):
    """Accept ISO or month/day/year timestamps from the downloaded CSV."""
    value = value.strip()
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


def read_clean_csv(path, mapping, timestamp_column='datetime'):
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
                timestamp = parse_timestamp(row[time_index])
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


def load_csv(path, *, table='CleanedSensorData', schema='dbo',
             timestamp_column='datetime', validate_only=False):
    logger = get_logger(__name__)
    connection = None
    stage = 'CSV validation'
    try:
        destination = identifier(schema) + '.' + identifier(table)
        mapping = read_aliases()
        aliases, rows = read_clean_csv(path, mapping, timestamp_column)
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
