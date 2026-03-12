# Phase 2: Functional SQL Editor with Syntax Highlighting

## Goal

Multi-tab SQL editor that executes queries against the active connection, with syntax highlighting, line numbers, and SQL formatting.

## Current State

- `widgets/editor.py` has a tabbed layout with `QPlainTextEdit` per tab — no syntax highlighting, no line numbers, no execution logic
- Toolbar buttons (Run, Run Selection, Format) exist but are not connected
- `_info_label` exists but shows nothing
- Tab management works (add/close/reorder) but tabs have no persistent identity

## New Files

### `widgets/sql_highlighter.py` — SQL Syntax Highlighter

Subclass `QSyntaxHighlighter`. Define highlight rules as `(compiled_regex, QTextCharFormat)` pairs.

**Token categories and colors (Catppuccin Mocha palette):**

| Token | Color | Example |
|---|---|---|
| Keywords | `#cba6f7` (mauve) | `SELECT`, `FROM`, `WHERE`, `JOIN`, `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `ALTER`, `DROP`, `TABLE`, `INDEX`, `INTO`, `VALUES`, `SET`, `AND`, `OR`, `NOT`, `IN`, `IS`, `NULL`, `AS`, `ON`, `ORDER`, `BY`, `GROUP`, `HAVING`, `LIMIT`, `OFFSET`, `UNION`, `EXISTS`, `BETWEEN`, `LIKE`, `CASE`, `WHEN`, `THEN`, `ELSE`, `END`, `BEGIN`, `COMMIT`, `ROLLBACK`, `GRANT`, `REVOKE`, `PRIMARY`, `FOREIGN`, `KEY`, `REFERENCES`, `CONSTRAINT`, `DEFAULT`, `CASCADE`, `RESTRICT` |
| Data types | `#f9e2af` (yellow) | `INT`, `INTEGER`, `VARCHAR`, `TEXT`, `BOOLEAN`, `DATE`, `TIMESTAMP`, `SERIAL`, `BIGINT`, `FLOAT`, `DOUBLE`, `DECIMAL`, `NUMERIC`, `CHAR`, `BLOB`, `JSON`, `JSONB`, `UUID` |
| Strings | `#a6e3a1` (green) | `'single quoted'`, `"double quoted"` |
| Numbers | `#fab387` (peach) | `42`, `3.14`, `-1` |
| Comments | `#6c7086` (overlay) | `-- line comment`, `/* block */` |
| Functions | `#89b4fa` (blue) | `COUNT`, `SUM`, `AVG`, `MAX`, `MIN`, `COALESCE`, `CONCAT`, `NOW`, `CURRENT_TIMESTAMP`, `IFNULL`, `NULLIF`, `CAST`, `CONVERT`, `UPPER`, `LOWER`, `TRIM`, `LENGTH`, `SUBSTRING`, `REPLACE` |
| Operators | `#89dceb` (sky) | `=`, `!=`, `<>`, `<`, `>`, `<=`, `>=`, `+`, `-`, `*`, `/` |

**Implementation details:**
- Keywords and functions matched as whole words (`\b` word boundaries), case-insensitive
- String matching handles escaped quotes within strings
- Block comments (`/* */`) require multi-line state tracking via `setCurrentBlockState()`
- Apply highlighter to each `CodeEditor` widget when created

### `widgets/code_editor.py` — Editor with Line Numbers

Custom widget combining `QPlainTextEdit` with a line number gutter.

**`LineNumberArea(QWidget)`:**
- Paints line numbers in the gutter area
- Background: `#181825`, text color: `#585b70`, current line number: `#cdd6f4`
- Width auto-calculated from digit count of total lines

**`CodeEditor(QPlainTextEdit)`:**
- Manages `LineNumberArea` as a child widget
- Overrides `resizeEvent` to update gutter geometry
- Connects `blockCountChanged` → update gutter width
- Connects `updateRequest` → scroll gutter with editor
- Highlights current line with subtle background (`#1e1e2e` → `#242438` or similar)
- On creation, attaches `SQLHighlighter` to `self.document()`
- Sets monospace font: JetBrains Mono / Fira Code / Consolas fallback
- Tab stop: 4 spaces width
- No line wrap by default

## Files to Modify

### `widgets/editor.py`

**Replace `QPlainTextEdit` with `CodeEditor`:**
- `_add_tab()` creates `CodeEditor` instead of `QPlainTextEdit`
- Each tab gets its own `SQLHighlighter` instance (attached automatically by `CodeEditor`)

**Wire toolbar buttons:**

**Run button (`self._run_btn`):**
- Get full text from current tab's `CodeEditor`
- Emit `query_submitted(sql: str)` signal
- Disable run button while query is executing (re-enable on result/error)

**Run Selection button (`self._run_sel_btn`):**
- If editor has selected text → use selection
- Else → find the single statement at cursor position:
  - Split text on `;`
  - Find which statement range the cursor falls in
  - Use that statement
- Emit `query_submitted(sql: str)`

**Format button (`self._fmt_btn`):**
- Get current tab text
- Format with `sqlparse.format(sql, reindent=True, keyword_case='upper')`
- Replace editor text with formatted result
- Preserve cursor position as best as possible

**Add `set_driver(driver)` method:**
- Store driver reference (needed so MainWindow knows editor is ready)

**Add keyboard shortcuts:**
- `Ctrl+Enter` → Run (same as Run button)
- `Ctrl+Shift+Enter` → Run Selection

**Expose helper properties:**
- `current_editor() -> CodeEditor` — returns the active tab's editor widget
- `current_sql() -> str` — returns text of active tab

**Signals:**
```python
query_submitted = Signal(str)  # SQL text to execute
```

### `main_window.py`

**Wire editor to execution pipeline:**
- Connect `editor.query_submitted` to a `_execute_query(sql)` method
- `_execute_query(sql)`:
  - Start timer
  - Create `QueryWorker(self._active_driver.execute, sql)`
  - On finished: stop timer, pass results to ResultView (wired fully in Phase 3, for now just log to Messages tab)
  - On error: stop timer, show error in Messages tab
  - Update `_info_label` with duration

**Pass driver to editor:**
- After `ConnectionDialog.accept()`, call `self._editor.set_driver(self._active_driver)`

## New Dependency

Add to `pyproject.toml`:
```toml
"sqlparse>=0.5.0",
```

## Statement-at-Cursor Algorithm

```python
def _find_statement_at_cursor(text: str, cursor_position: int) -> str:
    """Find the SQL statement that contains the cursor position."""
    statements = sqlparse.split(text)
    pos = 0
    for stmt in statements:
        # Find this statement's position in the original text
        idx = text.find(stmt.strip(), pos)
        start = idx
        end = idx + len(stmt.strip())
        if start <= cursor_position <= end:
            return stmt.strip()
        pos = end
    # Fallback: return full text
    return text.strip()
```

## Testing

- Unit test: `SQLHighlighter` applies correct formats to known SQL strings (verify via `QTextDocument` block formats)
- Unit test: `CodeEditor` has line number area with correct width
- Unit test: `EditorPanel.current_sql()` returns text of active tab
- Unit test: Format button transforms `select * from users where id=1` into properly indented uppercase SQL
- Unit test: statement-at-cursor correctly identifies single statements in multi-statement text

## Dependencies

- `sqlparse` (new, add to pyproject.toml)
- Uses existing `QueryWorker` for execution
