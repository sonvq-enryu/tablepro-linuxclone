"""MySQL driver implementation using mysql-connector-python."""

from typing import Any

import mysql.connector

from tablefree.db.config import ConnectionConfig
from tablefree.db.driver import ColumnInfo, DatabaseDriver, ForeignKeyInfo, IndexInfo

# System databases that should be excluded from schema listings.
_SYSTEM_DATABASES = frozenset(
    {"information_schema", "mysql", "performance_schema", "sys"}
)


def _get_key(row: dict, upper: str, lower: str, default: Any = None) -> Any:
    """Retrieve a value from *row* trying the UPPER key first, then lower.

    Unlike ``row.get(upper) or row.get(lower)``, this is ``None``-aware
    and correctly handles falsy values like ``0`` or ``""``.
    """
    val = row.get(upper)
    if val is not None:
        return val
    val = row.get(lower)
    if val is not None:
        return val
    return default


class MySQLDriver(DatabaseDriver):
    """MySQL driver backed by mysql-connector-python."""

    def connect(self) -> None:
        if self._connection is not None:
            return
        self._connection = mysql.connector.connect(
            host=self._config.host,
            port=self._config.port,
            database=self._config.database,
            user=self._config.username,
            password=self._config.password,
            autocommit=True,
            **self._config.options,
        )

    def disconnect(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def execute(self, query: str, params: tuple | None = None) -> list[dict[str, Any]]:
        if self._connection is None:
            raise RuntimeError("Not connected — call connect() first")
        cursor = self._connection.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            # Non-SELECT statements produce no result set.
            if cursor.description is None:
                return []
            return [dict(row) for row in cursor.fetchall()]
        finally:
            cursor.close()

    # ── Metadata introspection ───────────────────────────────

    def get_schemas(self) -> list[str]:
        rows = self.execute("SHOW DATABASES")
        return sorted(
            r["Database"]
            for r in rows
            if r["Database"].lower() not in _SYSTEM_DATABASES
        )

    def get_tables(self, schema: str | None = None) -> list[str]:
        schema = schema or self._config.database
        rows = self.execute(
            """
            SELECT table_name
              FROM information_schema.tables
             WHERE table_schema = %s
               AND table_type   = 'BASE TABLE'
             ORDER BY table_name
            """,
            (schema,),
        )
        # MySQL may return the key as TABLE_NAME or table_name depending
        # on the server's lower_case_table_names setting.
        key = "TABLE_NAME" if rows and "TABLE_NAME" in rows[0] else "table_name"
        return [r[key] for r in rows]

    def get_columns(self, table: str, schema: str | None = None) -> list[ColumnInfo]:
        schema = schema or self._config.database
        rows = self.execute(
            """
            SELECT column_name,
                   data_type,
                   is_nullable,
                   column_default,
                   ordinal_position
              FROM information_schema.columns
             WHERE table_schema = %s
               AND table_name   = %s
             ORDER BY ordinal_position
            """,
            (schema, table),
        )
        return [
            ColumnInfo(
                name=r.get("COLUMN_NAME") or r.get("column_name", ""),
                data_type=r.get("DATA_TYPE") or r.get("data_type", ""),
                is_nullable=(r.get("IS_NULLABLE") or r.get("is_nullable", "NO"))
                == "YES",
                column_default=r.get("COLUMN_DEFAULT") or r.get("column_default"),
                ordinal_position=r.get("ORDINAL_POSITION")
                or r.get("ordinal_position", 0),
            )
            for r in rows
        ]

    def get_indexes(self, table: str, schema: str | None = None) -> list[IndexInfo]:
        schema = schema or self._config.database
        rows = self.execute(
            """
            SELECT index_name,
                   column_name,
                   non_unique,
                   seq_in_index
              FROM information_schema.statistics
             WHERE table_schema = %s
               AND table_name   = %s
             ORDER BY index_name, seq_in_index
            """,
            (schema, table),
        )

        # Group columns by index name.
        indexes: dict[str, IndexInfo] = {}
        for r in rows:
            idx_name = _get_key(r, "INDEX_NAME", "index_name", "")
            col_name = _get_key(r, "COLUMN_NAME", "column_name", "")
            non_unique = _get_key(r, "NON_UNIQUE", "non_unique", 1)

            if idx_name not in indexes:
                indexes[idx_name] = IndexInfo(
                    name=idx_name,
                    columns=[],
                    is_unique=not bool(non_unique),
                    is_primary=(idx_name == "PRIMARY"),
                )
            indexes[idx_name].columns.append(col_name)

        return list(indexes.values())

    def get_foreign_keys(
        self, table: str, schema: str | None = None
    ) -> list[ForeignKeyInfo]:
        schema = schema or self._config.database
        rows = self.execute(
            """
            SELECT
                tc.constraint_name,
                kcu.column_name,
                kcu.referenced_table_name,
                kcu.referenced_column_name,
                rc.delete_rule,
                rc.update_rule
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.referential_constraints rc
                ON tc.constraint_name = rc.constraint_name
                AND tc.table_schema = rc.constraint_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = %s
                AND tc.table_name = %s
            """,
            (schema, table),
        )
        return [
            ForeignKeyInfo(
                name=r.get("CONSTRAINT_NAME") or r.get("constraint_name", ""),
                column=r.get("COLUMN_NAME") or r.get("column_name", ""),
                ref_table=r.get("REFERENCED_TABLE_NAME")
                or r.get("referenced_table_name", ""),
                ref_column=r.get("REFERENCED_COLUMN_NAME")
                or r.get("referenced_column_name", ""),
                on_delete=r.get("DELETE_RULE") or r.get("delete_rule", "NO ACTION"),
                on_update=r.get("UPDATE_RULE") or r.get("update_rule", "NO ACTION"),
            )
            for r in rows
        ]

    def get_ddl(self, table: str, schema: str | None = None) -> str:
        schema = schema or self._config.database
        rows = self.execute(
            f"SHOW CREATE TABLE `{schema}`.`{table}`",
        )
        if rows:
            row = rows[0]
            key = "Create Table" if "Create Table" in row else "create table"
            return row.get(key, "")
        return ""
