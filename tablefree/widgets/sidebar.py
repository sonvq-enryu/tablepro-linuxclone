"""Sidebar widget — Database navigator with tree structure."""

from PySide6.QtCore import Qt, Signal, QThreadPool, QObject, QRect
from PySide6.QtGui import QAction, QPainter, QFont, QPen, QBrush, QFontMetrics
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QStyledItemDelegate,
    QStyle,
)

from tablefree.db.connection_store import ConnectionStore
from tablefree.db.driver import DatabaseDriver
from tablefree.theme import current
from tablefree.workers.query_worker import QueryWorker


class _SlotHelper(QObject):
    """Helper to cleanly pass context arguments to a slot on the main thread.

    Lambdas without a QObject context execute in the emitting thread (background),
    which crashes when updating the GUI. This helper ensures a QueuedConnection
    is used, safely marshaling the call back to the main thread.
    """

    def __init__(self, parent: QObject, callback, *args, **kwargs) -> None:
        super().__init__(parent)
        self.callback = callback
        self.args = args
        self.kwargs = kwargs

    def on_finished(self, result: object) -> None:
        try:
            self.callback(*self.args, result, **self.kwargs)
        finally:
            self.deleteLater()

    def on_error(self, error: Exception) -> None:
        try:
            self.callback(*self.args, error, **self.kwargs)
        finally:
            self.deleteLater()


class SidebarDelegate(QStyledItemDelegate):
    """Render tree items with custom chevrons, icons, and metadata badges."""

    _ICON_MAP = {
        "schema": "◈",
        "category": "▤",
        "table": "▦",
        "column": "•",
        "loading": "◌",
        "error": "!",
    }
    _MIN_COLUMN_NAME_WIDTH = 120

    def _draw_badges(self, painter: QPainter, rect: QRect, badges: list[tuple[str, object, object]], base_font: QFont) -> int:
        """Draw right-aligned rounded badges and return consumed width."""
        if not badges:
            return 0

        badge_font = QFont(base_font)
        badge_font.setPointSize(max(8, base_font.pointSize() - 2))
        painter.setFont(badge_font)
        fm = QFontMetrics(badge_font)
        x = rect.right() - 8
        consumed = 0

        for text, bg, fg in badges:
            width = min(fm.horizontalAdvance(text) + 12, 120)
            height = fm.height() + 4
            x -= width
            badge_rect = QRect(x, rect.top() + (rect.height() - height) // 2, width, height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bg))
            painter.drawRoundedRect(badge_rect, 4, 4)
            painter.setPen(QPen(fg))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)
            x -= 6
            consumed += width + 6

        painter.setFont(base_font)
        return consumed

    def _column_badges(
        self, data: dict, is_pk: bool, available_width: int, base_font: QFont
    ) -> list[tuple[str, object, object]]:
        """Build metadata badges while preserving room for the column name."""
        colors = current()
        badges: list[tuple[str, object, object]] = []
        if is_pk:
            badges.append(("PK", colors.sidebar_pk, colors.base))

        data_type = str(data.get("data_type", "unknown"))
        if len(data_type) > 20:
            data_type = f"{data_type[:17]}..."

        # Keep metadata secondary: only render type when row has enough room.
        badge_font = QFont(base_font)
        badge_font.setPointSize(max(8, base_font.pointSize() - 2))
        fm = QFontMetrics(badge_font)
        type_width = min(fm.horizontalAdvance(data_type) + 12, 100)
        required_for_name = self._MIN_COLUMN_NAME_WIDTH + type_width + 16
        if available_width >= required_for_name:
            badges.append((data_type, colors.badge_bg, colors.badge_text))

        return badges

    def _node_icon_color(self, node_type: str, is_pk: bool):
        colors = current()
        if node_type == "schema":
            return colors.sidebar_schema
        if node_type == "table":
            return colors.sidebar_table
        if node_type == "column" and is_pk:
            return colors.sidebar_pk
        if node_type == "column":
            return colors.sidebar_column
        if node_type == "loading":
            return colors.sidebar_loading
        if node_type == "error":
            return colors.error
        return colors.muted

    def paint(self, painter: QPainter, option, index) -> None:
        colors = current()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if is_selected:
            painter.fillRect(option.rect, colors.selected_bg)
        text_pen = QPen(colors.selected_text if is_selected else colors.item_text)

        data = index.data(Qt.ItemDataRole.UserRole) or {}
        node_type = data.get("type", "")
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        rect = option.rect
        font = option.font
        if node_type in ("schema", "table"):
            font.setBold(True)
        if node_type == "loading":
            font.setItalic(True)
            text_pen = QPen(colors.sidebar_loading)
        if node_type == "error":
            text_pen = QPen(colors.error)
        painter.setFont(font)

        # Draw expand/collapse chevron for expandable item types.
        x = rect.left() + 6
        if node_type in ("schema", "category", "table"):
            view = option.widget
            if view and hasattr(view, "isExpanded"):
                chevron = "▾" if view.isExpanded(index) else "▸"
                painter.setPen(QPen(colors.muted))
                chevron_rect = QRect(x, rect.top(), 12, rect.height())
                painter.drawText(chevron_rect, Qt.AlignmentFlag.AlignCenter, chevron)
            x += 14

        # Draw node icon.
        is_pk = bool(data.get("is_pk"))
        icon = "◆" if node_type == "column" and is_pk else self._ICON_MAP.get(node_type, "•")
        painter.setPen(QPen(self._node_icon_color(node_type, is_pk)))
        icon_rect = QRect(x, rect.top(), 14, rect.height())
        painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, icon)
        x += 16

        badges: list[tuple[str, object, object]] = []
        if node_type == "column":
            available_width = rect.width() - (x - rect.left()) - 8
            badges = self._column_badges(data, is_pk, available_width, font)

        consumed = self._draw_badges(painter, rect, badges, font)
        text_rect = QRect(x, rect.top(), max(20, rect.width() - (x - rect.left()) - consumed - 4), rect.height())
        painter.setPen(text_pen)
        fm = QFontMetrics(font)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            fm.elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width()),
        )
        painter.restore()

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(32)
        return size


class Sidebar(QWidget):
    """Left panel: database navigator with connection dropdown and schema tree."""

    table_selected = Signal(str, str)
    table_double_clicked = Signal(str, str)
    structure_requested = Signal(str, str)
    connection_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._driver: DatabaseDriver | None = None
        self._thread_pool: QThreadPool | None = None
        self._store = ConnectionStore()
        self._combo_updating = False
        self._last_error_message = ""
        self._load_epoch = 0
        self._setup_ui()
        self._refresh_connection_combo()

    def _setup_ui(self) -> None:
        self.setObjectName("sidebar-panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header
        header = QWidget()
        header.setObjectName("sidebar-header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 8, 8)

        title = QLabel("Database Navigator")
        title.setObjectName("sidebar-title")
        header_layout.addWidget(title)

        self._connection_status = QLabel()
        self._connection_status.setObjectName("sidebar-connection-status")
        self._connection_status.setFixedSize(8, 8)
        self._connection_status.setToolTip("Disconnected")
        header_layout.addWidget(self._connection_status)
        header_layout.addStretch()

        self._menu_btn = QPushButton("⋮")
        self._menu_btn.setObjectName("sidebar-icon-btn")
        self._menu_btn.setToolTip("Options")
        self._menu_btn.setFixedSize(28, 28)
        self._menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._menu_btn.clicked.connect(self._on_options_clicked)
        header_layout.addWidget(self._menu_btn)

        self._refresh_btn = QPushButton("↻")
        self._refresh_btn.setObjectName("sidebar-icon-btn")
        self._refresh_btn.setToolTip("Refresh schema")
        self._refresh_btn.setFixedSize(28, 28)
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.setVisible(False)
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)
        header_layout.addWidget(self._refresh_btn)

        layout.addWidget(header)

        # ── Connection Dropdown
        conn_container = QWidget()
        conn_container.setObjectName("search-container")
        conn_layout = QVBoxLayout(conn_container)
        conn_layout.setContentsMargins(8, 4, 8, 4)
        conn_layout.setSpacing(4)

        self._conn_combo = QComboBox()
        self._conn_combo.setObjectName("connection-combo")
        self._conn_combo.currentIndexChanged.connect(self._on_connection_combo_changed)
        conn_layout.addWidget(self._conn_combo)

        layout.addWidget(conn_container)

        # ── Search
        search_container = QWidget()
        search_container.setObjectName("search-container")
        search_layout = QVBoxLayout(search_container)
        search_layout.setContentsMargins(8, 4, 8, 6)

        self._search = QLineEdit()
        self._search.setObjectName("sidebar-search")
        self._search.setPlaceholderText("Filter tables...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self._search)

        layout.addWidget(search_container)

        sep = QFrame()
        sep.setObjectName("sidebar-separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        # ── Tree
        self._tree = QTreeWidget()
        self._tree.setObjectName("schema-tree")
        self._tree.setHeaderHidden(True)
        self._tree.setItemDelegate(SidebarDelegate(self._tree))
        self._tree.setIndentation(16)
        self._tree.setAnimated(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tree.itemExpanded.connect(self._on_item_expanded)

        layout.addWidget(self._tree, stretch=1)

        # ── Footer
        self._footer = QLabel("Connect to a database to browse schema")
        self._footer.setObjectName("sidebar-footer")
        self._footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._footer.setWordWrap(True)
        layout.addWidget(self._footer)
        self._update_connection_status(False)

    def set_driver(self, driver: DatabaseDriver) -> None:
        """Populate the tree with schema/table data from the driver."""
        self._driver = driver
        self._load_epoch += 1
        self._thread_pool = None
        if hasattr(driver, "_connection") and driver._connection:
            if hasattr(driver._connection, "thread_pool"):
                self._thread_pool = driver._connection.thread_pool
        if self._thread_pool is None:
            self._thread_pool = QThreadPool.globalInstance()

        self._tree.clear()

        # Update connection dropdown
        conn_name = driver.config.name or "Unnamed"
        driver_type = type(driver).__name__.replace("Driver", "")
        display_name = f"{conn_name} ({driver_type})"

        self._refresh_connection_combo(active_label=display_name)

        self._refresh_btn.setVisible(True)
        self._footer.setVisible(False)
        self._update_connection_status(True)

        self._load_schemas()

    def _load_schemas(self) -> None:
        if not self._driver:
            return

        self._tree.clear()
        loading_item = QTreeWidgetItem(self._tree)
        loading_item.setText(0, "Loading schemas...")
        loading_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "loading"})
        epoch = self._load_epoch
        worker = QueryWorker(self._driver.get_schemas)
        done_helper = _SlotHelper(self, self._on_schemas_loaded, epoch)
        worker.signals.finished.connect(done_helper.on_finished)
        err_helper = _SlotHelper(self, self._on_root_load_error, epoch)
        worker.signals.error.connect(err_helper.on_error)
        self._thread_pool.start(worker)

    def _on_schemas_loaded(self, epoch: int, schemas: list[str]) -> None:
        if epoch != self._load_epoch:
            return
        self._tree.clear()
        for schema in schemas:
            schema_item = QTreeWidgetItem(self._tree)
            schema_item.setText(0, f"{schema}")
            schema_item.setData(
                0, Qt.ItemDataRole.UserRole, {"type": "schema", "schema": schema}
            )

            tables_node = QTreeWidgetItem(schema_item)
            tables_node.setText(0, "Tables")
            tables_node.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {"type": "category", "category": "tables", "schema": schema},
            )
            tables_node.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
            )
            schema_item.addChild(tables_node)

            self._tree.addTopLevelItem(schema_item)
            schema_item.setExpanded(True)

    def _load_tables_for_category(self, category_item: QTreeWidgetItem) -> None:
        data = category_item.data(0, Qt.ItemDataRole.UserRole)
        schema = data["schema"]

        self._set_loading_child(category_item, "Loading tables...")

        epoch = self._load_epoch
        worker = QueryWorker(self._driver.get_tables, schema)
        helper = _SlotHelper(self, self._on_tables_loaded, epoch, schema=schema)
        worker.signals.finished.connect(helper.on_finished)
        err_helper = _SlotHelper(
            self, self._on_item_load_error, epoch, schema=schema, category="tables"
        )
        worker.signals.error.connect(err_helper.on_error)
        self._thread_pool.start(worker)

    def _on_tables_loaded(self, epoch: int, tables: list[str], schema: str) -> None:
        if epoch != self._load_epoch:
            return
        category_item = self._find_category_item(schema, "tables")
        if category_item is None:
            return
        self._clear_children(category_item)
        for table in tables:
            table_item = QTreeWidgetItem(category_item)
            table_item.setText(0, table)
            table_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {"type": "table", "schema": schema, "table": table},
            )
            table_item.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
            )
            category_item.addChild(table_item)

        category_item.setText(0, f"Tables ({len(tables)})")
        category_item.setExpanded(True)

    def _load_columns_for_table(self, table_item: QTreeWidgetItem) -> None:
        table_data = table_item.data(0, Qt.ItemDataRole.UserRole)
        schema = table_data["schema"]
        table = table_data["table"]

        self._set_loading_child(table_item, "Loading columns...")

        epoch = self._load_epoch
        worker = QueryWorker(self._get_table_metadata, table, schema)
        helper = _SlotHelper(
            self, self._on_columns_loaded, epoch, schema=schema, table=table
        )
        worker.signals.finished.connect(helper.on_finished)
        err_helper = _SlotHelper(
            self, self._on_item_load_error, epoch, schema=schema, table=table
        )
        worker.signals.error.connect(err_helper.on_error)
        self._thread_pool.start(worker)

    def _get_table_metadata(self, table: str, schema: str) -> tuple[list, set[str]]:
        """Fetch columns and PK metadata in one worker task."""
        columns = self._driver.get_columns(table, schema)
        indexes = self._driver.get_indexes(table, schema)
        pk_columns: set[str] = set()
        for idx in indexes:
            if idx.is_primary:
                pk_columns.update(idx.columns)
        return columns, pk_columns

    def _on_columns_loaded(
        self, epoch: int, metadata: tuple[list, set[str]], schema: str, table: str
    ) -> None:
        if epoch != self._load_epoch:
            return
        table_item = self._find_table_item(schema, table)
        if table_item is None:
            return
        self._clear_children(table_item)
        columns, pk_columns = metadata
        table_data = table_item.data(0, Qt.ItemDataRole.UserRole) or {}
        for col in columns:
            col_item = QTreeWidgetItem(table_item)
            col_item.setText(0, col.name)
            col_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {
                    "type": "column",
                    "schema": table_data.get("schema", ""),
                    "table": table_data.get("table", ""),
                    "column": col.name,
                    "data_type": col.data_type,
                    "is_nullable": bool(col.is_nullable),
                    "is_pk": col.name in pk_columns,
                },
            )
            table_item.addChild(col_item)
        table_item.setExpanded(True)

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        if (
            data["type"] == "category"
            and data["category"] == "tables"
            and item.childCount() == 0
        ):
            self._load_tables_for_category(item)
        elif data["type"] == "table" and item.childCount() == 0:
            self._load_columns_for_table(item)

    def _on_root_load_error(self, epoch: int, error: Exception) -> None:
        if epoch != self._load_epoch:
            return
        self._tree.clear()
        error_item = QTreeWidgetItem(self._tree)
        error_item.setText(0, "Failed to load schemas")
        error_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "error"})
        error_item.setToolTip(0, str(error))
        self._last_error_message = str(error)

    def _on_item_load_error(
        self,
        epoch: int,
        error: Exception,
        schema: str | None = None,
        category: str | None = None,
        table: str | None = None,
    ) -> None:
        if epoch != self._load_epoch:
            return
        parent_item: QTreeWidgetItem | None = None
        if table and schema:
            parent_item = self._find_table_item(schema, table)
        elif category and schema:
            parent_item = self._find_category_item(schema, category)
        if parent_item is None:
            return
        self._clear_children(parent_item)
        err_item = QTreeWidgetItem(parent_item)
        err_item.setText(0, "Failed to load")
        err_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "error"})
        err_item.setToolTip(0, str(error))
        parent_item.setExpanded(True)
        self._last_error_message = str(error)

    def _set_loading_child(self, parent_item: QTreeWidgetItem, label: str) -> None:
        self._clear_children(parent_item)
        loading = QTreeWidgetItem(parent_item)
        loading.setText(0, label)
        loading.setData(0, Qt.ItemDataRole.UserRole, {"type": "loading"})
        parent_item.setExpanded(True)

    @staticmethod
    def _clear_children(parent_item: QTreeWidgetItem) -> None:
        while parent_item.childCount() > 0:
            parent_item.removeChild(parent_item.child(0))

    def _find_schema_item(self, schema: str) -> QTreeWidgetItem | None:
        for i in range(self._tree.topLevelItemCount()):
            schema_item = self._tree.topLevelItem(i)
            if not schema_item:
                continue
            data = schema_item.data(0, Qt.ItemDataRole.UserRole) or {}
            if data.get("type") == "schema" and data.get("schema") == schema:
                return schema_item
        return None

    def _find_category_item(self, schema: str, category: str) -> QTreeWidgetItem | None:
        schema_item = self._find_schema_item(schema)
        if schema_item is None:
            return None
        for i in range(schema_item.childCount()):
            child = schema_item.child(i)
            data = child.data(0, Qt.ItemDataRole.UserRole) or {}
            if data.get("type") == "category" and data.get("category") == category:
                return child
        return None

    def _find_table_item(self, schema: str, table: str) -> QTreeWidgetItem | None:
        category_item = self._find_category_item(schema, "tables")
        if category_item is None:
            return None
        for i in range(category_item.childCount()):
            child = category_item.child(i)
            data = child.data(0, Qt.ItemDataRole.UserRole) or {}
            if data.get("type") == "table" and data.get("table") == table:
                return child
        return None

    def clear(self) -> None:
        """Reset the sidebar to disconnected state."""
        self._driver = None
        self._load_epoch += 1
        self._tree.clear()
        self._refresh_connection_combo()
        self._refresh_btn.setVisible(False)
        self._footer.setVisible(True)
        self._update_connection_status(False)

    def refresh_connections(self) -> None:
        """Refresh quick-connect dropdown from saved profiles."""
        active_label = None
        if self._driver:
            conn_name = self._driver.config.name or "Unnamed"
            driver_type = type(self._driver).__name__.replace("Driver", "")
            active_label = f"{conn_name} ({driver_type})"
        self._refresh_connection_combo(active_label=active_label)

    def _refresh_connection_combo(self, active_label: str | None = None) -> None:
        profiles = self._store.load_all()
        self._combo_updating = True
        self._conn_combo.clear()

        if active_label:
            self._conn_combo.addItem(f"Connected: {active_label}", None)
        else:
            self._conn_combo.addItem("Quick connect...", None)

        for profile in profiles:
            conn_id = profile.get("id")
            if not conn_id:
                continue
            name = profile.get("name", "Unnamed")
            host = profile.get("host", "localhost")
            port = profile.get("port", "")
            dtype = profile.get("driver_type", "")
            prefix = "PG" if "postgres" in dtype else "MY"
            self._conn_combo.addItem(f"[{prefix}] {name} ({host}:{port})", conn_id)

        self._conn_combo.setCurrentIndex(0)
        self._conn_combo.setEnabled(self._conn_combo.count() > 1 or bool(active_label))
        self._combo_updating = False

    def _on_connection_combo_changed(self, index: int) -> None:
        if self._combo_updating or index <= 0:
            return
        conn_id = self._conn_combo.itemData(index)
        if not conn_id:
            return
        self.connection_requested.emit(conn_id)
        self._combo_updating = True
        self._conn_combo.setCurrentIndex(0)
        self._combo_updating = False

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

        if text:
            if child_match:
                item.setExpanded(True)
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
            if schema_item:
                item_data = schema_item.data(0, Qt.ItemDataRole.UserRole)
                if item_data and item_data.get("schema") == schema:
                    # Find the Tables category and reload
                    for j in range(schema_item.childCount()):
                        child = schema_item.child(j)
                        child_data = child.data(0, Qt.ItemDataRole.UserRole)
                        if (
                            child_data
                            and child_data.get("type") == "category"
                            and child_data.get("category") == "tables"
                        ):
                            self._load_tables_for_category(child)
                            return

    def _on_refresh_clicked(self) -> None:
        if self._driver:
            self.set_driver(self._driver)

    def _on_options_clicked(self) -> None:
        menu = QMenu(self)

        refresh_connections = QAction("Refresh connection list", self)
        refresh_connections.triggered.connect(self.refresh_connections)
        menu.addAction(refresh_connections)

        clear_filter = QAction("Clear filter", self)
        clear_filter.triggered.connect(self._search.clear)
        menu.addAction(clear_filter)

        collapse_all = QAction("Collapse all", self)
        collapse_all.triggered.connect(self._tree.collapseAll)
        menu.addAction(collapse_all)

        menu.exec(self._menu_btn.mapToGlobal(self._menu_btn.rect().bottomLeft()))

    def _update_connection_status(self, connected: bool) -> None:
        self._connection_status.setProperty("connected", connected)
        self._connection_status.setToolTip("Connected" if connected else "Disconnected")
        style = self._connection_status.style()
        style.unpolish(self._connection_status)
        style.polish(self._connection_status)
        self._connection_status.update()

    def refresh_theme(self) -> None:
        """Force repaint for custom delegate-drawn tree rows."""
        self._tree.viewport().update()
