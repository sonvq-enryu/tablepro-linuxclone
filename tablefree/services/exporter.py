"""Data export helpers for CSV, JSON, and SQL formats."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class CsvOptions:
    delimiter: str = ","
    include_header: bool = True
    quote_char: str = '"'
    null_text: str = ""
    line_ending: str = "\n"
    encoding: str = "utf-8"


@dataclass(slots=True)
class JsonOptions:
    pretty: bool = True
    include_nulls: bool = True
    encoding: str = "utf-8"


@dataclass(slots=True)
class SqlOptions:
    table_name: str
    include_create: bool = False
    include_drop: bool = False
    batch_size: int = 500
    encoding: str = "utf-8"
    column_types: list[str] | None = None


def _normalize_rows(rows: list[list[Any]], null_text: str) -> list[list[Any]]:
    return [[null_text if value is None else value for value in row] for row in rows]


def export_csv(
    columns: list[str],
    rows: list[list[Any]],
    path: str,
    options: CsvOptions | None = None,
) -> None:
    opts = options or CsvOptions()
    normalized_rows = _normalize_rows(rows, opts.null_text)

    with Path(path).open("w", newline="", encoding=opts.encoding) as handle:
        writer = csv.writer(
            handle,
            delimiter=opts.delimiter,
            quotechar=opts.quote_char,
            lineterminator=opts.line_ending,
        )
        if opts.include_header:
            writer.writerow(columns)
        writer.writerows(normalized_rows)


def export_json(
    columns: list[str],
    rows: list[list[Any]],
    path: str,
    options: JsonOptions | None = None,
) -> None:
    opts = options or JsonOptions()
    payload: list[dict[str, Any]] = []

    for row in rows:
        item: dict[str, Any] = {}
        for index, column in enumerate(columns):
            value = row[index] if index < len(row) else None
            if value is None and not opts.include_nulls:
                continue
            item[column] = value
        payload.append(item)

    with Path(path).open("w", encoding=opts.encoding) as handle:
        json.dump(
            payload,
            handle,
            indent=2 if opts.pretty else None,
            ensure_ascii=False,
        )


def _sql_escape_identifier(name: str) -> str:
    return f'"{name.replace(chr(34), chr(34) * 2)}"'


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return f"'\\x{bytes(value).hex()}'"

    text = str(value).replace("'", "''")
    return f"'{text}'"


def _create_table_ddl(table_name: str, columns: list[str], column_types: list[str]) -> str:
    column_defs: list[str] = []
    for index, column in enumerate(columns):
        col_type = column_types[index] if index < len(column_types) else "TEXT"
        col_type = col_type or "TEXT"
        column_defs.append(f"    {_sql_escape_identifier(column)} {col_type}")
    return f"CREATE TABLE {_sql_escape_identifier(table_name)} (\n" + ",\n".join(column_defs) + "\n);"


def export_sql(
    columns: list[str],
    rows: list[list[Any]],
    path: str,
    options: SqlOptions,
) -> None:
    if not options.table_name:
        raise ValueError("table_name is required for SQL export")
    if options.batch_size <= 0:
        raise ValueError("batch_size must be > 0")

    table_name = _sql_escape_identifier(options.table_name)
    column_list = ", ".join(_sql_escape_identifier(col) for col in columns)
    lines: list[str] = []

    if options.include_drop:
        lines.append(f"DROP TABLE IF EXISTS {table_name};")
        lines.append("")

    if options.include_create:
        ddl_types = options.column_types or ["TEXT"] * len(columns)
        lines.append(_create_table_ddl(options.table_name, columns, ddl_types))
        lines.append("")

    for start in range(0, len(rows), options.batch_size):
        batch = rows[start : start + options.batch_size]
        values_sql = ",\n".join(
            "(" + ", ".join(_sql_literal(value) for value in row) + ")" for row in batch
        )
        lines.append(
            f"INSERT INTO {table_name} ({column_list}) VALUES\n{values_sql};"
        )
        lines.append("")

    with Path(path).open("w", encoding=options.encoding, newline="") as handle:
        handle.write("\n".join(lines).rstrip() + "\n")


def export_data(
    columns: list[str],
    rows: list[list[Any]],
    path: str,
    format: str,
    options: CsvOptions | JsonOptions | SqlOptions,
) -> None:
    normalized = format.strip().lower()
    if normalized == "csv":
        if not isinstance(options, CsvOptions):
            raise TypeError("CSV export requires CsvOptions")
        export_csv(columns, rows, path, options)
        return
    if normalized == "json":
        if not isinstance(options, JsonOptions):
            raise TypeError("JSON export requires JsonOptions")
        export_json(columns, rows, path, options)
        return
    if normalized == "sql":
        if not isinstance(options, SqlOptions):
            raise TypeError("SQL export requires SqlOptions")
        export_sql(columns, rows, path, options)
        return

    raise ValueError(f"Unsupported export format: {format}")
