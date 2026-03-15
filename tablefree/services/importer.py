"""SQL import helpers with transaction and progress support."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from tablefree.db.driver import DatabaseDriver


@dataclass(slots=True)
class ImportOptions:
    encoding: str = "utf-8"
    wrap_in_transaction: bool = True
    disable_foreign_keys: bool = False


@dataclass(slots=True)
class ImportResult:
    total_statements: int
    executed_statements: int
    success: bool
    error_message: str | None = None
    error_statement: int | None = None
    failed_statement_text: str | None = None


def split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False

    i = 0
    while i < len(sql):
        char = sql[i]
        next_char = sql[i + 1] if i + 1 < len(sql) else ""

        if in_line_comment:
            current.append(char)
            if char == "\n":
                in_line_comment = False
        elif in_block_comment:
            current.append(char)
            if char == "*" and next_char == "/":
                current.append(next_char)
                i += 1
                in_block_comment = False
        elif in_single_quote:
            current.append(char)
            if char == "'" and next_char == "'":
                current.append(next_char)
                i += 1
            elif char == "'":
                in_single_quote = False
        elif in_double_quote:
            current.append(char)
            if char == '"':
                in_double_quote = False
        elif char == "-" and next_char == "-":
            in_line_comment = True
            current.append(char)
            current.append(next_char)
            i += 1
        elif char == "/" and next_char == "*":
            in_block_comment = True
            current.append(char)
            current.append(next_char)
            i += 1
        elif char == "'":
            in_single_quote = True
            current.append(char)
        elif char == '"':
            in_double_quote = True
            current.append(char)
        elif char == ";":
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(char)
        i += 1

    trailing = "".join(current).strip()
    if trailing:
        statements.append(trailing)

    return statements


def _detect_driver_family(driver: DatabaseDriver) -> str:
    name = type(driver).__name__.lower()
    if "mysql" in name:
        return "mysql"
    if "postgres" in name:
        return "postgres"
    return "unknown"


def import_sql(
    driver: DatabaseDriver,
    path: str,
    options: ImportOptions | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> ImportResult:
    opts = options or ImportOptions()
    sql_text = Path(path).read_text(encoding=opts.encoding)
    statements = split_sql_statements(sql_text)
    total = len(statements)
    executed = 0
    driver_family = _detect_driver_family(driver)

    def _execute(statement: str) -> None:
        driver.execute(statement)

    try:
        if opts.wrap_in_transaction:
            _execute("BEGIN")

        if opts.disable_foreign_keys:
            if driver_family == "mysql":
                _execute("SET FOREIGN_KEY_CHECKS = 0")
            elif driver_family == "postgres":
                _execute("SET CONSTRAINTS ALL DEFERRED")

        for index, statement in enumerate(statements, start=1):
            _execute(statement)
            executed = index
            if progress_callback is not None:
                progress_callback(index, total)

        if opts.disable_foreign_keys and driver_family == "mysql":
            _execute("SET FOREIGN_KEY_CHECKS = 1")

        if opts.wrap_in_transaction:
            _execute("COMMIT")

        return ImportResult(
            total_statements=total,
            executed_statements=executed,
            success=True,
        )
    except Exception as exc:
        if opts.wrap_in_transaction:
            try:
                _execute("ROLLBACK")
            except Exception:
                pass
        if opts.disable_foreign_keys and driver_family == "mysql":
            try:
                _execute("SET FOREIGN_KEY_CHECKS = 1")
            except Exception:
                pass

        failed_statement = None
        if 0 <= executed < total:
            failed_statement = statements[executed]

        return ImportResult(
            total_statements=total,
            executed_statements=executed,
            success=False,
            error_message=str(exc),
            error_statement=executed + 1 if total > executed else None,
            failed_statement_text=failed_statement,
        )
