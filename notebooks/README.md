# Cleaned data notebook

From the repository root, install the notebook dependencies and start Jupyter:

```bash
.venv/bin/python -m pip install -r notebooks/requirements.txt
.venv/bin/python -m jupyterlab notebooks/01_explore_clean_data.ipynb
```

Use the Python kernel from this environment. If using the VS Code notebook editor,
select `.venv/bin/python` as the kernel.

Configure the repository `.env` using `.env.example`. The notebook reuses
`src.database.get_connection()` to connect to `DB_SERVER` and `DB_NAME` and read
`dbo.CleanedSensorData`. The configured account needs SELECT permission on the
table. Install Microsoft ODBC Driver 18 for SQL Server separately from the Python
requirements.

Run the cells in order. Optional start/end timestamps restrict the query;
otherwise it loads the entire table into memory. The resulting `df` has a
sorted datetime index and one column per sensor. Connections are closed after
loading, and no database writes are performed.

Clear notebook outputs before committing to keep sensor readings out of Git.

## Google Drive CSV notebook

`02_explore_google_drive_csv.ipynb` provides the same inspections and charts using
a CSV stored on Google Drive. It runs independently of SQL Server and reads its
Drive configuration from the repository's `.env`.

```bash
.venv/bin/python -m pip install -r notebooks/requirements-drive.txt
.venv/bin/python -m jupyterlab notebooks/02_explore_google_drive_csv.ipynb
```

Set the file's share link or ID in the repository's `.env` (also shown in
`.env.example`):

```dotenv
DRIVE_FILE_URL_OR_ID="https://drive.google.com/file/d/YOUR_FILE_ID/view"
```

The file must allow downloads for **Anyone with the link**. The notebook uses
[gdown](https://github.com/wkentaro/gdown) to handle Drive's download pages.
No access-mode setting, Google sign-in, or Google Cloud setup is needed.
The `.env` file is Git-ignored. After changing it, rerun the import and
configuration cells so the notebook reloads the value. In the notebook's configuration cell, set
`TIMESTAMP_COLUMN` to the CSV's timestamp header (default: `datetime`). Timestamp
header matching ignores capitalization and surrounding whitespace, so `DateTime`
also works with the default. Multiple matching timestamp headers are rejected.
The remaining columns should be
numeric sensor readings; blanks remain missing. Optional start/end timestamps
filter the downloaded data, with an inclusive start and exclusive end. Each load
downloads the current CSV in full, so the file must fit in memory. The notebook
reads an uploaded CSV, not a Google Sheets document.

Clear notebook outputs before committing to keep sensor readings out of Git.
