# Phase 4: Table Structure Viewer

## Goal

View column definitions, indexes, foreign keys, and DDL for any table in a four-tab structure panel.

## New Files

### `widgets/table_structure.py` — Structure Viewer Widget

`StructureView(QWidget)` containing a `QTabWidget` with four tabs:

**Columns Tab:**
- `QTableWidget` with columns: Name, Type, Nullable, Default, Extra, Key
- Populate via `driver.get_columns(table, schema)`
- Nullable shows "YES"/"NO"
- Key shows "PRI" for primary key columns, "FOR" for foreign key, "UNI" for unique

**Indexes Tab:**
- `QTableWidget` with columns: Name, Columns, Type, Unique, Primary
- Populate via `driver.get_indexes(table, schema)`
- Columns cell shows comma-separated column names
- Type shows BTREE/HASH/FULLTEXT etc.
- Unique/Primary show checkmark or "Yes"/"No"

**Foreign Keys Tab:**
- `QTableWidget` with columns: Name, Column, References, On Delete, On Update
- Populate via `driver.get_foreign_keys(table, schema)` (new driver method)
- References shows `table_name.column_name`

**DDL Tab:**
- Read-only `CodeEditor` (from Phase 2) with SQL highlighting
- Populate via `driver.get_ddl(table, schema)` (new driver method)
- Shows the full CREATE TABLE statement
- Selectable/copyable

**Public API:**
```python
def load_structure(self, driver: DatabaseDriver, table: str, schema: str | None = None) -> None:
    """Fetch and display all structure metadata for the given table."""
```
- Each fetch runs on a `QueryWorker`
- Show loading indicator while fetching
- Switch to Columns tab by default

## Files to Modify

### `db/driver.py` — Add Abstract Methods and Data Classes

**New dataclass:**
```python
@dataclass
class ForeignKeyInfo:
    name: str
    column: str
    ref_table: str
    ref_column: str
    on_delete: str  # CASCADE, RESTRICT, SET NULL, SET DEFAULT, NO ACTION
    on_update: str
```

**New abstract methods on `DatabaseDriver`:**
```python
@abstractmethod
def get_foreign_keys(self, table: str, schema: str | None = None) -> list[ForeignKeyInfo]:
    """Return foreign key constraints for the given table."""
    ...

@abstractmethod
def get_ddl(self, table: str, schema: str | None = None) -> str:
    """Return the CREATE TABLE DDL statement for the given table."""
    ...
```

### `db/mysql_driver.py` — Implement New Methods

**`get_foreign_keys()`:**
```sql
SELECT
    tc.constraint_name,
    kcu.column_name,
    kcu.referenced_table_name,
    kcu.referenced_column_name,
    rc.delete_rule,
    rc.update_rule
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.referential_constraints rc
    ON tc.constraint_name = rc.constraint_name
    AND tc.table_schema = rc.constraint_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_schema = %s
    AND tc.table_name = %s
```

**`get_ddl()`:**
```sql
SHOW CREATE TABLE `schema`.`table`
```
Returns the second column of the result as the DDL string.

### `db/postgres_driver.py` — Implement New Methods

**`get_foreign_keys()`:**
```sql
SELECT
    con.conname AS name,
    att.attname AS column,
    ref_cl.relname AS ref_table,
    ref_att.attname AS ref_column,
    CASE con.confdeltype
        WHEN 'a' THEN 'NO ACTION'
        WHEN 'r' THEN 'RESTRICT'
        WHEN 'c' THEN 'CASCADE'
        WHEN 'n' THEN 'SET NULL'
        WHEN 'd' THEN 'SET DEFAULT'
    END AS on_delete,
    CASE con.confupdtype
        WHEN 'a' THEN 'NO ACTION'
        WHEN 'r' THEN 'RESTRICT'
        WHEN 'c' THEN 'CASCADE'
        WHEN 'n' THEN 'SET NULL'
        WHEN 'd' THEN 'SET DEFAULT'
    END AS on_update
FROM pg_constraint con
JOIN pg_class cl ON cl.oid = con.conrelid
JOIN pg_namespace ns ON ns.oid = cl.relnamespace
JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY(con.conkey)
JOIN pg_class ref_cl ON ref_cl.oid = con.confrelid
JOIN pg_attribute ref_att ON ref_att.attrelid = con.confrelid AND ref_att.attnum = ANY(con.confkey)
WHERE con.contype = 'f'
    AND cl.relname = %s
    AND ns.nspname = %s
```

**`get_ddl()`:**

Reconstruct DDL from metadata by querying `information_schema.columns`, `pg_indexes`, and `pg_constraint`. Build the CREATE TABLE statement string programmatically:

```python
def get_ddl(self, table: str, schema: str | None = None) -> str:
    schema = schema or "public"
    # Get columns
    columns = self.get_columns(table, schema)
    # Get indexes
    indexes = self.get_indexes(table, schema)
    # Get foreign keys
    fks = self.get_foreign_keys(table, schema)

    # Build DDL string
    lines = [f'CREATE TABLE "{schema}"."{table}" (']
    col_lines = []
    for col in columns:
        line = f'    "{col.name}" {col.data_type}'
        if not col.is_nullable:
            line += " NOT NULL"
        if col.column_default is not None:
            line += f" DEFAULT {col.column_default}"
        col_lines.append(line)

    # Primary key
    pk = [i for i in indexes if i.is_primary]
    if pk:
        pk_cols = ", ".join(f'"{c}"' for c in pk[0].columns)
        col_lines.append(f"    PRIMARY KEY ({pk_cols})")

    # Foreign keys
    for fk in fks:
        col_lines.append(
            f'    CONSTRAINT "{fk.name}" FOREIGN KEY ("{fk.column}") '
            f'REFERENCES "{fk.ref_table}" ("{fk.ref_column}") '
            f'ON DELETE {fk.on_delete} ON UPDATE {fk.on_update}'
        )

    lines.append(",\n".join(col_lines))
    lines.append(");")

    # Non-primary indexes as separate statements
    for idx in indexes:
        if not idx.is_primary:
            unique = "UNIQUE " if idx.is_unique else ""
            idx_cols = ", ".join(f'"{c}"' for c in idx.columns)
            lines.append(f'CREATE {unique}INDEX "{idx.name}" ON "{schema}"."{table}" ({idx_cols});')

    return "\n".join(lines)
```

### `widgets/result_view.py` — Add Structure Tab

- Add a fourth tab "Structure" to the `QTabWidget`
- Embed `StructureView` widget inside the tab
- Expose `show_structure(driver, table, schema)` method that:
  - Switches to Structure tab
  - Calls `self._structure_view.load_structure(driver, table, schema)`

### `widgets/sidebar.py` — Wire "View Structure" Context Menu

- On right-click → "View Structure": emit `structure_requested(schema, table)` signal

### `main_window.py` — Connect Signals

- Connect `sidebar.structure_requested` → `result_view.show_structure(self._active_driver, table, schema)`

## Testing

- Unit test: `ForeignKeyInfo` dataclass fields
- Integration test (MySQL): `get_foreign_keys()` on a table with FK constraints returns correct data
- Integration test (PostgreSQL): same
- Integration test (MySQL): `get_ddl()` returns valid SQL containing CREATE TABLE
- Integration test (PostgreSQL): same
- Unit test: `StructureView.load_structure()` with mock driver populates all four tabs

## Dependencies

None — uses existing driver interface, CodeEditor (Phase 2), and QueryWorker.
