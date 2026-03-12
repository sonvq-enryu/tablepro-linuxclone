# Phase 7: Import & Export

## Goal

Export query results or table data to CSV, JSON, and SQL formats. Import SQL files with transaction safety and progress tracking.

## New Files

### `services/exporter.py` — Export Engine

**`export_csv(data, path, options)`:**
```python
@dataclass
class CsvOptions:
    delimiter: str = ","          # comma, semicolon, tab, pipe
    include_header: bool = True
    quote_char: str = '"'
    null_text: str = ""           # what to write for NULL values
    line_ending: str = "\n"       # LF, CRLF
    encoding: str = "utf-8"
```
- Use Python's `csv` module with configured dialect
- Write header row if `include_header` is True
- Replace `None` values with `null_text`

**`export_json(data, path, options)`:**
```python
@dataclass
class JsonOptions:
    pretty: bool = True           # indent with 2 spaces
    include_nulls: bool = True    # include keys with null values
    encoding: str = "utf-8"
```
- Export as array of objects: `[{"col1": "val1", "col2": "val2"}, ...]`
- Use `json.dump()` with `indent=2` if pretty, `ensure_ascii=False`

**`export_sql(data, path, options)`:**
```python
@dataclass
class SqlOptions:
    table_name: str
    include_create: bool = False  # prepend CREATE TABLE
    include_drop: bool = False    # prepend DROP TABLE IF EXISTS
    batch_size: int = 500         # rows per INSERT statement
    encoding: str = "utf-8"
```
- Generate `INSERT INTO "table" (cols) VALUES (vals), (vals), ...;` batched
- If `include_create`: prepend CREATE TABLE (requires column type info)
- If `include_drop`: prepend `DROP TABLE IF EXISTS "table";`
- Properly escape string values (single-quote doubling)
- Handle NULL as literal `NULL` (not quoted)

**Common interface:**
```python
def export_data(
    columns: list[str],
    rows: list[list[Any]],
    path: str,
    format: str,  # "csv", "json", "sql"
    options: CsvOptions | JsonOptions | SqlOptions,
) -> None:
```

### `services/importer.py` — SQL File Import

```python
def import_sql(
    driver: DatabaseDriver,
    path: str,
    options: ImportOptions,
    progress_callback: Callable[[int, int], None] | None = None,
) -> ImportResult:
```

```python
@dataclass
class ImportOptions:
    encoding: str = "utf-8"
    wrap_in_transaction: bool = True
    disable_foreign_keys: bool = False

@dataclass
class ImportResult:
    total_statements: int
    executed_statements: int
    success: bool
    error_message: str | None = None
    error_statement: int | None = None  # which statement failed
```

**Implementation:**
1. Read the SQL file
2. Split into individual statements (on `;`, respecting string literals and comments)
3. If `wrap_in_transaction`: execute `BEGIN` first
4. If `disable_foreign_keys`:
   - MySQL: `SET FOREIGN_KEY_CHECKS = 0`
   - PostgreSQL: `SET CONSTRAINTS ALL DEFERRED`
5. Execute each statement sequentially
6. Call `progress_callback(current_index, total_count)` after each
7. On error: if wrapped in transaction, execute `ROLLBACK`; record error details
8. On success: if wrapped in transaction, execute `COMMIT`
9. Re-enable foreign keys if disabled

### `widgets/export_dialog.py` — Export Dialog

`ExportDialog(QDialog)`:

```
┌── Export Data ───────────────────────────────────┐
│                                                   │
│  Format:  ○ CSV   ○ JSON   ○ SQL                 │
│                                                   │
│  ┌─ CSV Options ──────────────────────────────┐  │
│  │ Delimiter:    [ Comma ▾ ]                   │  │
│  │ Include header: [✓]                         │  │
│  │ NULL text:    [        ]                    │  │
│  │ Encoding:     [ UTF-8 ▾ ]                   │  │
│  └─────────────────────────────────────────────┘  │
│                                                   │
│  File: [ /path/to/file.csv         ] [ Browse ]  │
│                                                   │
│  Rows: 1,234 rows will be exported               │
│                                                   │
│                         [ Cancel ] [ Export ]     │
└───────────────────────────────────────────────────┘
```

- Format radio buttons switch the options panel (CSV / JSON / SQL options)
- SQL options include: table name, include CREATE TABLE, include DROP, batch size
- File path via `QFileDialog.getSaveFileName` with appropriate filter
- Export button runs `export_data()` on a `QueryWorker`
- Show success/error message on completion

### `widgets/import_dialog.py` — Import Dialog

`ImportDialog(QDialog)`:

```
┌── Import SQL ────────────────────────────────────┐
│                                                   │
│  File: [ /path/to/file.sql         ] [ Browse ]  │
│  ─── or drag and drop a .sql file ───            │
│                                                   │
│  Encoding:              [ UTF-8 ▾ ]              │
│  Wrap in transaction:   [✓]                       │
│  Disable foreign keys:  [ ]                       │
│                                                   │
│  Preview: 47 statements detected                  │
│                                                   │
│  ┌──────────────────────────────────────────┐     │
│  │ ████████████████░░░░░░░░  32/47          │     │
│  └──────────────────────────────────────────┘     │
│                                                   │
│                         [ Cancel ] [ Import ]     │
└───────────────────────────────────────────────────┘
```

- File selection via `QFileDialog.getOpenFileName` with filter `"SQL Files (*.sql);;All Files (*)"`
- Drag-and-drop support: `setAcceptDrops(True)`, handle `dragEnterEvent`/`dropEvent`
- On file selected: count statements and show preview count
- Import button runs `import_sql()` on a `QueryWorker`
- `QProgressBar` updates via `progress_callback`
- On completion: show success message or error with failed statement number
- On error: show the failed statement text and database error message

## Files to Modify

### `main_window.py`

**Add menu items:**
- File → "Export Data..." (`Ctrl+Shift+E`) → opens `ExportDialog` with current result data
- File → "Import SQL..." (`Ctrl+Shift+I`) → opens `ImportDialog` with active driver

**Wire export:**
```python
def _on_export(self):
    result = self._result_view.current_result
    if result is None:
        QMessageBox.information(self, "Export", "No data to export. Run a query first.")
        return
    dialog = ExportDialog(result.columns, result.rows, self)
    dialog.exec()
```

**Wire import:**
```python
def _on_import(self):
    if not self._active_driver:
        QMessageBox.information(self, "Import", "Connect to a database first.")
        return
    dialog = ImportDialog(self._active_driver, self)
    if dialog.exec():
        # Refresh sidebar to show any new tables
        self._sidebar.set_driver(self._active_driver)
```

### `widgets/result_view.py`

- Wire "Export ↗" link in info bar to emit a signal or open `ExportDialog` directly
- Expose `current_result` property so MainWindow can access data for export

## Statement Splitting

Splitting SQL on `;` naively will break on semicolons inside string literals or comments. Use a simple state machine:

```python
def split_sql_statements(sql: str) -> list[str]:
    statements = []
    current = []
    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False

    i = 0
    while i < len(sql):
        char = sql[i]
        next_char = sql[i + 1] if i + 1 < len(sql) else ""

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            current.append(char)
        elif in_block_comment:
            current.append(char)
            if char == "*" and next_char == "/":
                current.append(next_char)
                i += 1
                in_block_comment = False
        elif in_single_quote:
            current.append(char)
            if char == "'" and next_char == "'":
                current.append(next_char)  # escaped quote
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

    # Last statement (may not end with ;)
    stmt = "".join(current).strip()
    if stmt:
        statements.append(stmt)
    return statements
```

## Testing

- Unit test: `export_csv()` produces correct CSV with header and values
- Unit test: `export_csv()` with semicolon delimiter
- Unit test: `export_csv()` NULL values replaced with configured text
- Unit test: `export_json()` produces valid JSON array of objects
- Unit test: `export_json()` pretty vs compact
- Unit test: `export_sql()` produces correct INSERT statements with proper escaping
- Unit test: `export_sql()` batches 500 rows per INSERT
- Unit test: `export_sql()` with include_create and include_drop
- Unit test: `split_sql_statements()` handles semicolons in strings
- Unit test: `split_sql_statements()` handles comments
- Unit test: `import_sql()` with mock driver executes statements in order
- Unit test: `import_sql()` with transaction rollback on error

## Dependencies

None — uses Python stdlib `csv` and `json` modules.
