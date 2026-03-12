"""Tests for SQL syntax highlighter - simplified without widgets."""

import pytest
import sqlparse


def test_keyword_set():
    from tablefree.widgets.sql_highlighter import SQLHighlighter

    assert "SELECT" in SQLHighlighter.KEYWORDS
    assert "FROM" in SQLHighlighter.KEYWORDS
    assert "WHERE" in SQLHighlighter.KEYWORDS
    assert "JOIN" in SQLHighlighter.KEYWORDS


def test_datatype_set():
    from tablefree.widgets.sql_highlighter import SQLHighlighter

    assert "INT" in SQLHighlighter.DATA_TYPES
    assert "VARCHAR" in SQLHighlighter.DATA_TYPES
    assert "TEXT" in SQLHighlighter.DATA_TYPES


def test_function_set():
    from tablefree.widgets.sql_highlighter import SQLHighlighter

    assert "COUNT" in SQLHighlighter.FUNCTIONS
    assert "SUM" in SQLHighlighter.FUNCTIONS
    assert "NOW" in SQLHighlighter.FUNCTIONS


def test_sqlparse_format():
    sql = "select * from users where id=1"
    formatted = sqlparse.format(sql, reindent=True, keyword_case="upper")
    assert "SELECT" in formatted
    assert "FROM" in formatted


def test_sqlparse_split():
    sql = "SELECT 1; SELECT 2;"
    statements = sqlparse.split(sql)
    assert len(statements) >= 1
