from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QStyle, QStyleOptionButton

from ..fluent import CheckBox, FLUENT_AVAILABLE


class TickCheckBox(CheckBox):
    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if FLUENT_AVAILABLE:
            return
        if not self.isChecked():
            return

        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        rect = self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, opt, self)
        if not rect.isValid():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#efede0"))
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        p1x = int(rect.left() + rect.width() * 0.22)
        p1y = int(rect.top() + rect.height() * 0.56)
        p2x = int(rect.left() + rect.width() * 0.42)
        p2y = int(rect.top() + rect.height() * 0.74)
        p3x = int(rect.left() + rect.width() * 0.78)
        p3y = int(rect.top() + rect.height() * 0.30)

        painter.drawLine(p1x, p1y, p2x, p2y)
        painter.drawLine(p2x, p2y, p3x, p3y)
