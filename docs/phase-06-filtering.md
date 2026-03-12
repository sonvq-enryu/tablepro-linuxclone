# Phase 6: Filtering System

## Goal

Visual filter builder to construct WHERE clauses without writing SQL. Supports 18 operators, AND/OR logic, quick search, raw SQL mode, and saved presets.

## New Files

### `widgets/filter_panel.py` — Filter Builder Widget

**`FilterRow(QWidget)`** — A single filter condition:
```
[ Column ▾ ] [ Operator ▾ ] [ Value input        ] [×]
```

- **Column dropdown (`QComboBox`):** Populated with column names from current result + "Raw SQL" option
- **Operator dropdown (`QComboBox`):** Changes available operators based on column selection
- **Value input (`QLineEdit`):** Text input for the filter value. Hidden for IS NULL/IS NOT NULL/IS EMPTY/IS NOT EMPTY. Shows two inputs for BETWEEN (min/max).
- **Remove button:** "×" removes this filter row
- **Checkbox:** Enable/disable this individual filter without removing it

**`FilterPanel(QWidget)`** — Container for filter rows:

```
┌─────────────────────────────────────────────────────────┐
│ 🔍 Quick search: [________________________]            │
│                                                         │
│ ☑ [ Column ▾ ] [ equals ▾ ] [ value     ] [×]   [AND] │
│ ☑ [ Column ▾ ] [ > ▾      ] [ 100       ] [×]   [OR ] │
│                                                         │
│ [ + Add Filter ]           [ Apply ] [ Clear ] [ 💾 ]  │
└─────────────────────────────────────────────────────────┘
```

**18 operators:**

| Category | Operators | Value Input |
|---|---|---|
| Exact match | `equals`, `not equals` | Single text field |
| Text matching | `contains`, `not contains`, `starts with`, `ends with` | Single text field |
| Comparison | `>`, `>=`, `<`, `<=` | Single text field |
| NULL handling | `IS NULL`, `IS NOT NULL` | No input |
| Empty string | `IS EMPTY`, `IS NOT EMPTY` | No input |
| List | `IN`, `NOT IN` | Comma-separated text field |
| Range | `BETWEEN` | Two text fields (min, max) |
| Pattern | `REGEX` | Single text field |

**Quick Search:**
- Text input at the top of the filter panel
- Client-side filtering: hides rows in the grid that don't contain the search term in any column
- Does NOT generate SQL — purely local filtering on loaded data
- Case-insensitive substring match

**Raw SQL mode:**
- When "Raw SQL" is selected in the Column dropdown, the operator dropdown hides and the value input becomes a wide text field for typing a raw WHERE clause fragment
- Example: `created_at > NOW() - INTERVAL '7 days'`

**AND/OR toggle:**
- Each filter row (except the first) has an AND/OR toggle button
- AND = all conditions must match; OR = any condition matches
- Mixed: groups are parenthesized: `(A AND B) OR C`

**Signals:**
```python
filters_applied = Signal(str)   # emits the WHERE clause string
filters_cleared = Signal()
```

**`build_where_clause() -> str` method:**
- Iterate enabled filter rows
- Map each to SQL fragment:
  - `equals` → `"column" = 'value'`
  - `contains` → `"column" LIKE '%value%'`
  - `starts with` → `"column" LIKE 'value%'`
  - `IS NULL` → `"column" IS NULL`
  - `IN` → `"column" IN ('a', 'b', 'c')`
  - `BETWEEN` → `"column" BETWEEN 'min' AND 'max'`
  - `REGEX` → MySQL: `"column" REGEXP 'pattern'`, PostgreSQL: `"column" ~ 'pattern'`
- Combine with AND/OR logic
- Return the full WHERE clause (without the `WHERE` keyword)

**Saved presets:**
- Save button (💾) opens a dialog to name the current filter configuration
- Load button opens a dropdown of saved presets
- Stored in QSettings under `filters/{connection_id}/{table_name}/presets`
- Preset stores: list of `{column, operator, value, enabled, logic}` dicts

## Files to Modify

### `widgets/result_view.py`

**Add filter toggle:**
- Add a filter icon button ("⫧ Filter") in the info bar
- Clicking toggles `FilterPanel` visibility above the data grid

**Insert FilterPanel:**
- Place `FilterPanel` between info bar and `QTableWidget`
- Initially hidden

**On `filters_applied(where_clause)`:**
- If the current result came from a table click (sidebar), re-execute with WHERE:
  ```sql
  SELECT * FROM schema.table WHERE {where_clause} LIMIT {page_size} OFFSET {offset}
  ```
- If the current result came from a manual query, append WHERE clause:
  - Parse original query and inject WHERE clause (simple case: append before LIMIT/ORDER BY)
  - Or: show info that filters only work on table-browsing mode

**On `filters_cleared()`:**
- Re-execute the original query without WHERE clause

**Store filter state per tab:**
- Each tab remembers its filter panel state (visible, filter rows, applied status)

### `main_window.py`

- No changes needed if result_view handles re-execution internally
- May need to pass driver reference to FilterPanel for dialect-specific SQL (REGEX syntax)

## SQL Injection Prevention

- All filter values must be passed as parameters, not interpolated into SQL
- `build_where_clause()` returns `(clause_str, params_tuple)` not raw SQL
- The Raw SQL mode is an exception — warn user that raw SQL is executed as-is

## Testing

- Unit test: single `equals` filter produces correct WHERE clause
- Unit test: `contains` produces `LIKE '%value%'`
- Unit test: `IS NULL` produces `"column" IS NULL` with no params
- Unit test: `BETWEEN` produces `"column" BETWEEN %s AND %s` with two params
- Unit test: `IN` with `a, b, c` produces `"column" IN (%s, %s, %s)` with three params
- Unit test: AND logic combines correctly: `"col1" = %s AND "col2" > %s`
- Unit test: OR logic: `"col1" = %s OR "col2" = %s`
- Unit test: disabled filter rows are skipped
- Unit test: empty filter produces empty string
- Unit test: Quick Search hides non-matching rows locally
- Unit test: Save/load preset round-trips correctly

## Dependencies

None.
