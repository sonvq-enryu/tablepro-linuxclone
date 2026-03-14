"""Tests for ChangeTracker."""

import pytest
from tablefree.models.change_tracker import (
    CellEdit,
    ChangeTracker,
    RowDelete,
    RowInsert,
)


def test_change_tracker_import():
    from tablefree.models import ChangeTracker

    assert ChangeTracker is not None


def test_record_cell_edit():
    tracker = ChangeTracker()
    tracker.record_edit(0, 0, "old", "new")
    assert tracker.has_changes is True
    assert len(tracker.pending_changes) == 1


def test_record_multiple_edits():
    tracker = ChangeTracker()
    tracker.record_edit(0, 0, "old1", "new1")
    tracker.record_edit(0, 1, "old2", "new2")
    tracker.record_edit(1, 0, "old3", "new3")
    assert len(tracker.pending_changes) == 3


def test_auto_revert():
    tracker = ChangeTracker()
    tracker.set_original_value(0, 0, "original")
    tracker.record_edit(0, 0, "original", "original")
    assert len(tracker.pending_changes) == 0


def test_record_insert():
    tracker = ChangeTracker()
    tracker.record_insert(0, ["val1", "val2"])
    assert tracker.has_changes is True
    changes = tracker.pending_changes
    assert len(changes) == 1
    assert isinstance(changes[0], RowInsert)


def test_record_delete():
    tracker = ChangeTracker()
    tracker.record_delete(0, ["val1", "val2"])
    assert tracker.has_changes is True
    changes = tracker.pending_changes
    assert len(changes) == 1
    assert isinstance(changes[0], RowDelete)


def test_undo():
    tracker = ChangeTracker()
    tracker.record_edit(0, 0, "old", "new")
    change = tracker.undo()
    assert change is not None
    assert isinstance(change, CellEdit)
    assert change.old_value == "old"
    assert tracker.can_redo is True


def test_redo():
    tracker = ChangeTracker()
    tracker.record_edit(0, 0, "old", "new")
    tracker.undo()
    change = tracker.redo()
    assert change is not None
    assert isinstance(change, CellEdit)
    assert change.new_value == "new"


def test_commit_clears_changes():
    tracker = ChangeTracker()
    tracker.record_edit(0, 0, "old", "new")
    tracker.commit()
    assert tracker.has_changes is False
    assert len(tracker.pending_changes) == 0


def test_discard_clears_changes():
    tracker = ChangeTracker()
    tracker.record_edit(0, 0, "old", "new")
    tracker.discard()
    assert tracker.has_changes is False
    assert tracker.can_undo is False
    assert tracker.can_redo is False


def test_generate_sql_cell_edit():
    tracker = ChangeTracker()
    tracker.record_edit(0, 0, "old", "new")
    sql_statements = tracker.generate_sql("users", ["id", "name"], ["id"])
    assert len(sql_statements) == 1
    sql, params = sql_statements[0]
    assert "UPDATE" in sql
    assert "users" in sql


def test_generate_sql_row_insert():
    tracker = ChangeTracker()
    tracker.record_insert(0, [1, "John"])
    sql_statements = tracker.generate_sql("users", ["id", "name"], ["id"])
    assert len(sql_statements) == 1
    sql, params = sql_statements[0]
    assert "INSERT" in sql
    assert "users" in sql


def test_generate_sql_row_delete():
    tracker = ChangeTracker()
    tracker.record_delete(0, [1, "John"])
    sql_statements = tracker.generate_sql("users", ["id", "name"], ["id"])
    assert len(sql_statements) == 1
    sql, params = sql_statements[0]
    assert "DELETE" in sql
    assert "users" in sql


def test_max_undo_levels():
    tracker = ChangeTracker()
    for i in range(150):
        tracker.record_edit(i, 0, f"old{i}", f"new{i}")
    assert tracker.can_undo is True
    # After 100+ edits, we should still be able to undo
    change = tracker.undo()
    assert change is not None
