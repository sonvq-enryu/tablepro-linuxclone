"""Tests for tablefree.services.exporter."""

from pathlib import Path

from tablefree.services import (
    CsvOptions,
    JsonOptions,
    SqlOptions,
    export_csv,
    export_json,
    export_sql,
)


def test_export_csv_with_header(tmp_path: Path) -> None:
    out = tmp_path / "out.csv"
    export_csv(["id", "name"], [[1, "Alice"], [2, "Bob"]], str(out), CsvOptions())
    text = out.read_text(encoding="utf-8")
    assert text == "id,name\n1,Alice\n2,Bob\n"


def test_export_csv_semicolon_delimiter(tmp_path: Path) -> None:
    out = tmp_path / "out.csv"
    export_csv(
        ["id", "name"],
        [[1, "Alice"]],
        str(out),
        CsvOptions(delimiter=";"),
    )
    assert out.read_text(encoding="utf-8") == "id;name\n1;Alice\n"


def test_export_csv_null_replacement(tmp_path: Path) -> None:
    out = tmp_path / "out.csv"
    export_csv(
        ["id", "name"],
        [[1, None]],
        str(out),
        CsvOptions(null_text="(null)"),
    )
    assert out.read_text(encoding="utf-8") == "id,name\n1,(null)\n"


def test_export_json_array_of_objects(tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    export_json(
        ["id", "name"],
        [[1, "Alice"]],
        str(out),
        JsonOptions(pretty=True),
    )
    text = out.read_text(encoding="utf-8")
    assert '"id": 1' in text
    assert '"name": "Alice"' in text


def test_export_json_compact_mode(tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    export_json(
        ["id", "name"],
        [[1, "Alice"]],
        str(out),
        JsonOptions(pretty=False),
    )
    assert out.read_text(encoding="utf-8") == '[{"id": 1, "name": "Alice"}]'


def test_export_sql_insert_and_escaping(tmp_path: Path) -> None:
    out = tmp_path / "out.sql"
    export_sql(
        ["id", "name", "note"],
        [[1, "O'Neil", None]],
        str(out),
        SqlOptions(table_name="users", batch_size=500),
    )
    text = out.read_text(encoding="utf-8")
    assert 'INSERT INTO "users" ("id", "name", "note") VALUES' in text
    assert "(1, 'O''Neil', NULL)" in text


def test_export_sql_batches_rows(tmp_path: Path) -> None:
    out = tmp_path / "out.sql"
    rows = [[i] for i in range(0, 1200)]
    export_sql(["id"], rows, str(out), SqlOptions(table_name="events", batch_size=500))
    text = out.read_text(encoding="utf-8")
    assert text.count('INSERT INTO "events"') == 3


def test_export_sql_with_drop_and_create(tmp_path: Path) -> None:
    out = tmp_path / "out.sql"
    export_sql(
        ["id", "name"],
        [[1, "Alice"]],
        str(out),
        SqlOptions(
            table_name="users",
            include_drop=True,
            include_create=True,
            column_types=["integer", "text"],
        ),
    )
    text = out.read_text(encoding="utf-8")
    assert 'DROP TABLE IF EXISTS "users";' in text
    assert 'CREATE TABLE "users"' in text
