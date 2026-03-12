"""Result view widget — Tabbed results / messages output."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class ResultView(QWidget):
    """Bottom panel: query result display with Results/Messages tabs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("result-panel")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Tab bar for Results / Messages ───────────────────
        self._tabs = QTabWidget()
        self._tabs.setObjectName("result-tabs")
        self._tabs.setDocumentMode(True)

        # --- Results tab (placeholder table) ---
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(0)

        # Info bar
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

        # Placeholder data table
        self._table = QTableWidget(5, 4)
        self._table.setObjectName("result-table")
        self._table.setHorizontalHeaderLabels(["id", "name", "email", "created_at"])
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setDefaultSectionSize(28)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )

        # Fill sample data
        sample_data = [
            ("1", "Alice Johnson", "alice@example.com", "2025-01-15 09:30:00"),
            ("2", "Bob Smith", "bob@example.com", "2025-02-20 14:15:00"),
            ("3", "Carol White", "carol@example.com", "2025-03-01 11:00:00"),
            ("4", "Dan Brown", "dan@example.com", "2025-03-05 16:45:00"),
            ("5", "Eve Davis", "eve@example.com", "2025-03-10 08:20:00"),
        ]
        for row, data in enumerate(sample_data):
            for col, value in enumerate(data):
                item = QTableWidgetItem(value)
                self._table.setItem(row, col, item)

        self._rows_label.setText(f"{len(sample_data)} rows")
        self._time_label.setText("12 ms")

        results_layout.addWidget(self._table, stretch=1)
        self._tabs.addTab(results_widget, "Results")

        # --- Messages tab ---
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

        # --- History tab ---
        history_widget = QWidget()
        hist_layout = QVBoxLayout(history_widget)
        hist_layout.setContentsMargins(0, 0, 0, 0)

        history_output = QPlainTextEdit()
        history_output.setObjectName("history-output")
        history_output.setReadOnly(True)
        history_output.setPlaceholderText("Query history will appear here…")
        hist_layout.addWidget(history_output)
        self._tabs.addTab(history_widget, "History")

        layout.addWidget(self._tabs, stretch=1)

    def append_message(self, message: str) -> None:
        self._messages.appendPlainText(message)
        self._tabs.setCurrentIndex(1)

    def display_results(self, results: list[dict] | list[tuple]) -> None:
        if not results:
            self._table.setRowCount(0)
            self._rows_label.setText("0 rows")
            return

        if isinstance(results[0], dict):
            columns = list(results[0].keys())
            self._table.setColumnCount(len(columns))
            self._table.setHorizontalHeaderLabels(columns)
            self._table.setRowCount(len(results))
            for row_idx, row in enumerate(results):
                for col_idx, col in enumerate(columns):
                    value = str(row.get(col, ""))
                    item = QTableWidgetItem(value)
                    self._table.setItem(row_idx, col_idx, item)
        else:
            num_cols = len(results[0]) if results else 0
            self._table.setColumnCount(num_cols)
            self._table.setHorizontalHeaderLabels(
                [f"Column {i + 1}" for i in range(num_cols)]
            )
            self._table.setRowCount(len(results))
            for row_idx, row in enumerate(results):
                for col_idx, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    self._table.setItem(row_idx, col_idx, item)

        self._rows_label.setText(f"{len(results)} rows")
