"""SQL preview dialog for viewing generated SQL statements."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tablefree.widgets.code_editor import CodeEditor


class SQLPreviewDialog(QDialog):
    """Dialog for previewing generated SQL before committing changes."""

    def __init__(
        self,
        sql_statements: list[tuple[str, tuple]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._sql_statements = sql_statements
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("SQL Preview")
        self.resize(700, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header
        header = QLabel("Generated SQL Statements")
        header.setObjectName("dialog-header")
        layout.addWidget(header)

        # Warning banner if DELETE statements present
        has_delete = any("DELETE" in sql.upper() for sql, _ in self._sql_statements)
        if has_delete:
            warning = QLabel(
                "Warning: DELETE statements detected. These operations cannot be undone."
            )
            warning.setObjectName("warning-banner")
            warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(warning)

        # SQL code editor (read-only)
        self._editor = CodeEditor()
        self._editor.setReadOnly(True)

        # Format SQL statements
        sql_text = self._format_sql()
        self._editor.setPlainText(sql_text)

        layout.addWidget(self._editor, stretch=1)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        # Statement count
        count = len(self._sql_statements)
        count_label = QLabel(f"{count} statement{'s' if count != 1 else ''}")
        count_label.setObjectName("statement-count")
        button_layout.addWidget(count_label)

        button_layout.addStretch()

        # Copy button
        copy_btn = QPushButton("Copy")
        copy_btn.setShortcut(QKeySequence("Ctrl+C"))
        copy_btn.clicked.connect(self._copy_to_clipboard)
        button_layout.addWidget(copy_btn)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setShortcut(QKeySequence("Esc"))
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)

        # Execute button
        self._execute_btn = QPushButton("Execute")
        self._execute_btn.setObjectName("primary-button")
        self._execute_btn.setShortcut(QKeySequence("Ctrl+Return"))
        self._execute_btn.clicked.connect(self.accept)
        button_layout.addWidget(self._execute_btn)

        layout.addLayout(button_layout)

    def _format_sql(self) -> str:
        """Format SQL statements for display."""
        lines = []
        for sql, params in self._sql_statements:
            if params:
                # Replace placeholders with actual values for display
                formatted_sql = sql
                for param in params:
                    if param is None:
                        formatted_sql = formatted_sql.replace("%s", "NULL", 1)
                    elif isinstance(param, str):
                        formatted_sql = formatted_sql.replace("%s", f"'{param}'", 1)
                    else:
                        formatted_sql = formatted_sql.replace("%s", str(param), 1)
                lines.append(formatted_sql + ";")
            else:
                lines.append(sql + ";")
            lines.append("")
        return "\n".join(lines)

    def _copy_to_clipboard(self) -> None:
        """Copy SQL to clipboard."""
        from PySide6.QtWidgets import QApplication

        sql_text = self._format_sql()
        QApplication.clipboard().setText(sql_text)

    def get_sql_statements(self) -> list[tuple[str, tuple]]:
        """Return the SQL statements with parameters."""
        return self._sql_statements
