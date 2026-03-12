"""Tests for editor panel - simplified without widgets."""

import pytest


def test_editor_import():
    from tablefree.widgets.editor import EditorPanel

    assert EditorPanel is not None


def test_editor_signal_exists():
    from tablefree.widgets.editor import EditorPanel

    assert hasattr(EditorPanel, "query_submitted")


def test_code_editor_import():
    from tablefree.widgets.code_editor import CodeEditor

    assert CodeEditor is not None


def test_line_number_area_import():
    from tablefree.widgets.code_editor import LineNumberArea

    assert LineNumberArea is not None


def test_sqlparse_import():
    import sqlparse

    assert sqlparse is not None


def test_sqlparse_format():
    import sqlparse

    sql = "select * from users where id=1"
    formatted = sqlparse.format(sql, reindent=True, keyword_case="upper")
    assert "SELECT" in formatted


def test_sqlparse_split():
    import sqlparse

    sql = "SELECT 1; SELECT 2;"
    statements = sqlparse.split(sql)
    assert len(statements) >= 1
