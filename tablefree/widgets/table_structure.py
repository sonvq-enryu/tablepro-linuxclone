"""Table Structure Viewer Widget."""

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tablefree.db.driver import DatabaseDriver
from tablefree.widgets.code_editor import CodeEditor
from tablefree.workers.query_worker import QueryWorker


class StructureView(QWidget):
    """Structure viewer with four tabs: Columns, Indexes, Foreign Keys, DDL."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._driver: DatabaseDriver | None = None
        self._current_table: str | None = None
        self._current_schema: str | None = None
        self._thread_pool = QThreadPool.globalInstance()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()

        columns_widget = QWidget()
        columns_layout = QVBoxLayout(columns_widget)
        columns_layout.setContentsMargins(0, 0, 0, 0)

        self._columns_table = QTableWidget()
        self._columns_table.setObjectName("structure-columns-table")
        self._columns_table.setAlternatingRowColors(True)
        self._columns_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._columns_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._columns_table.verticalHeader().setDefaultSectionSize(28)
        self._columns_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        columns_layout.addWidget(self._columns_table)

        self._tabs.addTab(columns_widget, "Columns")

        indexes_widget = QWidget()
        indexes_layout = QVBoxLayout(indexes_widget)
        indexes_layout.setContentsMargins(0, 0, 0, 0)

        self._indexes_table = QTableWidget()
        self._indexes_table.setObjectName("structure-indexes-table")
        self._indexes_table.setAlternatingRowColors(True)
        self._indexes_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._indexes_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._indexes_table.verticalHeader().setDefaultSectionSize(28)
        self._indexes_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        indexes_layout.addWidget(self._indexes_table)

        self._tabs.addTab(indexes_widget, "Indexes")

        fk_widget = QWidget()
        fk_layout = QVBoxLayout(fk_widget)
        fk_layout.setContentsMargins(0, 0, 0, 0)

        self._fk_table = QTableWidget()
        self._fk_table.setObjectName("structure-fk-table")
        self._fk_table.setAlternatingRowColors(True)
        self._fk_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._fk_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._fk_table.verticalHeader().setDefaultSectionSize(28)
        self._fk_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        fk_layout.addWidget(self._fk_table)

        self._tabs.addTab(fk_widget, "Foreign Keys")

        ddl_widget = QWidget()
        ddl_layout = QVBoxLayout(ddl_widget)
        ddl_layout.setContentsMargins(0, 0, 0, 0)

        self._ddl_editor = CodeEditor()
        self._ddl_editor.setObjectName("structure-ddl-editor")
        self._ddl_editor.setReadOnly(True)
        ddl_layout.addWidget(self._ddl_editor)

        self._tabs.addTab(ddl_widget, "DDL")

        self._loading_label = QLabel("Loading...")
        self._loading_label.setObjectName("structure-loading")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setVisible(False)

        layout.addWidget(self._tabs)
        layout.addWidget(self._loading_label)

        self._tabs.setCurrentIndex(0)

    def load_structure(
        self, driver: DatabaseDriver, table: str, schema: str | None = None
    ) -> None:
        """Fetch and display all structure metadata for the given table."""
        self._driver = driver
        self._current_table = table
        self._current_schema = schema

        self._show_loading(True)

        columns_worker = QueryWorker(driver.get_columns, table, schema)
        columns_worker.signals.finished.connect(self._on_columns_loaded)
        columns_worker.signals.error.connect(self._on_load_error)
        self._thread_pool.start(columns_worker)

        indexes_worker = QueryWorker(driver.get_indexes, table, schema)
        indexes_worker.signals.finished.connect(self._on_indexes_loaded)
        indexes_worker.signals.error.connect(self._on_load_error)
        self._thread_pool.start(indexes_worker)

        fk_worker = QueryWorker(driver.get_foreign_keys, table, schema)
        fk_worker.signals.finished.connect(self._on_fk_loaded)
        fk_worker.signals.error.connect(self._on_load_error)
        self._thread_pool.start(fk_worker)

        ddl_worker = QueryWorker(driver.get_ddl, table, schema)
        ddl_worker.signals.finished.connect(self._on_ddl_loaded)
        ddl_worker.signals.error.connect(self._on_load_error)
        self._thread_pool.start(ddl_worker)

    def _show_loading(self, show: bool) -> None:
        self._loading_label.setVisible(show)

    def _on_columns_loaded(self, columns: list) -> None:
        self._populate_columns_table(columns)
        self._check_loading_complete()

    def _on_indexes_loaded(self, indexes: list) -> None:
        self._populate_indexes_table(indexes)
        self._check_loading_complete()

    def _on_fk_loaded(self, fks: list) -> None:
        self._populate_fk_table(fks)
        self._check_loading_complete()

    def _on_ddl_loaded(self, ddl: str) -> None:
        self._ddl_editor.setPlainText(ddl)
        self._check_loading_complete()

    def _on_load_error(self, error: Exception) -> None:
        print(f"Error loading structure: {error}")
        self._show_loading(False)

    def _check_loading_complete(self) -> None:
        if self.sender() is None:
            return
        self._show_loading(False)

    def _populate_columns_table(self, columns: list) -> None:
        self._columns_table.setColumnCount(6)
        self._columns_table.setHorizontalHeaderLabels(
            ["Name", "Type", "Nullable", "Default", "Extra", "Key"]
        )
        self._columns_table.setRowCount(len(columns))

        for row, col in enumerate(columns):
            name_item = QTableWidgetItem(col.name)
            type_item = QTableWidgetItem(col.data_type)
            nullable_item = QTableWidgetItem("YES" if col.is_nullable else "NO")
            default_item = QTableWidgetItem(col.column_default or "")
            extra_item = QTableWidgetItem("")

            pk_cols = getattr(col, "is_primary_key", False)
            key_item = QTableWidgetItem("PRI" if pk_cols else "")

            self._columns_table.setItem(row, 0, name_item)
            self._columns_table.setItem(row, 1, type_item)
            self._columns_table.setItem(row, 2, nullable_item)
            self._columns_table.setItem(row, 3, default_item)
            self._columns_table.setItem(row, 4, extra_item)
            self._columns_table.setItem(row, 5, key_item)

        self._columns_table.resizeColumnsToContents()

    def _populate_indexes_table(self, indexes: list) -> None:
        self._indexes_table.setColumnCount(5)
        self._indexes_table.setHorizontalHeaderLabels(
            ["Name", "Columns", "Type", "Unique", "Primary"]
        )
        self._indexes_table.setRowCount(len(indexes))

        for row, idx in enumerate(indexes):
            name_item = QTableWidgetItem(idx.name)
            columns_item = QTableWidgetItem(", ".join(idx.columns))
            type_item = QTableWidgetItem("BTREE")
            unique_item = QTableWidgetItem("Yes" if idx.is_unique else "No")
            primary_item = QTableWidgetItem("Yes" if idx.is_primary else "No")

            self._indexes_table.setItem(row, 0, name_item)
            self._indexes_table.setItem(row, 1, columns_item)
            self._indexes_table.setItem(row, 2, type_item)
            self._indexes_table.setItem(row, 3, unique_item)
            self._indexes_table.setItem(row, 4, primary_item)

        self._indexes_table.resizeColumnsToContents()

    def _populate_fk_table(self, fks: list) -> None:
        self._fk_table.setColumnCount(5)
        self._fk_table.setHorizontalHeaderLabels(
            ["Name", "Column", "References", "On Delete", "On Update"]
        )
        self._fk_table.setRowCount(len(fks))

        for row, fk in enumerate(fks):
            name_item = QTableWidgetItem(fk.name)
            column_item = QTableWidgetItem(fk.column)
            ref_item = QTableWidgetItem(f"{fk.ref_table}.{fk.ref_column}")
            on_delete_item = QTableWidgetItem(fk.on_delete)
            on_update_item = QTableWidgetItem(fk.on_update)

            self._fk_table.setItem(row, 0, name_item)
            self._fk_table.setItem(row, 1, column_item)
            self._fk_table.setItem(row, 2, ref_item)
            self._fk_table.setItem(row, 3, on_delete_item)
            self._fk_table.setItem(row, 4, on_update_item)

        self._fk_table.resizeColumnsToContents()
