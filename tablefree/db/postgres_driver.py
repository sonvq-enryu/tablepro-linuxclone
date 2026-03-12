"""PostgreSQL driver implementation using psycopg2."""

from typing import Any

import psycopg2
import psycopg2.extras

from tablefree.db.config import ConnectionConfig
from tablefree.db.driver import ColumnInfo, DatabaseDriver, ForeignKeyInfo, IndexInfo


class PostgreSQLDriver(DatabaseDriver):
    """PostgreSQL driver backed by psycopg2."""

    def connect(self) -> None:
        if self._connection is not None:
            return
        self._connection = psycopg2.connect(
            host=self._config.host,
            port=self._config.port,
            dbname=self._config.database,
            user=self._config.username,
            password=self._config.password,
            **self._config.options,
        )
        # Enable autocommit so metadata queries and SELECT don't need
        # explicit transaction handling.
        self._connection.autocommit = True

    def disconnect(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def execute(self, query: str, params: tuple | None = None) -> list[dict[str, Any]]:
        if self._connection is None:
            raise RuntimeError("Not connected — call connect() first")
        with self._connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor,
        ) as cur:
            cur.execute(query, params)
            # Non-SELECT statements (DDL / DML) produce no rows.
            if cur.description is None:
                return []
            return [dict(row) for row in cur.fetchall()]

    # ── Metadata introspection ───────────────────────────────

    def get_schemas(self) -> list[str]:
        rows = self.execute(
            """
            SELECT schema_name
              FROM information_schema.schemata
             WHERE schema_name NOT LIKE 'pg_%%'
               AND schema_name <> 'information_schema'
             ORDER BY schema_name
            """
        )
        return [r["schema_name"] for r in rows]

    def get_tables(self, schema: str | None = None) -> list[str]:
        schema = schema or "public"
        rows = self.execute(
            """
            SELECT table_name
              FROM information_schema.tables
             WHERE table_schema = %s
               AND table_type = 'BASE TABLE'
             ORDER BY table_name
            """,
            (schema,),
        )
        return [r["table_name"] for r in rows]

    def get_columns(self, table: str, schema: str | None = None) -> list[ColumnInfo]:
        schema = schema or "public"
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
                name=r["column_name"],
                data_type=r["data_type"],
                is_nullable=r["is_nullable"] == "YES",
                column_default=r["column_default"],
                ordinal_position=r["ordinal_position"],
            )
            for r in rows
        ]

    def get_indexes(self, table: str, schema: str | None = None) -> list[IndexInfo]:
        schema = schema or "public"
        rows = self.execute(
            """
            SELECT i.relname            AS index_name,
                   ix.indisunique       AS is_unique,
                   ix.indisprimary      AS is_primary,
                   array_agg(a.attname ORDER BY k.n) AS columns
              FROM pg_class t
              JOIN pg_index ix     ON t.oid = ix.indrelid
              JOIN pg_class i      ON i.oid = ix.indexrelid
              JOIN pg_namespace ns ON ns.oid = t.relnamespace
              JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS k(attnum, n)
                   ON TRUE
              JOIN pg_attribute a   ON a.attrelid = t.oid
                                   AND a.attnum   = k.attnum
             WHERE t.relname  = %s
               AND ns.nspname = %s
             GROUP BY i.relname, ix.indisunique, ix.indisprimary
             ORDER BY i.relname
            """,
            (table, schema),
        )
        return [
            IndexInfo(
                name=r["index_name"],
                columns=list(r["columns"]),
                is_unique=r["is_unique"],
                is_primary=r["is_primary"],
            )
            for r in rows
        ]

    def get_foreign_keys(
        self, table: str, schema: str | None = None
    ) -> list[ForeignKeyInfo]:
        schema = schema or "public"
        rows = self.execute(
            """
            SELECT
                con.conname AS name,
                att.attname AS column,
                ref_cl.relname AS ref_table,
                ref_att.attname AS ref_column,
                CASE con.confdeltype
                    WHEN 'a' THEN 'NO ACTION'
                    WHEN 'r' THEN 'RESTRICT'
                    WHEN 'c' THEN 'CASCADE'
                    WHEN 'n' THEN 'SET NULL'
                    WHEN 'd' THEN 'SET DEFAULT'
                END AS on_delete,
                CASE con.confupdtype
                    WHEN 'a' THEN 'NO ACTION'
                    WHEN 'r' THEN 'RESTRICT'
                    WHEN 'c' THEN 'CASCADE'
                    WHEN 'n' THEN 'SET NULL'
                    WHEN 'd' THEN 'SET DEFAULT'
                END AS on_update
            FROM pg_constraint con
            JOIN pg_class cl ON cl.oid = con.conrelid
            JOIN pg_namespace ns ON ns.oid = cl.relnamespace
            JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY(con.conkey)
            JOIN pg_class ref_cl ON ref_cl.oid = con.confrelid
            JOIN pg_attribute ref_att ON ref_att.attrelid = con.confrelid AND ref_att.attnum = ANY(con.confkey)
            WHERE con.contype = 'f'
                AND cl.relname = %s
                AND ns.nspname = %s
            """,
            (table, schema),
        )
        return [
            ForeignKeyInfo(
                name=r["name"],
                column=r["column"],
                ref_table=r["ref_table"],
                ref_column=r["ref_column"],
                on_delete=r["on_delete"],
                on_update=r["on_update"],
            )
            for r in rows
        ]

    def get_ddl(self, table: str, schema: str | None = None) -> str:
        schema = schema or "public"
        columns = self.get_columns(table, schema)
        indexes = self.get_indexes(table, schema)
        fks = self.get_foreign_keys(table, schema)

        lines = [f'CREATE TABLE "{schema}"."{table}" (']
        col_lines = []
        for col in columns:
            line = f'    "{col.name}" {col.data_type}'
            if not col.is_nullable:
                line += " NOT NULL"
            if col.column_default is not None:
                line += f" DEFAULT {col.column_default}"
            col_lines.append(line)

        pk = [i for i in indexes if i.is_primary]
        if pk:
            pk_cols = ", ".join(f'"{c}"' for c in pk[0].columns)
            col_lines.append(f"    PRIMARY KEY ({pk_cols})")

        for fk in fks:
            col_lines.append(
                f'    CONSTRAINT "{fk.name}" FOREIGN KEY ("{fk.column}") '
                f'REFERENCES "{fk.ref_table}" ("{fk.ref_column}") '
                f"ON DELETE {fk.on_delete} ON UPDATE {fk.on_update}"
            )

        lines.append(",\n".join(col_lines))
        lines.append(");")

        for idx in indexes:
            if not idx.is_primary:
                unique = "UNIQUE " if idx.is_unique else ""
                idx_cols = ", ".join(f'"{c}"' for c in idx.columns)
                lines.append(
                    f'CREATE {unique}INDEX "{idx.name}" ON "{schema}"."{table}" ({idx_cols});'
                )

        return "\n".join(lines)
