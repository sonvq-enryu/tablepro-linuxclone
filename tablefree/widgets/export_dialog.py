"""Dialog for exporting query results into CSV/JSON/SQL files."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from tablefree.services import CsvOptions, JsonOptions, SqlOptions, export_data
from tablefree.workers import QueryWorker


class ExportDialog(QDialog):
    """Modal dialog for exporting currently loaded table/query rows."""

    def __init__(
        self,
        columns: list[str],
        rows: list[list[object]],
        *,
        column_types: list[str] | None = None,
        table_name: str = "exported_table",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._columns = columns
        self._rows = rows
        self._column_types = column_types or []
        self._default_table_name = table_name
        self._thread_pool = QThreadPool.globalInstance()
        self._worker: QueryWorker | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Export Data")
        self.resize(600, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        format_row = QHBoxLayout()
        format_row.addWidget(QLabel("Format:"))
        self._csv_radio = QRadioButton("CSV")
        self._json_radio = QRadioButton("JSON")
        self._sql_radio = QRadioButton("SQL")
        self._csv_radio.setChecked(True)
        self._csv_radio.toggled.connect(self._on_format_changed)
        self._json_radio.toggled.connect(self._on_format_changed)
        self._sql_radio.toggled.connect(self._on_format_changed)
        format_row.addWidget(self._csv_radio)
        format_row.addWidget(self._json_radio)
        format_row.addWidget(self._sql_radio)
        format_row.addStretch()
        layout.addLayout(format_row)

        self._options_stack = QStackedWidget()
        self._options_stack.addWidget(self._build_csv_options())
        self._options_stack.addWidget(self._build_json_options())
        self._options_stack.addWidget(self._build_sql_options())
        layout.addWidget(self._options_stack)

        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("File:"))
        self._path_input = QLineEdit()
        file_row.addWidget(self._path_input, stretch=1)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_path)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        self._rows_label = QLabel(f"Rows: {len(self._rows)} rows will be exported")
        layout.addWidget(self._rows_label)

        self._status_label = QLabel("Ready")
        layout.addWidget(self._status_label)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        self._export_btn = QPushButton("Export")
        self._export_btn.setDefault(True)
        self._export_btn.clicked.connect(self._on_export)
        button_row.addWidget(self._export_btn)
        layout.addLayout(button_row)

        self._set_default_filename()

    def _build_csv_options(self) -> QWidget:
        box = QGroupBox("CSV Options")
        form = QFormLayout(box)

        self._csv_delimiter = QComboBox()
        self._csv_delimiter.addItems(["Comma (,)", "Semicolon (;)", "Tab (\\t)", "Pipe (|)"])
        form.addRow("Delimiter:", self._csv_delimiter)

        self._csv_header = QCheckBox()
        self._csv_header.setChecked(True)
        form.addRow("Include header:", self._csv_header)

        self._csv_null_text = QLineEdit()
        form.addRow("NULL text:", self._csv_null_text)

        self._csv_encoding = QComboBox()
        self._csv_encoding.addItems(["utf-8", "utf-8-sig", "latin-1"])
        form.addRow("Encoding:", self._csv_encoding)
        return box

    def _build_json_options(self) -> QWidget:
        box = QGroupBox("JSON Options")
        form = QFormLayout(box)

        self._json_pretty = QCheckBox()
        self._json_pretty.setChecked(True)
        form.addRow("Pretty print:", self._json_pretty)

        self._json_include_nulls = QCheckBox()
        self._json_include_nulls.setChecked(True)
        form.addRow("Include NULL keys:", self._json_include_nulls)

        self._json_encoding = QComboBox()
        self._json_encoding.addItems(["utf-8", "utf-8-sig", "latin-1"])
        form.addRow("Encoding:", self._json_encoding)
        return box

    def _build_sql_options(self) -> QWidget:
        box = QGroupBox("SQL Options")
        form = QFormLayout(box)

        self._sql_table_name = QLineEdit(self._default_table_name)
        form.addRow("Table name:", self._sql_table_name)

        self._sql_include_create = QCheckBox()
        form.addRow("Include CREATE TABLE:", self._sql_include_create)

        self._sql_include_drop = QCheckBox()
        form.addRow("Include DROP TABLE:", self._sql_include_drop)

        self._sql_batch_size = QSpinBox()
        self._sql_batch_size.setRange(1, 100_000)
        self._sql_batch_size.setValue(500)
        form.addRow("Batch size:", self._sql_batch_size)

        self._sql_encoding = QComboBox()
        self._sql_encoding.addItems(["utf-8", "utf-8-sig", "latin-1"])
        form.addRow("Encoding:", self._sql_encoding)
        return box

    def _current_format(self) -> str:
        if self._json_radio.isChecked():
            return "json"
        if self._sql_radio.isChecked():
            return "sql"
        return "csv"

    def _set_default_filename(self) -> None:
        if self._path_input.text().strip():
            return
        ext = self._current_format()
        self._path_input.setText(str(Path.home() / f"tablefree-export.{ext}"))

    def _on_format_changed(self) -> None:
        format_name = self._current_format()
        index_map = {"csv": 0, "json": 1, "sql": 2}
        self._options_stack.setCurrentIndex(index_map[format_name])
        self._set_default_filename()

    def _browse_path(self) -> None:
        current_format = self._current_format()
        filter_map = {
            "csv": "CSV Files (*.csv);;All Files (*)",
            "json": "JSON Files (*.json);;All Files (*)",
            "sql": "SQL Files (*.sql);;All Files (*)",
        }
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data",
            self._path_input.text().strip(),
            filter_map[current_format],
        )
        if path:
            self._path_input.setText(path)

    def _build_options(self) -> CsvOptions | JsonOptions | SqlOptions:
        current_format = self._current_format()
        if current_format == "csv":
            delimiter_map = {
                "Comma (,)": ",",
                "Semicolon (;)": ";",
                "Tab (\\t)": "\t",
                "Pipe (|)": "|",
            }
            return CsvOptions(
                delimiter=delimiter_map[self._csv_delimiter.currentText()],
                include_header=self._csv_header.isChecked(),
                null_text=self._csv_null_text.text(),
                encoding=self._csv_encoding.currentText(),
            )
        if current_format == "json":
            return JsonOptions(
                pretty=self._json_pretty.isChecked(),
                include_nulls=self._json_include_nulls.isChecked(),
                encoding=self._json_encoding.currentText(),
            )

        return SqlOptions(
            table_name=self._sql_table_name.text().strip(),
            include_create=self._sql_include_create.isChecked(),
            include_drop=self._sql_include_drop.isChecked(),
            batch_size=self._sql_batch_size.value(),
            encoding=self._sql_encoding.currentText(),
            column_types=self._column_types,
        )

    def _set_running(self, running: bool) -> None:
        self._export_btn.setEnabled(not running)

    def _on_export(self) -> None:
        export_path = self._path_input.text().strip()
        if not export_path:
            QMessageBox.warning(self, "Export", "Choose an output file path.")
            return

        export_format = self._current_format()
        options = self._build_options()
        if isinstance(options, SqlOptions) and not options.table_name:
            QMessageBox.warning(self, "Export", "SQL export requires a table name.")
            return

        self._set_running(True)
        self._status_label.setText("Exporting...")
        self._worker = QueryWorker(
            export_data,
            self._columns,
            self._rows,
            export_path,
            export_format,
            options,
        )
        self._worker.signals.finished.connect(self._on_export_finished)
        self._worker.signals.error.connect(self._on_export_error)
        self._thread_pool.start(self._worker)

    def _on_export_finished(self, _: object) -> None:
        self._set_running(False)
        self._status_label.setText("Export complete.")
        QMessageBox.information(self, "Export", "Data exported successfully.")
        self.accept()

    def _on_export_error(self, error: Exception) -> None:
        self._set_running(False)
        self._status_label.setText("Export failed.")
        QMessageBox.critical(self, "Export Failed", str(error))
