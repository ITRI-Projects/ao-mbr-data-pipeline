"""Read connection identity and effective import permissions; make no writes."""
import re

import pyodbc

from src.database import get_connection


QUERY = """
SELECT
    CONVERT(nvarchar(128), SERVERPROPERTY('ServerName')) AS server_name,
    DB_NAME() AS database_name,
    ORIGINAL_LOGIN() AS login_name,
    USER_NAME() AS database_user,
    IS_SRVROLEMEMBER('sysadmin') AS is_sysadmin,
    HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'CREATE TABLE') AS can_create_table,
    HAS_PERMS_BY_NAME('dbo', 'SCHEMA', 'ALTER') AS can_alter_dbo,
    HAS_PERMS_BY_NAME('dbo', 'SCHEMA', 'INSERT') AS can_insert_dbo,
    DATABASEPROPERTYEX(DB_NAME(), 'Updateability') AS updateability
"""


def main():
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        try:
            row = cursor.execute(QUERY).fetchone()
            for column, value in zip(cursor.description, row):
                print(f'{column[0]}: {value}')
        finally:
            cursor.close()
        return 0
    except pyodbc.Error as error:
        state = str(error.args[0]) if error.args else ''
        state = state if re.fullmatch(r'[A-Z0-9]{5}', state) else 'unknown'
        print(f'Database check failed (SQLSTATE={state}).')
        return 1
    except (ValueError, OSError):
        print('Database check failed. Check required environment settings.')
        return 1
    finally:
        if connection is not None:
            connection.close()


if __name__ == '__main__':
    raise SystemExit(main())
