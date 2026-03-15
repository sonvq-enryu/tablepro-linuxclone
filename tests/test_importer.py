"""Tests for tablefree.services.importer."""

from pathlib import Path

from tablefree.services import ImportOptions, import_sql, split_sql_statements


class MockMySQLDriver:
    def __init__(self, fail_on: str | None = None) -> None:
        self.commands: list[str] = []
        self.fail_on = fail_on

    def execute(self, query: str, params: tuple | None = None):  # noqa: ANN001
        self.commands.append(query)
        if self.fail_on and self.fail_on in query:
            raise RuntimeError("boom")
        return []


def test_split_sql_statements_handles_semicolon_in_strings() -> None:
    sql = """
    INSERT INTO users(name) VALUES ('A;B');
    SELECT 1;
    """
    statements = split_sql_statements(sql)
    assert statements == [
        "INSERT INTO users(name) VALUES ('A;B')",
        "SELECT 1",
    ]


def test_split_sql_statements_handles_comments() -> None:
    sql = """
    -- keep this ; in comment
    SELECT 1;
    /* block ; comment */
    SELECT 2;
    """
    statements = split_sql_statements(sql)
    assert len(statements) == 2
    assert statements[0].endswith("SELECT 1")
    assert statements[1].endswith("SELECT 2")


def test_import_sql_executes_in_order_and_reports_progress(tmp_path: Path) -> None:
    sql_path = tmp_path / "import.sql"
    sql_path.write_text("SELECT 1;SELECT 2;", encoding="utf-8")

    driver = MockMySQLDriver()
    progress: list[tuple[int, int]] = []
    result = import_sql(
        driver,
        str(sql_path),
        ImportOptions(wrap_in_transaction=True),
        progress_callback=lambda current, total: progress.append((current, total)),
    )

    assert result.success is True
    assert driver.commands == ["BEGIN", "SELECT 1", "SELECT 2", "COMMIT"]
    assert progress == [(1, 2), (2, 2)]


def test_import_sql_rolls_back_on_error(tmp_path: Path) -> None:
    sql_path = tmp_path / "import.sql"
    sql_path.write_text("SELECT 1;SELECT fail_me;", encoding="utf-8")

    driver = MockMySQLDriver(fail_on="fail_me")
    result = import_sql(
        driver,
        str(sql_path),
        ImportOptions(wrap_in_transaction=True),
    )

    assert result.success is False
    assert result.error_statement == 2
    assert result.failed_statement_text == "SELECT fail_me"
    assert driver.commands[-1] == "ROLLBACK"
