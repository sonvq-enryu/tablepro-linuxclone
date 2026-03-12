# Phase 9: Tab Persistence & State

## Goal

Each editor tab maintains independent state (SQL text, results, pending changes). Tab state persists across app restarts, keyed by connection. Tabs support pinning, context menus, and drag reordering.

## Files to Modify

### `widgets/editor.py` — Per-Tab State Management

**Define `TabState` dataclass:**
```python
@dataclass
class TabState:
    tab_id: str           # UUID
    title: str            # "Query 1", "users", etc.
    sql: str              # Current editor text
    pinned: bool = False  # Pinned tabs can't be closed
```

**State tracking:**
- Each tab gets a unique `tab_id` (UUID generated on creation)
- Store `self._tab_states: dict[str, TabState]` keyed by tab_id
- Store tab_id on the `CodeEditor` widget: `editor.setProperty("tab_id", tab_id)`

**Save state to QSettings:**
```python
def _save_tab_states(self) -> None:
    """Persist all tab states to QSettings, keyed by connection ID."""
    if not self._connection_id:
        return
    states = []
    for i in range(self._tabs.count()):
        editor = self._tabs.widget(i)
        tab_id = editor.property("tab_id")
        state = self._tab_states.get(tab_id)
        if state:
            state.sql = editor.toPlainText()
            state.title = self._tabs.tabText(i)
            states.append(asdict(state))
    settings = QSettings()
    settings.setValue(f"tabs/{self._connection_id}", json.dumps(states))
```

**Restore state from QSettings:**
```python
def restore_tabs(self, connection_id: str) -> None:
    """Restore saved tab states for the given connection."""
    self._connection_id = connection_id
    settings = QSettings()
    data = settings.value(f"tabs/{connection_id}", "")
    if not data:
        # No saved state — create one default tab
        self._add_tab("Query 1")
        return

    states = json.loads(data)
    # Remove existing tabs
    while self._tabs.count():
        self._tabs.removeTab(0)

    for s in states:
        state = TabState(**s)
        self._tab_states[state.tab_id] = state
        self._add_tab_with_state(state)
```

**Auto-save triggers:**
- `QTimer` with 500ms debounce after any text change
- On tab close/create/switch
- On `closeEvent` (app closing)

```python
def _setup_autosave(self) -> None:
    self._save_timer = QTimer()
    self._save_timer.setSingleShot(True)
    self._save_timer.setInterval(500)
    self._save_timer.timeout.connect(self._save_tab_states)

def _on_text_changed(self) -> None:
    """Called on any editor text change — debounce save."""
    self._save_timer.start()
```

**Pin tabs:**
- Pinned tabs show a pin icon in the tab text (or bold title)
- `_close_tab()` checks if tab is pinned — refuses to close if so
- Pinned tabs survive "Close Other Tabs" and "Close All" (non-pinned)

**Tab context menu (right-click on tab bar):**
- "Close" — close this tab (if not pinned)
- "Close Others" — close all tabs except this one (and pinned tabs)
- "Close All" — close all non-pinned tabs
- "Pin Tab" / "Unpin Tab" — toggle pin state
- "Duplicate" — create new tab with same SQL content

**Implementation — tab bar context menu:**
```python
def _setup_tab_context_menu(self) -> None:
    tab_bar = self._tabs.tabBar()
    tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    tab_bar.customContextMenuRequested.connect(self._show_tab_context_menu)

def _show_tab_context_menu(self, pos: QPoint) -> None:
    tab_index = self._tabs.tabBar().tabAt(pos)
    if tab_index < 0:
        return

    menu = QMenu(self)
    # ... add actions based on tab state ...
    menu.exec(self._tabs.tabBar().mapToGlobal(pos))
```

### `main_window.py` — Connection-Scoped Tab Restore

**On connect:**
```python
def _on_connect_finished(self, driver):
    ...
    connection_id = self._current_conn_id
    self._editor.restore_tabs(connection_id)
```

**On disconnect / app close:**
```python
def closeEvent(self, event):
    self._editor._save_tab_states()  # save before closing
    self._conn_manager.close_all()
    super().closeEvent(event)
```

**On connection switch:**
- Save current tabs for old connection
- Restore tabs for new connection

### Result View State Per Tab

Each editor tab should also remember its associated result state:
- When switching editor tabs, the result view should show the results for that tab
- This means result data is stored per-tab (not globally)

**Add to `TabState`:**
```python
@dataclass
class TabState:
    tab_id: str
    title: str
    sql: str
    pinned: bool = False
    # Result state (not persisted to disk — re-executed on restore)
    last_query: str | None = None  # query that produced current results
```

**On tab switch:**
```python
def _on_tab_changed(self, index: int) -> None:
    # Save current result to old tab state (in memory)
    # Load result from new tab state
    # If new tab has no result, clear result view
    self._save_timer.start()  # trigger autosave
```

Note: Query results themselves are NOT persisted to disk (they could be stale). Only the SQL text is saved. On restore, the result area starts empty — user re-executes if needed.

## Tab Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+T` or `Ctrl+N` | New query tab |
| `Ctrl+W` | Close current tab |
| `Ctrl+1` through `Ctrl+9` | Switch to tab N |
| `Ctrl+Shift+]` | Next tab |
| `Ctrl+Shift+[` | Previous tab |
| `Ctrl+Shift+T` | Reopen last closed tab |

**Reopen last closed tab:**
- Maintain `self._closed_tabs: list[TabState]` (max 10)
- On tab close, push state to stack
- On `Ctrl+Shift+T`, pop and restore

## Testing

- Unit test: create 3 tabs, save state, clear tabs, restore state → 3 tabs with correct SQL text
- Unit test: pinned tab refuses to close
- Unit test: "Close Others" leaves pinned tabs and the current tab
- Unit test: autosave timer fires 500ms after text change
- Unit test: tab state is keyed by connection_id — different connections get different tabs
- Unit test: reopen closed tab restores SQL content
- Unit test: context menu shows correct items (Pin/Unpin based on state)

## Dependencies

None — uses QSettings, QTimer, and standard Qt widgets.
