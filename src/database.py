import os

import pyodbc
from dotenv import load_dotenv

load_dotenv()


def _required_setting(name):
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment setting: {name}")
    return value


def _odbc_value(value):
    # Utility function for braces protect semicolons; 
    # closing braces must be escaped in ODBC values.
    return "{" + value.replace("}", "}}") + "}"


def get_connection():
    driver = _required_setting("DB_DRIVER")
    server = _required_setting("DB_SERVER")
    database = _required_setting("DB_NAME")
    trusted = os.getenv("DB_TRUSTED_CONNECTION", "true").strip().lower()
    if trusted not in {"true", "false", "yes", "no", "1", "0"}:
        raise ValueError("DB_TRUSTED_CONNECTION must be true or false")

    connection_string = (
        f"DRIVER={_odbc_value(driver)};"
        f"SERVER={_odbc_value(server)};"
        f"DATABASE={_odbc_value(database)};"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )
    if trusted in {"true", "yes", "1"}:
        connection_string += "Trusted_Connection=yes;"
    else:
        username = _required_setting("DB_USERNAME")
        password = _required_setting("DB_PASSWORD")
        connection_string += (
            f"UID={_odbc_value(username)};"
            f"PWD={_odbc_value(password)};"
        )

    return pyodbc.connect(connection_string, timeout=5)


def close_connection(connection):
    if connection is not None:
        connection.close()
