from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import QTextCursor
from datetime import datetime
from .. import style as S


class LogPanel(QTextEdit):
    """Read-only, colour-coded, auto-scrolling log with a 500-line ceiling."""

    _MAX_LINES = 500

    from typing import ClassVar

    _COLOURS: ClassVar[dict[str, str]] = {
        "info": S.LOG_INFO,
        "success": S.LOG_SUCCESS,
        "error": S.LOG_ERROR,
        "warning": S.LOG_WARNING,
        "api": S.LOG_API,
        "download": S.LOG_DOWNLOAD,
    }

    def __init__(
        self,
        parent=None,
        *,
        max_lines: int | None = None,
        compact: bool = True,
    ):
        super().__init__(parent)
        self._max_lines = max_lines if max_lines is not None else self._MAX_LINES
        self.setObjectName("logPanel")
        self.setReadOnly(True)
        if compact:
            self.setMinimumHeight(140)
            self.setMaximumHeight(260)
        else:
            self.setMinimumHeight(260)
            self.setMaximumHeight(16777215)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)

    def append(self, text: str, level: str = "info") -> None:
        colour = self._COLOURS.get(level, S.LOG_INFO)
        ts = datetime.now().strftime("%H:%M:%S")
        html = f'<span style="color:{colour}">[{ts}] {text}</span>'
        super().append(html)
        # Trim oldest lines if ceiling exceeded
        doc = self.document()
        if self._max_lines > 0 and doc.blockCount() > self._max_lines:
            cursor = QTextCursor(doc.firstBlock())
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()
        # Auto-scroll
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear(self) -> None:
        super().clear()


