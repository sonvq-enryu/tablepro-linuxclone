"""Cache for database schema metadata used by auto-completion."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QThreadPool, Signal

from tablefree.db.driver import ColumnInfo, DatabaseDriver
from tablefree.workers.query_worker import QueryWorker


class SchemaMetadataCache(QObject):
    """Caches schemas, tables, and columns fetched from the active driver.

    Columns are loaded lazily on first request per table. An epoch counter
    invalidates stale results when the driver changes.
    """

    cache_updated = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._driver: DatabaseDriver | None = None
        self._epoch = 0
        self._schemas: list[str] = []
        self._tables: dict[str, list[str]] = {}  # schema -> table names
        self._columns: dict[tuple[str, str], list[ColumnInfo]] = {}  # (schema, table) -> cols
        self._pending_columns: set[tuple[str, str]] = set()

    def set_driver(self, driver: DatabaseDriver | None) -> None:
        """Replace the active driver and refresh the cache."""
        self._driver = driver
        self._epoch += 1
        self._schemas.clear()
        self._tables.clear()
        self._columns.clear()
        self._pending_columns.clear()
        if driver is not None:
            self._fetch_schemas()

    def get_schemas(self) -> list[str]:
        return list(self._schemas)

    def get_tables(self, schema: str | None = None) -> list[str]:
        if schema and schema in self._tables:
            return list(self._tables[schema])
        # Return tables from all known schemas
        all_tables: list[str] = []
        for tables in self._tables.values():
            all_tables.extend(tables)
        return all_tables

    def get_all_table_names(self) -> list[str]:
        """Return a flat list of every cached table name."""
        return self.get_tables()

    def get_columns(self, table: str, schema: str | None = None) -> list[ColumnInfo]:
        """Return cached columns for *table*. Triggers lazy fetch if not cached."""
        if schema:
            key = (schema, table)
            if key in self._columns:
                return list(self._columns[key])
            self._fetch_columns(table, schema)
            return []

        # Search across all schemas
        for (s, t), cols in self._columns.items():
            if t == table:
                return list(cols)
        # Try to find which schema owns this table and fetch
        for s, tables in self._tables.items():
            if table in tables:
                self._fetch_columns(table, s)
                break
        return []

    # ── Private fetchers ─────────────────────────────────────

    def _fetch_schemas(self) -> None:
        driver = self._driver
        if driver is None:
            return
        epoch = self._epoch

        def _work() -> list[str]:
            return driver.get_schemas()

        worker = QueryWorker(_work)
        worker.signals.finished.connect(lambda result, e=epoch: self._on_schemas(result, e))
        QThreadPool.globalInstance().start(worker)

    def _on_schemas(self, schemas: Any, epoch: int) -> None:
        if epoch != self._epoch:
            return
        self._schemas = list(schemas) if schemas else []
        # Fetch tables for each schema
        for schema in self._schemas:
            self._fetch_tables(schema)
        self.cache_updated.emit()

    def _fetch_tables(self, schema: str) -> None:
        driver = self._driver
        if driver is None:
            return
        epoch = self._epoch

        def _work() -> list[str]:
            return driver.get_tables(schema)

        worker = QueryWorker(_work)
        worker.signals.finished.connect(
            lambda result, s=schema, e=epoch: self._on_tables(result, s, e)
        )
        QThreadPool.globalInstance().start(worker)

    def _on_tables(self, tables: Any, schema: str, epoch: int) -> None:
        if epoch != self._epoch:
            return
        self._tables[schema] = list(tables) if tables else []
        self.cache_updated.emit()

    def _fetch_columns(self, table: str, schema: str) -> None:
        driver = self._driver
        if driver is None:
            return
        key = (schema, table)
        if key in self._pending_columns:
            return
        self._pending_columns.add(key)
        epoch = self._epoch

        def _work() -> list[ColumnInfo]:
            return driver.get_columns(table, schema)

        worker = QueryWorker(_work)
        worker.signals.finished.connect(
            lambda result, s=schema, t=table, e=epoch: self._on_columns(result, s, t, e)
        )
        worker.signals.error.connect(lambda _exc, k=key: self._pending_columns.discard(k))
        QThreadPool.globalInstance().start(worker)

    def _on_columns(self, columns: Any, schema: str, table: str, epoch: int) -> None:
        key = (schema, table)
        self._pending_columns.discard(key)
        if epoch != self._epoch:
            return
        self._columns[key] = list(columns) if columns else []
        self.cache_updated.emit()
