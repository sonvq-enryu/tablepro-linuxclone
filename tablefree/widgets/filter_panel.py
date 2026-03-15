"""Filter panel widget — Visual filter builder for WHERE clauses."""

import re
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import Signal, Qt, QSettings
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

OPERATORS = {
    "text": [
        ("equals", "equals"),
        ("not equals", "not equals"),
        ("contains", "contains"),
        ("not contains", "not contains"),
        ("starts with", "starts with"),
        ("ends with", "ends with"),
        ("IS NULL", "IS NULL"),
        ("IS NOT NULL", "IS NOT NULL"),
        ("IS EMPTY", "IS EMPTY"),
        ("IS NOT EMPTY", "IS NOT EMPTY"),
        ("IN", "IN"),
        ("NOT IN", "NOT IN"),
        ("BETWEEN", "BETWEEN"),
        ("REGEX", "REGEX"),
    ],
    "number": [
        ("equals", "equals"),
        ("not equals", "not equals"),
        (">", ">"),
        (">=", ">="),
        ("<", "<"),
        ("<=", "<="),
        ("IS NULL", "IS NULL"),
        ("IS NOT NULL", "IS NOT NULL"),
        ("IN", "IN"),
        ("NOT IN", "NOT IN"),
        ("BETWEEN", "BETWEEN"),
    ],
    "boolean": [
        ("equals", "equals"),
        ("IS NULL", "IS NULL"),
        ("IS NOT NULL", "IS NOT NULL"),
    ],
}


@dataclass
class FilterCondition:
    """Represents a single filter condition."""

    column: str = ""
    operator: str = ""
    value: Any = None
    value2: Any = None
    enabled: bool = True
    logic: str = "AND"


class FilterRow(QWidget):
    """A single filter condition row."""

    def __init__(self, columns: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._columns = columns
        self._setup_ui()
        self._populate_columns()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)

        self._enabled_checkbox = QCheckBox()
        self._enabled_checkbox.setChecked(True)
        self._enabled_checkbox.stateChanged.connect(self._on_enabled_changed)
        layout.addWidget(self._enabled_checkbox)

        self._logic_combo = QComboBox()
        self._logic_combo.addItems(["AND", "OR"])
        self._logic_combo.setFixedWidth(60)
        self._logic_combo.currentTextChanged.connect(self._on_logic_changed)
        layout.addWidget(self._logic_combo)

        self._column_combo = QComboBox()
        self._column_combo.setEditable(True)
        self._column_combo.setMinimumWidth(120)
        self._column_combo.currentTextChanged.connect(self._on_column_changed)
        layout.addWidget(self._column_combo)

        self._operator_combo = QComboBox()
        self._operator_combo.setMinimumWidth(100)
        self._operator_combo.currentTextChanged.connect(self._on_operator_changed)
        layout.addWidget(self._operator_combo)

        self._value_input = QLineEdit()
        self._value_input.setPlaceholderText("value")
        layout.addWidget(self._value_input, stretch=1)

        self._value2_input = QLineEdit()
        self._value2_input.setPlaceholderText("max")
        self._value2_input.setVisible(False)
        layout.addWidget(self._value2_input)

        self._remove_btn = QPushButton("×")
        self._remove_btn.setFixedWidth(24)
        self._remove_btn.setObjectName("filter-remove-btn")
        self._remove_btn.clicked.connect(self._on_remove_clicked)
        layout.addWidget(self._remove_btn)

    def _populate_columns(self) -> None:
        self._column_combo.clear()
        self._column_combo.addItem("Raw SQL")
        if self._columns:
            self._column_combo.addItems(self._columns)
        self._update_operators()

    def set_columns(self, columns: list[str]) -> None:
        current = self._column_combo.currentText()
        self._columns = columns
        self._populate_columns()
        if current:
            idx = self._column_combo.findText(current)
            if idx >= 0:
                self._column_combo.setCurrentIndex(idx)
            else:
                self._column_combo.setCurrentText(current)

    def _update_operators(self) -> None:
        self._operator_combo.clear()
        column = self._column_combo.currentText()

        if column == "Raw SQL":
            self._value_input.setVisible(True)
            self._value_input.setPlaceholderText("WHERE clause fragment")
            self._value2_input.setVisible(False)
            return

        try:
            col_idx = (
                self._columns.index(column)
                if self._columns and column in self._columns
                else -1
            )
        except (ValueError, AttributeError):
            col_idx = -1

        if (
            col_idx >= 0
            and hasattr(self, "_column_types")
            and self._column_types
            and col_idx < len(self._column_types)
        ):
            col_type = self._column_types[col_idx].lower()
            if (
                "int" in col_type
                or "float" in col_type
                or "decimal" in col_type
                or "numeric" in col_type
            ):
                op_list = OPERATORS["number"]
            elif "bool" in col_type:
                op_list = OPERATORS["boolean"]
            else:
                op_list = OPERATORS["text"]
        else:
            op_list = OPERATORS["text"]

        for _, label in op_list:
            self._operator_combo.addItem(label)

        self._update_value_visibility()

    def _update_value_visibility(self) -> None:
        operator = self._operator_combo.currentText()

        no_value_ops = {"IS NULL", "IS NOT NULL", "IS EMPTY", "IS NOT EMPTY"}

        if operator in no_value_ops:
            self._value_input.setVisible(False)
            self._value2_input.setVisible(False)
        elif operator == "BETWEEN":
            self._value_input.setVisible(True)
            self._value_input.setPlaceholderText("min")
            self._value2_input.setVisible(True)
            self._value2_input.setPlaceholderText("max")
        elif operator == "Raw SQL":
            self._value_input.setVisible(True)
            self._value_input.setPlaceholderText("WHERE clause fragment")
            self._value2_input.setVisible(False)
        else:
            self._value_input.setVisible(True)
            self._value2_input.setVisible(False)

    def set_column_types(self, types: list[str]) -> None:
        self._column_types = types
        self._update_operators()

    def _on_column_changed(self, text: str) -> None:
        if text == "Raw SQL":
            self._operator_combo.setVisible(False)
        else:
            self._operator_combo.setVisible(True)
            self._update_operators()
        self._update_value_visibility()

    def _on_operator_changed(self, text: str) -> None:
        self._update_value_visibility()

    def _on_enabled_changed(self, state: int) -> None:
        self._set_enabled_recursive(state == Qt.CheckState.Checked.value)

    def _set_enabled_recursive(self, enabled: bool) -> None:
        self._logic_combo.setEnabled(enabled)
        self._column_combo.setEnabled(enabled)
        self._operator_combo.setEnabled(enabled)
        self._value_input.setEnabled(enabled)
        self._value2_input.setEnabled(enabled)

    def _on_logic_changed(self, text: str) -> None:
        pass

    def _on_remove_clicked(self) -> None:
        self.deleteLater()

    def set_logic_visible(self, visible: bool) -> None:
        self._logic_combo.setVisible(visible)

    def get_condition(self) -> FilterCondition:
        column = self._column_combo.currentText()
        operator = self._operator_combo.currentText()

        if column == "Raw SQL":
            operator = "RAW_SQL"
            value = self._value_input.text()
        elif operator in {"IS NULL", "IS NOT NULL", "IS EMPTY", "IS NOT EMPTY"}:
            value = None
        else:
            value = self._value_input.text()

        value2 = self._value2_input.text() if self._value2_input.isVisible() else None

        return FilterCondition(
            column=column,
            operator=operator,
            value=value,
            value2=value2,
            enabled=self._enabled_checkbox.isChecked(),
            logic=self._logic_combo.currentText(),
        )

    def set_condition(self, cond: FilterCondition) -> None:
        idx = self._column_combo.findText(cond.column)
        if idx >= 0:
            self._column_combo.setCurrentIndex(idx)
        else:
            self._column_combo.setCurrentText(cond.column)

        idx = self._operator_combo.findText(cond.operator)
        if idx >= 0:
            self._operator_combo.setCurrentIndex(idx)

        if cond.value is not None:
            self._value_input.setText(str(cond.value))
        if cond.value2 is not None:
            self._value2_input.setText(str(cond.value2))

        self._enabled_checkbox.setChecked(cond.enabled)
        self._logic_combo.setCurrentText(cond.logic)


class SavePresetDialog(QDialog):
    """Dialog for saving a filter preset."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Save Filter Preset")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Enter a name for this filter preset:"))

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Preset name")
        layout.addWidget(self._name_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def preset_name(self) -> str:
        return self._name_input.text().strip()


class FilterPanel(QWidget):
    """Container for filter rows with quick search and preset management."""

    filters_applied = Signal(str, tuple)
    filters_cleared = Signal()

    def __init__(
        self,
        driver: Any = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._driver = driver
        self._filter_rows: list[FilterRow] = []
        self._columns: list[str] = []
        self._column_types: list[str] = []
        self._connection_id: str = ""
        self._table_name: str = ""
        self._quick_search_hidden_rows: set[int] = set()
        self._original_row_visibility: dict[int, bool] = {}
        self._table_widget: Any = None
        self._setup_ui()

    def set_driver(self, driver: Any) -> None:
        self._driver = driver

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        quick_search_layout = QHBoxLayout()
        quick_search_layout.setSpacing(8)

        quick_label = QLabel("🔍 Quick search:")
        quick_search_layout.addWidget(quick_label)

        self._quick_search = QLineEdit()
        self._quick_search.setPlaceholderText("Filter rows locally...")
        self._quick_search.textChanged.connect(self._on_quick_search_changed)
        quick_search_layout.addWidget(self._quick_search, stretch=1)

        layout.addLayout(quick_search_layout)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("filter-sep")
        layout.addWidget(sep)

        self._filters_container = QVBoxLayout()
        self._filters_container.setSpacing(0)
        layout.addLayout(self._filters_container)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        self._add_filter_btn = QPushButton("+ Add Filter")
        self._add_filter_btn.clicked.connect(self._add_filter_row)
        button_layout.addWidget(self._add_filter_btn)

        button_layout.addStretch()

        self._apply_btn = QPushButton("Apply")
        self._apply_btn.setObjectName("filter-apply-btn")
        self._apply_btn.clicked.connect(self._on_apply_clicked)
        button_layout.addWidget(self._apply_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._on_clear_clicked)
        button_layout.addWidget(self._clear_btn)

        self._save_btn = QPushButton("💾")
        self._save_btn.setToolTip("Save preset")
        self._save_btn.setFixedWidth(32)
        self._save_btn.clicked.connect(self._on_save_preset)
        button_layout.addWidget(self._save_btn)

        self._load_btn = QPushButton("📂")
        self._load_btn.setToolTip("Load preset")
        self._load_btn.setFixedWidth(32)
        self._load_btn.clicked.connect(self._on_load_preset)
        button_layout.addWidget(self._load_btn)

        layout.addLayout(button_layout)

    def set_columns(self, columns: list[str], column_types: list[str]) -> None:
        self._columns = columns or []
        self._column_types = column_types or []

        for row in self._filter_rows:
            if hasattr(row, "set_columns"):
                row.set_columns(self._columns)
            if hasattr(row, "set_column_types"):
                row.set_column_types(self._column_types)

    def set_context(self, connection_id: str, table_name: str) -> None:
        self._connection_id = connection_id
        self._table_name = table_name

    def _add_filter_row(self) -> None:
        row = FilterRow(self._columns, self)
        row.set_column_types(self._column_types)

        is_first = len(self._filter_rows) == 0
        row.set_logic_visible(not is_first)

        row._remove_btn.clicked.connect(lambda: self._remove_filter_row(row))

        self._filter_rows.append(row)
        self._filters_container.addWidget(row)

    def _remove_filter_row(self, row: FilterRow) -> None:
        if row in self._filter_rows:
            self._filter_rows.remove(row)
            row.deleteLater()

        if self._filter_rows:
            self._filter_rows[0].set_logic_visible(False)

    def _on_quick_search_changed(self, text: str) -> None:
        if self._table_widget is None:
            return

        search_text = text.lower()
        row_count = self._table_widget.rowCount()

        for row in range(row_count):
            if not search_text:
                self._table_widget.showRow(row)
                continue

            row_hidden = True
            for col in range(self._table_widget.columnCount()):
                item = self._table_widget.item(row, col)
                if item and search_text in item.text().lower():
                    row_hidden = False
                    break

            if row_hidden:
                self._table_widget.hideRow(row)
            else:
                self._table_widget.showRow(row)

    def set_table_widget(self, table: QWidget) -> None:
        self._table_widget = table

    def build_where_clause(self) -> tuple[str, tuple]:
        """Build WHERE clause from filter rows. Returns (clause, params)."""
        enabled_conditions = [
            row.get_condition()
            for row in self._filter_rows
            if row.get_condition().enabled
        ]

        if not enabled_conditions:
            return ("", ())

        parts: list[str] = []
        params: list[Any] = []

        for i, cond in enumerate(enabled_conditions):
            if i > 0:
                parts.append(cond.logic)

            if cond.column == "Raw SQL":
                parts.append(f"({cond.value})")
                continue

            col = f'"{cond.column}"'

            if cond.operator in ("IS NULL", "IS NOT NULL"):
                parts.append(f"{col} {cond.operator}")
            elif cond.operator in ("IS EMPTY", "IS NOT EMPTY"):
                if cond.operator == "IS EMPTY":
                    parts.append(f"({col} = '' OR {col} IS NULL)")
                else:
                    parts.append(f"({col} != '' AND {col} IS NOT NULL)")
            elif cond.operator == "BETWEEN":
                if cond.value and cond.value2:
                    parts.append(f"{col} BETWEEN %s AND %s")
                    params.append(cond.value)
                    params.append(cond.value2)
            elif cond.operator in ("IN", "NOT IN"):
                if cond.value:
                    items = [
                        it.strip() for it in str(cond.value).split(",") if it.strip()
                    ]
                    if items:
                        placeholders = ", ".join(["%s"] * len(items))
                        parts.append(f"{col} {cond.operator} ({placeholders})")
                        params.extend(items)
            elif cond.operator == "REGEX":
                if cond.value:
                    if self._driver and "mysql" in type(self._driver).__name__.lower():
                        parts.append(f"{col} REGEXP %s")
                    else:
                        parts.append(f"{col} ~ %s")
                    params.append(cond.value)
            elif cond.operator in ("equals", "="):
                parts.append(f"{col} = %s")
                params.append(cond.value)
            elif cond.operator == "not equals":
                parts.append(f"{col} != %s")
                params.append(cond.value)
            elif cond.operator == "contains":
                parts.append(f"{col} LIKE %s")
                params.append(f"%{cond.value}%")
            elif cond.operator == "not contains":
                parts.append(f"{col} NOT LIKE %s")
                params.append(f"%{cond.value}%")
            elif cond.operator == "starts with":
                parts.append(f"{col} LIKE %s")
                params.append(f"{cond.value}%")
            elif cond.operator == "ends with":
                parts.append(f"{col} LIKE %s")
                params.append(f"%{cond.value}")
            elif cond.operator in (">", ">=", "<", "<="):
                parts.append(f"{col} {cond.operator} %s")
                params.append(cond.value)

        if not parts:
            return ("", ())

        full_clause = " ".join(parts)

        has_parens = full_clause.count("(") != full_clause.count(")")
        if has_parens:
            full_clause = f"({full_clause})"

        return (full_clause, tuple(params))

    def _on_apply_clicked(self) -> None:
        clause, params = self.build_where_clause()
        if clause:
            self.filters_applied.emit(clause, params)
        else:
            self.filters_cleared.emit()

    def _on_clear_clicked(self) -> None:
        for row in self._filter_rows[:]:
            row.deleteLater()
        self._filter_rows.clear()
        self._quick_search.clear()
        self.filters_cleared.emit()

    def _on_save_preset(self) -> None:
        if not self._table_name:
            QMessageBox.warning(self, "Save Preset", "No table selected.")
            return

        dialog = SavePresetDialog(self)
        if not dialog.exec():
            return

        name = dialog.preset_name()
        if not name:
            QMessageBox.warning(self, "Save Preset", "Please enter a name.")
            return

        conditions = [row.get_condition() for row in self._filter_rows]
        preset_data = [
            {
                "column": cond.column,
                "operator": cond.operator,
                "value": cond.value,
                "value2": cond.value2,
                "enabled": cond.enabled,
                "logic": cond.logic,
            }
            for cond in conditions
        ]

        settings = QSettings()
        preset_key = f"filters/{self._connection_id}/{self._table_name}/presets"
        preset_dict = settings.value(preset_key) or {}
        if not isinstance(preset_dict, dict):
            preset_dict = {}
        preset_dict[name] = preset_data
        settings.setValue(preset_key, preset_dict)

        QMessageBox.information(self, "Save Preset", f"Preset '{name}' saved.")

    def _on_load_preset(self) -> None:
        if not self._table_name:
            QMessageBox.warning(self, "Load Preset", "No table selected.")
            return

        settings = QSettings()
        preset_key = f"filters/{self._connection_id}/{self._table_name}/presets"

        preset_dict = settings.value(preset_key)
        if not preset_dict:
            QMessageBox.information(self, "Load Preset", "No saved presets found.")
            return

        preset_dict = dict(preset_dict) if isinstance(preset_dict, dict) else {}
        if not preset_dict:
            QMessageBox.information(self, "Load Preset", "No saved presets found.")
            return

        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getItem(
            self, "Load Preset", "Select a preset:", list(preset_dict.keys()), 0, False
        )

        if not ok or not name:
            return

        preset_data = preset_dict[name]
        if not isinstance(preset_data, list):
            return

        for row in self._filter_rows[:]:
            row.deleteLater()
        self._filter_rows.clear()

        for cond_data in preset_data:
            self._add_filter_row()
            if self._filter_rows:
                row = self._filter_rows[-1]
                cond = FilterCondition(
                    column=cond_data.get("column", ""),
                    operator=cond_data.get("operator", ""),
                    value=cond_data.get("value"),
                    value2=cond_data.get("value2"),
                    enabled=cond_data.get("enabled", True),
                    logic=cond_data.get("logic", "AND"),
                )
                row.set_condition(cond)

    def get_filter_state(self) -> dict:
        """Get current filter state for persistence."""
        return {
            "visible": self.isVisible(),
            "conditions": [row.get_condition().__dict__ for row in self._filter_rows],
            "quick_search": self._quick_search.text(),
        }

    def reset_state(self) -> None:
        """Reset filter panel state without emitting signals."""
        for row in self._filter_rows[:]:
            row.deleteLater()
        self._filter_rows.clear()
        self._quick_search.clear()
        self.setVisible(False)

    def restore_filter_state(self, state: dict) -> None:
        """Restore filter state from persistence."""
        self.setVisible(bool(state.get("visible")))

        conditions = state.get("conditions", [])
        for cond_data in conditions:
            self._add_filter_row()
            if self._filter_rows:
                row = self._filter_rows[-1]
                cond = FilterCondition(**cond_data)
                row.set_condition(cond)

        quick_search = state.get("quick_search")
        if isinstance(quick_search, str):
            self._quick_search.setText(quick_search)
