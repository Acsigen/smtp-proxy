"""Database connection and schema initialization."""

import sqlite3
from pathlib import Path
import threading


class Database:
    """SQLite database connection manager."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._ensure_directory()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _ensure_directory(self) -> None:
        """Ensure the database directory exists."""
        db_dir = Path(self.path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def _init_schema(self) -> None:
        """Initialize the database schema."""
        schema = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            recipients TEXT NOT NULL,
            subject TEXT DEFAULT '',
            body TEXT NOT NULL,
            raw_message BLOB NOT NULL,
            size_bytes INTEGER NOT NULL,
            received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'received',
            smtp_auth_user TEXT DEFAULT '',
            client_ip TEXT DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_emails_received_at ON emails(received_at DESC);
        CREATE INDEX IF NOT EXISTS idx_emails_sender ON emails(sender);
        CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status);
        """
        with self._lock:
            self.conn.executescript(schema)
            self.conn.commit()

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a query with thread safety."""
        with self._lock:
            cursor = self.conn.execute(query, params)
            self.conn.commit()
            return cursor

    def executemany(self, query: str, params_list: list[tuple]) -> sqlite3.Cursor:
        """Execute many queries with thread safety."""
        with self._lock:
            cursor = self.conn.executemany(query, params_list)
            self.conn.commit()
            return cursor

    def fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        """Fetch one row."""
        with self._lock:
            cursor = self.conn.execute(query, params)
            return cursor.fetchone()

    def fetchall(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Fetch all rows."""
        with self._lock:
            cursor = self.conn.execute(query, params)
            return cursor.fetchall()

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            self.conn.close()
