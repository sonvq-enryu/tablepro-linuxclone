"""Editor panel widget — Tabbed query editor with toolbar."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class EditorPanel(QWidget):
    """Center panel: tabbed SQL query editor with action toolbar."""

    _tab_counter: int = 1

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("editor-panel")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Toolbar ──────────────────────────────────────────
        toolbar = QWidget()
        toolbar.setObjectName("editor-toolbar")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(8, 4, 8, 4)
        tb_layout.setSpacing(6)

        # Run button
        run_btn = QPushButton("▶  Run")
        run_btn.setObjectName("toolbar-btn-primary")
        run_btn.setToolTip("Execute query (Ctrl+Enter)")
        run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        tb_layout.addWidget(run_btn)

        # Run selection button
        run_sel_btn = QPushButton("▶▶  Run Selection")
        run_sel_btn.setObjectName("toolbar-btn")
        run_sel_btn.setToolTip("Execute selected text")
        run_sel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        tb_layout.addWidget(run_sel_btn)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setObjectName("toolbar-separator")
        sep.setFixedHeight(20)
        tb_layout.addWidget(sep)

        # Format button
        fmt_btn = QPushButton("✨  Format")
        fmt_btn.setObjectName("toolbar-btn")
        fmt_btn.setToolTip("Beautify SQL")
        fmt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        tb_layout.addWidget(fmt_btn)

        tb_layout.addStretch()

        # Timer / row count label
        self._info_label = QLabel("")
        self._info_label.setObjectName("editor-info")
        tb_layout.addWidget(self._info_label)

        layout.addWidget(toolbar)

        # ── Separator ────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("editor-separator")
        line.setFixedHeight(1)
        layout.addWidget(line)

        # ── Tab widget ───────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setObjectName("editor-tabs")
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.setDocumentMode(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)

        # "+" button to add new tabs
        add_tab_btn = QPushButton(" + ")
        add_tab_btn.setObjectName("add-tab-btn")
        add_tab_btn.setToolTip("New query tab")
        add_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_tab_btn.setFixedSize(28, 28)
        add_tab_btn.clicked.connect(self._new_tab)
        self._tabs.setCornerWidget(add_tab_btn, Qt.Corner.TopRightCorner)

        # Start with one default tab
        self._add_tab("Query 1")
        layout.addWidget(self._tabs, stretch=1)

    def _add_tab(self, title: str) -> None:
        editor = QPlainTextEdit()
        editor.setObjectName("sql-editor")
        editor.setPlaceholderText(
            "-- Write your SQL queries here…\n"
            "-- Press Ctrl+Enter to execute\n\n"
            "SELECT * FROM users LIMIT 100;"
        )
        editor.setTabStopDistance(32.0)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._tabs.addTab(editor, title)
        self._tabs.setCurrentWidget(editor)

    def _new_tab(self) -> None:
        self._tab_counter += 1
        self._add_tab(f"Query {self._tab_counter}")

    def _close_tab(self, index: int) -> None:
        if self._tabs.count() > 1:
            self._tabs.removeTab(index)
