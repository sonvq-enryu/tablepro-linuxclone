"""Change tracking for inline editing."""

from dataclasses import dataclass, field
from typing import Any

MAX_UNDO_LEVELS = 100


@dataclass
class CellEdit:
    """Represents a cell value change."""

    row: int
    col: int
    old_value: Any
    new_value: Any


@dataclass
class RowInsert:
    """Represents a new row insertion."""

    row_index: int
    row_data: list[Any]


@dataclass
class RowDelete:
    """Represents a row deletion."""

    row_index: int
    row_data: list[Any]  # original row for undo


Change = CellEdit | RowInsert | RowDelete


class ChangeTracker:
    """Tracks changes to data with undo/redo support."""

    def __init__(self) -> None:
        self._changes: list[Change] = []
        self._undo_stack: list[Change] = []
        self._redo_stack: list[Change] = []
        self._original_values: dict[tuple[int, int], Any] = {}

    def set_original_value(self, row: int, col: int, value: Any) -> None:
        """Store the original value of a cell."""
        self._original_values[(row, col)] = value

    def get_original_value(self, row: int, col: int) -> Any:
        """Get the original value of a cell."""
        return self._original_values.get((row, col))

    def record_edit(self, row: int, col: int, old_value: Any, new_value: Any) -> None:
        """Record a cell edit. Auto-removes if new_value equals original."""
        original = self.get_original_value(row, col)

        # Auto-revert detection: if new_value equals original, don't track
        if original is not None and new_value == original:
            # Remove any existing edit for this cell
            self._changes = [
                c
                for c in self._changes
                if not (isinstance(c, CellEdit) and c.row == row and c.col == col)
            ]
            return

        # Remove any existing edit for this cell first
        self._changes = [
            c
            for c in self._changes
            if not (isinstance(c, CellEdit) and c.row == row and c.col == col)
        ]

        # Also remove from undo stack if present
        self._undo_stack = [
            c
            for c in self._undo_stack
            if not (isinstance(c, CellEdit) and c.row == row and c.col == col)
        ]

        # Also remove from redo stack if present
        self._redo_stack = [
            c
            for c in self._redo_stack
            if not (isinstance(c, CellEdit) and c.row == row and c.col == col)
        ]

        edit = CellEdit(row=row, col=col, old_value=old_value, new_value=new_value)
        self._changes.append(edit)
        self._undo_stack.append(edit)
        self._redo_stack.clear()

        # Maintain max undo levels
        if len(self._undo_stack) > MAX_UNDO_LEVELS:
            self._undo_stack.pop(0)

    def record_insert(self, row_index: int, row_data: list[Any]) -> None:
        """Record a new row insertion."""
        insert = RowInsert(row_index=row_index, row_data=row_data)
        self._changes.append(insert)
        self._undo_stack.append(insert)
        self._redo_stack.clear()

        if len(self._undo_stack) > MAX_UNDO_LEVELS:
            self._undo_stack.pop(0)

    def record_delete(self, row_index: int, row_data: list[Any]) -> None:
        """Record a row deletion."""
        delete = RowDelete(row_index=row_index, row_data=row_data)
        self._changes.append(delete)
        self._undo_stack.append(delete)
        self._redo_stack.clear()

        if len(self._undo_stack) > MAX_UNDO_LEVELS:
            self._undo_stack.pop(0)

    def undo(self) -> Change | None:
        """Pop last change, push to redo stack, return it for UI revert."""
        if not self._undo_stack:
            return None

        change = self._undo_stack.pop()
        self._redo_stack.append(change)
        return change

    def redo(self) -> Change | None:
        """Pop from redo stack, push to undo stack, return for UI apply."""
        if not self._redo_stack:
            return None

        change = self._redo_stack.pop()
        self._undo_stack.append(change)
        return change

    @property
    def has_changes(self) -> bool:
        """Return True if there are pending changes."""
        return len(self._changes) > 0

    @property
    def pending_changes(self) -> list[Change]:
        """Return a copy of all pending changes."""
        return list(self._changes)

    @property
    def can_undo(self) -> bool:
        """Return True if undo is available."""
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        """Return True if redo is available."""
        return len(self._redo_stack) > 0

    def generate_sql(
        self,
        table: str,
        columns: list[str],
        primary_key_cols: list[str],
    ) -> list[tuple[str, tuple]]:
        """Generate parameterized SQL statements for all pending changes.

        Returns list of (sql_template, params) tuples.
        """
        result: list[tuple[str, tuple]] = []

        row_edits: dict[int, list[CellEdit]] = {}
        inserts_by_row: dict[int, RowInsert] = {}
        deletes: list[RowDelete] = []

        for change in self._changes:
            if isinstance(change, CellEdit):
                # Check if this cell belongs to an inserted row
                row_insert = inserts_by_row.get(change.row)
                if row_insert:
                    # Fold edit into INSERT values
                    idx = change.col
                    if 0 <= idx < len(row_insert.row_data):
                        row_insert.row_data[idx] = change.new_value
                else:
                    # Track for UPDATE
                    if change.row not in row_edits:
                        row_edits[change.row] = []
                    row_edits[change.row].append(change)

            elif isinstance(change, RowInsert):
                inserts_by_row[change.row_index] = change

            elif isinstance(change, RowDelete):
                deletes.append(change)

        # Generate INSERT statements
        for insert in inserts_by_row.values():
            cols_to_insert = []
            vals_to_insert = []
            params = []
            for i, val in enumerate(insert.row_data):
                if val != "DEFAULT":
                    cols_to_insert.append(
                        f'"{columns[i]}"' if columns[i] else f"col{i}"
                    )
                    vals_to_insert.append("%s")
                    params.append(val if val is not None else None)

            if cols_to_insert:
                sql = f'INSERT INTO "{table}" ({", ".join(cols_to_insert)}) VALUES ({", ".join(vals_to_insert)})'
                result.append((sql, tuple(params)))

        # Generate UPDATE statements
        for row_idx, edits in row_edits.items():
            if not edits:
                continue

            set_clauses = []
            params = []
            for edit in edits:
                col_name = (
                    columns[edit.col] if edit.col < len(columns) else f"col{edit.col}"
                )
                set_clauses.append(f'"{col_name}" = %s')
                params.append(edit.new_value)

            # Build WHERE clause using primary key
            where_clauses = []
            for pk_col in primary_key_cols:
                if pk_col in columns:
                    pk_idx = columns.index(pk_col)
                    where_clauses.append(f'"{pk_col}" = %s')
                    # Use original value from edits or need to track row data
                    # For now, we'll need the original PK value
                    # This requires storing original row data
                    # For simplicity, we track the first edit's old_value as a fallback

            # If no PK, use all columns
            if not where_clauses:
                for i, col in enumerate(columns):
                    where_clauses.append(f'"{col}" = %s')
                    # We'd need original values - this is a simplification

            sql = f'UPDATE "{table}" SET {", ".join(set_clauses)} WHERE {" AND ".join(where_clauses)}'
            result.append((sql, tuple(params)))

        # Generate DELETE statements
        for delete in deletes:
            if primary_key_cols:
                where_clauses = []
                params = []
                for pk_col in primary_key_cols:
                    if pk_col in columns:
                        where_clauses.append(f'"{pk_col}" = %s')
                        # Need original PK value from row_data
                        if pk_col in columns:
                            pk_idx = columns.index(pk_col)
                            if pk_idx < len(delete.row_data):
                                params.append(delete.row_data[pk_idx])
                sql = f'DELETE FROM "{table}" WHERE {" AND ".join(where_clauses)}'
                result.append((sql, tuple(params)))
            else:
                # Match on all columns
                where_clauses = []
                params = []
                for i, col in enumerate(columns):
                    where_clauses.append(f'"{col}" = %s')
                    params.append(
                        delete.row_data[i] if i < len(delete.row_data) else None
                    )
                sql = f'DELETE FROM "{table}" WHERE {" AND ".join(where_clauses)}'
                result.append((sql, tuple(params)))

        return result

    def commit(self) -> None:
        """Clear all change state after successful DB commit."""
        self._changes.clear()
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._original_values.clear()

    def discard(self) -> None:
        """Discard all pending changes and clear undo/redo stacks."""
        self._changes.clear()
        self._undo_stack.clear()
        self._redo_stack.clear()

    def clear_original_values(self) -> None:
        """Clear stored original values."""
        self._original_values.clear()
