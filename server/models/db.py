"""SQLite persistence. One file, plain SQL, rows returned as dicts."""
import json
import sqlite3
import uuid
from contextlib import contextmanager

from config.settings import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS farmer (
  farmer_id TEXT PRIMARY KEY, name TEXT NOT NULL, language TEXT NOT NULL DEFAULT 'hi',
  phone TEXT, state TEXT NOT NULL, district TEXT NOT NULL, village TEXT
);
CREATE TABLE IF NOT EXISTS plot (
  plot_id TEXT PRIMARY KEY, farmer_id TEXT NOT NULL, name TEXT NOT NULL, area_acres REAL NOT NULL,
  lat REAL NOT NULL, lon REAL NOT NULL, survey_number TEXT, nearest_market TEXT,
  created_seq INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS season (
  season_id TEXT PRIMARY KEY, plot_id TEXT NOT NULL, crop TEXT NOT NULL, season_label TEXT NOT NULL,
  sowing_date TEXT NOT NULL, status TEXT NOT NULL, policy_number TEXT
);
CREATE TABLE IF NOT EXISTS entry (
  entry_id TEXT PRIMARY KEY, season_id TEXT NOT NULL, entry_date TEXT NOT NULL, category TEXT NOT NULL,
  item TEXT, quantity REAL, unit TEXT, cost_inr REAL, price_per_unit_inr REAL, raw_text TEXT,
  photo_id TEXT, source TEXT NOT NULL, logged_by TEXT NOT NULL DEFAULT 'farmer',
  deleted INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS photo (
  photo_id TEXT PRIMARY KEY, season_id TEXT NOT NULL, event_id TEXT, taken_at TEXT NOT NULL,
  lat REAL, lon REAL, location_source TEXT NOT NULL, file_path TEXT NOT NULL,
  vision_tag TEXT, vision_confidence REAL, is_placeholder INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS event (
  event_id TEXT PRIMARY KEY, plot_id TEXT NOT NULL, season_id TEXT, type TEXT NOT NULL,
  event_date TEXT NOT NULL, status TEXT NOT NULL, trigger TEXT NOT NULL, trigger_detail TEXT,
  confirmed_at TEXT, report_deadline TEXT NOT NULL, estimated_loss_quintals REAL, farmer_notes TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_pack (
  pack_id TEXT PRIMARY KEY, event_id TEXT NOT NULL, generated_at TEXT NOT NULL, file_path TEXT NOT NULL,
  data_sources TEXT NOT NULL, past_deadline INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS simulation (
  sim_id TEXT PRIMARY KEY, plot_id TEXT NOT NULL, date TEXT NOT NULL, precipitation_mm REAL NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alert (
  alert_id TEXT PRIMARY KEY, event_id TEXT, plot_id TEXT, kind TEXT NOT NULL, message TEXT NOT NULL,
  created_at TEXT NOT NULL, read INTEGER NOT NULL DEFAULT 0
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.database_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def rows(conn, sql: str, params=()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def one(conn, sql: str, params=()) -> dict | None:
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None


def insert(conn, table: str, data: dict) -> None:
    cols = ", ".join(data)
    marks = ", ".join("?" for _ in data)
    conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(data.values()))


def update(conn, table: str, key: str, key_value, data: dict) -> None:
    if not data:
        return
    sets = ", ".join(f"{k} = ?" for k in data)
    conn.execute(f"UPDATE {table} SET {sets} WHERE {key} = ?", (*data.values(), key_value))


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def loads(value):
    return json.loads(value) if value else None
