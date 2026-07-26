"""Storage for Mini App state and submissions.

Same reasoning as the bot engine: SQLite with WAL, one file, trivial to back
up. Apps get a per-user JSON blob for their own state plus an append-only
submissions log the owner reads.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS app_state (
    app     TEXT NOT NULL,
    tg_id   INTEGER NOT NULL,
    payload TEXT NOT NULL,
    updated REAL NOT NULL,
    PRIMARY KEY (app, tg_id)
);

CREATE TABLE IF NOT EXISTS submissions (
    id       INTEGER PRIMARY KEY,
    app      TEXT NOT NULL,
    tg_id    INTEGER NOT NULL,
    username TEXT DEFAULT '',
    kind     TEXT NOT NULL,
    payload  TEXT NOT NULL,
    created  REAL NOT NULL,
    handled  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_sub_app_created ON submissions(app, created DESC);
CREATE INDEX IF NOT EXISTS ix_sub_user ON submissions(app, tg_id, created);
"""


class AppStore:
    def __init__(self, path: str | Path = "miniapps.db") -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ----------------------------------------------------------- app state

    def save_state(self, app: str, tg_id: int, payload: dict[str, Any]) -> None:
        blob = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                "INSERT INTO app_state (app, tg_id, payload, updated) VALUES (?,?,?,?) "
                "ON CONFLICT(app, tg_id) DO UPDATE SET payload=excluded.payload, "
                "updated=excluded.updated",
                (app, tg_id, blob, time.time()),
            )
            self._conn.commit()

    def read_state(self, app: str, tg_id: int) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM app_state WHERE app=? AND tg_id=?", (app, tg_id)
            ).fetchone()
        if row is None:
            return {}
        try:
            return json.loads(row["payload"])
        except json.JSONDecodeError:  # pragma: no cover - written by us
            return {}

    def profile(self, app: str, tg_id: int) -> dict[str, Any]:
        """Small summary the front-end shows without a second round trip."""
        with self._lock:
            count = self._conn.execute(
                "SELECT COUNT(*) FROM submissions WHERE app=? AND tg_id=?", (app, tg_id)
            ).fetchone()[0]
        return {"submissions": int(count), "state": self.read_state(app, tg_id)}

    # ---------------------------------------------------------- submissions

    def add_submission(
        self, *, app: str, tg_id: int, username: str, kind: str, payload: dict[str, Any]
    ) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO submissions (app, tg_id, username, kind, payload, created) "
                "VALUES (?,?,?,?,?,?)",
                (
                    app,
                    tg_id,
                    username[:64],
                    kind[:32],
                    json.dumps(payload, ensure_ascii=False)[:16_000],
                    time.time(),
                ),
            )
            self._conn.commit()
        return int(cursor.lastrowid)

    def recent_submissions(self, app: str, tg_id: int, minutes: int = 1) -> int:
        since = time.time() - minutes * 60
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM submissions WHERE app=? AND tg_id=? AND created>=?",
                (app, tg_id, since),
            ).fetchone()
        return int(row[0])

    def list_submissions(self, app: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM submissions WHERE app=? ORDER BY created DESC LIMIT ?",
                (app, limit),
            ).fetchall()
        out = []
        for row in rows:
            try:
                payload = json.loads(row["payload"])
            except json.JSONDecodeError:  # pragma: no cover
                payload = {"raw": row["payload"]}
            out.append(
                {
                    "id": row["id"],
                    "tg_id": row["tg_id"],
                    "username": row["username"],
                    "kind": row["kind"],
                    "payload": payload,
                    "created": row["created"],
                    "handled": bool(row["handled"]),
                }
            )
        return out

    def mark_handled(self, submission_id: int) -> bool:
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE submissions SET handled=1 WHERE id=?", (submission_id,)
            )
            self._conn.commit()
        return cursor.rowcount > 0
