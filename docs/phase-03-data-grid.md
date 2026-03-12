# Phase 3: Real Data Grid with Pagination & Sorting

## Goal

ResultView displays actual query results in a performant data grid with pagination, column sorting, NULL styling, type-aware rendering, and copy support.

## Current State

- `widgets/result_view.py` has a `QTableWidget` with 5 hardcoded sample rows
- Info bar shows row count and time but with static values
- Results/Messages/History tabs exist as shells
- No pagination, no sorting, no real data flow

## New Files

### `models/query_result.py` — Query Result Data Model

```python
@dataclass
class QueryResult:
    columns: list[str]          # Column names
    rows: list[list[Any]]       # Row data (list of lists)
    column_types: list[str]     # SQL type names per column (e.g. "integer", "varchar")
    row_count: int              # Total rows returned
    duration_ms: float          # Execution time in milliseconds
    error: str | None = None    # Error message if query failed
    affected_rows: int = 0      # For INSERT/UPDATE/DELETE
```

Create `tablefree/models/__init__.py` and `tablefree/models/query_result.py`.

## Files to Modify

### `widgets/result_view.py` — Complete Rewrite of Results Tab

**Remove:**
- All hardcoded sample data
- Static `QTableWidget(5, 4)` initialization

**Add `display_results(result: QueryResult)` method:**
1. Switch to Results tab
2. Clear existing table data
3. Set column count and headers from `result.columns`
4. Populate visible page of rows (see Pagination below)
5. Update info bar labels: `"{row_count} rows | {duration_ms} ms | Page {page} of {total_pages}"`
6. Apply type-aware rendering per column

**Add `display_error(error: str)` method:**
1. Switch to Messages tab
2. Append timestamped error message:
   ```
   [2026-03-12 14:30:00] ERROR: <error text>
   ```

**Add `append_message(msg: str)` method:**
- Append to Messages tab output

### Pagination

Add a pagination bar widget below the data grid:

```
[ 100 ▾ ] rows per page    |◀  ◀  Page 1 of 5  ▶  ▶|
```

**Components:**
- `QComboBox` for page size: 50, 100, 500, 1000, All
- First/Prev/Next/Last `QPushButton`s
- `QLabel` showing "Page X of Y"

**Implementation:**
- Store full `QueryResult` in `self._current_result`
- `self._page_size: int` (default 100)
- `self._current_page: int` (default 0, zero-indexed)
- `_display_page(page: int)` — slice `self._current_result.rows[start:end]` and populate table
- `_total_pages` computed from `len(rows) / page_size`
- Changing page size resets to page 0

### Column Sorting

**Click header to cycle:** unsorted → ascending → descending → unsorted

**Implementation:**
- Connect `QHeaderView.sectionClicked(int)` to `_on_header_clicked(col)`
- Track `self._sort_column: int | None` and `self._sort_order: Qt.SortOrder | None`
- On click, cycle through states
- Sort `self._current_result.rows` in-place (stable sort) by the clicked column
- Re-display current page
- Show sort indicator: append " ▲" or " ▼" to header text of sorted column
- Clear indicator from previously sorted column

**Sort comparison:**
- None/NULL values sort last regardless of direction
- Numeric types: compare as numbers
- Everything else: compare as case-insensitive strings

### NULL Display

- When cell value is `None`, display styled "NULL" text
- Use `QTableWidgetItem` with:
  - Text: `"NULL"`
  - Foreground: `#585b70` (gray)
  - Font: italic
  - Set a custom data role flag so we can distinguish real "NULL" string from actual NULL

### Type-Aware Rendering

Based on `result.column_types[col_index]`:

| Type Pattern | Rendering |
|---|---|
| `int`, `integer`, `bigint`, `smallint`, `serial` | Right-aligned |
| `float`, `double`, `decimal`, `numeric`, `real` | Right-aligned |
| `bool`, `boolean` | Center-aligned, display "true"/"false" |
| `date`, `timestamp`, `datetime`, `time` | Left-aligned, format with locale |
| `json`, `jsonb` | Left-aligned, truncated with "..." if > 100 chars |
| Everything else | Left-aligned (default) |

### Copy Support

- `Ctrl+C` on selected cells → copy as TSV (tab-separated values)
- Include column headers as first row if full rows are selected
- Handle multi-cell selection (contiguous rectangle)

**Implementation:**
- Override `keyPressEvent` or install event filter on the `QTableWidget`
- On `Ctrl+C`:
  ```python
  selected = self._table.selectedRanges()
  # Build TSV string from selected cells
  QApplication.clipboard().setText(tsv_text)
  ```

### `main_window.py` — Wire Query Execution End-to-End

**`_execute_query(sql: str)` method (complete implementation):**

```python
def _execute_query(self, sql: str) -> None:
    if not self._active_driver:
        self._result_view.display_error("No active connection")
        return

    self._editor._info_label.setText("Executing...")
    start_time = time.perf_counter()

    worker = QueryWorker(self._active_driver.execute, sql)

    def on_finished(rows: list[dict]):
        duration = (time.perf_counter() - start_time) * 1000
        if rows:
            columns = list(rows[0].keys())
            data = [list(r.values()) for r in rows]
            # Detect column types from first non-null values
            col_types = _infer_types(rows, columns)
            result = QueryResult(
                columns=columns,
                rows=data,
                column_types=col_types,
                row_count=len(data),
                duration_ms=round(duration, 1),
            )
            self._result_view.display_results(result)
        else:
            self._result_view.append_message(
                f"Query executed successfully ({round(duration, 1)} ms, no rows returned)"
            )
        self._editor._info_label.setText(f"{len(rows)} rows | {round(duration, 1)} ms")

    def on_error(err: Exception):
        duration = (time.perf_counter() - start_time) * 1000
        self._result_view.display_error(str(err))
        self._editor._info_label.setText(f"Error | {round(duration, 1)} ms")

    worker.signals.finished.connect(on_finished)
    worker.signals.error.connect(on_error)
    self._thread_pool.start(worker)
```

**Type inference helper:**
```python
def _infer_types(rows: list[dict], columns: list[str]) -> list[str]:
    """Infer column types from Python types of first non-None values."""
    types = []
    for col in columns:
        for row in rows:
            val = row[col]
            if val is not None:
                if isinstance(val, bool):
                    types.append("boolean")
                elif isinstance(val, int):
                    types.append("integer")
                elif isinstance(val, float):
                    types.append("float")
                else:
                    types.append("text")
                break
        else:
            types.append("text")
    return types
```

**Also wire sidebar `table_selected` signal:**
- `sidebar.table_selected(schema, table)` → `_execute_query(f"SELECT * FROM {schema}.{table} LIMIT 1000")`
- Use proper quoting for identifiers

## QSS Additions (both dark.qss and light.qss)

```css
/* Pagination bar */
QWidget#pagination-bar { ... }
QPushButton#page-btn { ... }
QPushButton#page-btn:disabled { ... }
QComboBox#page-size-combo { ... }
QLabel#page-info { ... }

/* NULL cell styling handled via QTableWidgetItem properties, not QSS */
```

## Testing

- Unit test: `QueryResult` dataclass creation and field access
- Unit test: `display_results()` populates table with correct column count, row count, headers
- Unit test: `display_error()` switches to Messages tab and appends text
- Unit test: pagination — 250 rows with page size 100 = 3 pages; page 0 shows rows 0-99, page 2 shows rows 200-249
- Unit test: sort ascending/descending produces correct row order
- Unit test: NULL values display as italic gray "NULL"
- Unit test: copy selected cells produces correct TSV

## Dependencies

None — uses only Qt built-in widgets and existing project code.

## Milestone

**After Phase 3, the app is a usable MVP:** connect to MySQL/PostgreSQL → browse schema → write SQL with highlighting → execute → view paginated, sortable results.
