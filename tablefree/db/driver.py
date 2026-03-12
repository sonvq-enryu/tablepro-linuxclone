"""DatabaseDriver abstract base class — the core driver interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from tablefree.db.config import ConnectionConfig


@dataclass
class ColumnInfo:
    """Metadata for a single table column."""

    name: str
    data_type: str
    is_nullable: bool
    column_default: str | None
    ordinal_position: int


@dataclass
class IndexInfo:
    """Metadata for a single index."""

    name: str
    columns: list[str] = field(default_factory=list)
    is_unique: bool = False
    is_primary: bool = False


@dataclass
class ForeignKeyInfo:
    """Metadata for a single foreign key constraint."""

    name: str
    column: str
    ref_table: str
    ref_column: str
    on_delete: str
    on_update: str


class DatabaseDriver(ABC):
    """Abstract base class for all database drivers.

    Every concrete driver must implement the abstract methods defined here.
    The class also provides context-manager support and a default
    ``test_connection()`` implementation built on ``connect()`` + ``execute()``.
    """

    def __init__(self, config: ConnectionConfig) -> None:
        self._config = config
        self._connection: Any = None

    # ── Properties ───────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        """Whether the driver currently holds an open connection."""
        return self._connection is not None

    @property
    def config(self) -> ConnectionConfig:
        """Return the immutable connection config."""
        return self._config

    # ── Abstract interface ───────────────────────────────────

    @abstractmethod
    def connect(self) -> None:
        """Establish a connection to the database."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection and release resources."""
        ...

    @abstractmethod
    def execute(self, query: str, params: tuple | None = None) -> list[dict[str, Any]]:
        """Execute a query and return results as a list of dicts.

        Each dict maps column-name → value for one row.
        For non-SELECT statements the list may be empty.
        """
        ...

    @abstractmethod
    def get_schemas(self) -> list[str]:
        """Return a list of schema (or database) names."""
        ...

    @abstractmethod
    def get_tables(self, schema: str | None = None) -> list[str]:
        """Return table names in the given schema.

        If *schema* is ``None`` the driver should use a sensible default
        (e.g. ``"public"`` for PostgreSQL, the current database for MySQL).
        """
        ...

    @abstractmethod
    def get_columns(self, table: str, schema: str | None = None) -> list[ColumnInfo]:
        """Return column metadata for *table*."""
        ...

    @abstractmethod
    def get_indexes(self, table: str, schema: str | None = None) -> list[IndexInfo]:
        """Return index metadata for *table*."""
        ...

    @abstractmethod
    def get_foreign_keys(
        self, table: str, schema: str | None = None
    ) -> list[ForeignKeyInfo]:
        """Return foreign key constraints for *table*."""
        ...

    @abstractmethod
    def get_ddl(self, table: str, schema: str | None = None) -> str:
        """Return the CREATE TABLE DDL statement for *table*."""
        ...

    # ── Concrete helpers ─────────────────────────────────────

    def test_connection(self) -> bool:
        """Quick connectivity check — returns ``True`` on success."""
        try:
            self.connect()
            result = self.execute("SELECT 1")
            return len(result) > 0
        except Exception:
            return False
        finally:
            self.disconnect()

    # ── Context manager ──────────────────────────────────────

    def __enter__(self) -> "DatabaseDriver":
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        self.disconnect()
        return False
