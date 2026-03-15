"""Tests for tablefree.services.query_history."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tablefree.services import QueryHistoryStore


def _store(tmp_path: Path) -> QueryHistoryStore:
    return QueryHistoryStore(db_path=str(tmp_path / "history.db"))


def test_record_and_get_entry(tmp_path: Path) -> None:
    store = _store(tmp_path)
    entry_id = store.record(
        query_text="SELECT * FROM users",
        connection_name="local-db",
        duration_ms=12.3,
        status="success",
        rows_affected=3,
    )
    entry = store.get_entry(entry_id)
    assert entry is not None
    assert entry.query_text == "SELECT * FROM users"
    assert entry.connection_name == "local-db"
    assert entry.status == "success"
    assert entry.rows_affected == 3


def test_search_term_and_filters(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record("SELECT * FROM users", "conn-a", 5.0, "success", rows_affected=2)
    store.record("SELECT * FROM orders", "conn-b", 8.0, "error", error_message="boom")

    users = store.search(term="users")
    assert len(users) == 1
    assert users[0].connection_name == "conn-a"

    conn_b = store.search(connection="conn-b")
    assert len(conn_b) == 1
    assert conn_b[0].query_text == "SELECT * FROM orders"

    errors = store.search(status="error")
    assert len(errors) == 1
    assert errors[0].status == "error"


def test_cleanup_by_count_and_age(tmp_path: Path) -> None:
    db_path = tmp_path / "history.db"
    store = QueryHistoryStore(db_path=str(db_path))
    old_id = store.record("SELECT 1", "conn", 1.0, "success")
    store.record("SELECT 2", "conn", 1.0, "success")
    store.record("SELECT 3", "conn", 1.0, "success")

    old_iso = (datetime.now(UTC) - timedelta(days=365)).isoformat()
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "UPDATE query_history SET executed_at = ? WHERE id = ?",
            (old_iso, old_id),
        )

    deleted = store.cleanup(max_entries=1, max_age_days=90)
    assert deleted >= 2
    remaining = store.search(limit=100)
    assert len(remaining) == 1


def test_delete_clear_and_get_connections(tmp_path: Path) -> None:
    store = _store(tmp_path)
    id_a = store.record("SELECT * FROM a", "alpha", 1.0, "success")
    store.record("SELECT * FROM b", "beta", 1.0, "success")
    store.record("SELECT * FROM c", "alpha", 1.0, "error")

    connections = store.get_connections()
    assert connections == ["alpha", "beta"]

    store.delete(id_a)
    assert store.get_entry(id_a) is None

    store.clear()
    assert store.search(limit=100) == []
