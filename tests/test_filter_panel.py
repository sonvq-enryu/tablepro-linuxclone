"""Tests for FilterPanel build_where_clause logic."""

import pytest
from tablefree.widgets.filter_panel import FilterCondition, FilterPanel


class MockFilterRow:
    def __init__(self, condition: FilterCondition):
        self._condition = condition

    def get_condition(self) -> FilterCondition:
        return self._condition


def _create_mock_row(condition: FilterCondition) -> MockFilterRow:
    return MockFilterRow(condition)


def test_filter_condition_creation():
    cond = FilterCondition(column="name", operator="equals", value="test")
    assert cond.column == "name"
    assert cond.operator == "equals"
    assert cond.value == "test"
    assert cond.enabled is True
    assert cond.logic == "AND"


def test_build_where_clause_equals():
    class TestPanel(FilterPanel):
        def __init__(self):
            self._filter_rows = []

    panel = TestPanel()
    panel._filter_rows = []

    cond = FilterCondition(column="name", operator="equals", value="test", enabled=True)
    panel._filter_rows.append(_create_mock_row(cond))

    clause, params = panel.build_where_clause()
    assert '"name" = %s' in clause
    assert params == ("test",)


def test_build_where_clause_contains():
    class TestPanel(FilterPanel):
        def __init__(self):
            self._filter_rows = []

    panel = TestPanel()
    panel._filter_rows = []

    cond = FilterCondition(
        column="name", operator="contains", value="test", enabled=True
    )
    panel._filter_rows.append(_create_mock_row(cond))

    clause, params = panel.build_where_clause()
    assert '"name" LIKE %s' in clause
    assert "%test%" in params


def test_build_where_clause_starts_with():
    class TestPanel(FilterPanel):
        def __init__(self):
            self._filter_rows = []

    panel = TestPanel()
    panel._filter_rows = []

    cond = FilterCondition(
        column="name", operator="starts with", value="test", enabled=True
    )
    panel._filter_rows.append(_create_mock_row(cond))

    clause, params = panel.build_where_clause()
    assert '"name" LIKE %s' in clause
    assert params == ("test%",)


def test_build_where_clause_ends_with():
    class TestPanel(FilterPanel):
        def __init__(self):
            self._filter_rows = []

    panel = TestPanel()
    panel._filter_rows = []

    cond = FilterCondition(
        column="name", operator="ends with", value="test", enabled=True
    )
    panel._filter_rows.append(_create_mock_row(cond))

    clause, params = panel.build_where_clause()
    assert '"name" LIKE %s' in clause
    assert params == ("%test",)


def test_build_where_clause_is_null():
    class TestPanel(FilterPanel):
        def __init__(self):
            self._filter_rows = []

    panel = TestPanel()
    panel._filter_rows = []

    cond = FilterCondition(column="name", operator="IS NULL", value=None, enabled=True)
    panel._filter_rows.append(_create_mock_row(cond))

    clause, params = panel.build_where_clause()
    assert '"name" IS NULL' in clause
    assert params == ()


def test_build_where_clause_is_not_null():
    class TestPanel(FilterPanel):
        def __init__(self):
            self._filter_rows = []

    panel = TestPanel()
    panel._filter_rows = []

    cond = FilterCondition(
        column="name", operator="IS NOT NULL", value=None, enabled=True
    )
    panel._filter_rows.append(_create_mock_row(cond))

    clause, params = panel.build_where_clause()
    assert '"name" IS NOT NULL' in clause
    assert params == ()


def test_build_where_clause_between():
    class TestPanel(FilterPanel):
        def __init__(self):
            self._filter_rows = []

    panel = TestPanel()
    panel._filter_rows = []

    cond = FilterCondition(
        column="age", operator="BETWEEN", value="18", value2="65", enabled=True
    )
    panel._filter_rows.append(_create_mock_row(cond))

    clause, params = panel.build_where_clause()
    assert '"age" BETWEEN %s AND %s' in clause
    assert params == ("18", "65")


def test_build_where_clause_in():
    class TestPanel(FilterPanel):
        def __init__(self):
            self._filter_rows = []

    panel = TestPanel()
    panel._filter_rows = []

    cond = FilterCondition(
        column="status", operator="IN", value="a, b, c", enabled=True
    )
    panel._filter_rows.append(_create_mock_row(cond))

    clause, params = panel.build_where_clause()
    assert '"status" IN' in clause
    assert params == ("a", "b", "c")


def test_build_where_clause_and_logic():
    class TestPanel(FilterPanel):
        def __init__(self):
            self._filter_rows = []

    panel = TestPanel()
    panel._filter_rows = []

    cond1 = FilterCondition(
        column="name", operator="equals", value="test1", enabled=True, logic="AND"
    )
    cond2 = FilterCondition(
        column="age", operator=">", value="18", enabled=True, logic="AND"
    )
    panel._filter_rows.append(_create_mock_row(cond1))
    panel._filter_rows.append(_create_mock_row(cond2))

    clause, params = panel.build_where_clause()
    assert "AND" in clause
    assert params == ("test1", "18")


def test_build_where_clause_or_logic():
    class TestPanel(FilterPanel):
        def __init__(self):
            self._filter_rows = []

    panel = TestPanel()
    panel._filter_rows = []

    cond1 = FilterCondition(
        column="name", operator="equals", value="test1", enabled=True, logic="OR"
    )
    cond2 = FilterCondition(
        column="age", operator=">", value="18", enabled=True, logic="OR"
    )
    panel._filter_rows.append(_create_mock_row(cond1))
    panel._filter_rows.append(_create_mock_row(cond2))

    clause, params = panel.build_where_clause()
    assert "OR" in clause
    assert params == ("test1", "18")


def test_build_where_clause_disabled_filter():
    class TestPanel(FilterPanel):
        def __init__(self):
            self._filter_rows = []

    panel = TestPanel()
    panel._filter_rows = []

    cond1 = FilterCondition(
        column="name", operator="equals", value="test1", enabled=True
    )
    cond2 = FilterCondition(column="age", operator=">", value="18", enabled=False)
    panel._filter_rows.append(_create_mock_row(cond1))
    panel._filter_rows.append(_create_mock_row(cond2))

    clause, params = panel.build_where_clause()
    assert "name" in clause
    assert "age" not in clause
    assert params == ("test1",)


def test_build_where_clause_empty():
    class TestPanel(FilterPanel):
        def __init__(self):
            self._filter_rows = []

    panel = TestPanel()
    panel._filter_rows = []

    clause, params = panel.build_where_clause()
    assert clause == ""
    assert params == ()


def test_build_where_clause_comparison_operators():
    class TestPanel(FilterPanel):
        def __init__(self):
            self._filter_rows = []

    for op in [">", ">=", "<", "<="]:
        panel = TestPanel()
        panel._filter_rows = []
        cond = FilterCondition(column="age", operator=op, value="18", enabled=True)
        panel._filter_rows.append(_create_mock_row(cond))

        clause, params = panel.build_where_clause()
        assert f'"age" {op} %s' in clause
        assert params == ("18",)


def test_build_where_clause_not_equals():
    class TestPanel(FilterPanel):
        def __init__(self):
            self._filter_rows = []

    panel = TestPanel()
    panel._filter_rows = []

    cond = FilterCondition(
        column="name", operator="not equals", value="test", enabled=True
    )
    panel._filter_rows.append(_create_mock_row(cond))

    clause, params = panel.build_where_clause()
    assert '"name" != %s' in clause
    assert params == ("test",)


def test_build_where_clause_raw_sql():
    class TestPanel(FilterPanel):
        def __init__(self):
            self._filter_rows = []

    panel = TestPanel()
    panel._filter_rows = []

    cond = FilterCondition(
        column="Raw SQL", operator="RAW_SQL", value="created_at > NOW()", enabled=True
    )
    panel._filter_rows.append(_create_mock_row(cond))

    clause, params = panel.build_where_clause()
    assert "created_at > NOW()" in clause
    assert params == ()


def test_build_where_clause_not_contains():
    class TestPanel(FilterPanel):
        def __init__(self):
            self._filter_rows = []

    panel = TestPanel()
    panel._filter_rows = []

    cond = FilterCondition(
        column="name", operator="not contains", value="test", enabled=True
    )
    panel._filter_rows.append(_create_mock_row(cond))

    clause, params = panel.build_where_clause()
    assert '"name" NOT LIKE %s' in clause
    assert "%test%" in params


def test_build_where_clause_not_in():
    class TestPanel(FilterPanel):
        def __init__(self):
            self._filter_rows = []

    panel = TestPanel()
    panel._filter_rows = []

    cond = FilterCondition(
        column="status", operator="NOT IN", value="a, b", enabled=True
    )
    panel._filter_rows.append(_create_mock_row(cond))

    clause, params = panel.build_where_clause()
    assert '"status" NOT IN' in clause
    assert params == ("a", "b")
