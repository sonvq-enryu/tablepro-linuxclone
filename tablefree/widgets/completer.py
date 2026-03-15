"""Auto-completion popup and provider for the SQL editor."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from PySide6.QtCore import QModelIndex, QStringListModel, Qt, Signal
from PySide6.QtGui import QFocusEvent, QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QListView,
    QPlainTextEdit,
    QVBoxLayout,
)

from tablefree.services.schema_cache import SchemaMetadataCache
from tablefree.theme import current
from tablefree.widgets.sql_highlighter import SQLHighlighter

# ── Data ─────────────────────────────────────────────────────

_SQL_KEYWORDS = sorted(SQLHighlighter.KEYWORDS)
_SQL_FUNCTIONS = sorted(SQLHighlighter.FUNCTIONS)
_SQL_DATA_TYPES = sorted(SQLHighlighter.DATA_TYPES)

# Keywords after which table/schema names are expected
_TABLE_CONTEXT_KW = {
    "FROM",
    "JOIN",
    "INTO",
    "UPDATE",
    "TABLE",
    "INNER",
    "LEFT",
    "RIGHT",
    "OUTER",
    "FULL",
    "CROSS",
    "NATURAL",
}

# Keywords after which column names (+ keywords/functions) are expected
_COLUMN_CONTEXT_KW = {"SELECT", "WHERE", "ON", "SET", "HAVING", "AND", "OR", "BY"}


@dataclass
class CompletionItem:
    text: str
    kind: str  # "keyword" | "function" | "datatype" | "schema" | "table" | "column"
    detail: str = ""


# ── Popup widget ─────────────────────────────────────────────


class CompletionPopup(QFrame):
    """Floating list popup for auto-completion candidates."""

    item_selected = Signal(str)

    def __init__(self, parent: QPlainTextEdit) -> None:
        super().__init__(parent, Qt.WindowType.ToolTip)
        self._editor = parent
        self._model = QStringListModel(self)
        self._items: list[CompletionItem] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._list = QListView(self)
        self._list.setModel(self._model)
        self._list.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self._list.clicked.connect(self._on_clicked)
        layout.addWidget(self._list)

        self.setFixedWidth(300)
        self.setMaximumHeight(250)
        self.hide()
        self.refresh_theme()

    def refresh_theme(self) -> None:
        colors = current()
        self.setStyleSheet(
            f"""
            CompletionPopup {{
                background-color: {colors.surface.name()};
                border: 1px solid {colors.overlay.name()};
                border-radius: 4px;
            }}
            QListView {{
                background-color: {colors.surface.name()};
                color: {colors.text.name()};
                border: none;
                font-size: 12px;
                outline: none;
            }}
            QListView::item {{
                padding: 3px 8px;
            }}
            QListView::item:selected {{
                background-color: {colors.overlay.name()};
                color: {colors.text.name()};
            }}
            """
        )

    def show_items(self, items: list[CompletionItem], cursor_rect) -> None:
        if not items:
            self.hide()
            return
        self._items = items
        self._model.setStringList([it.text for it in items])

        # Select first item
        first = self._model.index(0, 0)
        self._list.setCurrentIndex(first)

        # Size to content (max 10 items visible)
        row_height = self._list.sizeHintForRow(0) if self._model.rowCount() > 0 else 20
        visible_rows = min(len(items), 10)
        list_height = row_height * visible_rows + 4
        self.setFixedHeight(min(list_height, 250))

        # Position relative to the text viewport (cursor_rect is viewport-local).
        editor = self._editor
        viewport = editor.viewport()
        below_global = viewport.mapToGlobal(cursor_rect.bottomLeft())

        # Keep popup within visible editor viewport: flip above when needed.
        viewport_top_global = viewport.mapToGlobal(viewport.rect().topLeft()).y()
        viewport_bottom_global = viewport.mapToGlobal(viewport.rect().bottomLeft()).y()

        if below_global.y() + self.height() > viewport_bottom_global:
            above_global = viewport.mapToGlobal(cursor_rect.topLeft())
            y = max(viewport_top_global, above_global.y() - self.height())
            self.move(below_global.x(), y)
        else:
            self.move(below_global)

        self.show()
        self.raise_()

    def navigate(self, direction: int) -> None:
        """Move selection up (-1) or down (+1)."""
        if not self.isVisible():
            return
        row = self._list.currentIndex().row() + direction
        row = max(0, min(row, self._model.rowCount() - 1))
        self._list.setCurrentIndex(self._model.index(row, 0))

    def selected_text(self) -> str | None:
        idx = self._list.currentIndex()
        if idx.isValid():
            return self._model.data(idx, Qt.ItemDataRole.DisplayRole)
        return None

    def _on_clicked(self, index: QModelIndex) -> None:
        text = self._model.data(index, Qt.ItemDataRole.DisplayRole)
        if text:
            self.item_selected.emit(text)


# ── Completion provider ──────────────────────────────────────


class CompletionProvider:
    """Builds completion candidates based on cursor context and schema cache."""

    def __init__(self, cache: SchemaMetadataCache) -> None:
        self._cache = cache

    def get_completions(self, text_before_cursor: str) -> list[CompletionItem]:
        """Return completion items for the text preceding the cursor."""
        if self._is_inside_string(text_before_cursor):
            return []

        prefix = self._extract_prefix(text_before_cursor)
        if not prefix:
            return []

        # Dot-notation: qualifier.partial
        if "." in prefix:
            return self._dot_completions(prefix)

        context = self._detect_context(text_before_cursor, prefix)
        candidates = self._build_candidates(context)
        return self._filter(candidates, prefix)

    def get_completions_forced(self, text_before_cursor: str) -> list[CompletionItem]:
        """Like get_completions but bypasses minimum prefix length."""
        if self._is_inside_string(text_before_cursor):
            return []

        prefix = self._extract_prefix(text_before_cursor)
        if "." in prefix:
            return self._dot_completions(prefix)
        context = self._detect_context(text_before_cursor, prefix)
        candidates = self._build_candidates(context)
        if prefix:
            return self._filter(candidates, prefix)
        return candidates

    # ── Prefix extraction ────────────────────────────────────

    @staticmethod
    def _is_inside_string(text: str) -> bool:
        """Return True when cursor is inside a quoted string/identifier."""
        in_single = False
        in_double = False
        i = 0
        while i < len(text):
            ch = text[i]
            if in_single:
                if ch == "'":
                    if i + 1 < len(text) and text[i + 1] == "'":
                        i += 2
                        continue
                    in_single = False
                i += 1
                continue

            if in_double:
                if ch == '"':
                    if i + 1 < len(text) and text[i + 1] == '"':
                        i += 2
                        continue
                    in_double = False
                i += 1
                continue

            if ch == "'":
                in_single = True
            elif ch == '"':
                in_double = True
            i += 1

        return in_single or in_double

    @staticmethod
    def _extract_prefix(text: str) -> str:
        """Scan backward for word chars and dots."""
        i = len(text) - 1
        while i >= 0 and (text[i].isalnum() or text[i] in ("_", ".")):
            i -= 1
        return text[i + 1 :]

    # ── Context detection ────────────────────────────────────

    @staticmethod
    def _detect_context(text: str, prefix: str) -> str:
        """Determine SQL context by scanning backward for the nearest keyword."""
        # Strip the prefix itself
        before = text[: len(text) - len(prefix)].rstrip()
        # Handle ORDER BY, GROUP BY as single unit
        upper = before.upper()
        if upper.endswith("BY"):
            pre_by = before[: len(before) - 2].rstrip().upper()
            if pre_by.endswith("ORDER") or pre_by.endswith("GROUP"):
                return "COLUMN"

        # Find last keyword-like token
        match = re.search(r"\b([A-Za-z_]+)\s*$", before)
        if match:
            kw = match.group(1).upper()
            if kw in _TABLE_CONTEXT_KW:
                return "TABLE"
            if kw in _COLUMN_CONTEXT_KW:
                return "COLUMN"
        return "GENERAL"

    # ── Candidate building ───────────────────────────────────

    def _build_candidates(self, context: str) -> list[CompletionItem]:
        items: list[CompletionItem] = []
        if context == "TABLE":
            for s in self._cache.get_schemas():
                items.append(CompletionItem(s, "schema"))
            for t in self._cache.get_all_table_names():
                items.append(CompletionItem(t, "table"))
        elif context == "COLUMN":
            for t in self._cache.get_all_table_names():
                items.append(CompletionItem(t, "table"))
            # Add columns from all cached tables
            self._add_all_cached_columns(items)
            items.extend(CompletionItem(k, "keyword") for k in _SQL_KEYWORDS)
            items.extend(CompletionItem(f, "function") for f in _SQL_FUNCTIONS)
        else:  # GENERAL
            items.extend(CompletionItem(k, "keyword") for k in _SQL_KEYWORDS)
            items.extend(CompletionItem(f, "function") for f in _SQL_FUNCTIONS)
            items.extend(CompletionItem(d, "datatype") for d in _SQL_DATA_TYPES)
            for t in self._cache.get_all_table_names():
                items.append(CompletionItem(t, "table"))
        return items

    def _add_all_cached_columns(self, items: list[CompletionItem]) -> None:
        seen: set[str] = set()
        for schema in self._cache.get_schemas():
            for table in self._cache.get_tables(schema):
                for col in self._cache.get_columns(table, schema):
                    if col.name not in seen:
                        seen.add(col.name)
                        items.append(CompletionItem(col.name, "column", col.data_type))

    def _dot_completions(self, prefix: str) -> list[CompletionItem]:
        """Handle schema.table or table.column completions."""
        parts = prefix.rsplit(".", 1)
        qualifier = parts[0]
        partial = parts[1] if len(parts) > 1 else ""

        items: list[CompletionItem] = []

        # Check if qualifier is a schema name
        if qualifier in self._cache.get_schemas():
            for t in self._cache.get_tables(qualifier):
                items.append(CompletionItem(t, "table"))
        else:
            # Assume qualifier is a table name — show its columns
            cols = self._cache.get_columns(qualifier)
            for col in cols:
                items.append(CompletionItem(col.name, "column", col.data_type))

            # Also check aliases — scan FROM/JOIN clauses would be complex,
            # so for now just try to find a table matching the qualifier
            if not cols:
                # Try all schemas
                for schema in self._cache.get_schemas():
                    for table in self._cache.get_tables(schema):
                        if table.lower() == qualifier.lower():
                            for col in self._cache.get_columns(table, schema):
                                items.append(
                                    CompletionItem(col.name, "column", col.data_type)
                                )
                            break

        if partial:
            return self._filter(items, partial)
        return items

    # ── Filtering ────────────────────────────────────────────

    @staticmethod
    def _filter(items: list[CompletionItem], prefix: str) -> list[CompletionItem]:
        prefix_lower = prefix.lower()
        matched: list[CompletionItem] = []
        for item in items:
            text_lower = item.text.lower()
            if text_lower.startswith(prefix_lower):
                matched.append(item)
            elif prefix_lower in text_lower:
                matched.append(item)
        # Sort: prefix matches first, then alphabetical
        matched.sort(
            key=lambda it: (
                not it.text.lower().startswith(prefix_lower),
                it.text.lower(),
            )
        )
        return matched
