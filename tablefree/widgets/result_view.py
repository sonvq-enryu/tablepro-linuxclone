"""Result view widget — Tabbed results / messages output."""

from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tablefree.models import QueryResult
from tablefree.widgets.table_structure import StructureView

from tablefree.db.driver import DatabaseDriver


class ResultView(QWidget):
    """Bottom panel: query result display with Results/Messages tabs."""

    NULL_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("result-panel")
        self._current_result: QueryResult | None = None
        self._page_size: int = 100
        self._current_page: int = 0
        self._sort_column: int | None = None
        self._sort_order: Qt.SortOrder | None = None
        self._setup_ui()
        self._table.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self._table and event.type() == event.Type.KeyPress:
            if event.matches(QKeySequence.StandardKey.Copy):
                self._copy_selected_cells()
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

        export_label = QLabel("Export ↗")
        export_label.setObjectName("result-action-link")
        export_label.setCursor(Qt.CursorShape.PointingHandCursor)
        info_layout.addWidget(export_label)

        results_layout.addWidget(info_bar)

        self._table = QTableWidget(0, 0)
        self._table.setObjectName("result-table")
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
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
