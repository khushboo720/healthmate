"""SQLite access layer (stdlib sqlite3, parameterised queries only)."""
import sqlite3
from typing import Any, Iterator

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  age INTEGER,
  gender TEXT DEFAULT '',
  blood_group TEXT DEFAULT '',
  allergies TEXT DEFAULT '',
  medical_history TEXT DEFAULT '',
  water_goal_ml INTEGER DEFAULT 2500,
  sleep_goal_h REAL DEFAULT 8,
  activity_goal_min INTEGER DEFAULT 30,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS health_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  recorded_at TEXT NOT NULL,
  weight_kg REAL, height_cm REAL, systolic INTEGER, diastolic INTEGER,
  glucose_mgdl REAL, temperature_c REAL, notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS medicines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  dosage TEXT NOT NULL,
  times TEXT NOT NULL,            -- JSON list of "HH:MM"
  frequency TEXT NOT NULL DEFAULT 'daily',  -- daily | alternate | weekly
  start_date TEXT NOT NULL,
  end_date TEXT,
  notes TEXT DEFAULT '',
  active INTEGER NOT NULL DEFAULT 1,
  prescription_id INTEGER REFERENCES prescriptions(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS prescriptions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  doctor TEXT DEFAULT '',
  prescribed_on TEXT NOT NULL,
  notes TEXT DEFAULT '',
  filename TEXT DEFAULT '',
  stored_path TEXT DEFAULT '',
  extracted_text TEXT DEFAULT '',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS medicine_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  medicine_id INTEGER NOT NULL REFERENCES medicines(id) ON DELETE CASCADE,
  scheduled_for TEXT NOT NULL,    -- "YYYY-MM-DD HH:MM"
  status TEXT NOT NULL,           -- taken | skipped
  logged_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (medicine_id, scheduled_for)
);
CREATE TABLE IF NOT EXISTS wellness_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  log_date TEXT NOT NULL,
  water_ml INTEGER DEFAULT 0,
  sleep_hours REAL DEFAULT 0,
  activity_min INTEGER DEFAULT 0,
  mood TEXT DEFAULT '',
  UNIQUE (user_id, log_date)
);
CREATE TABLE IF NOT EXISTS appointments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  doctor TEXT NOT NULL,
  specialization TEXT DEFAULT '',
  clinic TEXT DEFAULT '',
  scheduled_at TEXT NOT NULL,     -- "YYYY-MM-DD HH:MM"
  purpose TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'upcoming'  -- upcoming | completed | cancelled
);
CREATE TABLE IF NOT EXISTS chat_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL,             -- user | assistant
  content TEXT NOT NULL,
  mode TEXT DEFAULT '',           -- live | demo | safety
  emergency INTEGER DEFAULT 0,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  stored_path TEXT NOT NULL,
  extracted_text TEXT DEFAULT '',
  flagged TEXT DEFAULT '[]',      -- JSON list of parsed results
  summary TEXT DEFAULT '',
  summary_mode TEXT DEFAULT '',
  test_date TEXT DEFAULT '',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS lab_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  report_id INTEGER REFERENCES reports(id) ON DELETE CASCADE,
  test_name TEXT NOT NULL,
  test_key TEXT NOT NULL,
  value REAL NOT NULL,
  unit TEXT DEFAULT '',
  ref_low REAL,
  ref_high REAL,
  status TEXT NOT NULL DEFAULT 'normal',   -- low | high | normal
  test_date TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'report'    -- report | manual | sample
);
CREATE INDEX IF NOT EXISTS idx_lab_user_key_date ON lab_results (user_id, test_key, test_date);
"""

# Columns added after the first release. Applied to existing databases on startup.
MIGRATIONS = [
    ("medicines", "prescription_id", "INTEGER REFERENCES prescriptions(id) ON DELETE SET NULL"),
    ("reports", "test_date", "TEXT DEFAULT ''"),
]


def connect() -> sqlite3.Connection:
    # FastAPI may run a request's dependencies and endpoint on different worker threads.
    # Each connection is still used by one request at a time, so this is safe.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        for table, column, ddl in MIGRATIONS:
            existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}  # names come from the constant above
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def get_db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def rows(db: sqlite3.Connection, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def row(db: sqlite3.Connection, sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
    r = db.execute(sql, params).fetchone()
    return dict(r) if r else None
