"""Code editor widget with line numbers and SQL syntax highlighting."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import (
    QFont,
    QFontInfo,
    QKeyEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextBlock,
    QTextCursor,
    QTextFormat,
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from tablefree.theme import current
from tablefree.widgets.sql_highlighter import SQLHighlighter

# Avoid circular import — TYPE_CHECKING only
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tablefree.widgets.completer import CompletionPopup, CompletionProvider


class LineNumberArea(QWidget):
    """Gutter widget that displays line numbers."""

    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event: QPaintEvent) -> None:
        self._editor._line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    """Custom plain text editor with line numbers and SQL highlighting."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._line_number_area = LineNumberArea(self)
        self._highlighter = SQLHighlighter(self.document())
        self._completion_provider: CompletionProvider | None = None
        self._completion_popup: CompletionPopup | None = None
        self._completion_timer = QTimer(self)
        self._completion_timer.setSingleShot(True)
        self._completion_timer.setInterval(80)
        self._completion_timer.timeout.connect(self._request_completions)

        self._setup_editor()
        self._connect_signals()

    def _setup_editor(self) -> None:
        font = QFont()
        font.setFamily("JetBrains Mono")
        font.setPointSize(10)
        if not QFontInfo(font).family() == "JetBrains Mono":
            font.setFamily("Fira Code")
            if not QFontInfo(font).family() == "Fira Code":
                font.setFamily("Consolas")
                if not QFontInfo(font).family() == "Consolas":
                    font.setFamily("Monospace")
        self.setFont(font)

        self.setTabStopDistance(32.0)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.refresh_theme()

    def _connect_signals(self) -> None:
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)

    # ── Completion integration ───────────────────────────────

    def set_completion_provider(self, provider: CompletionProvider) -> None:
        from tablefree.widgets.completer import CompletionPopup

        self._completion_provider = provider
        if self._completion_popup is None:
            self._completion_popup = CompletionPopup(self)
            self._completion_popup.item_selected.connect(self._accept_completion_text)

    def _hide_popup(self) -> None:
        if self._completion_popup and self._completion_popup.isVisible():
            self._completion_popup.hide()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        popup = self._completion_popup
        popup_visible = popup is not None and popup.isVisible()

        # Escape hides popup
        if event.key() == Qt.Key.Key_Escape and popup_visible:
            self._hide_popup()
            event.accept()
            return

        # Navigation inside popup
        if popup_visible and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            direction = -1 if event.key() == Qt.Key.Key_Up else 1
            popup.navigate(direction)
            event.accept()
            return

        # Accept completion
        if popup_visible and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Tab):
            text = popup.selected_text()
            if text:
                self._accept_completion_text(text)
                event.accept()
                return

        # Ctrl+Space: force trigger
        if (event.modifiers() == Qt.KeyboardModifier.ControlModifier
                and event.key() == Qt.Key.Key_Space):
            self._request_completions(force=True)
            event.accept()
            return

        # Let the editor handle the keystroke
        super().keyPressEvent(event)

        # Schedule completion after typing
        key = event.key()
        if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self._completion_timer.start()
        elif event.text() and (event.text().isalnum() or event.text() in ("_", ".")):
            self._completion_timer.start()
        else:
            self._hide_popup()

    def _request_completions(self, *, force: bool = False) -> None:
        provider = self._completion_provider
        popup = self._completion_popup
        if provider is None or popup is None:
            return

        cursor = self.textCursor()
        block_text = cursor.block().text()
        col = cursor.positionInBlock()
        text_before = block_text[:col]

        # Get full text up to cursor for context (use current block + preceding blocks
        # for multi-line context, but keep it simple: just scan backwards through text)
        full_text_before = self.toPlainText()[:cursor.position()]

        if force:
            items = provider.get_completions_forced(full_text_before)
        else:
            items = provider.get_completions(full_text_before)

        if not items:
            self._hide_popup()
            return

        # Need at least 2 chars for auto-trigger (not forced)
        if not force:
            prefix = provider._extract_prefix(full_text_before)
            if "." not in prefix and len(prefix) < 2:
                self._hide_popup()
                return

        cursor_rect = self.cursorRect()
        popup.show_items(items, cursor_rect)

    def _accept_completion_text(self, text: str) -> None:
        """Replace the current prefix with the selected completion text."""
        provider = self._completion_provider
        if provider is None:
            return

        cursor = self.textCursor()
        full_text_before = self.toPlainText()[:cursor.position()]
        prefix = provider._extract_prefix(full_text_before)

        # If prefix has a dot, only replace after the last dot
        if "." in prefix:
            replace_len = len(prefix.rsplit(".", 1)[1])
        else:
            replace_len = len(prefix)

        cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, replace_len)
        cursor.insertText(text)
        self.setTextCursor(cursor)
        self._hide_popup()

    def focusOutEvent(self, event) -> None:
        self._hide_popup()
        super().focusOutEvent(event)

    # ── Line number area ─────────────────────────────────────

    def _update_line_number_area_width(self, _: int | None = None) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(
                0, rect.y(), self._line_number_area.width(), rect.height()
            )

        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )
        self._hide_popup()

    def line_number_area_width(self) -> int:
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1

        space = 10 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

    def _line_number_area_paint_event(self, event: QPaintEvent) -> None:
        colors = current()
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), colors.gutter)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)

                if block == self.textCursor().block():
                    painter.setPen(colors.line_num_active)
                else:
                    painter.setPen(colors.line_num)

                painter.drawText(
                    0,
                    top,
                    self._line_number_area.width() - 5,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )

            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def _highlight_current_line(self) -> None:
        extra_selections = []
        colors = current()

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(colors.current_line)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)

    def refresh_theme(self) -> None:
        """Apply runtime colors and refresh painter-based elements."""
        colors = current()
        self.setStyleSheet(
            f"""
            CodeEditor {{
                background-color: {colors.base.name()};
                color: {colors.text.name()};
                selection-background-color: {colors.overlay.name()};
                selection-color: {colors.text.name()};
            }}
            """
        )
        self._highlighter.refresh_theme()
        self._line_number_area.update()
        self._highlight_current_line()
        self.viewport().update()
        if self._completion_popup:
            self._completion_popup.refresh_theme()

    def selectAll(self) -> None:
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        self.setTextCursor(cursor)
