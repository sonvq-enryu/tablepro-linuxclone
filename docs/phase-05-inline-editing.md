# Phase 5: Inline Editing & Change Tracking

## Goal

Edit cells, insert rows, delete rows directly in the data grid. Changes are queued in memory with full undo/redo. Preview generated SQL before committing to the database.

## New Files

### `models/change_tracker.py` — In-Memory Change Queue

**Change types:**
```python
@dataclass
class CellEdit:
    row: int
    col: int
    old_value: Any
    new_value: Any

@dataclass
class RowInsert:
    row_index: int
    row_data: list[Any]

@dataclass
class RowDelete:
    row_index: int
    row_data: list[Any]  # original row for undo

Change = CellEdit | RowInsert | RowDelete
```

**`ChangeTracker` class:**

```python
class ChangeTracker:
    def __init__(self) -> None:
        self._changes: list[Change] = []
        self._undo_stack: list[Change] = []  # max 100 levels
        self._redo_stack: list[Change] = []

    def record_edit(self, row, col, old_value, new_value) -> None:
        """Record a cell edit. Auto-removes if new_value equals original."""

    def record_insert(self, row_index, row_data) -> None:
        """Record a new row insertion."""

    def record_delete(self, row_index, row_data) -> None:
        """Record a row deletion."""

    def undo(self) -> Change | None:
        """Pop last change, push to redo stack, return it for UI revert."""

    def redo(self) -> Change | None:
        """Pop from redo stack, push to undo stack, return for UI apply."""

    @property
    def has_changes(self) -> bool: ...

    @property
    def pending_changes(self) -> list[Change]: ...

    def generate_sql(
        self,
        table: str,
        columns: list[str],
        primary_key_cols: list[str],
    ) -> list[tuple[str, tuple]]:
        """Generate parameterized SQL statements for all pending changes.

        Returns list of (sql_template, params) tuples.
        """

    def commit(self) -> None:
        """Clear all change state after successful DB commit."""

    def discard(self) -> None:
        """Discard all pending changes and clear undo/redo stacks."""
```

**SQL generation logic:**

- **CellEdit** → `UPDATE "table" SET "col" = %s WHERE "pk1" = %s AND "pk2" = %s`
  - Uses primary key for WHERE clause
  - Multiple edits to same row are merged into a single UPDATE with multiple SET clauses
- **RowInsert** → `INSERT INTO "table" ("col1", "col2", ...) VALUES (%s, %s, ...)`
  - Edits to an inserted row fold into the INSERT values (no separate UPDATE)
- **RowDelete** → `DELETE FROM "table" WHERE "pk1" = %s AND "pk2" = %s`
  - If no primary key exists, match on ALL column values

**Auto-revert detection:**
- When a `CellEdit` is recorded, check if `new_value == original_value` (the value before any edits)
- If so, remove the edit from the changes list entirely
- Track original values separately from current values

## Files to Modify

### `widgets/result_view.py` — Enable Inline Editing

**Switch edit triggers:**
- Change `QTableWidget.EditTrigger.NoEditTriggers` → `QTableWidget.EditTrigger.DoubleClicked`
- Connect `QTableWidget.cellChanged` signal to record edits in `ChangeTracker`

**Detect primary key:**
- After displaying results, if the query targets a single table, call `driver.get_indexes(table, schema)` to find primary key columns
- Store `self._primary_key_cols: list[str]`
- Store `self._current_table: str` and `self._current_schema: str`

**Add toolbar buttons above data grid:**

```
[ + Insert ] [ ✕ Delete ] |  [ Preview SQL 👁 ] [ Discard ] [ Commit ✓ ]    Pending: 3 changes
```

- **Insert (+ button):** Append empty row at bottom, record `RowInsert`
  - Pre-fill columns that have defaults with "DEFAULT" placeholder
  - New row gets green background
- **Delete:** Mark selected rows for deletion, record `RowDelete`
  - Apply strikethrough text + red-tinted background
  - Rows remain visible until commit/discard
- **Preview SQL:** Open a dialog showing syntax-highlighted generated SQL
  - Show all statements that would be executed
  - Warning banner if DELETE statements are present
- **Discard:** Revert all changes — reload original data, clear ChangeTracker
- **Commit (`Ctrl+S`):** Execute all generated SQL via QueryWorker
  - On success: clear ChangeTracker, refresh results (re-execute original query)
  - On error: show error, keep changes intact for retry

**Visual indicators:**

| State | Cell Background | Text Style |
|---|---|---|
| Edited cell | `rgba(249, 226, 175, 0.15)` (yellow tint) | Normal |
| Inserted row | `rgba(166, 227, 161, 0.15)` (green tint) | Normal |
| Deleted row | `rgba(243, 139, 168, 0.10)` (red tint) | Strikethrough |
| NULL value | (unchanged from Phase 3) | Gray italic |

**Undo/Redo:**
- `Ctrl+Z` → call `ChangeTracker.undo()`, revert the cell/row in the grid
- `Ctrl+Shift+Z` → call `ChangeTracker.redo()`, re-apply the change
- Up to 100 levels

**Guard against editing without primary key:**
- If no primary key is detected, show a warning when user tries to commit: "No primary key detected. DELETE and UPDATE statements will match on all column values. Proceed?"
- Still allow editing (user may know what they're doing)

### `main_window.py`

- Wire `Ctrl+S` shortcut to commit changes in active result view
- Pass driver reference to result_view for executing commits

### `widgets/sql_preview_dialog.py` (new file)

Simple `QDialog`:
- Read-only `CodeEditor` showing the generated SQL
- "Copy" button to copy SQL to clipboard
- "Close" and "Execute" buttons
- Warning banner if destructive operations (DELETE, DROP) are present

## Change Tracking State Per Tab

Each editor tab should have its own `ChangeTracker` instance. When switching tabs, the result view's change tracker context switches too.

Store in a dict: `self._change_trackers: dict[str, ChangeTracker]` keyed by tab ID.

## Testing

- Unit test: `ChangeTracker` — record 3 cell edits, verify `pending_changes` has 3 entries
- Unit test: `ChangeTracker` — record edit then revert to original value, verify change is auto-removed
- Unit test: `ChangeTracker` — undo pops last change, redo re-applies
- Unit test: `generate_sql()` — cell edit produces correct UPDATE with parameterized values
- Unit test: `generate_sql()` — row insert produces correct INSERT
- Unit test: `generate_sql()` — row delete produces correct DELETE with PK WHERE clause
- Unit test: `generate_sql()` — multiple edits to same row merge into single UPDATE
- Unit test: `generate_sql()` — edit to an inserted row folds into INSERT values

## Dependencies

None — uses existing driver, CodeEditor (Phase 2), QueryWorker.
