"""MainWindow — Core application window with three-panel layout."""

import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from tablefree.db.manager import ConnectionManager
from tablefree.models import QueryResult
from tablefree.widgets.connection_dialog import ConnectionDialog
from tablefree.widgets.editor import EditorPanel
from tablefree.widgets.result_view import ResultView
from tablefree.widgets.sidebar import Sidebar
from tablefree.workers.query_worker import QueryWorker

_ROOT = Path(__file__).resolve().parent.parent
_RESOURCES = _ROOT / "resources"


class MainWindow(QMainWindow):
    """Three-panel main window: sidebar | editor / results."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_dark = True  # start with dark theme
        self._conn_manager = ConnectionManager()
        self._active_driver = None
        self._current_query = ""
        self._setup_window()
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_layout()
        self._setup_status_bar()
        self._apply_theme()

    # ── Window ───────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowTitle("TableFree")
        self.resize(1200, 800)
        self._center_on_screen()

        icon_path = _RESOURCES / "icons" / "app_icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _center_on_screen(self) -> None:
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2 + geo.x()
            y = (geo.height() - self.height()) // 2 + geo.y()
            self.move(x, y)

    # ── Menu Bar ─────────────────────────────────────────────

    def _setup_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        # File
        file_menu = menu_bar.addMenu("&File")

        new_connection = QAction("New Connection", self)
        new_connection.setShortcut("Ctrl+Shift+N")
        new_connection.setStatusTip("Open connection dialog")
        new_connection.triggered.connect(self._open_connection_dialog)
        file_menu.addAction(new_connection)

        new_query = QAction("New Query Tab", self)
        new_query.setShortcut("Ctrl+N")
        new_query.setStatusTip("Open a new query tab")
        file_menu.addAction(new_query)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Exit the application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit
        edit_menu = menu_bar.addMenu("&Edit")
        undo = QAction("Undo", self)
        undo.setShortcut("Ctrl+Z")
        undo.triggered.connect(self._on_undo)
        edit_menu.addAction(undo)

        redo = QAction("Redo", self)
        redo.setShortcut("Ctrl+Shift+Z")
        redo.triggered.connect(self._on_redo)
        edit_menu.addAction(redo)

        edit_menu.addSeparator()

        cut = QAction("Cut", self)
        cut.setShortcut("Ctrl+X")
        edit_menu.addAction(cut)

        copy = QAction("Copy", self)
        copy.setShortcut("Ctrl+C")
        edit_menu.addAction(copy)

        paste = QAction("Paste", self)
        paste.setShortcut("Ctrl+V")
        edit_menu.addAction(paste)

        edit_menu.addSeparator()

        find = QAction("Find", self)
        find.setShortcut("Ctrl+F")
        edit_menu.addAction(find)

        # View
        view_menu = menu_bar.addMenu("&View")

        toggle_sidebar = QAction("Toggle Sidebar", self)
        toggle_sidebar.setShortcut("Ctrl+B")
        toggle_sidebar.setStatusTip("Show/hide the sidebar")
        toggle_sidebar.triggered.connect(self._toggle_sidebar)
        view_menu.addAction(toggle_sidebar)

        view_menu.addSeparator()

        toggle_theme = QAction("Toggle Theme", self)
        toggle_theme.setShortcut("Ctrl+T")
        toggle_theme.setStatusTip("Switch between dark and light themes")
        toggle_theme.triggered.connect(self._toggle_theme)
        view_menu.addAction(toggle_theme)

        # Help
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("About TableFree", self)
        about_action.setStatusTip("About this application")
        help_menu.addAction(about_action)

    # ── Toolbar ────────────────────────────────────────────────

    def _setup_toolbar(self) -> None:
        self._toolbar_widget = QWidget()
        self._toolbar_widget.setObjectName("main-toolbar")
        tb_layout = QHBoxLayout(self._toolbar_widget)
        tb_layout.setContentsMargins(8, 4, 8, 4)
        tb_layout.setSpacing(4)

        def _make_btn(text: str, tooltip: str = "") -> QPushButton:
            btn = QPushButton(text)
            btn.setObjectName("main-toolbar-btn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if tooltip:
                btn.setToolTip(tooltip)
            return btn

        def _make_sep() -> QFrame:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.VLine)
            sep.setObjectName("main-toolbar-separator")
            sep.setFixedHeight(20)
            return sep

        new_conn_btn = _make_btn("+ New Connection", "Open connection dialog (Ctrl+Shift+N)")
        new_conn_btn.clicked.connect(self._open_connection_dialog)
        tb_layout.addWidget(new_conn_btn)

        new_query_btn = _make_btn("New Query", "New query tab (Ctrl+N)")
        new_query_btn.clicked.connect(self._on_new_query_tab)
        tb_layout.addWidget(new_query_btn)

        tb_layout.addWidget(_make_sep())

        import_btn = _make_btn("Import")
        tb_layout.addWidget(import_btn)

        export_btn = _make_btn("Export")
        tb_layout.addWidget(export_btn)

        tb_layout.addWidget(_make_sep())

        self._commit_btn = _make_btn("Commit", "Commit changes (Ctrl+S)")
        self._commit_btn.setShortcut("Ctrl+S")
        tb_layout.addWidget(self._commit_btn)

        self._rollback_btn = _make_btn("Rollback", "Discard changes")
        tb_layout.addWidget(self._rollback_btn)

        tb_layout.addStretch()

    def _on_new_query_tab(self) -> None:
        self._editor._new_tab()

    # ── Layout ───────────────────────────────────────────────

    def _setup_layout(self) -> None:
        self._sidebar = Sidebar()
        self._sidebar.setMinimumWidth(200)
        self._sidebar.table_selected.connect(self._on_table_selected)
        self._sidebar.structure_requested.connect(self._on_structure_requested)

        self._editor = EditorPanel()
        self._editor.query_submitted.connect(self._execute_query)

        self._result_view = ResultView()
        self._result_view.setMinimumHeight(100)

        # Wire EditorPanel tab changes to ResultView change trackers
        self._editor.tab_changed.connect(self._result_view.switch_tab)
        self._result_view.switch_tab(self._editor.active_tab_id())

        # Wire global toolbar buttons to ResultView actions
        self._commit_btn.clicked.connect(self._result_view._on_commit)
        self._rollback_btn.clicked.connect(self._result_view._on_discard)

        self._v_splitter = QSplitter(Qt.Orientation.Vertical)
        self._v_splitter.addWidget(self._editor)
        self._v_splitter.addWidget(self._result_view)
        self._v_splitter.setSizes([450, 250])
        self._v_splitter.setChildrenCollapsible(False)

        self._h_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._h_splitter.addWidget(self._sidebar)
        self._h_splitter.addWidget(self._v_splitter)
        self._h_splitter.setSizes([260, 940])
        self._h_splitter.setChildrenCollapsible(False)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._toolbar_widget)
        central_layout.addWidget(self._h_splitter, stretch=1)
        self.setCentralWidget(central)

    # ── Status Bar ───────────────────────────────────────────

    def _setup_status_bar(self) -> None:
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        # Left: connection indicator
        self._conn_indicator = QLabel("●  Disconnected")
        self._conn_indicator.setObjectName("status-connection")
        status_bar.addWidget(self._conn_indicator)

        # Spacer
        spacer = QWidget()
        spacer.setFixedWidth(1)
        status_bar.addWidget(spacer, stretch=1)

        # Right: version
        version_label = QLabel("TableFree v0.1.0")
        version_label.setObjectName("status-version")
        status_bar.addPermanentWidget(version_label)

    # ── Sidebar Toggle ───────────────────────────────────────

    def _toggle_sidebar(self) -> None:
        self._sidebar.setVisible(not self._sidebar.isVisible())

    # ── Theming ──────────────────────────────────────────────

    def _toggle_theme(self) -> None:
        self._is_dark = not self._is_dark
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme_file = "dark.qss" if self._is_dark else "light.qss"
        qss_path = _RESOURCES / "styles" / theme_file

        if qss_path.exists():
            stylesheet = qss_path.read_text(encoding="utf-8")
            self.setStyleSheet(stylesheet)
        else:
            self.setStyleSheet("")

    def _open_connection_dialog(self) -> None:
        dialog = ConnectionDialog(self._conn_manager, self)
        if dialog.exec():
            self._active_driver = dialog.active_driver
            if self._active_driver:
                name = self._active_driver.config.name or "Unnamed"
                self._conn_indicator.setText(f"●  Connected to {name}")
                self._conn_indicator.setObjectName("status-connection-active")
                self._conn_indicator.style().unpolish(self._conn_indicator)
                self._conn_indicator.style().polish(self._conn_indicator)
                self._sidebar.set_driver(self._active_driver)
                self._editor.set_driver(self._active_driver)
                self._result_view.set_driver(self._active_driver)

    def _on_undo(self) -> None:
        """Handle undo in result view."""
        # Focus on result view to handle undo there
        self._result_view.setFocus()

    def _on_redo(self) -> None:
        """Handle redo in result view."""
        self._result_view.setFocus()

    def _execute_query(self, sql: str) -> None:
        if not self._active_driver:
            self._result_view.append_message(
                "No active connection. Please connect to a database first."
            )
            self._editor.set_query_complete()
            return

        self._current_query = sql  # Store for result view
        self._editor._info_label.setText("Executing...")
        self._query_start_time = time.perf_counter()

        worker = QueryWorker(self._active_driver.execute, sql)
        worker.signals.finished.connect(self._on_query_finished)
        worker.signals.error.connect(self._on_query_error)

        from PySide6.QtCore import QThreadPool

        QThreadPool.globalInstance().start(worker)

    def _infer_types(self, rows: list[dict], columns: list[str]) -> list[str]:
        """Infer column types from Python types of first non-None values."""
        types = []
        for col in columns:
            for row in rows:
                val = row.get(col)
                if val is not None:
                    if isinstance(val, bool):
                        types.append("boolean")
                    elif isinstance(val, int):
                        types.append("integer")
                    elif isinstance(val, float):
                        types.append("float")
                    else:
                        types.append("text")
                    break
            else:
                types.append("text")
        return types

    def _on_query_finished(self, result: object) -> None:
        elapsed = (time.perf_counter() - self._query_start_time) * 1000
        duration_ms = round(elapsed, 1)

        if isinstance(result, list) and result:
            if isinstance(result[0], dict):
                columns = list(result[0].keys())
                data = [list(r.values()) for r in result]
                col_types = self._infer_types(result, columns)
                query_result = QueryResult(
                    columns=columns,
                    rows=data,
                    column_types=col_types,
                    row_count=len(data),
                    duration_ms=duration_ms,
                    query=self._current_query,
                )
                self._result_view.display_results(query_result)
            else:
                self._result_view.append_message(
                    f"Query executed successfully ({duration_ms} ms, {len(result)} rows returned)"
                )
            self._editor._info_label.setText(f"{len(result)} rows | {duration_ms} ms")
        elif isinstance(result, tuple):
            rows_affected, _ = result
            self._result_view.append_message(
                f"Query executed successfully. {rows_affected} rows affected ({duration_ms} ms)."
            )
            self._editor._info_label.setText(f"{rows_affected} rows | {duration_ms} ms")
        else:
            self._result_view.append_message(
                f"Query executed successfully ({duration_ms} ms)"
            )
            self._editor._info_label.setText(f"{duration_ms} ms")

        self._editor.set_query_complete()

    def _on_query_error(self, error: Exception) -> None:
        elapsed = (time.perf_counter() - self._query_start_time) * 1000
        duration_ms = round(elapsed, 1)
        self._result_view.display_error(str(error))
        self._editor._info_label.setText(f"Error | {duration_ms} ms")
        self._editor.set_query_complete()

    def _on_table_selected(self, schema: str, table: str) -> None:
        if self._active_driver:
            driver_type = type(self._active_driver).__name__.lower()
            if "mysql" in driver_type:
                sql = f"SELECT * FROM `{schema}`.`{table}` LIMIT 1000"
            else:
                sql = f'SELECT * FROM "{schema}"."{table}" LIMIT 1000'
            self._execute_query(sql)

    def _on_structure_requested(self, schema: str, table: str) -> None:
        if self._active_driver:
            self._result_view.show_structure(self._active_driver, table, schema)

    def closeEvent(self, event) -> None:
        self._sidebar.clear()
        self._conn_manager.close_all()
        super().closeEvent(event)
