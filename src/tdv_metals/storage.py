"""Small SQLite persistence layer for auditable research snapshots and backtests."""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ResearchStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS backtests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def save_snapshot(self, payload: dict[str, Any]) -> int:
        with self._connection() as connection:
            cursor = connection.execute(
                "INSERT INTO snapshots(created_at, payload_json) VALUES (?, ?)",
                (datetime.now(timezone.utc).isoformat(), json.dumps(payload, default=str, allow_nan=False)),
            )
            return int(cursor.lastrowid)

    def latest_snapshot(self) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT payload_json FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()
        return json.loads(row[0]) if row else None

    def save_backtest(self, symbol: str, payload: dict[str, Any]) -> int:
        with self._connection() as connection:
            cursor = connection.execute(
                "INSERT INTO backtests(created_at, symbol, payload_json) VALUES (?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), symbol, json.dumps(payload, default=str, allow_nan=False)),
            )
            return int(cursor.lastrowid)
