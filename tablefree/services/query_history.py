"""SQLite-backed query history storage."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass(slots=True)
class HistoryEntry:
    id: int
    query_text: str
    connection_name: str
    executed_at: str
    duration_ms: float
    status: str
    error_message: str | None
    rows_affected: int


class QueryHistoryStore:
    """Persist and search query execution history."""

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            db_path = str(Path.home() / ".local" / "share" / "TableFree" / "query_history.db")
        self._db_path = Path(db_path).expanduser()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._fts_enabled = False
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_history (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_text      TEXT NOT NULL,
                    connection_name TEXT NOT NULL,
                    executed_at     TEXT NOT NULL,
                    duration_ms     REAL NOT NULL,
                    status          TEXT NOT NULL,
                    error_message   TEXT,
                    rows_affected   INTEGER DEFAULT 0
                )
                """
            )
            try:
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS query_history_fts
                    USING fts5(query_text, content='query_history', content_rowid='id')
                    """
                )
                conn.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS query_history_ai
                    AFTER INSERT ON query_history
                    BEGIN
                        INSERT INTO query_history_fts(rowid, query_text)
                        VALUES (new.id, new.query_text);
                    END
                    """
                )
                conn.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS query_history_ad
                    AFTER DELETE ON query_history
                    BEGIN
                        INSERT INTO query_history_fts(query_history_fts, rowid, query_text)
                        VALUES ('delete', old.id, old.query_text);
                    END
                    """
                )
                self._fts_enabled = True
            except sqlite3.OperationalError:
                # Some sqlite builds may not include FTS5.
                self._fts_enabled = False

    def record(
        self,
        query_text: str,
        connection_name: str,
        duration_ms: float,
        status: str,
        error_message: str | None = None,
        rows_affected: int = 0,
    ) -> int:
        if status not in {"success", "error"}:
            raise ValueError("status must be 'success' or 'error'")

        executed_at = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO query_history (
                    query_text,
                    connection_name,
                    executed_at,
                    duration_ms,
                    status,
                    error_message,
                    rows_affected
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query_text,
                    connection_name,
                    executed_at,
                    duration_ms,
                    status,
                    error_message,
                    rows_affected,
                ),
            )
            return int(cursor.lastrowid)

    def search(
        self,
        term: str | None = None,
        connection: str | None = None,
        status: str | None = None,
        since: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[HistoryEntry]:
        limit = max(1, limit)
        offset = max(0, offset)

        where_parts: list[str] = []
        params: list[object] = []

        if connection:
            where_parts.append("q.connection_name = ?")
            params.append(connection)
        if status:
            where_parts.append("q.status = ?")
            params.append(status.lower())
        if since:
            where_parts.append("q.executed_at >= ?")
            params.append(since)

        use_fts = bool(term and term.strip() and self._fts_enabled)
        if use_fts:
            base = (
                "SELECT q.* FROM query_history q "
                "JOIN query_history_fts f ON f.rowid = q.id "
                "WHERE f.query_text MATCH ?"
            )
            params = [term.strip(), *params]
        else:
            base = "SELECT q.* FROM query_history q"
            if term and term.strip():
                where_parts.append("q.query_text LIKE ?")
                params.append(f"%{term.strip()}%")

        if where_parts:
            joiner = " AND " if " WHERE " in base else " WHERE "
            base = f"{base}{joiner}{' AND '.join(where_parts)}"

        sql = f"{base} ORDER BY q.executed_at DESC, q.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def get_entry(self, entry_id: int) -> HistoryEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM query_history WHERE id = ?",
                (entry_id,),
            ).fetchone()
        return self._row_to_entry(row) if row else None

    def delete(self, entry_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM query_history WHERE id = ?", (entry_id,))

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM query_history")

    def cleanup(self, max_entries: int = 10000, max_age_days: int = 90) -> int:
        deleted = 0
        cutoff = datetime.now(UTC) - timedelta(days=max(0, max_age_days))
        cutoff_iso = cutoff.isoformat()

        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM query_history WHERE executed_at < ?",
                (cutoff_iso,),
            )
            if cur.rowcount > 0:
                deleted += int(cur.rowcount)

            max_entries = max(0, max_entries)
            if max_entries == 0:
                cur = conn.execute("DELETE FROM query_history")
            else:
                cur = conn.execute(
                    """
                    DELETE FROM query_history
                    WHERE id IN (
                        SELECT id
                        FROM query_history
                        ORDER BY executed_at DESC, id DESC
                        LIMIT -1 OFFSET ?
                    )
                    """,
                    (max_entries,),
                )
            if cur.rowcount > 0:
                deleted += int(cur.rowcount)
        return deleted

    def get_connections(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT connection_name
                FROM query_history
                WHERE connection_name <> ''
                ORDER BY connection_name COLLATE NOCASE ASC
                """
            ).fetchall()
        return [str(row["connection_name"]) for row in rows]

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> HistoryEntry:
        return HistoryEntry(
            id=int(row["id"]),
            query_text=str(row["query_text"]),
            connection_name=str(row["connection_name"]),
            executed_at=str(row["executed_at"]),
            duration_ms=float(row["duration_ms"]),
            status=str(row["status"]),
            error_message=row["error_message"],
            rows_affected=int(row["rows_affected"]),
        )
