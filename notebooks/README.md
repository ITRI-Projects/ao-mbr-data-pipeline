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
a CSV stored on Google Drive. It runs independently of SQL Server and `.env`.

```bash
.venv/bin/python -m pip install -r notebooks/requirements-drive.txt
.venv/bin/python -m jupyterlab notebooks/02_explore_google_drive_csv.ipynb
```

In the configuration cell, paste the file's share link or ID into
`DRIVE_FILE_URL_OR_ID`, choose `ACCESS_MODE`, and set `TIMESTAMP_COLUMN` to the
CSV's timestamp header (default: `datetime`). The remaining columns should be
numeric sensor readings; blanks remain missing. Optional start/end timestamps
filter the downloaded data, with an inclusive start and exclusive end. Each load
downloads the current CSV in full, so the file must fit in memory. The notebook
reads an uploaded CSV, not a Google Sheets document.

- **Shared link:** Set `ACCESS_MODE = "public"`. The file must allow downloads
  for **Anyone with the link**. No Google Cloud setup is needed. The notebook uses
  [gdown](https://github.com/wkentaro/gdown) to handle Drive's download pages.
- **Private file:** Keep `ACCESS_MODE = "oauth"`. Follow
  [Google's Python quickstart](https://developers.google.com/workspace/drive/api/quickstart/python)
  to enable the Drive API in a Google Cloud project, configure Google Auth
  Platform, and create an OAuth client of type **Desktop app**. For a personal
  Google account, choose an External audience and add your account as a test
  user while the app is in testing. Add the
  `https://www.googleapis.com/auth/drive.readonly` scope under Data Access.
  Save the downloaded client JSON as
  `data/google-drive/credentials.json` (create the directory if needed).
  On the first run, open the printed sign-in URL and authorize an account that
  can read the file. The callback uses `localhost:8765`, so your browser must be
  able to reach that port on the machine running the kernel. For remote Jupyter,
  forward that port over SSH first. Subsequent runs reuse
  `data/google-drive/token.json`; if authorization expires or is revoked, delete
  this token file and sign in again.

Private downloads use the [Drive API's file download method](https://developers.google.com/workspace/drive/api/guides/manage-downloads).
The read-only OAuth scope permits reading files accessible to the signed-in
account; the notebook requests only the configured file. Credentials and tokens
stay under the existing Git-ignored `data/` directory. Clear notebook outputs
before committing, including any sign-in URLs and sensor readings.
