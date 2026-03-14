"""Editor panel widget — Tabbed query editor with toolbar."""

import sqlparse

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tablefree.widgets.code_editor import CodeEditor


class EditorPanel(QWidget):
    """Center panel: tabbed SQL query editor with action toolbar."""

    _tab_counter: int = 1

    query_submitted = Signal(str)
    tab_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("editor-panel")
        self._driver = None
        self._query_running = False
        self._setup_ui()

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

        tb_layout.addStretch()

        self._info_label = QLabel("")
        self._info_label.setObjectName("editor-info")
        tb_layout.addWidget(self._info_label)

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

        add_tab_btn = QPushButton(" + ")
        add_tab_btn.setObjectName("add-tab-btn")
        add_tab_btn.setToolTip("New query tab")
        add_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_tab_btn.setFixedSize(28, 28)
        add_tab_btn.clicked.connect(self._new_tab)
        self._tabs.setCornerWidget(add_tab_btn, Qt.Corner.TopRightCorner)

        self._add_tab("[Query 1]")
        layout.addWidget(self._tabs, stretch=1)

    def _add_tab(self, title: str) -> None:
        editor = CodeEditor()
        editor.setObjectName("sql-editor")
        editor.setPlaceholderText(
            "-- Write your SQL queries here…\n"
            "-- Press Ctrl+Enter to execute\n\n"
            "SELECT * FROM users LIMIT 100;"
        )
        editor.installEventFilter(self)
        editor.setProperty("tab_id", self._tab_counter)
        self._tabs.addTab(editor, title)
        self._tabs.setCurrentWidget(editor)

    def _new_tab(self) -> None:
        self._tab_counter += 1
        self._add_tab(f"[Query {self._tab_counter}]")

    def _close_tab(self, index: int) -> None:
        if self._tabs.count() > 1:
            self._tabs.removeTab(index)

    def _on_tab_changed(self, index: int) -> None:
        widget = self._tabs.widget(index)
        if widget:
            tab_id = widget.property("tab_id")
            if tab_id is not None:
                self.tab_changed.emit(tab_id)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if isinstance(event, QKeyEvent):
            if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                if event.key() == Qt.Key.Key_Return:
                    self._on_run()
                    return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Return:
                self._on_run()
                event.accept()
                return
            elif event.modifiers() == (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
            ):
                if event.key() == Qt.Key.Key_Return:
                    self._on_run_selection()
                    event.accept()
                    return
        super().keyPressEvent(event)

    def _on_run(self) -> None:
        sql = self.current_sql()
        if sql.strip():
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
            self._set_running_state(True)
            self.query_submitted.emit(sql)

    def _on_explain(self) -> None:
        sql = self.current_sql()
        if sql.strip():
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

    def active_tab_id(self) -> int:
        widget = self._tabs.currentWidget()
        if widget is not None:
            tab_id = widget.property("tab_id")
            if tab_id is not None:
                return tab_id
        return 0

