"""
src/store/event_store.py
Write extracted events to SQLite (via stdlib sqlite3).
Provide analytics queries via DuckDB reading the same SQLite file.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Sequence

import duckdb
import pandas as pd

from src.extract.schema import Event

# ── Schema ────────────────────────────────────────────────────────────────────

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT,
    project     TEXT,
    topic       TEXT,
    action      TEXT NOT NULL,
    insight     TEXT,
    source_page TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_events_date    ON events(date);",
    "CREATE INDEX IF NOT EXISTS idx_events_project ON events(project);",
    "CREATE INDEX IF NOT EXISTS idx_events_source  ON events(source_page);",
]


# ── SQLite Write ──────────────────────────────────────────────────────────────

class EventStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE)
            for idx in _CREATE_INDEXES:
                conn.execute(idx)

    def insert_events(self, events: Sequence[Event]) -> int:
        """Insert events. Returns total count in table after insert."""
        if not events:
            return self.count()
        rows = [
            (e.date, e.project, e.topic, e.action, e.insight, e.source_page)
            for e in events
        ]
        with self._connect() as conn:
            conn.executemany(
                "INSERT INTO events (date, project, topic, action, insight, source_page) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
        return self.count()

    def clear(self) -> None:
        """Delete all events (useful when re-running full extraction)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM events")

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]


# ── DuckDB Analytics ──────────────────────────────────────────────────────────

class Analytics:
    """
    Read-only analytics over the SQLite events table using DuckDB.
    DuckDB can query SQLite files directly — no data copying needed.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _conn(self) -> duckdb.DuckDBPyConnection:
        conn = duckdb.connect(":memory:")
        conn.execute(f"ATTACH '{self.db_path}' AS events_db (TYPE sqlite, READ_ONLY)")
        return conn

    def monthly_activity(self) -> pd.DataFrame:
        """
        Return a DataFrame with columns: month, project, action_count.
        Suitable for a bar / timeline chart.
        """
        conn = self._conn()
        return conn.execute("""
            SELECT
                strftime(date, '%Y-%m')   AS month,
                COALESCE(project, 'Untagged') AS project,
                COUNT(*)                  AS action_count
            FROM events_db.events
            WHERE date IS NOT NULL
            GROUP BY month, project
            ORDER BY month, action_count DESC
        """).df()

    def top_projects(self, limit: int = 10) -> pd.DataFrame:
        conn = self._conn()
        return conn.execute(f"""
            SELECT
                COALESCE(project, 'Untagged') AS project,
                COUNT(*) AS action_count,
                COUNT(DISTINCT strftime(date, '%Y-%m')) AS active_months
            FROM events_db.events
            WHERE date IS NOT NULL
            GROUP BY project
            ORDER BY action_count DESC
            LIMIT {limit}
        """).df()

    def recent_insights(self, limit: int = 20) -> pd.DataFrame:
        conn = self._conn()
        return conn.execute(f"""
            SELECT date, project, topic, insight, source_page
            FROM events_db.events
            WHERE insight IS NOT NULL
            ORDER BY date DESC NULLS LAST
            LIMIT {limit}
        """).df()

    def year_summary(self, year: int) -> pd.DataFrame:
        """Month-by-month breakdown for a specific year."""
        conn = self._conn()
        return conn.execute(f"""
            SELECT
                strftime(date, '%Y-%m') AS month,
                COUNT(*) AS actions,
                COUNT(DISTINCT project) AS projects,
                COUNT(DISTINCT topic) AS topics
            FROM events_db.events
            WHERE date LIKE '{year}-%'
            GROUP BY month
            ORDER BY month
        """).df()
