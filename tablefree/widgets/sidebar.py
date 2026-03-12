"""Sidebar widget — Schema browser with search and tree structure."""

from PySide6.QtCore import Qt, Signal, QThreadPool

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tablefree.db.driver import DatabaseDriver
from tablefree.workers.query_worker import QueryWorker

_ICON_SCHEMA = "📁"
_ICON_TABLE = "📋"
_ICON_COLUMN = "📄"


class Sidebar(QWidget):
    """Left panel: schema tree browser with search filter."""

    table_selected = Signal(str, str)
    table_double_clicked = Signal(str, str)
    structure_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._driver: DatabaseDriver | None = None
        self._thread_pool: QThreadPool | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("sidebar-header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 10)

        title = QLabel("Schema Browser")
        title.setObjectName("sidebar-title")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self._badge = QLabel("● Disconnected")
        self._badge.setObjectName("connection-badge-inactive")
        header_layout.addWidget(self._badge)

        self._refresh_btn = QPushButton("⟳")
        self._refresh_btn.setObjectName("sidebar-refresh")
        self._refresh_btn.setToolTip("Refresh schema")
        self._refresh_btn.setFixedSize(24, 24)
        self._refresh_btn.setVisible(False)
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)
        header_layout.addWidget(self._refresh_btn)

        layout.addWidget(header)

        search_container = QWidget()
        search_container.setObjectName("search-container")
        search_layout = QVBoxLayout(search_container)
        search_layout.setContentsMargins(8, 6, 8, 6)

        self._search = QLineEdit()
        self._search.setObjectName("sidebar-search")
        self._search.setPlaceholderText("🔍  Filter objects…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self._search)

        layout.addWidget(search_container)

        sep = QFrame()
        sep.setObjectName("sidebar-separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        self._tree = QTreeWidget()
        self._tree.setObjectName("schema-tree")
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._tree.setAnimated(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tree.itemExpanded.connect(self._on_item_expanded)

        layout.addWidget(self._tree, stretch=1)

        self._footer = QLabel("Connect to a database to browse schema")
        self._footer.setObjectName("sidebar-footer")
        self._footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._footer.setWordWrap(True)
        layout.addWidget(self._footer)

    def set_driver(self, driver: DatabaseDriver) -> None:
        """Populate the tree with schema/table data from the driver."""
        self._driver = driver
        self._thread_pool = None
        if hasattr(driver._connection, "thread_pool"):
            self._thread_pool = driver._connection.thread_pool
        if self._thread_pool is None:
            self._thread_pool = QThreadPool.globalInstance()

        self._tree.clear()
        self._badge.setText("● Connected")
        self._badge.setObjectName("connection-badge-active")
        self._badge.style().unpolish(self._badge)
        self._badge.style().polish(self._badge)
        self._refresh_btn.setVisible(True)
        self._footer.setVisible(False)

        self._load_schemas()

    def _load_schemas(self) -> None:
        if not self._driver:
            return

        worker = QueryWorker(self._driver.get_schemas)
        worker.signals.finished.connect(self._on_schemas_loaded)
        worker.signals.error.connect(self._on_load_error)
        self._thread_pool.start(worker)

    def _on_schemas_loaded(self, schemas: list[str]) -> None:
        for schema in schemas:
            schema_item = QTreeWidgetItem(self._tree, [f"{_ICON_SCHEMA}  {schema}"])
            schema_item.setData(
                0, Qt.ItemDataRole.UserRole, {"type": "schema", "schema": schema}
            )
            schema_item.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
            )
            self._tree.addTopLevelItem(schema_item)

    def _load_tables_for_schema(self, schema_item: QTreeWidgetItem) -> None:
        schema_data = schema_item.data(0, Qt.ItemDataRole.UserRole)
        schema = schema_data["schema"]

        while schema_item.childCount() > 0:
            schema_item.removeChild(schema_item.child(0))

        worker = QueryWorker(self._driver.get_tables, schema)
        worker.signals.finished.connect(
            lambda tables: self._on_tables_loaded(schema_item, tables)
        )
        worker.signals.error.connect(self._on_load_error)
        self._thread_pool.start(worker)

    def _on_tables_loaded(
        self, schema_item: QTreeWidgetItem, tables: list[str]
    ) -> None:
        for table in tables:
            table_item = QTreeWidgetItem(schema_item, [f"{_ICON_TABLE}  {table}"])
            table_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {
                    "type": "table",
                    "schema": schema_item.data(0, Qt.ItemDataRole.UserRole)["schema"],
                    "table": table,
                },
            )
            table_item.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
            )
            schema_item.addChild(table_item)
        schema_item.setExpanded(True)

    def _load_columns_for_table(self, table_item: QTreeWidgetItem) -> None:
        table_data = table_item.data(0, Qt.ItemDataRole.UserRole)
        schema = table_data["schema"]
        table = table_data["table"]

        while table_item.childCount() > 0:
            table_item.removeChild(table_item.child(0))

        worker = QueryWorker(self._driver.get_columns, table, schema)
        worker.signals.finished.connect(
            lambda cols: self._on_columns_loaded(table_item, cols)
        )
        worker.signals.error.connect(self._on_load_error)
        self._thread_pool.start(worker)

    def _on_columns_loaded(self, table_item: QTreeWidgetItem, columns: list) -> None:
        for col in columns:
            col_item = QTreeWidgetItem(
                table_item, [f"{_ICON_COLUMN}  {col.name} ({col.data_type})"]
            )
            col_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {
                    "type": "column",
                    "schema": table_item.data(0, Qt.ItemDataRole.UserRole)["schema"],
                    "table": table_item.data(0, Qt.ItemDataRole.UserRole)["table"],
                    "column": col.name,
                },
            )
            table_item.addChild(col_item)
        table_item.setExpanded(True)

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        if data["type"] == "schema" and item.childCount() == 0:
            self._load_tables_for_schema(item)
        elif data["type"] == "table" and item.childCount() == 0:
            self._load_columns_for_table(item)

    def _on_load_error(self, error: Exception) -> None:
        print(f"Error loading schema: {error}")

    def clear(self) -> None:
        """Reset the sidebar to disconnected state."""
        self._driver = None
        self._tree.clear()
        self._badge.setText("● Disconnected")
        self._badge.setObjectName("connection-badge-inactive")
        self._badge.style().unpolish(self._badge)
        self._badge.style().polish(self._badge)
        self._refresh_btn.setVisible(False)
        self._footer.setVisible(True)

    def _on_search_changed(self, text: str) -> None:
        text = text.lower()
        for i in range(self._tree.topLevelItemCount()):
            schema_item = self._tree.topLevelItem(i)
            if schema_item:
                self._filter_tree_item(schema_item, text)

    def _filter_tree_item(self, item: QTreeWidgetItem, text: str) -> bool:
        item_text = item.text(0).lower()
        match = text in item_text

        child_match = False
        for i in range(item.childCount()):
            child = item.child(i)
            if child and self._filter_tree_item(child, text):
                child_match = True

        item.setHidden(not match and not child_match)

        if child_match and item.parent():
            item.parent().setExpanded(True)

        return match or child_match

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data["type"] == "table":
            self.table_selected.emit(data["schema"], data["table"])

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data["type"] == "table":
            self.table_double_clicked.emit(data["schema"], data["table"])

    def _on_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if not item:
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data["type"] != "table":
            return

        menu = QMenu(self)

        open_action = QAction("Open Table", self)
        open_action.triggered.connect(
            lambda: self.table_double_clicked.emit(data["schema"], data["table"])
        )
        menu.addAction(open_action)

        structure_action = QAction("View Structure", self)
        structure_action.triggered.connect(
            lambda: self.structure_requested.emit(data["schema"], data["table"])
        )
        menu.addAction(structure_action)

        menu.addSeparator()

        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(lambda: self._refresh_schema(data["schema"]))
        menu.addAction(refresh_action)

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _refresh_schema(self, schema: str) -> None:
        for i in range(self._tree.topLevelItemCount()):
            schema_item = self._tree.topLevelItem(i)
            if (
                schema_item
                and schema_item.data(0, Qt.ItemDataRole.UserRole)["schema"] == schema
            ):
                self._load_tables_for_schema(schema_item)
                return

    def _on_refresh_clicked(self) -> None:
        if self._driver:
            self.set_driver(self._driver)
