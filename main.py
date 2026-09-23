import time

import pyodbc

from src.database import close_connection, get_connection


def main():
    connection = None
    try:
        connection = get_connection()
        print("Connected to SQL Server successfully.")

        print("Press Ctrl+C to stop and disconnect.")

        # Replace this idle loop with pipeline work when ready.
        while True:
            time.sleep(1)
    except (pyodbc.Error, ValueError) as error:
        print(f"Database connection or operation failed: {error}")
        return 1
    except KeyboardInterrupt:
        print("Program interrupted. Closing the database connection.")
        return 130
    finally:
        if connection is not None:
            close_connection(connection)
            print("Database connection closed.")


if __name__ == "__main__":
    raise SystemExit(main())
