# Phase 1: Live Sidebar Schema Browser

## Goal

After connecting to a database, the sidebar populates with real schema and table data from the active driver. Clicking a table loads its data into the result view.

## Current State

- `widgets/sidebar.py` has a hardcoded placeholder tree with static categories (Tables, Views, Functions, Procedures) and fake items
- `main_window.py` opens `ConnectionDialog`, stores the active driver, and updates the status bar — but never passes the driver to the sidebar
- The search bar exists but is not wired to anything
- The footer says "Connect to a database to browse schema" but never changes

## Files to Modify

### `widgets/sidebar.py`

**Remove:**
- `_populate_placeholder_tree()` method and all static category/item data

**Add `set_driver(driver: DatabaseDriver)` method:**
- Store driver reference
- Clear the tree
- Call `driver.get_schemas()` on a `QueryWorker` (must not block the UI thread)
- On result, for each schema create a top-level `QTreeWidgetItem` (icon: folder)
- For each schema, call `driver.get_tables(schema)` on a `QueryWorker`
- On result, add table nodes as children (icon: grid/table)
- Lazy-load columns: when user expands a table node, call `driver.get_columns(table, schema)` and add column child nodes showing `name (type)`
- Update header badge: "● Connected" with green styling
- Hide footer label

**Add `clear()` method:**
- Reset tree to empty
- Show footer label again
- Reset badge to "● Disconnected"

**Wire search filtering:**
- Connect `self._search.textChanged` to a filter method
- On text change, iterate all tree items and hide/show based on case-insensitive match against item text
- If a child matches, ensure its parent is visible and expanded

**Add custom signals:**
```python
table_selected = Signal(str, str)        # (schema, table)
table_double_clicked = Signal(str, str)  # (schema, table)
```
- `itemClicked` → emit `table_selected` if the clicked item is a table node
- `itemDoubleClicked` → emit `table_double_clicked`

**Add right-click context menu on table nodes:**
- "Open Table" → emit `table_double_clicked`
- "View Structure" → emit a `structure_requested(schema, table)` signal
- "Refresh" → re-fetch tables for that schema

**Add refresh button in header:**
- Small refresh icon button next to the badge
- On click: call `set_driver()` again with the stored driver to rebuild the tree

### `main_window.py`

**After `ConnectionDialog.accept()`:**
- Call `self._sidebar.set_driver(self._active_driver)`
- Connect `sidebar.table_selected` signal (wire in Phase 3 when result view is functional)
- Connect `sidebar.table_double_clicked` signal (wire in Phase 2 when editor can execute)

**On disconnect / close:**
- Call `self._sidebar.clear()`

## Tree Structure

```
Schema Browser
├── 🔍 Filter objects…
├── ── schema_name (e.g. "public" for PG, database name for MySQL)
│   ├── 📋 users
│   │   ├── id (integer)
│   │   ├── name (varchar)
│   │   └── email (varchar)
│   ├── 📋 orders
│   └── 📋 products
└── ── another_schema
    └── ...
```

For MySQL, `get_schemas()` returns database names (excluding system DBs). For PostgreSQL, it returns schema names (excluding `pg_*` and `information_schema`).

## Data Flow

```
ConnectionDialog.accept()
  → MainWindow._open_connection_dialog()
    → sidebar.set_driver(driver)
      → QueryWorker(driver.get_schemas)
        → on finished: populate schema nodes
          → for each schema: QueryWorker(driver.get_tables, schema)
            → on finished: populate table child nodes
              → on expand table: QueryWorker(driver.get_columns, table, schema)
                → on finished: populate column child nodes
```

## Node Identification

Store metadata on each `QTreeWidgetItem` using `setData(Qt.ItemDataRole.UserRole, ...)`:

```python
# Schema node
item.setData(0, Qt.ItemDataRole.UserRole, {"type": "schema", "schema": schema_name})

# Table node
item.setData(0, Qt.ItemDataRole.UserRole, {"type": "table", "schema": schema_name, "table": table_name})

# Column node
item.setData(0, Qt.ItemDataRole.UserRole, {"type": "column", "schema": schema_name, "table": table_name, "column": col_name})
```

## Testing

- Unit test: create `Sidebar`, call `set_driver()` with a mock driver that returns known schemas/tables, assert tree items are populated correctly
- Unit test: call `clear()`, assert tree is empty and footer is visible
- Unit test: type in search bar, assert non-matching items are hidden
- Manual test: connect to a real MySQL/PG database, verify schema tree matches actual database contents

## Dependencies

None — uses existing `DatabaseDriver`, `QueryWorker`, and Qt widgets.
