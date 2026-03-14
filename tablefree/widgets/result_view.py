"""Result view widget — Tabbed results / messages output."""

from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tablefree.models import ChangeTracker, QueryResult
from tablefree.models.change_tracker import CellEdit, RowInsert, RowDelete
from tablefree.widgets.table_structure import StructureView
from tablefree.widgets.sql_preview_dialog import SQLPreviewDialog
from tablefree.widgets.filter_panel import FilterPanel

from tablefree.db.driver import DatabaseDriver


class ResultView(QWidget):
    """Bottom panel: query result display with Results/Messages tabs."""

    NULL_ROLE = Qt.ItemDataRole.UserRole + 1
    ORIGINAL_VALUE_ROLE = Qt.ItemDataRole.UserRole + 2
    EDIT_STATE_ROLE = (
        Qt.ItemDataRole.UserRole + 3
    )  # None, 'edited', 'inserted', 'deleted'

    EDIT_BG = QColor(249, 226, 175, 38)  # yellow tint ~15% opacity
    INSERT_BG = QColor(166, 227, 161, 38)  # green tint ~15% opacity
    DELETE_BG = QColor(243, 139, 168, 25)  # red tint ~10% opacity

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("result-panel")
        self._current_result: QueryResult | None = None
        self._page_size: int = 100
        self._current_page: int = 0
        self._sort_column: int | None = None
        self._sort_order: Qt.SortOrder | None = None
        self._driver: DatabaseDriver | None = None
        self._current_table: str = ""
        self._current_schema: str = ""
        self._primary_key_cols: list[str] = []
        self._change_tracker = ChangeTracker()
        self._original_row_data: dict[int, list[Any]] = {}
        self._original_query: str = ""
        self._filter_state_per_tab: dict[str, dict] = {}
        self._setup_ui()
        self._table.installEventFilter(self)
        self._table.cellChanged.connect(self._on_cell_changed)
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)

    def eventFilter(self, obj, event):
        if obj == self._table and event.type() == event.Type.KeyPress:
            if event.matches(QKeySequence.StandardKey.Copy):
                self._copy_selected_cells()
                return True
            if event.matches(QKeySequence.StandardKey.Undo):
                self._on_undo()
                return True
            if event.matches(QKeySequence.StandardKey.Redo):
                self._on_redo()
                return True
        return super().eventFilter(obj, event)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("result-tabs")
        self._tabs.setDocumentMode(True)

        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(0)

        info_bar = QWidget()
        info_bar.setObjectName("result-info-bar")
        info_layout = QHBoxLayout(info_bar)
        info_layout.setContentsMargins(10, 4, 10, 4)
        info_layout.setSpacing(8)

        self._rows_label = QLabel("0 rows")
        self._rows_label.setObjectName("result-info-text")
        info_layout.addWidget(self._rows_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setObjectName("result-info-sep")
        sep.setFixedHeight(14)
        info_layout.addWidget(sep)

        self._time_label = QLabel("0 ms")
        self._time_label.setObjectName("result-info-text")
        info_layout.addWidget(self._time_label)

        info_layout.addStretch()

        self._filter_toggle_btn = QPushButton("⫧ Filter")
        self._filter_toggle_btn.setObjectName("filter-toggle-btn")
        self._filter_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._filter_toggle_btn.clicked.connect(self._toggle_filter_panel)
        info_layout.addWidget(self._filter_toggle_btn)

        export_label = QLabel("Export ↗")
        export_label.setObjectName("result-action-link")
        export_label.setCursor(Qt.CursorShape.PointingHandCursor)
        info_layout.addWidget(export_label)

        results_layout.addWidget(info_bar)

        self._filter_panel = FilterPanel(driver=self._driver)
        self._filter_panel.setVisible(False)
        self._filter_panel.filters_applied.connect(self._on_filters_applied)
        self._filter_panel.filters_cleared.connect(self._on_filters_cleared)
        results_layout.addWidget(self._filter_panel)

        self._edit_toolbar = self._create_edit_toolbar()
        results_layout.addWidget(self._edit_toolbar)

        self._table = QTableWidget(0, 0)
        self._table.setObjectName("result-table")
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        self._table.verticalHeader().setDefaultSectionSize(28)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self._table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)

        results_layout.addWidget(self._table, stretch=1)

        self._pagination_bar = self._create_pagination_bar()
        results_layout.addWidget(self._pagination_bar)

        self._tabs.addTab(results_widget, "Results")

        messages_widget = QWidget()
        msg_layout = QVBoxLayout(messages_widget)
        msg_layout.setContentsMargins(0, 0, 0, 0)

        self._messages = QPlainTextEdit()
        self._messages.setObjectName("messages-output")
        self._messages.setReadOnly(True)
        self._messages.setPlaceholderText("Query execution messages will appear here…")
        self._messages.appendPlainText(
            "-- TableFree v0.1.0\n-- Ready. Connect to a database to start.\n"
        )
        msg_layout.addWidget(self._messages)
        self._tabs.addTab(messages_widget, "Messages")

        history_widget = QWidget()
        hist_layout = QVBoxLayout(history_widget)
        hist_layout.setContentsMargins(0, 0, 0, 0)

        history_output = QPlainTextEdit()
        history_output.setObjectName("history-output")
        history_output.setReadOnly(True)
        history_output.setPlaceholderText("Query history will appear here…")
        hist_layout.addWidget(history_output)
        self._tabs.addTab(history_widget, "History")

        self._structure_view = StructureView()
        self._tabs.addTab(self._structure_view, "Structure")

        layout.addWidget(self._tabs, stretch=1)

    def _create_pagination_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("pagination-bar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

        self._page_size_combo = QComboBox()
        self._page_size_combo.setObjectName("page-size-combo")
        self._page_size_combo.addItems(["50", "100", "500", "1000", "All"])
        self._page_size_combo.setCurrentText("100")
        self._page_size_combo.currentTextChanged.connect(self._on_page_size_changed)
        layout.addWidget(self._page_size_combo)

        size_label = QLabel("rows per page")
        size_label.setObjectName("page-info")
        layout.addWidget(size_label)

        layout.addStretch()

        self._first_btn = QPushButton("◀◀")
        self._first_btn.setObjectName("page-btn")
        self._first_btn.setFixedWidth(32)
        self._first_btn.clicked.connect(lambda: self._go_to_page(0))
        layout.addWidget(self._first_btn)

        self._prev_btn = QPushButton("◀")
        self._prev_btn.setObjectName("page-btn")
        self._prev_btn.setFixedWidth(24)
        self._prev_btn.clicked.connect(self._prev_page)
        layout.addWidget(self._prev_btn)

        self._page_label = QLabel("Page 1 of 1")
        self._page_label.setObjectName("page-info")
        layout.addWidget(self._page_label)

        self._next_btn = QPushButton("▶")
        self._next_btn.setObjectName("page-btn")
        self._next_btn.setFixedWidth(24)
        self._next_btn.clicked.connect(self._next_page)
        layout.addWidget(self._next_btn)

        self._last_btn = QPushButton("▶▶")
        self._last_btn.setObjectName("page-btn")
        self._last_btn.setFixedWidth(32)
        self._last_btn.clicked.connect(self._last_page)
        layout.addWidget(self._last_btn)

        return bar

    def _create_edit_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("edit-toolbar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

        self._insert_btn = QPushButton("+ Insert")
        self._insert_btn.setObjectName("edit-btn")
        self._insert_btn.clicked.connect(self._on_insert_row)
        layout.addWidget(self._insert_btn)

        self._delete_btn = QPushButton("✕ Delete")
        self._delete_btn.setObjectName("edit-btn")
        self._delete_btn.clicked.connect(self._on_delete_row)
        layout.addWidget(self._delete_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setObjectName("edit-sep")
        sep.setFixedHeight(14)
        layout.addWidget(sep)

        self._preview_btn = QPushButton("Preview SQL 👁")
        self._preview_btn.setObjectName("edit-btn")
        self._preview_btn.clicked.connect(self._on_preview_sql)
        layout.addWidget(self._preview_btn)

        self._discard_btn = QPushButton("Discard")
        self._discard_btn.setObjectName("edit-btn")
        self._discard_btn.clicked.connect(self._on_discard)
        layout.addWidget(self._discard_btn)

        self._commit_btn = QPushButton("Commit ✓")
        self._commit_btn.setObjectName("commit-btn")
        self._commit_btn.setShortcut(QKeySequence("Ctrl+S"))
        self._commit_btn.clicked.connect(self._on_commit)
        layout.addWidget(self._commit_btn)

        layout.addStretch()

        self._pending_label = QLabel("Pending: 0 changes")
        self._pending_label.setObjectName("pending-label")
        layout.addWidget(self._pending_label)

        bar.setVisible(False)
        return bar

    def _toggle_filter_panel(self) -> None:
        """Toggle filter panel visibility."""
        is_visible = not self._filter_panel.isVisible()
        self._filter_panel.setVisible(is_visible)
        if is_visible and self._current_result and self._current_result.columns:
            self._filter_panel.set_columns(
                self._current_result.columns, self._current_result.column_types
            )
            self._filter_panel.set_table_widget(self._table)

    def _on_filters_applied(self, where_clause: str, params: tuple) -> None:
        """Handle filters applied - re-execute query with WHERE clause."""
        if not self._current_table or not self._driver:
            return

        driver_type = type(self._driver).__name__.lower()

        page_size_str = str(self._page_size) if self._page_size > 0 else "1000"
        offset = self._current_page * self._page_size

        schema = self._current_schema or "public"
        table = self._current_table

        if "mysql" in driver_type:
            quoted_schema = f"`{schema}`"
            quoted_table = f"`{table}`"
        else:
            quoted_schema = f'"{schema}"'
            quoted_table = f'"{table}"'

        if where_clause:
            sql = f"SELECT * FROM {quoted_schema}.{quoted_table} WHERE {where_clause} LIMIT {page_size_str} OFFSET {offset}"
        else:
            sql = f"SELECT * FROM {quoted_schema}.{quoted_table} LIMIT {page_size_str} OFFSET {offset}"

        try:
            result = self._driver.execute(sql, params)
            if result and isinstance(result, list) and result:
                if isinstance(result[0], dict):
                    columns = list(result[0].keys())
                    data = [list(r.values()) for r in result]
                    col_types = self._infer_types(result, columns)
                    query_result = QueryResult(
                        columns=columns,
                        rows=data,
                        column_types=col_types,
                        row_count=len(data),
                        duration_ms=0,
                        query=sql,
                    )
                    self._current_result = query_result
                    self._display_page(0)
        except Exception as e:
            self.display_error(f"Filter error: {e}")

    def _on_filters_cleared(self) -> None:
        """Handle filters cleared - re-execute original query."""
        if not self._current_table or not self._driver or not self._original_query:
            return

        try:
            driver_type = type(self._driver).__name__.lower()
            page_size_str = str(self._page_size) if self._page_size > 0 else "1000"
            offset = self._current_page * self._page_size

            schema = self._current_schema or "public"
            table = self._current_table

            if "mysql" in driver_type:
                quoted_schema = f"`{schema}`"
                quoted_table = f"`{table}`"
            else:
                quoted_schema = f'"{schema}"'
                quoted_table = f'"{table}"'

            sql = f"SELECT * FROM {quoted_schema}.{quoted_table} LIMIT {page_size_str} OFFSET {offset}"

            result = self._driver.execute(sql)
            if result and isinstance(result, list) and result:
                if isinstance(result[0], dict):
                    columns = list(result[0].keys())
                    data = [list(r.values()) for r in result]
                    col_types = self._infer_types(result, columns)
                    query_result = QueryResult(
                        columns=columns,
                        rows=data,
                        column_types=col_types,
                        row_count=len(data),
                        duration_ms=0,
                        query=sql,
                    )
                    self._current_result = query_result
                    self._display_page(0)
        except Exception as e:
            self.display_error(f"Clear filter error: {e}")

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

    def _on_cell_changed(self, row: int, col: int) -> None:
        """Handle cell value changes."""
        if not self._current_result:
            return

        item = self._table.item(row, col)
        if not item:
            return

        # Get the new value
        new_value_text = item.text()
        new_value = self._parse_cell_value(new_value_text)

        # Get original value
        old_value = item.data(self.ORIGINAL_VALUE_ROLE)

        # Get edit state
        edit_state = item.data(self.EDIT_STATE_ROLE)

        # Skip if already deleted
        if edit_state == "deleted":
            return

        # Record the edit
        self._change_tracker.record_edit(row, col, old_value, new_value)

        # Update visual state
        if edit_state != "inserted":
            item.setData(self.EDIT_STATE_ROLE, "edited")
            item.setBackground(self.EDIT_BG)

        # Update pending changes label
        self._update_pending_label()

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        """Handle cell double-click for editing."""
        pass

    def _parse_cell_value(self, text: str) -> Any:
        """Parse cell text to appropriate Python value."""
        if text == "NULL":
            return None
        try:
            if "." in text:
                return float(text)
            return int(text)
        except ValueError:
            return text

    def _on_insert_row(self) -> None:
        """Insert a new row."""
        if not self._current_result:
            return

        row_count = self._table.rowCount()
        self._table.insertRow(row_count)

        # Initialize cells with empty/default values
        row_data = []
        for col in range(self._table.columnCount()):
            item = QTableWidgetItem("")
            item.setData(self.NULL_ROLE, False)
            item.setData(self.ORIGINAL_VALUE_ROLE, None)
            item.setData(self.EDIT_STATE_ROLE, "inserted")
            item.setBackground(self.INSERT_BG)
            self._table.setItem(row_count, col, item)
            row_data.append(None)

        # Record the insert
        self._change_tracker.record_insert(row_count, row_data)

        # Store original row data for undo
        self._original_row_data[row_count] = row_data

        # Update pending label
        self._update_pending_label()

    def _on_delete_row(self) -> None:
        """Delete selected rows."""
        selected_rows = set(r.topRow() for r in self._table.selectedRanges())
        if not selected_rows:
            return

        for row in sorted(selected_rows, reverse=True):
            # Check if already deleted
            first_item = self._table.item(row, 0)
            if first_item and first_item.data(self.EDIT_STATE_ROLE) == "deleted":
                continue

            # Get row data for undo
            row_data = []
            for col in range(self._table.columnCount()):
                item = self._table.item(row, col)
                val = item.text() if item else ""
                row_data.append(self._parse_cell_value(val))

            # Record deletion
            self._change_tracker.record_delete(row, row_data)

            # Store original data
            self._original_row_data[row] = row_data

            # Apply visual changes
            for col in range(self._table.columnCount()):
                item = self._table.item(row, col)
                if item:
                    item.setData(self.EDIT_STATE_ROLE, "deleted")
                    item.setBackground(self.DELETE_BG)
                    font = item.font()
                    font.setStrikeOut(True)
                    item.setFont(font)

        self._update_pending_label()

    def _on_preview_sql(self) -> None:
        """Show SQL preview dialog."""
        if not self._current_result or not self._current_table:
            return

        columns = self._current_result.columns
        sql_statements = self._change_tracker.generate_sql(
            self._current_table, columns, self._primary_key_cols
        )

        if not sql_statements:
            QMessageBox.information(
                self, "SQL Preview", "No pending changes to preview."
            )
            return

        dialog = SQLPreviewDialog(sql_statements, self)
        if dialog.exec():
            self._on_commit()

    def _on_discard(self) -> None:
        """Discard all pending changes."""
        if not self._change_tracker.has_changes:
            return

        reply = QMessageBox.question(
            self,
            "Discard Changes",
            "Are you sure you want to discard all pending changes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._change_tracker.discard()
            # Reload original data
            if self._current_result:
                self._display_page(self._current_page)
            self._update_pending_label()
            self._update_edit_toolbar_visibility()

    def _on_commit(self) -> None:
        """Commit changes to database."""
        if not self._change_tracker.has_changes:
            return

        if not self._primary_key_cols:
            reply = QMessageBox.warning(
                self,
                "No Primary Key",
                "No primary key detected. DELETE and UPDATE statements will match on all column values. Proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Generate SQL
        columns = self._current_result.columns if self._current_result else []
        sql_statements = self._change_tracker.generate_sql(
            self._current_table, columns, self._primary_key_cols
        )

        if not sql_statements:
            return

        # Execute SQL statements
        if self._driver:
            try:
                for sql, params in sql_statements:
                    self._driver.execute(sql, params)

                # Clear changes
                self._change_tracker.commit()
                self._original_row_data.clear()

                # Show success
                self.append_message("Changes committed successfully.")

                # Refresh results (would need original query to re-execute)
                if self._current_result:
                    self._display_page(self._current_page)

                self._update_pending_label()
                self._update_edit_toolbar_visibility()

            except Exception as e:
                self.display_error(f"Failed to commit changes: {e}")

    def _update_pending_label(self) -> None:
        """Update the pending changes label."""
        count = len(self._change_tracker.pending_changes)
        self._pending_label.setText(
            f"Pending: {count} change{'s' if count != 1 else ''}"
        )

    def _update_edit_toolbar_visibility(self) -> None:
        """Show/hide edit toolbar based on table context."""
        has_table = bool(self._current_table)
        self._edit_toolbar.setVisible(has_table)

    def _detect_table_from_query(self, query: str) -> None:
        """Try to detect table name from SELECT query."""
        if not query:
            self._current_table = ""
            self._current_schema = ""
            self._primary_key_cols = []
            return

        query_upper = query.upper().strip()

        # Simple pattern matching for "SELECT * FROM table" or "SELECT * FROM schema.table"
        import re

        # Match: SELECT ... FROM ["`]schema["`].["`]table["`] ... or SELECT ... FROM table ...
        pattern = r"FROM\s+(?:(?P<schema>[\w]+)\.)?(?P<table>[\w]+)"
        match = re.search(pattern, query_upper)
        if match:
            self._current_table = match.group("table")
            self._current_schema = match.group("schema") or "public"
        else:
            self._current_table = ""
            self._current_schema = ""

        # Try to get primary key columns if driver is available
        self._primary_key_cols = []
        if self._driver and self._current_table:
            try:
                indexes = self._driver.get_indexes(
                    self._current_table, self._current_schema
                )
                for idx in indexes:
                    if idx.is_primary:
                        self._primary_key_cols = idx.columns
                        break
            except Exception:
                pass

    def _on_undo(self) -> None:
        """Handle undo request."""
        change = self._change_tracker.undo()
        if change is None:
            return

        if isinstance(change, CellEdit):
            # Revert cell to old value
            item = self._table.item(change.row, change.col)
            if item:
                # Determine display value
                if change.old_value is None:
                    display = "NULL"
                    item.setData(self.NULL_ROLE, True)
                else:
                    display = str(change.old_value)
                    item.setData(self.NULL_ROLE, False)
                item.setText(display)
                item.setData(self.ORIGINAL_VALUE_ROLE, change.old_value)

                # Clear edit state if going back to original
                if change.old_value == self._change_tracker.get_original_value(
                    change.row, change.col
                ):
                    item.setData(self.EDIT_STATE_ROLE, None)
                    item.setBackground(QColor())

        elif isinstance(change, RowInsert):
            # Remove inserted row
            self._table.removeRow(change.row_index)
            self._original_row_data.pop(change.row_index, None)

        elif isinstance(change, RowDelete):
            # Restore deleted row
            # Need to re-insert row at original position
            self._table.insertRow(change.row_index)
            for col_idx, value in enumerate(change.row_data):
                item = QTableWidgetItem(str(value) if value is not None else "NULL")
                item.setData(self.NULL_ROLE, value is None)
                item.setData(self.ORIGINAL_VALUE_ROLE, value)
                self._table.setItem(change.row_index, col_idx, item)

        self._update_pending_label()

    def _on_redo(self) -> None:
        """Handle redo request."""
        change = self._change_tracker.redo()
        if change is None:
            return

        if isinstance(change, CellEdit):
            # Re-apply cell edit
            item = self._table.item(change.row, change.col)
            if item:
                if change.new_value is None:
                    display = "NULL"
                    item.setData(self.NULL_ROLE, True)
                else:
                    display = str(change.new_value)
                    item.setData(self.NULL_ROLE, False)
                item.setText(display)
                item.setData(self.EDIT_STATE_ROLE, "edited")
                item.setBackground(self.EDIT_BG)

        elif isinstance(change, RowInsert):
            # Re-insert row
            row_count = self._table.rowCount()
            self._table.insertRow(row_count)
            for col_idx, value in enumerate(change.row_data):
                item = QTableWidgetItem(str(value) if value is not None else "NULL")
                item.setData(self.NULL_ROLE, value is None)
                item.setData(self.ORIGINAL_VALUE_ROLE, value)
                item.setData(self.EDIT_STATE_ROLE, "inserted")
                item.setBackground(self.INSERT_BG)
                self._table.setItem(row_count, col_idx, item)

        elif isinstance(change, RowDelete):
            # Re-delete row
            for col in range(self._table.columnCount()):
                item = self._table.item(change.row_index, col)
                if item:
                    item.setData(self.EDIT_STATE_ROLE, "deleted")
                    item.setBackground(self.DELETE_BG)
                    font = item.font()
                    font.setStrikeOut(True)
                    item.setFont(font)

        self._update_pending_label()

    def set_driver(self, driver: DatabaseDriver) -> None:
        """Set the database driver for executing commits."""
        self._driver = driver
        self._filter_panel.set_driver(driver)

    def _on_page_size_changed(self, value: str) -> None:
        if value == "All":
            self._page_size = -1
        else:
            self._page_size = int(value)
        self._current_page = 0
        if self._current_result:
            self._display_page(0)

    def _go_to_page(self, page: int) -> None:
        self._current_page = page
        self._display_page(page)

    def _prev_page(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self._display_page(self._current_page)

    def _next_page(self) -> None:
        total_pages = self._total_pages
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._display_page(self._current_page)

    def _last_page(self) -> None:
        self._current_page = max(0, self._total_pages - 1)
        self._display_page(self._current_page)

    @property
    def _total_pages(self) -> int:
        if not self._current_result or self._page_size <= 0:
            return 1
        row_count = len(self._current_result.rows)
        return max(1, (row_count + self._page_size - 1) // self._page_size)

    def _display_page(self, page: int) -> None:
        if not self._current_result:
            return

        rows = self._current_result.rows
        if self._page_size > 0:
            start = page * self._page_size
            end = min(start + self._page_size, len(rows))
            page_rows = rows[start:end]
        else:
            page_rows = rows

        self._table.setRowCount(len(page_rows))

        for row_idx, row in enumerate(page_rows):
            for col_idx, value in enumerate(row):
                self._set_cell_item(
                    row_idx, col_idx, value, self._current_result.column_types[col_idx]
                )

        self._update_pagination_controls()
        self._update_header_sort_indicator()

    def _set_cell_item(self, row: int, col: int, value: Any, col_type: str) -> None:
        if value is None:
            item = QTableWidgetItem("NULL")
            item.setForeground(Qt.GlobalColor.gray)
            font = item.font()
            font.setItalic(True)
            item.setFont(font)
            item.setData(self.NULL_ROLE, True)
        else:
            display_value = self._format_cell_value(value, col_type)
            item = QTableWidgetItem(str(display_value))
            item.setData(self.NULL_ROLE, False)

        alignment = self._get_alignment_for_type(col_type)
        item.setTextAlignment(alignment)

        self._table.setItem(row, col, item)

    def _format_cell_value(self, value: Any, col_type: str) -> str:
        type_lower = col_type.lower()

        if type_lower in ("bool", "boolean"):
            return "true" if value else "false"

        if type_lower in ("json", "jsonb"):
            s = str(value)
            if len(s) > 100:
                return s[:97] + "..."
            return s

        if type_lower in ("date", "timestamp", "datetime", "time"):
            if isinstance(value, datetime):
                return value.strftime("%Y-%m-%d %H:%M:%S")
            return str(value)

        return value

    def _get_alignment_for_type(self, col_type: str) -> int:
        type_lower = col_type.lower()

        if type_lower in (
            "int",
            "integer",
            "bigint",
            "smallint",
            "serial",
            "float",
            "double",
            "decimal",
            "numeric",
            "real",
        ):
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        if type_lower in ("bool", "boolean"):
            return Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter

        return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

    def _on_header_clicked(self, col: int) -> None:
        if not self._current_result:
            return

        if self._sort_column == col:
            if self._sort_order is None:
                self._sort_order = Qt.SortOrder.AscendingOrder
            elif self._sort_order == Qt.SortOrder.AscendingOrder:
                self._sort_order = Qt.SortOrder.DescendingOrder
            else:
                self._sort_order = None
                self._sort_column = None
        else:
            self._sort_column = col
            self._sort_order = Qt.SortOrder.AscendingOrder

        if self._sort_order is not None:
            self._sort_rows()
        else:
            if self._current_result:
                self._current_result.rows.sort(key=lambda x: x, reverse=False)

        self._display_page(self._current_page)

    def _sort_rows(self) -> None:
        if (
            not self._current_result
            or self._sort_column is None
            or self._sort_order is None
        ):
            return

        col = self._sort_column
        reverse = self._sort_order == Qt.SortOrder.DescendingOrder

        def sort_key(row):
            val = row[col] if col < len(row) else None
            if val is None:
                return (1, "")
            if isinstance(val, bool):
                return (0, int(val))
            if isinstance(val, (int, float)):
                return (0, val)
            return (0, str(val).lower())

        self._current_result.rows.sort(key=sort_key, reverse=reverse)

    def _update_header_sort_indicator(self) -> None:
        header = self._table.horizontalHeader()
        for i in range(self._table.columnCount()):
            header.setSortIndicatorShown(False)

        if self._sort_column is not None and self._sort_order is not None:
            header.setSortIndicator(self._sort_column, self._sort_order)

        self._update_header_labels()

    def _update_header_labels(self) -> None:
        if not self._current_result:
            return

        for i, col_name in enumerate(self._current_result.columns):
            header_item = self._table.horizontalHeaderItem(i)
            if header_item is None:
                header_item = QTableWidgetItem()
                self._table.setHorizontalHeaderItem(i, header_item)
            if i == self._sort_column and self._sort_order is not None:
                indicator = (
                    " ▲" if self._sort_order == Qt.SortOrder.AscendingOrder else " ▼"
                )
                header_item.setText(col_name + indicator)
            else:
                header_item.setText(col_name)

    def _update_pagination_controls(self) -> None:
        total_pages = self._total_pages
        current = self._current_page + 1

        self._page_label.setText(f"Page {current} of {total_pages}")
        self._first_btn.setEnabled(current > 1)
        self._prev_btn.setEnabled(current > 1)
        self._next_btn.setEnabled(current < total_pages)
        self._last_btn.setEnabled(current < total_pages)

    def _copy_selected_cells(self) -> None:
        selected = self._table.selectedRanges()
        if not selected:
            return

        ranges = sorted(selected, key=lambda r: (r.topRow(), r.leftColumn()))

        min_row = min(r.topRow() for r in ranges)
        max_row = max(r.bottomRow() for r in ranges)
        min_col = min(r.leftColumn() for r in ranges)
        max_col = max(r.rightColumn() for r in ranges)

        full_row_selected = all(
            r.leftColumn() == min_col and r.rightColumn() == max_col for r in ranges
        )

        tsv_parts = []

        if full_row_selected and self._current_result:
            headers = [
                self._current_result.columns[i] for i in range(min_col, max_col + 1)
            ]
            tsv_parts.append("\t".join(str(h) for h in headers))

        for row_idx in range(min_row, max_row + 1):
            row_data = []
            for col_idx in range(min_col, max_col + 1):
                item = self._table.item(row_idx, col_idx)
                if item:
                    val = item.data(self.NULL_ROLE)
                    if val is True:
                        row_data.append("NULL")
                    else:
                        row_data.append(item.text())
                else:
                    row_data.append("")
            tsv_parts.append("\t".join(row_data))

        tsv = "\n".join(tsv_parts)
        QApplication.clipboard().setText(tsv)

    def display_results(self, result: QueryResult) -> None:
        self._tabs.setCurrentIndex(0)

        self._current_result = result
        self._current_page = 0
        self._sort_column = None
        self._sort_order = None

        # Clear change tracker
        self._change_tracker = ChangeTracker()
        self._original_row_data.clear()

        self._table.setColumnCount(len(result.columns))
        self._table.setHorizontalHeaderLabels(result.columns)
        self._table.setRowCount(0)

        self._display_page(0)

        total_pages = self._total_pages
        self._rows_label.setText(
            f"{result.row_count} rows | {result.duration_ms} ms | "
            f"Page {self._current_page + 1} of {total_pages}"
        )
        self._time_label.setText(f"{result.duration_ms} ms")

        # Try to detect table from query for inline editing
        self._detect_table_from_query(result.query)

        # Save original query for filter re-execution
        self._original_query = result.query

        # Set up filter panel
        connection_name = ""
        if self._driver and self._driver.config:
            connection_name = self._driver.config.name or ""

        if result.columns:
            self._filter_panel.set_columns(result.columns, result.column_types)
        self._filter_panel.set_table_widget(self._table)
        self._filter_panel.set_context(connection_name, self._current_table)

        # Show edit toolbar if we have a table
        self._update_edit_toolbar_visibility()

    def display_error(self, error: str) -> None:
        self._tabs.setCurrentIndex(1)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._messages.appendPlainText(f"[{timestamp}] ERROR: {error}")

    def append_message(self, message: str) -> None:
        self._messages.appendPlainText(message)
        self._tabs.setCurrentIndex(1)

    def show_structure(
        self, driver: "DatabaseDriver", table: str, schema: str | None = None
    ) -> None:
        """Show the structure tab for the given table."""
        self._tabs.setCurrentIndex(3)
        self._structure_view.load_structure(driver, table, schema)
