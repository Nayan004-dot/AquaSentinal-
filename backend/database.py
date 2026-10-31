"""SQLite schema and connection helpers."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS telemetry_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    captured_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    measurement_point TEXT NOT NULL CHECK (measurement_point = 'outlet'),
    firmware_version TEXT,
    measurements_json TEXT NOT NULL,
    ingestion_flags_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE(device_id, sequence)
);
CREATE INDEX IF NOT EXISTS idx_samples_device_captured
    ON telemetry_samples(device_id, captured_at, id);
CREATE INDEX IF NOT EXISTS idx_samples_device_received
    ON telemetry_samples(device_id, received_at);
CREATE TABLE IF NOT EXISTS outlet_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    UNIQUE(device_id, window_start, window_end)
);
CREATE INDEX IF NOT EXISTS idx_summaries_device_window
    ON outlet_summaries(device_id, window_start);
CREATE TABLE IF NOT EXISTS ingestion_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    sequence INTEGER,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_device_time
    ON ingestion_events(device_id, occurred_at);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def initialize(path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with session(path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def session(path: str | Path) -> Iterator[sqlite3.Connection]:
    """Yield a configured connection and always close it."""
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
