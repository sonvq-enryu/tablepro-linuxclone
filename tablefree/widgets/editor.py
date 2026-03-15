"""Editor panel widget — Tabbed query editor with toolbar."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from uuid import uuid4

import sqlparse

from PySide6.QtCore import QEvent, QObject, QPoint, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QKeyEvent, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tablefree.widgets.code_editor import CodeEditor


@dataclass
class TabState:
    tab_id: str
    title: str
    sql: str
    pinned: bool = False
    # In-memory hint only; query results are never persisted.
    last_query: str | None = None


class EditorPanel(QWidget):
    """Center panel: tabbed SQL query editor with action toolbar."""

    query_submitted = Signal(str)
    tab_changed = Signal(str)
    tab_closed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("editor-panel")
        self._driver = None
        self._query_running = False
        self._connection_id: str | None = None
        self._tab_states: dict[str, TabState] = {}
        self._closed_tabs: list[TabState] = []
        self._next_query_number = 1
        self._restoring_tabs = False
        self._spinner_frames = ["", ".", "..", "..."]
        self._spinner_index = 0
        self._pin_icon = self._create_pin_icon()
        self._setup_autosave()
        self._setup_ui()
        self._setup_tab_context_menu()
        self._setup_shortcuts()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QWidget()
        toolbar.setObjectName("editor-toolbar")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(8, 4, 8, 4)
        tb_layout.setSpacing(6)

        self._fmt_btn = QPushButton("Format")
        self._fmt_btn.setObjectName("toolbar-btn")
        self._fmt_btn.setToolTip("Beautify SQL")
        self._fmt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fmt_btn.clicked.connect(self._on_format)
        tb_layout.addWidget(self._fmt_btn)

        self._run_sel_btn = QPushButton("Run Selection")
        self._run_sel_btn.setObjectName("toolbar-btn")
        self._run_sel_btn.setToolTip("Execute selected text (Ctrl+Shift+Enter)")
        self._run_sel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_sel_btn.clicked.connect(self._on_run_selection)
        tb_layout.addWidget(self._run_sel_btn)

        left_sep = QFrame()
        left_sep.setObjectName("toolbar-separator")
        left_sep.setFrameShape(QFrame.Shape.VLine)
        left_sep.setFixedHeight(16)
        tb_layout.addWidget(left_sep)

        tb_layout.addStretch()

        self._spinner_label = QLabel("")
        self._spinner_label.setObjectName("editor-spinner")
        self._spinner_label.setFixedWidth(36)
        tb_layout.addWidget(self._spinner_label)

        self._info_label = QLabel("Ready")
        self._info_label.setObjectName("editor-info")
        tb_layout.addWidget(self._info_label)

        self._cursor_toolbar_label = QLabel("Ln 1, Col 1")
        self._cursor_toolbar_label.setObjectName("editor-cursor-info")
        tb_layout.addWidget(self._cursor_toolbar_label)

        right_sep = QFrame()
        right_sep.setObjectName("toolbar-separator")
        right_sep.setFrameShape(QFrame.Shape.VLine)
        right_sep.setFixedHeight(16)
        tb_layout.addWidget(right_sep)

        self._run_btn = QPushButton("Run")
        self._run_btn.setObjectName("toolbar-btn-primary")
        self._run_btn.setToolTip("Execute query (Ctrl+Enter)")
        self._run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_btn.clicked.connect(self._on_run)
        tb_layout.addWidget(self._run_btn)

        self._explain_btn = QPushButton("Explain")
        self._explain_btn.setObjectName("toolbar-btn-explain")
        self._explain_btn.setToolTip("Show query execution plan")
        self._explain_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._explain_btn.clicked.connect(self._on_explain)
        tb_layout.addWidget(self._explain_btn)

        layout.addWidget(toolbar)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("editor-separator")
        line.setFixedHeight(1)
        layout.addWidget(line)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("editor-tabs")
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.setDocumentMode(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs.tabBar().tabMoved.connect(self._on_tab_reordered)

        add_tab_btn = QPushButton(" + ")
        add_tab_btn.setObjectName("add-tab-btn")
        add_tab_btn.setToolTip("New query tab")
        add_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_tab_btn.setFixedSize(28, 28)
        add_tab_btn.clicked.connect(self._new_tab)
        self._tabs.setCornerWidget(add_tab_btn, Qt.Corner.TopRightCorner)

        layout.addWidget(self._tabs, stretch=1)

        status_bar = QWidget()
        status_bar.setObjectName("editor-status-bar")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(10, 2, 10, 2)
        status_layout.setSpacing(8)

        self._cursor_status_label = QLabel("Ln 1, Col 1")
        self._cursor_status_label.setObjectName("editor-status-text")
        status_layout.addWidget(self._cursor_status_label)
        status_layout.addStretch()

        self._connection_label = QLabel("Disconnected")
        self._connection_label.setObjectName("editor-status-connection")
        status_layout.addWidget(self._connection_label)
        layout.addWidget(status_bar)
        self._new_tab(title="Query 1")

    def _setup_autosave(self) -> None:
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._save_tab_states)
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(250)
        self._spinner_timer.timeout.connect(self._advance_spinner)

    def _setup_tab_context_menu(self) -> None:
        tab_bar = self._tabs.tabBar()
        tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tab_bar.customContextMenuRequested.connect(self._show_tab_context_menu)

    def _setup_shortcuts(self) -> None:
        self._shortcuts: list[QShortcut] = []
        self._register_shortcut("Ctrl+N", self._new_tab)
        self._register_shortcut("Ctrl+T", self._new_tab)
        self._register_shortcut("Ctrl+W", self._close_current_tab)
        self._register_shortcut("Ctrl+Shift+T", self._reopen_last_closed_tab)
        self._register_shortcut("Ctrl+Shift+]", self._next_tab)
        self._register_shortcut("Ctrl+Shift+[", self._previous_tab)
        for idx in range(1, 10):
            self._register_shortcut(
                f"Ctrl+{idx}",
                lambda tab_number=idx: self._switch_to_tab_number(tab_number),
            )

    def _register_shortcut(self, key: str, callback) -> None:
        shortcut = QShortcut(QKeySequence(key), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(callback)
        self._shortcuts.append(shortcut)

    def _display_title(self, state: TabState) -> str:
        if self._is_tab_modified(state):
            return f"{state.title}  •"
        return state.title

    def _is_tab_modified(self, state: TabState) -> bool:
        if state.last_query is None:
            return False
        return state.sql.strip() != state.last_query.strip()

    def _create_pin_icon(self) -> QIcon:
        pixmap = QPixmap(10, 10)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#f59e0b"))
        painter.drawEllipse(2, 2, 6, 6)
        painter.end()
        return QIcon(pixmap)

    def _apply_tab_visual_state(self, tab_id: str) -> None:
        for i in range(self._tabs.count()):
            editor = self._tabs.widget(i)
            if editor is None or editor.property("tab_id") != tab_id:
                continue
            state = self._tab_states.get(tab_id)
            if state is None:
                return
            self._tabs.setTabText(i, self._display_title(state))
            self._tabs.setTabIcon(i, self._pin_icon if state.pinned else QIcon())
            return

    def _add_tab_with_state(self, state: TabState, *, set_current: bool = True) -> None:
        editor = CodeEditor()
        editor.setObjectName("sql-editor")
        editor.setPlaceholderText(
            "-- Write your SQL queries here…\n"
            "-- Press Ctrl+Enter to execute\n\n"
            "SELECT * FROM users LIMIT 100;"
        )
        editor.installEventFilter(self)
        editor.setProperty("tab_id", state.tab_id)
        editor.textChanged.connect(self._on_text_changed)
        editor.cursorPositionChanged.connect(self._on_cursor_position_changed)
        editor.setPlainText(state.sql)
        self._tab_states[state.tab_id] = state
        self._tabs.addTab(editor, self._display_title(state))
        self._apply_tab_visual_state(state.tab_id)
        if set_current:
            self._tabs.setCurrentWidget(editor)
            self._update_cursor_labels(editor)

    def _new_tab(self, *, title: str | None = None, sql: str = "", pinned: bool = False) -> None:
        if title is None:
            title = f"Query {self._next_query_number}"
        title = self._normalize_title(title)
        self._next_query_number += 1
        state = TabState(tab_id=str(uuid4()), title=title, sql=sql, pinned=pinned)
        self._add_tab_with_state(state, set_current=True)
        self._save_if_needed()

    def _normalize_title(self, title: str) -> str:
        match = re.match(r"^\[Query\s+(\d+)\]$", title.strip())
        if match:
            return f"Query {match.group(1)}"
        return title.strip()

    def _close_tab(self, index: int, *, push_closed: bool = True) -> None:
        editor = self._tabs.widget(index)
        if not isinstance(editor, CodeEditor):
            return
        tab_id = editor.property("tab_id")
        if not isinstance(tab_id, str):
            return
        state = self._tab_states.get(tab_id)
        if state is None:
            return
        if state.pinned:
            return
        if self._tabs.count() <= 1:
            return

        state.sql = editor.toPlainText()
        if push_closed:
            self._closed_tabs.append(TabState(**asdict(state)))
            self._closed_tabs = self._closed_tabs[-10:]
        self._tabs.removeTab(index)
        self._tab_states.pop(tab_id, None)
        self.tab_closed.emit(tab_id)
        self._save_if_needed()

    def _on_tab_changed(self, index: int) -> None:
        widget = self._tabs.widget(index)
        if widget:
            tab_id = widget.property("tab_id")
            if isinstance(tab_id, str):
                self.tab_changed.emit(tab_id)
                if isinstance(widget, CodeEditor):
                    self._update_cursor_labels(widget)
                self._save_if_needed()

    def _on_tab_reordered(self, _from: int, _to: int) -> None:
        self._save_if_needed()

    def _on_text_changed(self) -> None:
        editor = self.sender()
        if not isinstance(editor, CodeEditor):
            return
        tab_id = editor.property("tab_id")
        if not isinstance(tab_id, str):
            return
        state = self._tab_states.get(tab_id)
        if state is None:
            return
        state.sql = editor.toPlainText()
        self._apply_tab_visual_state(tab_id)
        self._save_if_needed()

    def _on_cursor_position_changed(self) -> None:
        editor = self.sender()
        if isinstance(editor, CodeEditor) and editor is self.current_editor():
            self._update_cursor_labels(editor)

    def _update_cursor_labels(self, editor: CodeEditor | None) -> None:
        if editor is None:
            return
        cursor = editor.textCursor()
        text = f"Ln {cursor.blockNumber() + 1}, Col {cursor.columnNumber() + 1}"
        if hasattr(self, "_cursor_toolbar_label"):
            self._cursor_toolbar_label.setText(text)
        if hasattr(self, "_cursor_status_label"):
            self._cursor_status_label.setText(text)

    def _advance_spinner(self) -> None:
        self._spinner_index = (self._spinner_index + 1) % len(self._spinner_frames)
        self._spinner_label.setText(f"Running{self._spinner_frames[self._spinner_index]}")

    def _save_if_needed(self) -> None:
        if self._restoring_tabs:
            return
        self._save_timer.start()

    def _active_tab_id_or_none(self) -> str | None:
        widget = self._tabs.currentWidget()
        if widget is not None:
            tab_id = widget.property("tab_id")
            if isinstance(tab_id, str):
                return tab_id
        return None

    def _show_tab_context_menu(self, pos: QPoint) -> None:
        tab_bar = self._tabs.tabBar()
        tab_index = tab_bar.tabAt(pos)
        if tab_index < 0:
            return
        editor = self._tabs.widget(tab_index)
        if not isinstance(editor, CodeEditor):
            return
        tab_id = editor.property("tab_id")
        if not isinstance(tab_id, str):
            return
        state = self._tab_states.get(tab_id)
        if state is None:
            return

        labels = self._context_menu_labels_for_index(tab_index)
        menu = QMenu(self)
        close_action = menu.addAction(labels[0])
        close_action.setEnabled(not state.pinned)
        close_others_action = menu.addAction(labels[1])
        close_all_action = menu.addAction(labels[2])
        menu.addSeparator()
        pin_action = menu.addAction(labels[3])
        duplicate_action = menu.addAction(labels[4])

        chosen = menu.exec(tab_bar.mapToGlobal(pos))
        if chosen == close_action:
            self._close_tab(tab_index)
        elif chosen == close_others_action:
            self._close_other_tabs(tab_index)
        elif chosen == close_all_action:
            self._close_all_non_pinned()
        elif chosen == pin_action:
            self._toggle_pin(tab_index)
        elif chosen == duplicate_action:
            self._duplicate_tab(tab_index)

    def _context_menu_labels_for_index(self, index: int) -> list[str]:
        labels = ["Close", "Close Others", "Close All", "Pin Tab", "Duplicate"]
        editor = self._tabs.widget(index)
        if not isinstance(editor, CodeEditor):
            return labels
        tab_id = editor.property("tab_id")
        if not isinstance(tab_id, str):
            return labels
        state = self._tab_states.get(tab_id)
        if state is not None and state.pinned:
            labels[3] = "Unpin Tab"
        return labels

    def _toggle_pin(self, index: int) -> None:
        editor = self._tabs.widget(index)
        if not isinstance(editor, CodeEditor):
            return
        tab_id = editor.property("tab_id")
        if not isinstance(tab_id, str):
            return
        state = self._tab_states.get(tab_id)
        if state is None:
            return
        state.pinned = not state.pinned
        self._apply_tab_visual_state(tab_id)
        self._save_if_needed()

    def _duplicate_tab(self, index: int) -> None:
        editor = self._tabs.widget(index)
        if not isinstance(editor, CodeEditor):
            return
        tab_id = editor.property("tab_id")
        if not isinstance(tab_id, str):
            return
        state = self._tab_states.get(tab_id)
        if state is None:
            return
        self._new_tab(sql=editor.toPlainText(), title=f"{state.title} Copy")

    def _close_other_tabs(self, keep_index: int) -> None:
        for i in range(self._tabs.count() - 1, -1, -1):
            if i == keep_index:
                continue
            editor = self._tabs.widget(i)
            if not isinstance(editor, CodeEditor):
                continue
            tab_id = editor.property("tab_id")
            if not isinstance(tab_id, str):
                continue
            state = self._tab_states.get(tab_id)
            if state is not None and state.pinned:
                continue
            self._close_tab(i)
        self._save_if_needed()

    def _close_all_non_pinned(self) -> None:
        for i in range(self._tabs.count() - 1, -1, -1):
            editor = self._tabs.widget(i)
            if not isinstance(editor, CodeEditor):
                continue
            tab_id = editor.property("tab_id")
            if not isinstance(tab_id, str):
                continue
            state = self._tab_states.get(tab_id)
            if state is not None and state.pinned:
                continue
            if self._tabs.count() <= 1:
                break
            self._close_tab(i)
        self._save_if_needed()

    def _close_current_tab(self) -> None:
        current = self._tabs.currentIndex()
        if current >= 0:
            self._close_tab(current)

    def _switch_to_tab_number(self, tab_number: int) -> None:
        index = tab_number - 1
        if 0 <= index < self._tabs.count():
            self._tabs.setCurrentIndex(index)

    def _next_tab(self) -> None:
        if self._tabs.count() < 2:
            return
        self._tabs.setCurrentIndex((self._tabs.currentIndex() + 1) % self._tabs.count())

    def _previous_tab(self) -> None:
        if self._tabs.count() < 2:
            return
        self._tabs.setCurrentIndex((self._tabs.currentIndex() - 1) % self._tabs.count())

    def _reopen_last_closed_tab(self) -> None:
        if not self._closed_tabs:
            return
        state = self._closed_tabs.pop()
        if state.tab_id in self._tab_states:
            state.tab_id = str(uuid4())
        self._add_tab_with_state(state, set_current=True)
        self._save_if_needed()

    def _save_tab_states(self) -> None:
        if not self._connection_id:
            return
        states: list[dict[str, object]] = []
        for i in range(self._tabs.count()):
            editor = self._tabs.widget(i)
            if not isinstance(editor, CodeEditor):
                continue
            tab_id = editor.property("tab_id")
            if not isinstance(tab_id, str):
                continue
            state = self._tab_states.get(tab_id)
            if state is None:
                continue
            state.sql = editor.toPlainText()
            states.append(
                {
                    "tab_id": state.tab_id,
                    "title": state.title,
                    "sql": state.sql,
                    "pinned": state.pinned,
                    "last_query": state.last_query,
                }
            )
        settings = QSettings()
        settings.setValue(f"tabs/{self._connection_id}", json.dumps(states))
        active_tab_id = self._active_tab_id_or_none()
        if active_tab_id:
            settings.setValue(f"tabs/{self._connection_id}/active", active_tab_id)

    def save_tab_states(self) -> None:
        self._save_tab_states()

    def restore_tabs(self, connection_id: str) -> None:
        self._connection_id = connection_id
        settings = QSettings()
        payload = settings.value(f"tabs/{connection_id}", "")
        active_tab_id = settings.value(f"tabs/{connection_id}/active", "")
        restored_states: list[TabState] = []
        if isinstance(payload, str) and payload:
            try:
                data = json.loads(payload)
                if isinstance(data, list):
                    for item in data:
                        if not isinstance(item, dict):
                            continue
                        tab_id = item.get("tab_id")
                        title = item.get("title")
                        sql = item.get("sql", "")
                        pinned = item.get("pinned", False)
                        if not isinstance(tab_id, str) or not isinstance(title, str):
                            continue
                        if not isinstance(sql, str):
                            sql = ""
                        restored_states.append(
                            TabState(
                                tab_id=tab_id,
                                title=self._normalize_title(title),
                                sql=sql,
                                pinned=bool(pinned),
                                last_query=item.get("last_query"),
                            )
                        )
            except (json.JSONDecodeError, TypeError, ValueError):
                restored_states = []

        self._restoring_tabs = True
        try:
            while self._tabs.count():
                editor = self._tabs.widget(0)
                old_tab_id = editor.property("tab_id") if editor is not None else None
                if isinstance(old_tab_id, str):
                    self.tab_closed.emit(old_tab_id)
                self._tabs.removeTab(0)
            self._tab_states.clear()
            if restored_states:
                for state in restored_states:
                    self._tab_states[state.tab_id] = state
                    self._add_tab_with_state(state, set_current=False)
                    self._sync_query_counter(state.title)
                if isinstance(active_tab_id, str) and active_tab_id:
                    for i in range(self._tabs.count()):
                        editor = self._tabs.widget(i)
                        if editor is not None and editor.property("tab_id") == active_tab_id:
                            self._tabs.setCurrentIndex(i)
                            break
                    else:
                        self._tabs.setCurrentIndex(0)
                else:
                    self._tabs.setCurrentIndex(0)
            else:
                self._new_tab(title="Query 1")
        finally:
            self._restoring_tabs = False

    def _sync_query_counter(self, title: str) -> None:
        normalized = self._normalize_title(title)
        match = re.match(r"^Query\s+(\d+)$", normalized)
        if match:
            num = int(match.group(1))
            self._next_query_number = max(self._next_query_number, num + 1)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if isinstance(event, QKeyEvent) and event.type() == QEvent.Type.KeyPress:
            mods = event.modifiers()
            if mods == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Return:
                self._on_run()
                return True
            if mods == (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
            ) and event.key() == Qt.Key.Key_Return:
                self._on_run_selection()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        mods = event.modifiers()
        if mods == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Return:
            self._on_run()
            event.accept()
            return
        if mods == (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ) and event.key() == Qt.Key.Key_Return:
            self._on_run_selection()
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_run(self) -> None:
        sql = self.current_sql()
        if sql.strip():
            tab_id = self.active_tab_id()
            state = self._tab_states.get(tab_id)
            if state is not None:
                state.last_query = sql
                self._apply_tab_visual_state(tab_id)
            self._set_running_state(True)
            self.query_submitted.emit(sql)

    def _on_run_selection(self) -> None:
        editor = self.current_editor()
        if editor is None:
            return

        cursor = editor.textCursor()
        if cursor.hasSelection():
            sql = cursor.selectedText()
        else:
            sql = self._find_statement_at_cursor(
                editor.toPlainText(), cursor.position()
            )

        if sql.strip():
            tab_id = self.active_tab_id()
            state = self._tab_states.get(tab_id)
            if state is not None:
                state.last_query = sql
                self._apply_tab_visual_state(tab_id)
            self._set_running_state(True)
            self.query_submitted.emit(sql)

    def _on_explain(self) -> None:
        sql = self.current_sql()
        if sql.strip():
            tab_id = self.active_tab_id()
            state = self._tab_states.get(tab_id)
            if state is not None:
                state.last_query = sql
                self._apply_tab_visual_state(tab_id)
            self._set_running_state(True)
            self.query_submitted.emit(f"EXPLAIN {sql}")

    def _on_format(self) -> None:
        editor = self.current_editor()
        if editor is None:
            return

        sql = editor.toPlainText()
        if sql.strip():
            formatted = sqlparse.format(sql, reindent=True, keyword_case="upper")
            cursor = editor.textCursor()
            cursor_position = cursor.position()
            editor.setPlainText(formatted)
            if cursor_position <= len(formatted):
                cursor.setPosition(cursor_position)
                editor.setTextCursor(cursor)

    def _find_statement_at_cursor(self, text: str, cursor_position: int) -> str:
        statements = sqlparse.split(text)
        pos = 0
        for stmt in statements:
            stripped = stmt.strip()
            if not stripped:
                continue
            idx = text.find(stripped, pos)
            if idx == -1:
                continue
            start = idx
            end = idx + len(stripped)
            if start <= cursor_position <= end:
                return stripped
            pos = end
        return text.strip()

    def set_driver(self, driver) -> None:
        self._driver = driver
        if driver and getattr(driver, "config", None):
            self._connection_label.setText(driver.config.name or "Connected")
        else:
            self._connection_label.setText("Disconnected")

    def set_query_complete(self) -> None:
        self._set_running_state(False)

    def set_query_info(self, info: str) -> None:
        self._info_label.setText(info)

    def _set_running_state(self, running: bool) -> None:
        self._query_running = running
        self._run_btn.setEnabled(not running)
        self._run_sel_btn.setEnabled(not running)
        self._fmt_btn.setEnabled(not running)
        self._explain_btn.setEnabled(not running)
        if running:
            self._spinner_index = 0
            self._spinner_label.setText("Running")
            self._spinner_timer.start()
        else:
            self._spinner_timer.stop()
            self._spinner_label.setText("")

    def current_editor(self) -> CodeEditor | None:
        widget = self._tabs.currentWidget()
        if isinstance(widget, CodeEditor):
            return widget
        return None

    def current_sql(self) -> str:
        editor = self.current_editor()
        if editor is None:
            return ""
        return editor.toPlainText()

    def refresh_theme(self) -> None:
        """Refresh runtime-painted editor colors after theme toggle."""
        for i in range(self._tabs.count()):
            widget = self._tabs.widget(i)
            if isinstance(widget, CodeEditor):
                widget.refresh_theme()

    def active_tab_id(self) -> str:
        widget = self._tabs.currentWidget()
        if widget is not None:
            tab_id = widget.property("tab_id")
            if isinstance(tab_id, str):
                return tab_id
        return ""

