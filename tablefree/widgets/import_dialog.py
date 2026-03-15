"""Dialog for importing SQL files into the active database."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from tablefree.db.driver import DatabaseDriver
from tablefree.services import ImportOptions, ImportResult, import_sql, split_sql_statements
from tablefree.workers import QueryWorker


class ImportDialog(QDialog):
    """Modal dialog that imports .sql files with progress tracking."""

    def __init__(self, driver: DatabaseDriver, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._driver = driver
        self._thread_pool = QThreadPool.globalInstance()
        self._worker: QueryWorker | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Import SQL")
        self.resize(620, 360)
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("File:"))
        self._path_input = QLineEdit()
        self._path_input.textChanged.connect(self._refresh_preview)
        file_row.addWidget(self._path_input, stretch=1)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_path)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        layout.addWidget(QLabel("Drop a .sql file onto this dialog to load it."))

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        self._encoding = QComboBox()
        self._encoding.addItems(["utf-8", "utf-8-sig", "latin-1"])
        self._encoding.currentTextChanged.connect(self._refresh_preview)
        form.addRow("Encoding:", self._encoding)

        self._wrap_tx = QCheckBox()
        self._wrap_tx.setChecked(True)
        form.addRow("Wrap in transaction:", self._wrap_tx)

        self._disable_fk = QCheckBox()
        form.addRow("Disable foreign keys:", self._disable_fk)
        layout.addWidget(form_widget)

        self._preview_label = QLabel("Preview: no file selected")
        layout.addWidget(self._preview_label)

        self._progress = QProgressBar()
        self._progress.setMinimum(0)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        self._status_label = QLabel("Ready")
        layout.addWidget(self._status_label)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        self._import_btn = QPushButton("Import")
        self._import_btn.setDefault(True)
        self._import_btn.clicked.connect(self._on_import)
        buttons.addWidget(self._import_btn)
        layout.addLayout(buttons)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if urls and any(url.toLocalFile().lower().endswith(".sql") for url in urls):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            local_path = url.toLocalFile()
            if local_path.lower().endswith(".sql"):
                self._path_input.setText(local_path)
                event.acceptProposedAction()
                return
        event.ignore()

    def _browse_path(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import SQL",
            self._path_input.text().strip(),
            "SQL Files (*.sql);;All Files (*)",
        )
        if path:
            self._path_input.setText(path)

    def _statement_count(self, path: str, encoding: str) -> int:
        sql_text = Path(path).read_text(encoding=encoding)
        return len(split_sql_statements(sql_text))

    def _refresh_preview(self) -> None:
        path = self._path_input.text().strip()
        if not path:
            self._preview_label.setText("Preview: no file selected")
            self._progress.setValue(0)
            self._progress.setMaximum(0)
            self._progress.setMaximum(100)
            return

        try:
            count = self._statement_count(path, self._encoding.currentText())
            self._preview_label.setText(f"Preview: {count} statements detected")
            self._progress.setValue(0)
            self._progress.setMaximum(max(1, count))
        except Exception as exc:
            self._preview_label.setText(f"Preview error: {exc}")
            self._progress.setValue(0)
            self._progress.setMaximum(100)

    def _set_running(self, running: bool) -> None:
        self._import_btn.setEnabled(not running)

    def _on_progress(self, current: int, total: int) -> None:
        self._progress.setMaximum(max(1, total))
        self._progress.setValue(current)
        self._status_label.setText(f"Importing... {current}/{total}")

    def _on_import(self) -> None:
        path = self._path_input.text().strip()
        if not path:
            QMessageBox.warning(self, "Import", "Choose a SQL file to import.")
            return

        options = ImportOptions(
            encoding=self._encoding.currentText(),
            wrap_in_transaction=self._wrap_tx.isChecked(),
            disable_foreign_keys=self._disable_fk.isChecked(),
        )

        self._set_running(True)
        self._status_label.setText("Starting import...")
        self._worker = QueryWorker(import_sql, self._driver, path, options)
        self._worker.kwargs["progress_callback"] = self._worker.report_progress
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.finished.connect(self._on_import_finished)
        self._worker.signals.error.connect(self._on_import_error)
        self._thread_pool.start(self._worker)

    def _on_import_finished(self, result: object) -> None:
        self._set_running(False)
        if not isinstance(result, ImportResult):
            self._status_label.setText("Import failed.")
            QMessageBox.critical(self, "Import Failed", "Unexpected import result.")
            return

        if result.success:
            self._status_label.setText("Import complete.")
            QMessageBox.information(
                self,
                "Import Complete",
                f"Executed {result.executed_statements}/{result.total_statements} statements.",
            )
            self.accept()
            return

        self._status_label.setText("Import failed.")
        details = [
            f"Executed statements: {result.executed_statements}/{result.total_statements}",
            f"Failed statement index: {result.error_statement}",
            f"Database error: {result.error_message}",
        ]
        if result.failed_statement_text:
            details.append("")
            details.append("Failed SQL:")
            details.append(result.failed_statement_text)
        QMessageBox.critical(self, "Import Failed", "\n".join(details))

    def _on_import_error(self, error: Exception) -> None:
        self._set_running(False)
        self._status_label.setText("Import failed.")
        QMessageBox.critical(self, "Import Failed", str(error))
