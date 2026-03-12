# Phase 10: Keyboard Shortcuts & Polish

## Goal

Complete keyboard shortcut set across the entire application. Final UI polish, QSS theme updates for all new widgets, and general refinements.

## Global Shortcuts

Register via `QShortcut` in `MainWindow.__init__()`:

| Shortcut | Action | Implementation |
|---|---|---|
| `Ctrl+Enter` | Execute query | `self._editor.query_submitted` |
| `Ctrl+Shift+Enter` | Execute selection | Editor runs selected text |
| `Ctrl+N` | New query tab | `self._editor._new_tab()` |
| `Ctrl+W` | Close current tab | `self._editor._close_tab(current)` |
| `Ctrl+T` | New query tab (alias) | Same as Ctrl+N |
| `Ctrl+S` | Commit pending changes | `self._result_view.commit_changes()` |
| `Ctrl+Z` | Undo (context-aware) | Editor undo or grid undo |
| `Ctrl+Shift+Z` | Redo (context-aware) | Editor redo or grid redo |
| `Ctrl+B` | Toggle sidebar | `self._toggle_sidebar()` |
| `Ctrl+Shift+N` | New connection dialog | `self._open_connection_dialog()` |
| `Ctrl+Y` | Show query history | Switch result view to History tab |
| `Ctrl+Shift+E` | Export data | `self._on_export()` |
| `Ctrl+Shift+I` | Import SQL | `self._on_import()` |
| `Ctrl+F` | Find in editor | Open find bar in editor |
| `Ctrl+H` | Find and replace | Open find/replace bar |
| `Ctrl+1..9` | Switch to tab N | `self._editor._tabs.setCurrentIndex(N-1)` |
| `Ctrl+Shift+]` | Next tab | Increment tab index |
| `Ctrl+Shift+[` | Previous tab | Decrement tab index |
| `Ctrl+Shift+T` | Reopen closed tab | `self._editor.reopen_closed_tab()` |
| `F5` | Refresh sidebar | `self._sidebar.refresh()` |
| `Ctrl+Q` | Quit application | `self.close()` |
| `Ctrl+Shift+P` | Preview SQL changes | Open SQL preview dialog |
| `Alt+Ctrl+F` | Format SQL | `self._editor.format_current()` |

## Data Grid Keyboard Navigation

Install event filter on `QTableWidget` in `result_view.py`:

| Key | Action |
|---|---|
| `Arrow keys` | Move between cells |
| `Tab` | Move to next cell (right) |
| `Shift+Tab` | Move to previous cell (left) |
| `Enter` or `F2` | Enter edit mode on current cell |
| `Escape` | Cancel cell edit |
| `Delete` | Mark selected rows for deletion |
| `Home` | Jump to first cell in row |
| `End` | Jump to last cell in row |
| `Ctrl+Home` | Jump to first cell in grid |
| `Ctrl+End` | Jump to last cell in grid |
| `Page Up` | Previous page (pagination) |
| `Page Down` | Next page (pagination) |
| `Ctrl+C` | Copy selected cells as TSV |
| `Ctrl+A` | Select all cells |

**Implementation:**
```python
class DataGridEventFilter(QObject):
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            modifiers = event.modifiers()

            if key == Qt.Key.Key_PageDown:
                self._result_view.next_page()
                return True
            elif key == Qt.Key.Key_PageUp:
                self._result_view.prev_page()
                return True
            elif key == Qt.Key.Key_Delete:
                self._result_view.delete_selected_rows()
                return True
            elif key == Qt.Key.Key_F2 or key == Qt.Key.Key_Return:
                self._result_view.edit_current_cell()
                return True
            # ... etc
        return False
```

## Find Bar in Editor

**New widget: `widgets/find_bar.py`**

Inline find bar that appears at the top of the editor (not a dialog):

```
┌───────────────────────────────────────────────────────────┐
│ Find: [ search term        ] [ ▲ ] [ ▼ ] [ × ]  1 of 5  │
│ Replace: [ replacement     ] [ Replace ] [ Replace All ]  │
└───────────────────────────────────────────────────────────┘
```

- `Ctrl+F` shows find bar (replace row hidden)
- `Ctrl+H` shows find bar with replace row
- `Enter` / `▼` button → find next
- `Shift+Enter` / `▲` button → find previous
- `Escape` or `×` → close find bar
- Highlights all matches in the editor with semi-transparent background
- Current match highlighted differently
- Match count displayed: "N of M"
- Case sensitivity toggle button
- Whole word toggle button

**Integration with `CodeEditor`:**
```python
class CodeEditor(QPlainTextEdit):
    def __init__(self):
        ...
        self._find_bar = FindBar(self)
        # Position at top of editor

    def show_find(self, with_replace: bool = False) -> None:
        self._find_bar.show(with_replace)
        self._find_bar.focus_search()
```

## QSS Theme Updates

Add styles for all widgets introduced in Phases 4-9 to both `dark.qss` and `light.qss`:

### Filter Panel
```css
QWidget#filter-panel { background-color: #181825; border-bottom: 1px solid #313244; }
QWidget#filter-row { background: transparent; }
QPushButton#filter-add-btn { ... }
QPushButton#filter-apply-btn { ... }
QPushButton#filter-clear-btn { ... }
QComboBox#filter-column-combo { ... }
QComboBox#filter-operator-combo { ... }
QLineEdit#filter-value-input { ... }
```

### Structure View
```css
QTabWidget#structure-tabs::pane { ... }
QTabWidget#structure-tabs > QTabBar::tab { ... }
QTableWidget#structure-table { ... }
```

### History Panel
```css
QWidget#history-panel { ... }
QLineEdit#history-search { ... }
QComboBox#history-filter { ... }
QTableWidget#history-table { ... }
```

### Pagination Bar
```css
QWidget#pagination-bar { background-color: #181825; border-top: 1px solid #313244; }
QPushButton#page-btn { ... }
QPushButton#page-btn:disabled { color: #45475a; }
QComboBox#page-size-combo { min-width: 80px; }
QLabel#page-info { color: #6c7086; font-size: 11px; }
```

### Change Tracking Visual Indicators
```css
/* Cell backgrounds set programmatically via QTableWidgetItem, not QSS */
/* But toolbar buttons need styling: */
QPushButton#commit-btn { background-color: #a6e3a1; color: #1e1e2e; }
QPushButton#discard-btn { background-color: #f38ba8; color: #1e1e2e; }
QPushButton#preview-btn { ... }
QPushButton#insert-row-btn { ... }
QPushButton#delete-row-btn { ... }
```

### Find Bar
```css
QWidget#find-bar { background-color: #181825; border-bottom: 1px solid #313244; }
QLineEdit#find-input { ... }
QLineEdit#replace-input { ... }
QPushButton#find-next-btn { ... }
QPushButton#find-prev-btn { ... }
QPushButton#replace-btn { ... }
QPushButton#replace-all-btn { ... }
QLabel#find-count { color: #6c7086; font-size: 11px; }
```

### Export/Import Dialogs
```css
QDialog#export-dialog { background-color: #1e1e2e; }
QDialog#import-dialog { background-color: #1e1e2e; }
QRadioButton { color: #cdd6f4; }
QRadioButton::indicator { ... }
QProgressBar { ... }
QProgressBar::chunk { background-color: #cba6f7; }
```

## Light Theme

The `light.qss` file needs equivalent styles for all new widgets using the Catppuccin Latte palette:

| Dark (Mocha) | Light (Latte) |
|---|---|
| `#1e1e2e` (base) | `#eff1f5` |
| `#181825` (mantle) | `#e6e9ef` |
| `#313244` (surface0) | `#ccd0da` |
| `#45475a` (surface1) | `#bcc0cc` |
| `#585b70` (surface2) | `#acb0be` |
| `#6c7086` (overlay0) | `#9ca0b0` |
| `#cdd6f4` (text) | `#4c4f69` |
| `#cba6f7` (mauve) | `#8839ef` |
| `#89b4fa` (blue) | `#1e66f5` |
| `#a6e3a1` (green) | `#40a02b` |
| `#f38ba8` (red) | `#d20f39` |
| `#fab387` (peach) | `#fe640b` |
| `#f9e2af` (yellow) | `#df8e1d` |

## UI Polish Items

1. **Loading indicators:** Show spinner/progress when fetching schema, executing queries, or loading structure
2. **Empty states:** Meaningful messages when result view is empty, no connections saved, no history
3. **Tooltips:** Add tooltips to all toolbar buttons and icon-only buttons
4. **Window title:** Update to show current connection: "TableFree — [connection_name]"
5. **Tab titles:** When query targets a specific table, auto-rename tab: "users" instead of "Query 1"
6. **Status bar:** Show active connection, last query duration, row count
7. **Resize handles:** Ensure splitter handles are easily grabbable (min 3px hover area)
8. **Focus management:** After executing query, focus the result grid. After opening find bar, focus search input.

## Testing

- Unit test: each shortcut triggers the correct action
- Unit test: data grid event filter handles Page Up/Down, Delete, F2
- Unit test: find bar — search "SELECT" in editor with 3 occurrences, count shows "1 of 3"
- Unit test: find bar — "Replace All" replaces all occurrences
- Manual test: visually verify all widgets look correct in both dark and light themes
- Manual test: keyboard-only workflow — connect, browse schema, execute query, paginate results, switch tabs — all without mouse

## Dependencies

None.

## Milestone

**After Phase 10, the application is feature-complete** — a fully functional database management client matching the core feature set of TablePro, running natively on Linux with MySQL and PostgreSQL support.
