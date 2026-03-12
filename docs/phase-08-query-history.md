# Phase 8: Query History

## Goal

Persist every executed query to a local SQLite database with full-text search. Provide a searchable, filterable history panel for re-executing past queries.

## New Files

### `services/query_history.py` — History Storage

**Database location:** `~/.local/share/TableFree/query_history.db`

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS query_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    query_text      TEXT NOT NULL,
    connection_name TEXT NOT NULL,
    executed_at     TEXT NOT NULL,  -- ISO 8601 timestamp
    duration_ms     REAL NOT NULL,
    status          TEXT NOT NULL,  -- 'success' or 'error'
    error_message   TEXT,
    rows_affected   INTEGER DEFAULT 0
);

-- FTS5 virtual table for full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS query_history_fts
USING fts5(query_text, content=query_history, content_rowid=id);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS query_history_ai AFTER INSERT ON query_history BEGIN
    INSERT INTO query_history_fts(rowid, query_text) VALUES (new.id, new.query_text);
END;

CREATE TRIGGER IF NOT EXISTS query_history_ad AFTER DELETE ON query_history BEGIN
    INSERT INTO query_history_fts(query_history_fts, rowid, query_text) VALUES ('delete', old.id, old.query_text);
END;
```

**`QueryHistoryStore` class:**

```python
class QueryHistoryStore:
    def __init__(self, db_path: str | None = None) -> None:
        """Initialize with path. Creates DB and tables if not exist."""

    def record(
        self,
        query_text: str,
        connection_name: str,
        duration_ms: float,
        status: str,  # "success" or "error"
        error_message: str | None = None,
        rows_affected: int = 0,
    ) -> int:
        """Insert a history entry. Returns the new row ID."""

    def search(
        self,
        term: str | None = None,
        connection: str | None = None,
        status: str | None = None,
        since: str | None = None,  # ISO 8601 date
        limit: int = 100,
        offset: int = 0,
    ) -> list[HistoryEntry]:
        """Search history with optional filters.

        If term is provided, uses FTS5 for full-text search.
        Otherwise returns chronological entries with optional filters.
        """

    def get_entry(self, entry_id: int) -> HistoryEntry | None:
        """Get a single history entry by ID."""

    def delete(self, entry_id: int) -> None:
        """Delete a single history entry."""

    def clear(self) -> None:
        """Delete all history entries."""

    def cleanup(self, max_entries: int = 10000, max_age_days: int = 90) -> int:
        """Remove old entries exceeding limits. Returns count deleted."""

    def get_connections(self) -> list[str]:
        """Return distinct connection names for filter dropdown."""
```

**`HistoryEntry` dataclass:**
```python
@dataclass
class HistoryEntry:
    id: int
    query_text: str
    connection_name: str
    executed_at: str
    duration_ms: float
    status: str
    error_message: str | None
    rows_affected: int
```

**Cleanup strategy:**
- Run `cleanup()` on app startup
- Default: keep max 10,000 entries, delete entries older than 90 days
- Configurable via QSettings (future: settings dialog)

### `widgets/history_panel.py` — History UI

Replace the placeholder History tab in `result_view.py`.

**`HistoryPanel(QWidget)` layout:**

```
┌───────────────────────────────────────────────────────┐
│ 🔍 [ Search queries...                            ]  │
│ Connection: [ All ▾ ]  Status: [ All ▾ ]  [ Clear ]  │
├───────────────────────────────────────────────────────┤
│ Query                  │ Time         │ Duration │ ●  │
│────────────────────────│──────────────│──────────│────│
│ SELECT * FROM users... │ 14:30:00     │ 12 ms    │ ✓  │
│ INSERT INTO orders...  │ 14:28:15     │ 45 ms    │ ✓  │
│ SELECT * FROM foo...   │ 14:25:00     │ 3 ms     │ ✗  │
│                        │              │          │    │
└───────────────────────────────────────────────────────┘
```

**Components:**
- **Search bar (`QLineEdit`):** Full-text search, debounced 300ms after typing
- **Connection filter (`QComboBox`):** "All" + distinct connection names from history
- **Status filter (`QComboBox`):** "All", "Success", "Error"
- **Clear button:** Clear all history (with confirmation dialog)
- **Results table (`QTableWidget`):**
  - Columns: Query (truncated to ~80 chars), Time, Duration, Status (icon)
  - Sort by clicking headers (default: most recent first)
  - Alternating row colors

**Interactions:**
- **Double-click row:** Load query text into the current editor tab
  - Emit `query_load_requested(sql: str)` signal
- **Right-click context menu:**
  - "Load into Editor" — same as double-click
  - "Run Again" — emit `query_submitted(sql: str)` to execute immediately
  - "Copy Query" — copy full query text to clipboard
  - "Delete Entry" — remove from history

**Pagination:**
- Load 100 entries at a time
- "Load more" button at bottom or infinite scroll (on scroll to bottom, fetch next page)

**Signals:**
```python
query_load_requested = Signal(str)   # load SQL into editor
query_run_requested = Signal(str)    # execute SQL directly
```

## Files to Modify

### `widgets/result_view.py`

- Replace the placeholder History tab content with `HistoryPanel` widget
- Connect `HistoryPanel.query_load_requested` → forward to MainWindow
- Connect `HistoryPanel.query_run_requested` → forward to MainWindow

### `main_window.py`

**Initialize history store:**
```python
def __init__(self):
    ...
    self._history = QueryHistoryStore()
    self._history.cleanup()  # run cleanup on startup
```

**Record every query execution:**
- In `_execute_query()`, after query completes (success or error):
```python
self._history.record(
    query_text=sql,
    connection_name=self._active_driver.config.name,
    duration_ms=duration,
    status="success" if not error else "error",
    error_message=str(error) if error else None,
    rows_affected=len(rows),
)
# Refresh history panel
self._result_view.history_panel.refresh()
```

**Wire history signals:**
- `history_panel.query_load_requested` → set text in current editor tab
- `history_panel.query_run_requested` → call `_execute_query(sql)`

**Add shortcut:**
- `Ctrl+Y` → switch to History tab in result view

## Testing

- Unit test: `QueryHistoryStore` — record entry, search returns it
- Unit test: FTS search — record "SELECT * FROM users", search "users" finds it
- Unit test: filter by connection name
- Unit test: filter by status
- Unit test: `cleanup()` removes entries beyond max count
- Unit test: `cleanup()` removes entries older than max age
- Unit test: `delete()` removes single entry
- Unit test: `clear()` removes all entries
- Unit test: `get_connections()` returns distinct connection names
- Unit test: `HistoryPanel` emits correct signals on double-click and context menu

## Dependencies

None — uses Python stdlib `sqlite3` module.
