"""Code editor widget with line numbers and SQL syntax highlighting."""

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontInfo,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextBlock,
    QTextCursor,
    QTextFormat,
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from tablefree.widgets.sql_highlighter import SQLHighlighter


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

        self.setStyleSheet("""
            CodeEditor {
                background-color: #1e1e2e;
                color: #cdd6f4;
                selection-background-color: #45475a;
                selection-color: #cdd6f4;
            }
        """)

    def _connect_signals(self) -> None:
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)

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

    def line_number_area_width(self) -> int:
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1

        space = 10 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

    def _line_number_area_paint_event(self, event: QPaintEvent) -> None:
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor("#181825"))

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
                    painter.setPen(QColor("#cdd6f4"))
                else:
                    painter.setPen(QColor("#585b70"))

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

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#242438"))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)

    def selectAll(self) -> None:
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        self.setTextCursor(cursor)
