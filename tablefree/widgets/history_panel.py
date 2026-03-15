"""Query history panel with search and quick actions."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tablefree.services.query_history import HistoryEntry, QueryHistoryStore


class HistoryPanel(QWidget):
    """Searchable query history with load/run actions."""

    query_load_requested = Signal(str)
    query_run_requested = Signal(str)

    ENTRY_ID_ROLE = Qt.ItemDataRole.UserRole + 1
    QUERY_TEXT_ROLE = Qt.ItemDataRole.UserRole + 2

    def __init__(
        self,
        store: QueryHistoryStore,
        page_size: int = 100,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("history-panel")
        self._store = store
        self._page_size = max(1, page_size)
        self._offset = 0
        self._setup_ui()
        self.refresh(reset=True)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("history-search")
        self._search_input.setPlaceholderText("Search queries...")
        layout.addWidget(self._search_input)

        filters_row = QHBoxLayout()
        filters_row.setContentsMargins(0, 0, 0, 0)
        filters_row.setSpacing(8)

        self._connection_filter = QComboBox()
        self._connection_filter.setObjectName("history-filter")
        self._connection_filter.addItem("All connections", None)
        filters_row.addWidget(self._connection_filter)

        self._status_filter = QComboBox()
        self._status_filter.setObjectName("history-filter")
        self._status_filter.addItem("All statuses", None)
        self._status_filter.addItem("Success", "success")
        self._status_filter.addItem("Error", "error")
        filters_row.addWidget(self._status_filter)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setObjectName("history-clear-btn")
        filters_row.addWidget(self._clear_btn)

        filters_row.addStretch()
        layout.addLayout(filters_row)

        self._table = QTableWidget(0, 4)
        self._table.setObjectName("history-table")
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.setHorizontalHeaderLabels(["Query", "Time", "Duration", "Status"])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSortingEnabled(True)
        layout.addWidget(self._table, stretch=1)

        self._load_more_btn = QPushButton("Load more")
        self._load_more_btn.setObjectName("history-load-more")
        self._load_more_btn.setVisible(False)
        layout.addWidget(self._load_more_btn)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._on_filters_changed)

        self._search_input.textChanged.connect(self._on_search_text_changed)
        self._connection_filter.currentIndexChanged.connect(self._on_filters_changed)
        self._status_filter.currentIndexChanged.connect(self._on_filters_changed)
        self._clear_btn.clicked.connect(self._on_clear_clicked)
        self._load_more_btn.clicked.connect(self._load_more)
        self._table.cellDoubleClicked.connect(self._on_table_double_clicked)
        self._table.customContextMenuRequested.connect(self._show_context_menu)

    def refresh(self, reset: bool = True) -> None:
        if reset:
            self._offset = 0
            self._table.setSortingEnabled(False)
            self._table.setRowCount(0)
            self._table.setSortingEnabled(True)
            self._refresh_connection_filter()
        self._append_page()

    def _on_search_text_changed(self) -> None:
        self._search_timer.start()

    def _on_filters_changed(self) -> None:
        self.refresh(reset=True)

    def _load_more(self) -> None:
        self.refresh(reset=False)

    def _append_page(self) -> None:
        entries = self._store.search(
            term=self._search_input.text().strip() or None,
            connection=self._connection_filter.currentData(),
            status=self._status_filter.currentData(),
            limit=self._page_size,
            offset=self._offset,
        )
        if not entries and self._offset == 0:
            self._load_more_btn.setVisible(False)
            return

        for entry in entries:
            self._append_entry_row(entry)
        self._offset += len(entries)
        self._load_more_btn.setVisible(len(entries) == self._page_size)

    def _append_entry_row(self, entry: HistoryEntry) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)

        query_preview = self._truncate_query(entry.query_text)
        query_item = QTableWidgetItem(query_preview)
        query_item.setToolTip(entry.query_text)
        query_item.setData(self.ENTRY_ID_ROLE, entry.id)
        query_item.setData(self.QUERY_TEXT_ROLE, entry.query_text)

        time_item = QTableWidgetItem(self._format_time(entry.executed_at))
        duration_item = QTableWidgetItem(f"{entry.duration_ms:.1f} ms")
        duration_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        status_text = "OK" if entry.status == "success" else "ERR"
        status_item = QTableWidgetItem(status_text)
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        self._table.setItem(row, 0, query_item)
        self._table.setItem(row, 1, time_item)
        self._table.setItem(row, 2, duration_item)
        self._table.setItem(row, 3, status_item)

    def _show_context_menu(self, pos) -> None:  # noqa: ANN001
        row = self._table.rowAt(pos.y())
        if row < 0:
            return

        entry = self._entry_for_row(row)
        if entry is None:
            return

        menu = QMenu(self)
        load_action = QAction("Load into Editor", self)
        run_action = QAction("Run Again", self)
        copy_action = QAction("Copy Query", self)
        delete_action = QAction("Delete Entry", self)

        load_action.triggered.connect(lambda: self._emit_load(entry.query_text))
        run_action.triggered.connect(lambda: self._emit_run(entry.query_text))
        copy_action.triggered.connect(lambda: QApplication.clipboard().setText(entry.query_text))
        delete_action.triggered.connect(lambda: self._delete_entry(entry.id))

        menu.addAction(load_action)
        menu.addAction(run_action)
        menu.addAction(copy_action)
        menu.addSeparator()
        menu.addAction(delete_action)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _delete_entry(self, entry_id: int) -> None:
        self._store.delete(entry_id)
        self.refresh(reset=True)

    def _on_table_double_clicked(self, row: int, _col: int) -> None:
        entry = self._entry_for_row(row)
        if entry is None:
            return
        self._emit_load(entry.query_text)

    def _entry_for_row(self, row: int) -> HistoryEntry | None:
        item = self._table.item(row, 0)
        if item is None:
            return None
        entry_id = item.data(self.ENTRY_ID_ROLE)
        if entry_id is None:
            return None
        return self._store.get_entry(int(entry_id))

    def _on_clear_clicked(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Delete all query history entries?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._store.clear()
        self.refresh(reset=True)

    def _emit_load(self, query_text: str) -> None:
        self.query_load_requested.emit(query_text)

    def _emit_run(self, query_text: str) -> None:
        self.query_run_requested.emit(query_text)

    def _refresh_connection_filter(self) -> None:
        current = self._connection_filter.currentData()
        connections = self._store.get_connections()
        self._connection_filter.blockSignals(True)
        self._connection_filter.clear()
        self._connection_filter.addItem("All connections", None)
        for name in connections:
            self._connection_filter.addItem(name, name)
        if current is not None:
            idx = self._connection_filter.findData(current)
            if idx >= 0:
                self._connection_filter.setCurrentIndex(idx)
        self._connection_filter.blockSignals(False)

    @staticmethod
    def _truncate_query(query_text: str, max_len: int = 80) -> str:
        single_line = " ".join(query_text.split())
        if len(single_line) <= max_len:
            return single_line
        return f"{single_line[: max_len - 3]}..."

    @staticmethod
    def _format_time(iso_text: str) -> str:
        try:
            dt = datetime.fromisoformat(iso_text)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return iso_text
