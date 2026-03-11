"""MainWindow — Core application window with three-panel layout."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QStatusBar,
    QWidget,
)

from tablefree.widgets.editor import EditorPanel
from tablefree.widgets.result_view import ResultView
from tablefree.widgets.sidebar import Sidebar

_ROOT = Path(__file__).resolve().parent.parent
_RESOURCES = _ROOT / "resources"


class MainWindow(QMainWindow):
    """Three-panel main window: sidebar | editor / results."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_dark = True  # start with dark theme
        self._setup_window()
        self._setup_menu_bar()
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
        edit_menu.addAction(undo)

        redo = QAction("Redo", self)
        redo.setShortcut("Ctrl+Shift+Z")
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

    # ── Layout ───────────────────────────────────────────────

    def _setup_layout(self) -> None:
        # Sidebar (left)
        self._sidebar = Sidebar()
        self._sidebar.setMinimumWidth(200)

        # Editor (center-top)
        self._editor = EditorPanel()

        # Result view (center-bottom)
        self._result_view = ResultView()
        self._result_view.setMinimumHeight(100)

        # Vertical splitter: editor on top, results on bottom
        self._v_splitter = QSplitter(Qt.Orientation.Vertical)
        self._v_splitter.addWidget(self._editor)
        self._v_splitter.addWidget(self._result_view)
        self._v_splitter.setSizes([450, 250])
        self._v_splitter.setChildrenCollapsible(False)

        # Horizontal splitter: sidebar on left, vertical splitter on right
        self._h_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._h_splitter.addWidget(self._sidebar)
        self._h_splitter.addWidget(self._v_splitter)
        self._h_splitter.setSizes([260, 940])
        self._h_splitter.setChildrenCollapsible(False)

        self.setCentralWidget(self._h_splitter)

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
