import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[1] / 'data' / 'submissions.sqlite3'


class SubmissionStore:
    def __init__(self, path=DEFAULT_PATH):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=30)
        self.connection.execute('''CREATE TABLE IF NOT EXISTS submissions (
            key TEXT PRIMARY KEY, sensor TEXT NOT NULL, source_id TEXT,
            tag TEXT NOT NULL, timestamp TEXT NOT NULL, value_json TEXT NOT NULL,
            status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 1,
            http_status INTEGER, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
        self.connection.commit()

    def claim(self, destination, sensor, source_id, payload):
        encoded = json.dumps([destination, payload], sort_keys=True, separators=(',', ':'), allow_nan=False)
        key = hashlib.sha256(encoded.encode()).hexdigest()
        # Atomic insert/update prevents two processes claiming the same reading.
        with self.connection:
            cursor = self.connection.execute('''INSERT OR IGNORE INTO submissions
                (key, sensor, source_id, tag, timestamp, value_json, status)
                VALUES (?, ?, ?, ?, ?, ?, 'in_flight')''',
                (key, sensor, str(source_id), payload['fullTagName'], payload['datetime'], json.dumps(payload['value'])))
            if cursor.rowcount:
                return key, 'claimed'
            cursor = self.connection.execute('''UPDATE submissions SET status='in_flight',
                attempts=attempts+1, http_status=NULL, updated_at=CURRENT_TIMESTAMP
                WHERE key=? AND status='retry_ready' ''', (key,))
            if cursor.rowcount:
                return key, 'claimed'
            status = self.connection.execute('SELECT status FROM submissions WHERE key=?', (key,)).fetchone()[0]
        return key, status

    def finish(self, key, status, http_status=None):
        if status not in {'http_success', 'http_failed', 'uncertain'}:
            raise ValueError('Invalid delivery status')
        with self.connection:
            self.connection.execute('''UPDATE submissions SET status=?, http_status=?,
                updated_at=CURRENT_TIMESTAMP WHERE key=?''', (status, http_status, key))

    def resolve(self, key, action):
        status = {'delivered': 'confirmed_delivered', 'retry': 'retry_ready'}[action]
        with self.connection:
            cursor = self.connection.execute('''UPDATE submissions SET status=?, updated_at=CURRENT_TIMESTAMP
                WHERE key=? AND status IN ('in_flight', 'uncertain', 'http_failed')''', (status, key))
        if cursor.rowcount != 1:
            raise ValueError('No unresolved entry matches this key')

    def close(self):
        self.connection.close()


def main():
    parser = argparse.ArgumentParser(description='Inspect or resolve submission delivery records. Stop submission jobs before resolving entries.')
    parser.add_argument('--ledger', default=str(DEFAULT_PATH))
    parser.add_argument('--resolve', metavar='KEY')
    parser.add_argument('--action', choices=['delivered', 'retry'])
    args = parser.parse_args()
    if bool(args.resolve) != bool(args.action):
        parser.error('--resolve and --action must be provided together')
    store = SubmissionStore(args.ledger)
    try:
        if args.resolve:
            store.resolve(args.resolve, args.action)
            print('Resolution saved.')
        else:
            for row in store.connection.execute('''SELECT key, sensor, timestamp, status, attempts, http_status
                FROM submissions WHERE status IN ('in_flight', 'uncertain', 'http_failed') ORDER BY timestamp'''):
                print(*row, sep=' | ')
    finally:
        store.close()


if __name__ == '__main__':
    main()
